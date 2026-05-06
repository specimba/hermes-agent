"""
Test suite for KAIJU Governance system.

Tests cover:
- AgentProposal validation and hashing
- TrustScore calculation
- Gate decision stages (schema, trust, budget, capability, harm)
- Violation handling and trust slashing
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nexus_kernel.kaiju import (
    KAIJUGovernor, AgentProposal, TrustScore, GateResult,
    ViolationType, GateDecision, RuntimeType
)


class TestAgentProposal:
    """Test AgentProposal data model and hashing."""
    
    def test_proposal_creation(self):
        """Test basic proposal creation."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="code_execution",
            action_params={"code": "print('hello')"},
            requested_capability="basic"
        )
        assert prop.agent_id == "agent1"
        assert prop.action_type == "code_execution"
        assert prop.context_hash is not None
    
    def test_context_hash_deterministic(self):
        """Test that same proposals generate same hash."""
        timestamp = datetime(2026, 1, 1, 12, 0, 0)
        prop1 = AgentProposal(
            agent_id="agent1",
            action_type="test",
            timestamp=timestamp
        )
        prop2 = AgentProposal(
            agent_id="agent1",
            action_type="test",
            timestamp=timestamp
        )
        assert prop1.context_hash == prop2.context_hash
    
    def test_context_hash_unique(self):
        """Test that different proposals generate different hashes."""
        prop1 = AgentProposal(agent_id="agent1", action_type="test1")
        prop2 = AgentProposal(agent_id="agent1", action_type="test2")
        assert prop1.context_hash != prop2.context_hash


class TestTrustScore:
    """Test TrustScore calculation and updates."""
    
    def test_default_trust_score(self):
        """Test default trust score values."""
        ts = TrustScore(agent_id="agent1")
        assert ts.implementation_lane == 0.5
        assert ts.coordination_lane == 0.5
        assert ts.tool_usage_lane == 0.5
        assert abs(ts.overall - 0.5) < 0.001
    
    def test_custom_trust_score(self):
        """Test custom trust score calculation."""
        ts = TrustScore(
            agent_id="agent2",
            implementation_lane=0.8,
            coordination_lane=0.7,
            tool_usage_lane=0.9
        )
        expected = 0.8 * 0.4 + 0.7 * 0.3 + 0.9 * 0.3
        assert abs(ts.overall - expected) < 0.001


class TestKAIJUGovernorInitialization:
    """Test KAIJU Governor setup."""
    
    def test_init_with_defaults(self):
        """Test governor initializes with no dependencies."""
        gov = KAIJUGovernor()
        assert gov.zilliz_client is None
        assert gov.vap_chain is None
        assert len(gov._violation_history) == 0
    
    def test_init_with_dependencies(self):
        """Test governor initializes with Zilliz and VAP chain."""
        mock_zilliz = MagicMock()
        mock_vap = MagicMock()
        gov = KAIJUGovernor(zilliz_client=mock_zilliz, vap_chain=mock_vap)
        assert gov.zilliz_client == mock_zilliz
        assert gov.vap_chain == mock_vap


