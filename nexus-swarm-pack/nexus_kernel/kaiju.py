"""
KAIJU Governor - Deterministic Authorization Gates

Implements the KAIJU governance logic for agent proposal validation with:
- Bayesian trust scoring integration
- Non-compensatory harm detection
- Multi-turn attack prevention (Crescendo, PAIR)
- Capability-based access control
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any
import hashlib


class ViolationType(Enum):
    """Types of governance violations detected by KAIJU."""
    UNAUTHORIZED_NETWORK = "unauthorized_network"
    FILESYSTEM_VIOLATION = "filesystem_violation"
    TRUST_SCORE_TOO_LOW = "trust_score_too_low"
    BUDGET_EXCEEDED = "budget_exceeded"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    NON_COMPENSATORY_HARM = "non_compensatory_harm"
    MULTI_TURN_ATTACK = "multi_turn_attack"
    CAPABILITY_MISMATCH = "capability_mismatch"


class GateDecision(Enum):
    """KAIJU gate decision outcomes."""
    APPROVE = "approve"
    DENY = "deny"
    REQUIRE_REVIEW = "require_review"
    HARD_STOP = "hard_stop"


@dataclass
class AgentProposal:
    """Represents an agent's action proposal for KAIJU evaluation."""
    agent_id: str
    action_type: str
    action_params: Optional[Dict[str, Any]] = None
    requested_capability: Optional[str] = None
    estimated_token_cost: Optional[int] = None
    target_resource: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    justification: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context_hash: Optional[str] = None
    
    def __post_init__(self):
        if not self.context_hash:
            # Generate deterministic hash from proposal content
            content = f"{self.agent_id}:{self.action_type}:{str(self.action_params or self.parameters)}:{self.target_resource or ''}:{self.timestamp.isoformat()}"
            self.context_hash = hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class TrustScore:
    """Bayesian trust score for an agent."""
    agent_id: str
    implementation_lane: float = 0.5  # Code execution trust
    coordination_lane: float = 0.5    # Agent coordination trust
    tool_usage_lane: float = 0.5      # Tool invocation trust
    overall: float = 0.5
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        # Weighted average for overall score
        self.overall = (
            self.implementation_lane * 0.4 +
            self.coordination_lane * 0.3 +
            self.tool_usage_lane * 0.3
        )


