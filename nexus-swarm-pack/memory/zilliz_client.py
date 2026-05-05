#!/usr/bin/env python3
"""
Zilliz Dual-Cluster Vector Client
Handles connection to both nexus-serverless and nexus-os-town with auto-fallback.
"""
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class ZillizClient:
    """Unified client for NEXUS hybrid memory layer."""

    def __init__(self):
        self.connections = {}
        self._connect_all()

    def _connect_all(self):
        """Initialize connections to both clusters."""
        try:
            # Import here to ensure availability
            from pymilvus import connections, utility
            
            # Cluster 1: Serverless (Events/Failures)
            self._connect_cluster(
                name="serverless",
                uri=os.getenv("ZILLIZ_SERVERLESS_URI"),
                user=os.getenv("ZILLIZ_SERVERLESS_USER"),
                password=os.getenv("ZILLIZ_SERVERLESS_PASSWORD"),
                token=os.getenv("ZILLIZ_SERVERLESS_TOKEN")
            )

            # Cluster 2: Town (Trust/Governance)
            self._connect_cluster(
                name="town",
                uri=os.getenv("ZILLIZ_TOWN_URI"),
                token=os.getenv("ZILLIZ_TOWN_TOKEN")
            )

            logger.info("✅ Zilliz dual-cluster client initialized")

        except Exception as e:
            logger.warning(f"⚠️ Zilliz initialization partial: {e}")

    def _connect_cluster(self, name: str, uri: str, token: str = None, user: str = None, password: str = None):
        """Connect to a single cluster with fallback logic."""
        if not uri:
            raise ValueError(f"Missing URI for {name}")

        alias = f"nexus_{name}"
        
        # Import inside method to ensure scope
        from pymilvus import connections

        # Try token first
        if token:
            try:
                connections.connect(alias=alias, uri=uri, token=token)
                logger.info(f"✅ Connected to {name} (Token Auth)")
                self.connections[name] = alias
                return
            except Exception as e:
                logger.debug(f"Token auth failed for {name}: {e}")
                pass # Fall through to user/pass

        # Fallback to user/pass
        if user and password:
            try:
                connections.connect(alias=alias, uri=uri, user=user, password=password)
                logger.info(f"✅ Connected to {name} (User/Pass Auth)")
                self.connections[name] = alias
                return
            except Exception as e:
                logger.error(f"User/Pass auth failed for {name}: {e}")
                raise Exception(f"Failed to connect to {name}: {e}")

        raise Exception(f"No valid credentials for {name}")

    def list_collections(self, cluster: str = "all") -> Dict[str, List[str]]:
        """List collections in specified cluster(s)."""
        from pymilvus import utility

        results = {}
        targets = [cluster] if cluster != "all" else list(self.connections.keys())

        for name in targets:
            alias = self.connections.get(name)
            if alias:
                try:
                    cols = utility.list_collections(using=alias)
                    results[name] = cols
                except Exception as e:
                    results[name] = [f"Error: {e}"]
            else:
                results[name] = ["Not connected"]

        return results

    def search_semantic(self, cluster: str, collection: str, vector: List[float], limit: int = 5) -> List[Dict]:
        """Perform semantic search on a vector collection."""
        from pymilvus import utility, SearchParams

        alias = self.connections.get(cluster)
        if not alias:
            raise ValueError(f"Not connected to {cluster}")

        # Simple search example (requires collection to exist with proper schema)
        try:
            results = utility.search(
                collection_name=collection,
                data=[vector],
                anns_field="vector", # Default field name
                param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                limit=limit,
                using=alias
            )
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

# Singleton instance
_client_instance = None

def get_client() -> ZillizClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = ZillizClient()
    return _client_instance
