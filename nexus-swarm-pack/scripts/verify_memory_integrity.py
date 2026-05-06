#!/usr/bin/env python3
"""
Memory Layer Integrity Verification Script

Verifies Zilliz dual-cluster integrity, queries nexus_events and nexus_governance collections,
confirms VAP chain integrity via KAIJUGovernor, and generates a synchronization report.
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Dict, Any

# Add nexus-swarm-pack to path
sys.path.insert(0, '/workspace/rigs/32c6c066-3630-409b-9f13-9c84dec5f780/worktrees/gt__toast__cb8947b8/nexus-swarm-pack')

from src.nexus_os.vault.zilliz_client import ZillizClient
from nexus_kernel.kaiju import KAIJUGovernor, AgentProposal, GateDecision
from nexus_kernel.vap import VAPChain


async def verify_zilliz_clusters(zilliz: ZillizClient) -> Dict[str, Any]:
    """Verify Zilliz dual-cluster integrity."""
    print("🔍 Verifying Zilliz dual-cluster integrity...")
    
    health = await zilliz.health_check()
    report = {
        "zilliz_available": health["available"],
        "clusters": {},
        "collections_checked": {}
    }
    
    if not health["available"]:
        print("❌ Zilliz not available")
        return report
    
    # Check serverless cluster (nexus_events for EVENT track)
    serverless_health = health["clusters"].get("serverless", {})
    report["clusters"]["serverless"] = {
        "status": serverless_health.get("status", "unhealthy"),
        "error": serverless_health.get("error"),
        "collections_count": serverless_health.get("collections", 0)
    }
    
    # Check town cluster (nexus_governance for GOVERNANCE track)
    town_health = health["clusters"].get("town", {})
    report["clusters"]["town"] = {
        "status": town_health.get("status", "unhealthy"),
        "error": town_health.get("error"),
        "collections_count": town_health.get("collections", 0)
    }
    
    # Get entity counts for required collections
    for track_type in ["EVENT", "GOVERNANCE"]:
        try:
            entity_count = await zilliz.get_entity_count(track_type)
            collection_name = zilliz._get_collection_name(track_type)
            cluster = zilliz._get_cluster_for_track(track_type)
            
            # Check if collection exists
            exists = False
            if cluster and cluster in zilliz._connections:
                exists = zilliz._connections[cluster].has_collection(collection_name)
            
            report["collections_checked"][track_type] = {
                "collection_name": collection_name,
                "cluster": cluster,
                "entity_count": entity_count,
                "exists": exists
            }
            print(f"  ✓ {collection_name} ({cluster}): {entity_count} entities (exists: {exists})")
        except Exception as e:
            report["collections_checked"][track_type] = {"error": str(e)}
            print(f"  ❌ Failed to check {track_type}: {e}")
    
    return report


async def verify_vap_chain() -> Dict[str, Any]:
    """Verify VAP chain integrity via KAIJUGovernor."""
    print("\n🔗 Verifying VAP chain integrity...")
    
    report = {
        "vap_chain": {}
    }
    
    try:
        # Initialize VAP chain and KAIJU governor
        vap_chain = VAPChain()
        governor = KAIJUGovernor(vap_chain=vap_chain)
        
        # Log a test gate decision to populate chain if empty
        if vap_chain.get_chain_length() == 0:
            test_proposal = AgentProposal(
                agent_id="verification_agent",
                action_type="test",
                action_params={"test": True}
            )
            await governor.evaluate_proposal(test_proposal)
        
        # Verify chain integrity
        integrity_valid = vap_chain.verify_chain_integrity()
        audit_summary = vap_chain.get_audit_summary()
        
        report["vap_chain"] = {
            "integrity_valid": integrity_valid,
            "chain_length": vap_chain.get_chain_length(),
            "audit_summary": audit_summary
        }
        
        if integrity_valid:
            print("  ✓ VAP chain integrity verified")
        else:
            print("  ❌ VAP chain integrity FAILED")
        
        print(f"  Chain length: {vap_chain.get_chain_length()} entries")
        
    except Exception as e:
        report["vap_chain"] = {"error": str(e)}
        print(f"  ❌ VAP chain verification failed: {e}")
    
    return report


async def generate_report(
    zilliz_report: Dict[str, Any],
    vap_report: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate full synchronization report."""
    print("\n📄 Generating synchronization report...")
    
    full_report = {
        "report_metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "report_type": "memory_layer_integrity",
            "agent": "Flint",
            "bead_id": "cb8947b8-dd77-44db-bd00-052bcdd96743"
        },
        "zilliz_status": zilliz_report,
        "vap_chain_status": vap_report,
        "summary": {
            "zilliz_healthy": zilliz_report.get("zilliz_available", False) and 
                              all(c.get("status") == "healthy" for c in zilliz_report.get("clusters", {}).values()),
            "vap_integrity_valid": vap_report.get("vap_chain", {}).get("integrity_valid", False),
            "total_entities": sum(
                coll.get("entity_count", 0) 
                for coll in zilliz_report.get("collections_checked", {}).values() 
                if isinstance(coll, dict) and "entity_count" in coll
            )
        }
    }
    
    return full_report


async def main():
    """Main verification routine."""
    print("=" * 60)
    print("Memory Layer Integrity Verification")
    print("=" * 60)
    
    # Initialize Zilliz client
    zilliz = ZillizClient()
    
    # Verify Zilliz clusters
    zilliz_report = await verify_zilliz_clusters(zilliz)
    
    # Verify VAP chain
    vap_report = await verify_vap_chain()
    
    # Generate full report
    full_report = await generate_report(zilliz_report, vap_report)
    
    # Output report
    print("\n" + "=" * 60)
    print("Final Report")
    print("=" * 60)
    print(json.dumps(full_report, indent=2, default=str))
    
    # Write report to file
    report_path = "/workspace/rigs/32c6c066-3630-409b-9f13-9c84dec5f780/worktrees/gt__toast__cb8947b8/nexus-swarm-pack/memory_integrity_report.json"
    with open(report_path, "w") as f:
        json.dump(full_report, f, indent=2, default=str)
    print(f"\nReport saved to: {report_path}")
    
    # Exit with appropriate code
    if full_report["summary"]["zilliz_healthy"] and full_report["summary"]["vap_integrity_valid"]:
        print("\n✅ All checks passed")
        return 0
    else:
        print("\n❌ Some checks failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
