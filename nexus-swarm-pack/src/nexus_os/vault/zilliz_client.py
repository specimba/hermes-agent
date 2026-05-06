"""
zilliz_client.py — Zilliz Cloud Vector Memory Integration

Provides hybrid vector memory using Zilliz Cloud (Milvus-compatible) for semantic recall.

Design principles:
1. Local-first: SQLite remains primary source of truth
2. Async Mirror: Zilliz receives async writes for semantic indexing
3. Dual-Cluster: 
   - nexus-serverless: EVENT & FAILURE_PATTERN tracks (high velocity)
   - nexus-os-town: TRUST & GOVERNANCE tracks (steady state)
4. Security: Credentials ONLY from environment variables (never hardcoded)
5. Graceful Degradation: If Zilliz unavailable, fallback to local SQLite only

Usage:
    zilliz = ZillizClient()
    if zilliz.is_available():
        await zilliz.store_embedding(agent_id, lane, track_type, key, value, embedding)
        results = await zilliz.similar_search(query_embedding, top_k=5)
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────────────────────

def _get_zilliz_config() -> Dict[str, str]:
    """
    Get Zilliz configuration from environment variables.
    
    Required env vars:
    - ZILLIZ_SERVERLESS_URI: URI for nexus-serverless cluster
    - ZILLIZ_SERVERLESS_TOKEN: API token for nexus-serverless
    - ZILLIZ_TOWN_URI: URI for nexus-os-town cluster  
    - ZILLIZ_TOWN_TOKEN: API token for nexus-os-town
    
    Returns empty dict if not configured (graceful degradation).
    """
    config = {
        "serverless_uri": os.getenv("ZILLIZ_SERVERLESS_URI", ""),
        "serverless_token": os.getenv("ZILLIZ_SERVERLESS_TOKEN", ""),
        "town_uri": os.getenv("ZILLIZ_TOWN_URI", ""),
        "town_token": os.getenv("ZILLIZ_TOWN_TOKEN", ""),
    }
    
    # Check if at least one cluster is configured
    has_serverless = bool(config["serverless_uri"] and config["serverless_token"])
    has_town = bool(config["town_uri"] and config["town_token"])
    
    if not (has_serverless or has_town):
        logger.debug("Zilliz not configured (missing env vars). Running in local-only mode.")
        return {}
    
    return config


def is_zilliz_available() -> bool:
    """Check if Zilliz is configured and ready."""
    config = _get_zilliz_config()
    return bool(config)


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class VectorRecord:
    """Vector record for Zilliz storage."""
    id: str
    embedding: List[float]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "vector": self.embedding,
            "metadata": self.metadata
        }


# ─── Zilliz Client ───────────────────────────────────────────────────────────

class ZillizClient:
    """
    Zilliz Cloud client for hybrid vector memory.
    
    Supports dual-cluster architecture:
    - Serverless cluster: High-velocity event/failure data
    - Town cluster: Steady-state trust/governance data
    
    Automatically selects cluster based on track type.
    """
    
    # Track type to cluster mapping
    TRACK_CLUSTER_MAP = {
        "EVENT": "serverless",
        "FAILURE_PATTERN": "serverless",
        "TRUST": "town",
        "GOVERNANCE": "town",
        "CAPABILITY": "town",
    }
    
    def __init__(self):
        """Initialize Zilliz client."""
        self._config = _get_zilliz_config()
        self._connections: Dict[str, Any] = {}
        self._collections: Dict[str, Any] = {}
        self._available = False
        
        if self._config:
            self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize connections to configured clusters."""
        try:
            # Dynamically import pymilvus only if needed
            from pymilvus import MilvusClient
            
            # Connect to serverless cluster
            if self._config.get("serverless_uri"):
                try:
                    self._connections["serverless"] = MilvusClient(
                        uri=self._config["serverless_uri"],
                        token=self._config["serverless_token"]
                    )
                    logger.info("✓ Connected to Zilliz nexus-serverless cluster")
                except Exception as e:
                    logger.warning(f"Failed to connect to nexus-serverless: {e}")
            
            # Connect to town cluster
            if self._config.get("town_uri"):
                try:
                    self._connections["town"] = MilvusClient(
                        uri=self._config["town_uri"],
                        token=self._config["town_token"]
                    )
                    logger.info("✓ Connected to Zilliz nexus-os-town cluster")
                except Exception as e:
                    logger.warning(f"Failed to connect to nexus-os-town: {e}")
            
            self._available = bool(self._connections)
            
        except ImportError:
            logger.warning("pymilvus not installed. Zilliz integration disabled.")
            self._available = False
        except Exception as e:
            logger.error(f"Zilliz initialization error: {e}")
            self._available = False
    
    def is_available(self) -> bool:
        """Check if Zilliz client is ready."""
        return self._available
    
    def _get_cluster_for_track(self, track_type: str) -> Optional[str]:
        """Determine which cluster to use for a given track type."""
        cluster_name = self.TRACK_CLUSTER_MAP.get(track_type, "town")
        
        # Verify connection exists
        if cluster_name not in self._connections:
            # Fallback to any available cluster
            if "town" in self._connections:
                return "town"
            elif "serverless" in self._connections:
                return "serverless"
            return None
        
        return cluster_name
    
    def _get_collection_name(self, track_type: str) -> str:
        """Generate collection name for track type."""
        return f"nexus_{track_type.lower()}"
    
    async def ensure_collection(self, track_type: str, dimension: int = 1024):
        """
        Ensure collection exists with proper schema.
        
        Args:
            track_type: Type of track (EVENT, TRUST, etc.)
            dimension: Embedding dimension (default 1024 for modern models)
        """
        if not self._available:
            return
        
        cluster_name = self._get_cluster_for_track(track_type)
        if not cluster_name:
            return
        
        collection_name = self._get_collection_name(track_type)
        client = self._connections[cluster_name]
        
        try:
            # Check if collection exists
            if client.has_collection(collection_name):
                logger.debug(f"Collection {collection_name} already exists")
                return
            
            # Create collection with schema
            from pymilvus import DataType
            
            schema = client.create_schema(
                auto_id=False,
                enable_dynamic_field=True
            )
            schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=256, is_primary=True)
            schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=dimension)
            schema.add_field(field_name="metadata", datatype=DataType.JSON)
            schema.add_field(field_name="created_at", datatype=DataType.VARCHAR, max_length=64)
            
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="embedding",
                index_type="AUTOINDEX",
                metric_type="COSINE"
            )
            
            client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params
            )
            
            logger.info(f"✓ Created Zilliz collection: {collection_name} ({cluster_name})")
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
    
    async def store_embedding(
        self,
        agent_id: str,
        lane: str,
        track_type: str,
        key: str,
        value: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store embedding in Zilliz.
        
        Args:
            agent_id: Agent identifier
            lane: Execution lane
            track_type: Type of track (EVENT, TRUST, etc.)
            key: Record key
            value: Text value (for reference)
            embedding: Vector embedding
            metadata: Additional metadata
        """
        if not self._available:
            logger.debug("Zilliz not available, skipping embedding storage")
            return
        
        try:
            # Ensure collection exists
            await self.ensure_collection(track_type, len(embedding))
            
            cluster_name = self._get_cluster_for_track(track_type)
            if not cluster_name:
                return
            
            collection_name = self._get_collection_name(track_type)
            client = self._connections[cluster_name]
            
            # Generate unique ID
            record_id = f"{agent_id}_{lane}_{track_type}_{key}"
            
            # Prepare metadata
            full_metadata = {
                "agent_id": agent_id,
                "lane": lane,
                "track_type": track_type,
                "key": key,
                "value": value,
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
            
            # Create record
            record = VectorRecord(
                id=record_id,
                embedding=embedding,
                metadata=full_metadata
            )
            
            # Insert into Zilliz
            client.insert(
                collection_name=collection_name,
                data=[record.to_dict()]
            )
            
            logger.debug(f"✓ Stored embedding in Zilliz: {record_id}")
            
        except Exception as e:
            logger.error(f"Failed to store embedding in Zilliz: {e}")
    
    async def similar_search(
        self,
        query_embedding: List[float],
        track_type: Optional[str] = None,
        top_k: int = 5,
        filter_expr: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings.
        
        Args:
            query_embedding: Query vector
            track_type: Optional track type filter (searches all if None)
            top_k: Number of results to return
            filter_expr: Optional Milvus filter expression
            
        Returns:
            List of matching records with metadata and distance
        """
        if not self._available:
            return []
        
        results = []
        
        try:
            # Determine which collections to search
            if track_type:
                cluster_name = self._get_cluster_for_track(track_type)
                if not cluster_name:
                    return []
                collection_name = self._get_collection_name(track_type)
                collections_to_search = [(cluster_name, collection_name)]
            else:
                # Search all available collections
                collections_to_search = []
                for cluster_name, client in self._connections.items():
                    for track in self.TRACK_CLUSTER_MAP.keys():
                        if self.TRACK_CLUSTER_MAP[track] == cluster_name:
                            coll_name = self._get_collection_name(track)
                            if client.has_collection(coll_name):
                                collections_to_search.append((cluster_name, coll_name))
            
            # Search each collection
            for cluster_name, collection_name in collections_to_search:
                client = self._connections[cluster_name]
                
                search_results = client.search(
                    collection_name=collection_name,
                    data=[query_embedding],
                    limit=top_k,
                    filter=filter_expr,
                    output_fields=["metadata"]
                )
                
                # Process results
                for hit in search_results[0]:
                    results.append({
                        "id": hit.entity.id,
                        "distance": hit.distance,
                        "metadata": hit.entity.get("metadata", {}),
                        "collection": collection_name
                    })
            
            # Sort by distance (ascending for COSINE)
            results.sort(key=lambda x: x["distance"])
            
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Zilliz search error: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Zilliz connections.
        
        Returns:
            Health status dictionary
        """
        status = {
            "available": self._available,
            "clusters": {}
        }
        
        if not self._available:
            return status
        
        for cluster_name, client in self._connections.items():
            try:
                # Simple operation to test connection
                collections = client.list_collections()
                status["clusters"][cluster_name] = {
                    "status": "healthy",
                    "collections": len(collections)
                }
            except Exception as e:
                status["clusters"][cluster_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return status

    async def get_entity_count(self, track_type: str) -> int:
        """
        Get number of entities in the collection for a track type.
        
        Args:
            track_type: Type of track (EVENT, GOVERNANCE, etc.)
            
        Returns:
            Number of entities, or 0 if collection doesn't exist or error.
        """
        if not self._available:
            return 0
        
        cluster_name = self._get_cluster_for_track(track_type)
        if not cluster_name:
            return 0
        
        collection_name = self._get_collection_name(track_type)
        client = self._connections.get(cluster_name)
        if not client:
            return 0
        
        try:
            if client.has_collection(collection_name):
                return client.num_entities(collection_name)
            return 0
        except Exception as e:
            logger.error(f"Failed to get entity count for {collection_name}: {e}")
            return 0
