"""
NEXUS Cloud Edge Integration Module

Connects local NEXUS Kernel to:
1. Zilliz Dual-Cluster (Hot/Cold Memory)
2. Supabase (Relational State Mirror)
3. Zo Computer (Remote Execution Bridge)

Architecture:
┌─────────────────┐      ┌───────────────────────┐
│ Local Kernel    │─────▶│ Cloud Edge Manager    │
│ (Port 7352)     │      │ (Hybrid Sync)         │
└─────────────────┘      └───────────┬───────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
│ Zilliz HOT            │ │ Zilliz COLD           │ │ Supabase              │
│ nexus-serverless      │ │ nexus-os-town         │ │ nexus-gspp            │
│ (Events/Failures)     │ │ (Trust/Governance)    │ │ (State Mirror)        │
└───────────────────────┘ └───────────────────────┘ └───────────────────────┘
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

# Try importing optional dependencies
try:
    from pymilvus import connections, Collection, utility
    HAS_MILVUS = True
except ImportError:
    HAS_MILVUS = False

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

logger = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────────────────────

@dataclass
class ZillizConfig:
    """Zilliz Cloud Cluster Configuration."""
    uri: str
    token: str
    cluster_name: str
    purpose: str  # "hot" or "cold"

@dataclass
class SupabaseConfig:
    """Supabase Project Configuration."""
    url: str
    key: str
    project_name: str

def get_cloud_config() -> Dict[str, Any]:
    """Load cloud configuration from environment or config file."""
    return {
        "zilliz_serverless": ZillizConfig(
            uri=os.getenv("ZILLIZ_SERVERLESS_URI", "https://in05-2a4b7e6226ae27e.serverless.aws-eu-central-1.cloud.zilliz.com"),
            token=os.getenv("ZILLIZ_SERVERLESS_TOKEN", ""),
            cluster_name="nexus-serverless",
            purpose="serverless"
        ),
        "zilliz_town": ZillizConfig(
            uri=os.getenv("ZILLIZ_TOWN_URI", "https://in03-db7a5bcd01da539.serverless.aws-eu-central-1.cloud.zilliz.com"),
            token=os.getenv("ZILLIZ_TOWN_TOKEN", ""),
            cluster_name="nexus-os-town",
            purpose="town"
        ),
        "supabase": SupabaseConfig(
            url=os.getenv("SUPABASE_URL", ""),
            key=os.getenv("SUPABASE_KEY", ""),
            project_name="nexus-gspp"
        )
    }

# ─── Zilliz Dual-Cluster Client ─────────────────────────────────────────────

class ZillizDualCluster:
    """
    Manages asymmetric memory across two Zilliz clusters.
    
    HOT Cluster (nexus-serverless): 
      - High throughput, serverless scaling
      - Stores: EVENT, FAILURE_PATTERN tracks
      
    COLD Cluster (nexus-os-town):
      - Steady state, free tier
      - Stores: TRUST, GOVERNANCE, CAPABILITY tracks
    """
    
    def __init__(self, hot_config: ZillizConfig, cold_config: ZillizConfig):
        self.hot_config = hot_config
        self.cold_config = cold_config
        self.hot_conn = None
        self.cold_conn = None
        self.collections: Dict[str, Collection] = {}
        
    def connect(self) -> bool:
        """Establish connections to both clusters."""
        if not HAS_MILVUS:
            logger.warning("pymilvus not installed. Zilliz integration disabled.")
            return False
            
        try:
            # Connect to HOT cluster
            connections.connect(
                alias="hot",
                uri=self.hot_config.uri,
                token=self.hot_config.token
            )
            logger.info(f"✅ Connected to Zilliz HOT ({self.hot_config.cluster_name})")
            
            # Connect to COLD cluster
            connections.connect(
                alias="cold",
                uri=self.cold_config.uri,
                token=self.cold_config.token
            )
            logger.info(f"✅ Connected to Zilliz COLD ({self.cold_config.cluster_name})")
            
            return True
        except Exception as e:
            logger.error(f"❌ Zilliz connection failed: {e}")
            return False
    
    def get_collection(self, name: str, purpose: str = "hot") -> Optional[Collection]:
        """Get or create a collection in the appropriate cluster."""
        alias = "hot" if purpose == "hot" else "cold"
        key = f"{alias}:{name}"
        
        if key in self.collections:
            return self.collections[key]
            
        try:
            if utility.has_collection(name, using=alias):
                col = Collection(name, using=alias)
            else:
                # Create default schema if not exists
                from pymilvus import FieldSchema, CollectionSchema, DataType
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=768),
                    FieldSchema(name="metadata", dtype=DataType.JSON),
                    FieldSchema(name="timestamp", dtype=DataType.INT64)
                ]
                schema = CollectionSchema(fields, f"NEXUS {name} track")
                col = Collection(name, schema, using=alias)
                
                # Create index
                index_params = {"index_type": "FLAT", "metric_type": "COSINE"}
                col.create_index("vector", index_params)
                
            self.collections[key] = col
            logger.info(f"✅ Collection '{name}' ready on {purpose.upper()} cluster")
            return col
        except Exception as e:
            logger.error(f"Failed to get collection {name}: {e}")
            return None
    
    def store_event(self, event_id: str, embedding: List[float], metadata: Dict):
        """Store an event in the HOT cluster (high throughput)."""
        col = self.get_collection("event_track", purpose="hot")
        if not col:
            return False
            
        try:
            entities = [{
                "id": event_id,
                "vector": embedding,
                "metadata": metadata,
                "timestamp": int(datetime.now().timestamp())
            }]
            col.insert(entities)
            logger.debug(f"Event {event_id} stored in HOT cluster")
            return True
        except Exception as e:
            logger.error(f"Failed to store event: {e}")
            return False
    
    def store_governance(self, gov_id: str, embedding: List[float], metadata: Dict):
        """Store governance data in the COLD cluster (steady state)."""
        col = self.get_collection("governance_track", purpose="cold")
        if not col:
            return False
            
        try:
            entities = [{
                "id": gov_id,
                "vector": embedding,
                "metadata": metadata,
                "timestamp": int(datetime.now().timestamp())
            }]
            col.insert(entities)
            logger.debug(f"Governance {gov_id} stored in COLD cluster")
            return True
        except Exception as e:
            logger.error(f"Failed to store governance: {e}")
            return False

# ─── Supabase State Mirror ──────────────────────────────────────────────────

class SupabaseMirror:
    """
    Mirrors critical governance state to Supabase Postgres.
    Provides SQL query capability for dashboards and external tools.
    """
    
    def __init__(self, config: SupabaseConfig):
        self.config = config
        self.client: Optional[Client] = None
        
    def connect(self) -> bool:
        """Connect to Supabase project."""
        if not HAS_SUPABASE:
            logger.warning("supabase-py not installed. Supabase integration disabled.")
            return False
            
        if not self.config.url or not self.config.key:
            logger.warning("Supabase credentials missing. Skipping connection.")
            return False
            
        try:
            self.client = create_client(self.config.url, self.config.key)
            logger.info(f"✅ Connected to Supabase ({self.config.project_name})")
            return True
        except Exception as e:
            logger.error(f"❌ Supabase connection failed: {e}")
            return False
    
    def sync_trust_score(self, agent_id: str, lane: str, score: float):
        """Sync trust score update to Supabase."""
        if not self.client:
            return False
            
        try:
            data = {
                "agent_id": agent_id,
                "lane": lane,
                "score": score,
                "updated_at": datetime.now().isoformat()
            }
            # Upsert logic (update if exists, insert if not)
            self.client.table("trust_scores").upsert(data).execute()
            logger.debug(f"Trust score synced for {agent_id}:{lane}")
            return True
        except Exception as e:
            logger.error(f"Failed to sync trust score: {e}")
            return False
    
    def sync_governance_decision(self, decision_id: str, agent_id: str, action: str, decision: str):
        """Log governance decision to Supabase for audit."""
        if not self.client:
            return False
            
        try:
            data = {
                "id": decision_id,
                "agent_id": agent_id,
                "action": action,
                "decision": decision,
                "logged_at": datetime.now().isoformat()
            }
            self.client.table("governance_log").insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
            return False

# ─── Unified Cloud Edge Manager ─────────────────────────────────────────────

class CloudEdgeManager:
    """
    Main entry point for NEXUS Cloud Edge integration.
    Orchestrates Zilliz and Supabase connections.
    """
    
    def __init__(self):
        self.config = get_cloud_config()
        self.zilliz = ZillizDualCluster(
            self.config["zilliz_serverless"],
            self.config["zilliz_town"]
        )
        self.supabase = SupabaseMirror(self.config["supabase"])
        self.ready = False
        
    def initialize(self) -> bool:
        """Initialize all cloud connections."""
        logger.info("🌩️  Initializing NEXUS Cloud Edge...")
        
        zilliz_ok = self.zilliz.connect()
        supabase_ok = self.supabase.connect()
        
        if zilliz_ok or supabase_ok:
            self.ready = True
            logger.info("✅ Cloud Edge initialized successfully")
            return True
        else:
            logger.warning("⚠️  Cloud Edge initialization partial (no connections)")
            return False
    
    def is_ready(self) -> bool:
        return self.ready
    
    def record_event(self, event_id: str, embedding: List[float], metadata: Dict):
        """Record an event to the appropriate cloud storage."""
        if not self.ready:
            return False
        return self.zilliz.store_event(event_id, embedding, metadata)
    
    def record_governance(self, gov_id: str, embedding: List[float], metadata: Dict):
        """Record governance data to the appropriate cloud storage."""
        if not self.ready:
            return False
        success = self.zilliz.store_governance(gov_id, embedding, metadata)
        if success and self.supabase.client:
            # Also mirror to Supabase for SQL access
            self.supabase.sync_governance_decision(
                gov_id, 
                metadata.get("agent_id", "unknown"),
                metadata.get("action", "unknown"),
                metadata.get("decision", "unknown")
            )
        return success

# ─── CLI Test Entry Point ───────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🌩️  Testing NEXUS Cloud Edge Integration...")
    manager = CloudEdgeManager()
    
    if manager.initialize():
        print("\n✅ Cloud Edge Ready!")
        print(f"   - Zilliz HOT: {manager.config['zilliz_hot'].cluster_name}")
        print(f"   - Zilliz COLD: {manager.config['zilliz_cold'].cluster_name}")
        print(f"   - Supabase: {manager.config['supabase'].project_name}")
    else:
        print("\n⚠️  Cloud Edge not fully ready (check credentials)")