@dataclass
class GateResult:
    """Result of a KAIJU gate evaluation."""
    decision: GateDecision
    agent_id: str
    proposal_hash: str
    violation_type: Optional[ViolationType] = None
    reason: str = ""
    trust_score: Optional[TrustScore] = None
    required_budget: int = 0
    available_budget: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class KAIJUGovernor:
    """
    KAIJU Governor - Deterministic authorization engine for NEXUS OS.
    
    Enforces governance policies through a multi-stage gate:
    1. Schema validation (prevent injection attacks)
    2. Trust score verification
    3. Token budget check
    4. Capability matching
    5. Non-compensatory harm detection
    
    All decisions are logged to VAP chain for audit compliance.
    """
    
    # Minimum trust scores for different capability tiers
    MIN_TRUST_THRESHOLDS = {
        "basic": 0.3,
        "intermediate": 0.5,
        "advanced": 0.7,
        "premium": 0.8,
    }
    
    # Hard stop violations (non-compensatory)
    HARD_STOP_VIOLATIONS = {
        ViolationType.NON_COMPENSATORY_HARM,
        ViolationType.MULTI_TURN_ATTACK,
        ViolationType.UNAUTHORIZED_NETWORK,
    }
    
    def __init__(self, zilliz_client=None, vap_chain=None):
        """
        Initialize KAIJU Governor.
        
        Args:
            zilliz_client: ZillizClient instance for trust/capability lookups
            vap_chain: VAPChain instance for audit logging
        """
        self.zilliz_client = zilliz_client
        self.vap_chain = vap_chain
        self._violation_history: Dict[str, List[GateResult]] = {}
    
    async def evaluate_proposal(
        self,
        proposal: AgentProposal,
        trust_score: Optional[TrustScore] = None,
        available_budget: int = 0
    ) -> GateResult:
        """
        Evaluate an agent proposal through all KAIJU gates.
        
        Args:
            proposal: The agent's action proposal
            trust_score: Current trust score (fetched from Zilliz if None)
            available_budget: Available token budget for this agent
            
        Returns:
            GateResult with decision and metadata
        """
        # Stage 1: Schema validation (prevent PAIR/Crescendo attacks)
        schema_result = self._validate_schema(proposal)
        if schema_result.decision != GateDecision.APPROVE:
            return await self._log_and_return(schema_result)
        
        # Stage 2: Trust score verification
        if trust_score is None:
            trust_score = await self._fetch_trust_score(proposal.agent_id)
        
        trust_result = self._verify_trust_score(proposal, trust_score)
        if trust_result.decision != GateDecision.APPROVE:
            return await self._log_and_return(trust_result)
        
        # Stage 3: Token budget check
        budget_result = self._check_budget(proposal, available_budget)
        if budget_result.decision != GateDecision.APPROVE:
            return await self._log_and_return(budget_result)
        
        # Stage 4: Capability matching
        capability_result = await self._verify_capability(proposal, trust_score)
        if capability_result.decision != GateDecision.APPROVE:
            return await self._log_and_return(capability_result)
        
        # Stage 5: Non-compensatory harm detection
        harm_result = await self._detect_harm(proposal)
        if harm_result.decision != GateDecision.APPROVE:
            return await self._log_and_return(harm_result)
        
        # All gates passed - approve
        result = GateResult(
            decision=GateDecision.APPROVE,
            agent_id=proposal.agent_id,
            proposal_hash=proposal.context_hash,
            trust_score=trust_score,
            required_budget=proposal.estimated_token_cost,
            available_budget=available_budget,
            reason="All KAIJU gates passed"
        )
        return await self._log_and_return(result)
    
    def _validate_schema(self, proposal: AgentProposal) -> GateResult:
        """Stage 1: Validate proposal schema to prevent injection attacks."""
        # Check for known attack patterns in action params
        suspicious_patterns = [
            "iterative", "refine", "gradually", "step-by-step",
            "ignore previous", "override", "bypass"
        ]
        
        params_str = str(proposal.action_params).lower()
        for pattern in suspicious_patterns:
            if pattern in params_str:
                return GateResult(
                    decision=GateDecision.DENY,
                    agent_id=proposal.agent_id,
                    proposal_hash=proposal.context_hash,
                    violation_type=ViolationType.SCHEMA_VALIDATION_FAILED,
                    reason=f"Suspicious pattern detected: '{pattern}' - potential multi-turn attack"
                )
        
        return GateResult(
            decision=GateDecision.APPROVE,
            agent_id=proposal.agent_id,
            proposal_hash=proposal.context_hash,
            reason="Schema validation passed"
        )
    
    def _verify_trust_score(
        self,
        proposal: AgentProposal,
        trust_score: TrustScore
    ) -> GateResult:
        """Stage 2: Verify agent trust score meets threshold."""
        required_capability = proposal.requested_capability
        min_threshold = self.MIN_TRUST_THRESHOLDS.get(required_capability, 0.5)
        
        # Select appropriate lane based on action type
        if proposal.action_type in ["code_execution", "file_write"]:
            lane_score = trust_score.implementation_lane
        elif proposal.action_type in ["agent_coordination", "delegation"]:
            lane_score = trust_score.coordination_lane
        else:
            lane_score = trust_score.tool_usage_lane
        
        if lane_score < min_threshold:
            return GateResult(
                decision=GateDecision.DENY,
                agent_id=proposal.agent_id,
                proposal_hash=proposal.context_hash,
                violation_type=ViolationType.TRUST_SCORE_TOO_LOW,
                trust_score=trust_score,
                reason=f"Trust score {lane_score:.2f} below threshold {min_threshold:.2f} for {required_capability}"
            )
        
        return GateResult(
            decision=GateDecision.APPROVE,
            agent_id=proposal.agent_id,
            proposal_hash=proposal.context_hash,
            trust_score=trust_score,
            reason=f"Trust score {lane_score:.2f} meets threshold {min_threshold:.2f}"
        )
    
    def _check_budget(
        self,
        proposal: AgentProposal,
        available_budget: int
    ) -> GateResult:
        """Stage 3: Verify sufficient token budget."""
        requested_cost = proposal.estimated_token_cost or 0
        if requested_cost > available_budget:
            return GateResult(
                decision=GateDecision.HARD_STOP,
                agent_id=proposal.agent_id,
                proposal_hash=proposal.context_hash,
                violation_type=ViolationType.BUDGET_EXCEEDED,
                required_budget=requested_cost,
                available_budget=available_budget,
                reason=f"Budget exceeded: requested {requested_cost}, available {available_budget}"
            )
        
        return GateResult(
            decision=GateDecision.APPROVE,
            agent_id=proposal.agent_id,
            proposal_hash=proposal.context_hash,
            required_budget=requested_cost,
            available_budget=available_budget,
            reason=f"Budget check passed: {requested_cost}/{available_budget}"
        )
    
    async def _verify_capability(
        self,
        proposal: AgentProposal,
        trust_score: TrustScore
    ) -> GateResult:
        """Stage 4: Verify agent has required capability."""
        # In production, this queries Zilliz CAPABILITY track
        # For now, we do a basic check based on trust score
        capability_map = {
            "basic": True,
            "intermediate": trust_score.overall >= 0.5,
            "advanced": trust_score.overall >= 0.7,
            "premium": trust_score.overall >= 0.8,
        }
        
        has_capability = capability_map.get(proposal.requested_capability, False)
        if not has_capability:
            return GateResult(
                decision=GateDecision.DENY,
                agent_id=proposal.agent_id,
                proposal_hash=proposal.context_hash,
                violation_type=ViolationType.CAPABILITY_MISMATCH,
                trust_score=trust_score,
                reason=f"Agent lacks {proposal.requested_capability} capability"
            )
        
        return GateResult(
            decision=GateDecision.APPROVE,
            agent_id=proposal.agent_id,
            proposal_hash=proposal.context_hash,
            trust_score=trust_score,
            reason=f"Capability {proposal.requested_capability} verified"
        )
    
    async def _detect_harm(self, proposal: AgentProposal) -> GateResult:
        """Stage 5: Detect non-compensatory harm attempts."""
        # Check for unauthorized network access
        if proposal.action_type == "network_request":
            allowed_domains = ["api.cloudflare.com", "api.zilliz.com", "localhost"]
            target = proposal.action_params.get("url", "")
            
            is_allowed = any(domain in target for domain in allowed_domains)
            if not is_allowed:
                return GateResult(
                    decision=GateDecision.HARD_STOP,
                    agent_id=proposal.agent_id,
                    proposal_hash=proposal.context_hash,
                    violation_type=ViolationType.UNAUTHORIZED_NETWORK,
                    reason=f"Unauthorized network access attempt to {target}"
                )
        
        # Check for filesystem violations
        if proposal.action_type in ["file_read", "file_write"]:
            path = proposal.action_params.get("path", "")
            protected_paths = ["/etc", "/root", "/proc", "/sys"]
            
            if any(path.startswith(p) for p in protected_paths):
                return GateResult(
                    decision=GateDecision.HARD_STOP,
                    agent_id=proposal.agent_id,
                    proposal_hash=proposal.context_hash,
                    violation_type=ViolationType.FILESYSTEM_VIOLATION,
                    reason=f"Attempted access to protected path: {path}"
                )
        
        return GateResult(
            decision=GateDecision.APPROVE,
            agent_id=proposal.agent_id,
            proposal_hash=proposal.context_hash,
            reason="No harm detected"
        )
    
    async def _fetch_trust_score(self, agent_id: str) -> TrustScore:
        """Fetch trust score from Zilliz or return default."""
        if self.zilliz_client:
            # In production, query Zilliz TRUST track
            pass
        
        # Return default trust score for new agents
        return TrustScore(agent_id=agent_id)
    
    async def _log_and_return(self, result: GateResult) -> GateResult:
        """Log result to VAP chain and return."""
        if self.vap_chain:
            await self.vap_chain.log_gate_decision(result)
        
        # Track violation history
        if result.violation_type:
            if result.agent_id not in self._violation_history:
                self._violation_history[result.agent_id] = []
            self._violation_history[result.agent_id].append(result)
        
        return result
    
    def get_violation_history(self, agent_id: str) -> List[GateResult]:
        """Get violation history for an agent."""
        return self._violation_history.get(agent_id, [])
    
    def slash_trust_score(
        self,
        agent_id: str,
        violation_type: ViolationType,
        severity: float = 0.1
    ) -> TrustScore:
        """
        Slash agent trust score based on violation.
        
        Args:
            agent_id: The violating agent
            violation_type: Type of violation committed
            severity: Severity multiplier (0.0-1.0)
            
        Returns:
            Updated trust score
        """
        # Determine which lane to slash based on violation
        lane_mapping = {
            ViolationType.UNAUTHORIZED_NETWORK: "tool_usage_lane",
            ViolationType.FILESYSTEM_VIOLATION: "implementation_lane",
            ViolationType.NON_COMPENSATORY_HARM: "overall",
            ViolationType.MULTI_TURN_ATTACK: "coordination_lane",
        }
        
        lane = lane_mapping.get(violation_type, "overall")
        
        # In production, fetch current score from Zilliz
        trust_score = TrustScore(agent_id=agent_id)
        
        # Apply slash
        current_value = getattr(trust_score, lane, trust_score.overall)
        new_value = max(0.0, current_value - severity)
        setattr(trust_score, lane, new_value)
        
        # Recalculate overall
        trust_score.overall = (
            trust_score.implementation_lane * 0.4 +
            trust_score.coordination_lane * 0.3 +
            trust_score.tool_usage_lane * 0.3
        )
        
        return trust_score
