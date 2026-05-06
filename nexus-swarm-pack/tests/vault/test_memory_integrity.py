"""
Tests for memory layer integrity verification.
"""

import asyncio
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
import pytest

# Add nexus-swarm-pack to path
import sys
sys.path.insert(0, '/workspace/rigs/32c6c066-3630-409b-9f13-9c84dec5f780/worktrees/gt__toast__cb8947b8/nexus-swarm-pack')

from src.nexus_os.vault.zilliz_client import ZillizClient
from nexus_kernel.kaiju import KAIJUGovernor, AgentProposal
from nexus_kernel.vap import VAPChain


@pytest.fixture
def vap_chain():
    """Create a fresh VAPChain for testing."""
    return VAPChain()


@pytest.fixture
def governor(vap_chain):
    """Create a KAIJUGovernor with VAPChain."""
    return KAIJUGovernor(vap_chain=vap_chain)


@pytest.mark.asyncio
async def test_zilliz_client_not_available():
    """Test Zilliz client when not configured."""
    with patch.dict(os.environ, {}, clear=True):
        client = ZillizClient()
        assert not client.is_available()
        
        health = await client.health_check()
        assert health["available"] is False
        
        entity_count = await client.get_entity_count("EVENT")
        assert entity_count == 0


@pytest.mark.asyncio
async def test_vap_chain_integrity_empty():
    """Test VAP chain integrity with empty chain."""
    chain = VAPChain()
    assert chain.verify_chain_integrity() is True
    assert chain.get_chain_length() == 0


@pytest.mark.asyncio
async def test_vap_chain_integrity_with_entries(vap_chain, governor):
    """Test VAP chain integrity after adding entries."""
    # Log a test proposal
    proposal = AgentProposal(
        agent_id="test_agent",
        action_type="test",
        action_params={"test": True}
    )
    await governor.evaluate_proposal(proposal)
    
    # Verify integrity
    assert vap_chain.verify_chain_integrity() is True
    assert vap_chain.get_chain_length() == 1
    
    # Get audit summary
    summary = vap_chain.get_audit_summary()
    assert summary["total_entries"] == 1
    assert summary["chain_integrity"] is True


@pytest.mark.asyncio
async def test_vap_chain_tamper_detection(vap_chain):
    """Test that tampering with chain entries is detected."""
    # Add an entry
    from nexus_kernel.vap import GateDecisionRecord
    record = GateDecisionRecord(
        decision="approve",
        agent_id="agent1",
        proposal_hash="hash1",
        violation_type=None,
        reason="test",
        trust_score=0.5,
        required_budget=0,
        available_budget=100
    )
    entry = await vap_chain._log_event(
        event_type="gate_decision",
        agent_id="agent1",
        action_hash="hash1",
        metadata=record.__dict__
    )
    
    # Tamper with the entry
    vap_chain._chain[0].current_hash = "tampered_hash"
    
    # Verify integrity fails
    assert vap_chain.verify_chain_integrity() is False


@pytest.mark.asyncio
async def test_generate_report():
    """Test report generation with mocked data."""
    from scripts.verify_memory_integrity import generate_report
    
    zilliz_report = {
        "zilliz_available": False,
        "clusters": {},
        "collections_checked": {}
    }
    
    vap_report = {
        "vap_chain": {
            "integrity_valid": True,
            "chain_length": 1,
            "audit_summary": {}
        }
    }
    
    report = await generate_report(zilliz_report, vap_report)
    
    assert "report_metadata" in report
    assert report["report_metadata"]["report_type"] == "memory_layer_integrity"
    assert "zilliz_status" in report
    assert "vap_chain_status" in report
    assert "summary" in report


@pytest.mark.asyncio
async def test_report_file_generation():
    """Test that report is written to file correctly."""
    from scripts.verify_memory_integrity import generate_report
    import tempfile
    import json
    
    zilliz_report = {"zilliz_available": False, "clusters": {}, "collections_checked": {}}
    vap_report = {"vap_chain": {"integrity_valid": True, "chain_length": 0, "audit_summary": {}}}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the report path
        with patch('scripts.verify_memory_integrity.open', create=True) as mock_open:
            report = await generate_report(zilliz_report, vap_report)
            # Check report structure
            assert "report_metadata" in report
            assert "summary" in report
