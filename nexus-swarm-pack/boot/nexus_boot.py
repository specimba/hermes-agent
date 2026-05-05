#!/usr/bin/env python3
"""
NEXUS Boot Sequence - Phase C
Bridges Nexus Kernel (Port 7352) with OpenShell Execution Substrate
"""

import sys
import os

# Inject local paths
script_dir = os.path.dirname(os.path.abspath(__file__))
pack_dir = os.path.dirname(script_dir)
if pack_dir not in sys.path:
    sys.path.insert(0, pack_dir)
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nexus_kernel import KAIJUGovernor, VAPChain, TokenGuard, ArchivistV5
from runtimes.worker_registry import WorkerRegistry
from runtimes.openshell_executor import OpenShellExecutor

def boot_sequence():
    """Execute NEXUS OS boot sequence"""
    print("🧬 NEXUS OS v1.0-RC1 Boot Sequence")
    print("=" * 50)
    
    # Phase 1: Initialize Kernel
    print("\n[1/4] Initializing Kernel (Port 7352)...")
    governor = KAIJUGovernor()
    vap = VAPChain()
    token_guard = TokenGuard()
    archivist = ArchivistV5()
    print("✓ KAIJU Governor loaded")
    print("✓ VAP Audit Chain initialized")
    print("✓ TokenGuard ready")
    print("✓ Archivist v5.0 ready")
    
    # Phase 2: Initialize Worker Registry
    print("\n[2/4] Registering Execution Runtimes...")
    registry = WorkerRegistry.get_instance()
    registry.register_runtime("native", {"type": "native", "isolation": "none"})
    registry.register_runtime("foundry", {"type": "foundry", "isolation": "filesystem"})
    registry.register_runtime("openshell", {"type": "openshell", "isolation": "full"})
    registry.register_runtime("wrapper", {"type": "wrapper", "isolation": "network"})
    print(f"✓ {len(registry.list_runtimes())} runtimes registered")
    
    # Phase 3: Initialize OpenShell Executor
    print("\n[3/4] Connecting OpenShell Gateway...")
    executor = OpenShellExecutor(gateway_url="http://127.0.0.1:8080")
    if executor.health_check():
        print("✓ OpenShell gateway connected")
    else:
        print("⚠ OpenShell gateway not available (run openshell_setup.sh first)")
    
    # Phase 4: Integration Test
    print("\n[4/4] Running Integration Test...")
    from runtimes.sandbox_identity import SandboxIdentity, TaskPacket, SecurityLevel
    
    task = TaskPacket(
        agent_id="test_agent",
        action="execute_code",
        payload={"code": "print('hello')"},
        sandbox_identity=SandboxIdentity(
            policy_profile="codex_exec",
            capability_tags=["python", "filesystem_read"],
            trust_tier="standard"
        )
    )
    
    # Test KAIJU evaluation (async)
    import asyncio
    from nexus_kernel.kaiju import AgentProposal
    
    proposal = AgentProposal(
        agent_id="test_agent",
        action_type="code_execution",
        target_resource="/workspace/test.py",
        parameters={"language": "python"},
        justification="Testing boot sequence"
    )
    
    async def test_kaiju():
        result = await governor.evaluate_proposal(proposal)
        return result
    
    decision = asyncio.run(test_kaiju())
    print(f"✓ KAIJU decision: {decision.decision}")
    
    # Log to VAP
    vap_entry = asyncio.run(vap.log_gate_decision(decision))
    print(f"✓ VAP chain length: {vap.get_chain_length()}")
    
    print("\n" + "=" * 50)
    print("🎉 NEXUS OS Boot Complete - Ready for Swarm Operations")
    print("=" * 50)
    
    return {
        "governor": governor,
        "vap": vap,
        "token_guard": token_guard,
        "archivist": archivist,
        "registry": registry,
        "executor": executor
    }

if __name__ == "__main__":
    try:
        boot_sequence()
    except Exception as e:
        print(f"\n❌ Boot failed: {e}")
        sys.exit(1)