class TestSchemaValidation:
    """Test Stage 1: Schema validation for attack prevention."""
    
    def setup_method(self):
        self.gov = KAIJUGovernor()
    
    def test_clean_proposal_passes(self):
        """Test non-suspicious proposal passes schema validation."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="code_execution",
            action_params={"code": "x = 1"}
        )
        result = self.gov._validate_schema(prop)
        assert result.decision == GateDecision.APPROVE
    
    def test_suspicious_pattern_detected(self):
        """Test proposal with suspicious patterns is denied."""
        suspicious_patterns = ["iterative", "refine", "ignore previous", "bypass"]
        for pattern in suspicious_patterns:
            prop = AgentProposal(
                agent_id="agent1",
                action_type="code_execution",
                action_params={"code": f"do something {pattern}"}
            )
            result = self.gov._validate_schema(prop)
            assert result.decision == GateDecision.DENY
            assert result.violation_type == ViolationType.SCHEMA_VALIDATION_FAILED


class TestTrustScoreVerification:
    """Test Stage 2: Trust score verification."""
    
    def setup_method(self):
        self.gov = KAIJUGovernor()
    
    def test_trust_score_meets_threshold(self):
        """Test approval when trust score meets threshold."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="code_execution",
            requested_capability="basic"
        )
        trust = TrustScore(agent_id="agent1", implementation_lane=0.5)
        result = self.gov._verify_trust_score(prop, trust)
        assert result.decision == GateDecision.APPROVE
    
    def test_trust_score_below_threshold(self):
        """Test denial when trust score below threshold."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="code_execution",
            requested_capability="advanced"  # requires 0.7
        )
        trust = TrustScore(agent_id="agent1", implementation_lane=0.3)
        result = self.gov._verify_trust_score(prop, trust)
        assert result.decision == GateDecision.DENY
        assert result.violation_type == ViolationType.TRUST_SCORE_TOO_LOW
    
    def test_lane_selection_for_action_type(self):
        """Test correct lane is used for different action types."""
        gov = KAIJUGovernor()
        
        # Code execution uses implementation lane
        prop = AgentProposal(agent_id="a", action_type="code_execution")
        trust = TrustScore(agent_id="a", implementation_lane=0.8)
        result = gov._verify_trust_score(prop, trust)
        assert result.decision == GateDecision.APPROVE
        
        # Coordination uses coordination lane
        prop.action_type = "agent_coordination"
        trust.coordination_lane = 0.2
        result = gov._verify_trust_score(prop, trust)
        assert result.decision == GateDecision.DENY


class TestBudgetCheck:
    """Test Stage 3: Token budget verification."""
    
    def setup_method(self):
        self.gov = KAIJUGovernor()
    
    def test_sufficient_budget(self):
        """Test approval when budget is sufficient."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="test",
            estimated_token_cost=100
        )
        result = self.gov._check_budget(prop, available_budget=200)
        assert result.decision == GateDecision.APPROVE
    
    def test_insufficient_budget(self):
        """Test hard stop when budget exceeded."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="test",
            estimated_token_cost=500
        )
        result = self.gov._check_budget(prop, available_budget=200)
        assert result.decision == GateDecision.HARD_STOP
        assert result.violation_type == ViolationType.BUDGET_EXCEEDED


class TestCapabilityVerification:
    """Test Stage 4: Capability matching."""
    
    def setup_method(self):
        self.gov = KAIJUGovernor()
    
    @pytest.mark.asyncio
    async def test_basic_capability_always_allowed(self):
        """Test basic capability is always approved."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="test",
            requested_capability="basic"
        )
        trust = TrustScore(agent_id="agent1")
        result = await self.gov._verify_capability(prop, trust)
        assert result.decision == GateDecision.APPROVE
    
    @pytest.mark.asyncio
    async def test_advanced_capability_requires_trust(self):
        """Test advanced capability requires high trust."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="test",
            requested_capability="advanced"  # requires 0.7
        )
        trust = TrustScore(agent_id="agent1", overall=0.5)
        result = await self.gov._verify_capability(prop, trust)
        assert result.decision == GateDecision.DENY


class TestHarmDetection:
    """Test Stage 5: Non-compensatory harm detection."""
    
    def setup_method(self):
        self.gov = KAIJUGovernor()
    
    @pytest.mark.asyncio
    async def test_unauthorized_network_blocked(self):
        """Test unauthorized network access is hard stopped."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="network_request",
            action_params={"url": "https://malicious.com"}
        )
        result = await self.gov._detect_harm(prop)
        assert result.decision == GateDecision.HARD_STOP
        assert result.violation_type == ViolationType.UNAUTHORIZED_NETWORK
    
    @pytest.mark.asyncio
    async def test_allowed_network_passes(self):
        """Test allowed network access passes."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="network_request",
            action_params={"url": "https://api.zilliz.com/v1/collections"}
        )
        result = await self.gov._detect_harm(prop)
        assert result.decision == GateDecision.APPROVE
    
    @pytest.mark.asyncio
    async def test_protected_filesystem_blocked(self):
        """Test access to protected paths is blocked."""
        prop = AgentProposal(
            agent_id="agent1",
            action_type="file_read",
            action_params={"path": "/etc/passwd"}
        )
        result = await self.gov._detect_harm(prop)
        assert result.decision == GateDecision.HARD_STOP
        assert result.violation_type == ViolationType.FILESYSTEM_VIOLATION


class TestFullEvaluation:
    """Test full proposal evaluation flow."""
    
    @pytest.mark.asyncio
    async def test_full_approval_flow(self):
        """Test complete approval flow for valid proposal."""
        gov = KAIJUGovernor()
        prop = AgentProposal(
            agent_id="agent1",
            action_type="code_execution",
            requested_capability="basic",
            estimated_token_cost=100
        )
        trust = TrustScore(agent_id="agent1", implementation_lane=0.5)
        result = await gov.evaluate_proposal(prop, trust, available_budget=200)
        assert result.decision == GateDecision.APPROVE
        assert "All KAIJU gates passed" in result.reason
    
    @pytest.mark.asyncio
    async def test_full_denial_flow(self):
        """Test complete denial flow for invalid proposal."""
        gov = KAIJUGovernor()
        prop = AgentProposal(
            agent_id="agent1",
            action_type="code_execution",
            requested_capability="premium",  # requires 0.8
            estimated_token_cost=1000
        )
        trust = TrustScore(agent_id="agent1", implementation_lane=0.3)
        result = await gov.evaluate_proposal(prop, trust, available_budget=500)
        assert result.decision == GateDecision.DENY


class TestTrustSlashing:
    """Test trust score slashing for violations."""
    
    def test_slash_trust_score(self):
        """Test trust score reduction for violations."""
        gov = KAIJUGovernor()
        trust = gov.slash_trust_score(
            agent_id="agent1",
            violation_type=ViolationType.FILESYSTEM_VIOLATION,
            severity=0.2
        )
        assert trust.implementation_lane == 0.3  # 0.5 - 0.2
    
    def test_slash_updates_overall(self):
        """Test slashing recalculates overall score."""
        gov = KAIJUGovernor()
        trust = gov.slash_trust_score(
            agent_id="agent1",
            violation_type=ViolationType.NON_COMPENSATORY_HARM,
            severity=0.3
        )
        expected = (0.2 * 0.4) + (0.5 * 0.3) + (0.5 * 0.3)
        assert abs(trust.overall - expected) < 0.001


class TestViolationHistory:
    """Test violation history tracking."""
    
    def test_violation_history_recorded(self):
        """Test violations are recorded in history."""
        gov = KAIJUGovernor()
        prop = AgentProposal(agent_id="agent1", action_type="test")
        result = GateResult(
            decision=GateDecision.DENY,
            agent_id="agent1",
            proposal_hash="abc123",
            violation_type=ViolationType.TRUST_SCORE_TOO_LOW
        )
        gov._log_and_return(result)
        history = gov.get_violation_history("agent1")
        assert len(history) == 1
        assert history[0].violation_type == ViolationType.TRUST_SCORE_TOO_LOW


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
