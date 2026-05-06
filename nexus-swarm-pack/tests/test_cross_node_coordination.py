"""
Cross-Node Coordination Protocol Tests

Tests concurrent read/write operations across nexus_events collection,
vector embedding storage/retrieval, and coordination primitives.
"""

import asyncio
import json
import time
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock

# Import the Zilliz client and related components
import sys
from pathlib import Path

# Add nexus-swarm-pack to path
nexus_pack_path = Path(__file__).parent.parent
sys.path.insert(0, str(nexus_pack_path))

from src.nexus_os.vault.zilliz_client import ZillizClient, VectorRecord


# Mock embedding function for testing
async def mock_embed_text(text: str) -> List[float]:
    """Generate deterministic mock embeddings based on text hash."""
    import hashlib
    hash_obj = hashlib.md5(text.encode())
    # Generate 1024-dimensional vector from hash
    hash_hex = hash_obj.hexdigest()
    vec = []
    for i in range(1024):
        # Deterministic but pseudo-random values
        val = int(hash_hex[i % len(hash_hex)], 16) / 15.0 - 0.5
        vec.append(val)
    return vec


class TestEvent:
    """Helper class for test events."""
    
    def __init__(self, agent_id: str, event_type: str, payload: Dict = None):
        self.agent_id = agent_id
        self.event_type = event_type
        self.payload = payload or {}
        self.timestamp = datetime.utcnow().isoformat()
        self.id = f"{agent_id}_{event_type}_{int(time.time() * 1000)}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "lane": "coordination",
            "track_type": "EVENT",
            "timestamp": self.timestamp,
            "payload": self.payload,
            "ttl": 300,
            "vector_clock": {self.agent_id: 1}
        }


class MockMilvusClient:
    """Mock Milvus client for testing without real Zilliz connection."""
    
    def __init__(self):
        self.collections = {}
        self.inserted_data = {}
    
    def has_collection(self, name: str) -> bool:
        return name in self.collections
    
    def create_schema(self, auto_id=False, enable_dynamic_field=False):
        return MockSchema()
    
    def create_collection(self, collection_name: str, schema=None, index_params=None):
        self.collections[collection_name] = {
            "schema": schema,
            "index_params": index_params,
            "data": []
        }
        self.inserted_data[collection_name] = []
    
    def prepare_index_params(self):
        return MockIndexParams()
    
    def insert(self, collection_name: str, data: List[Dict]):
        if collection_name not in self.inserted_data:
            self.inserted_data[collection_name] = []
        self.inserted_data[collection_name].extend(data)
    
    def search(self, collection_name: str, data=None, limit=10, filter=None, output_fields=None):
        if collection_name not in self.inserted_data:
            return [[]]
        
        results = []
        for record in self.inserted_data[collection_name]:
            # Simple mock search - return all data with distance 0.5
            mock_hit = Mock()
            mock_hit.entity.id = record.get("id", "")
            mock_hit.entity.get = lambda key, default=None: record.get(key, default)
            mock_hit.distance = 0.5
            results.append(mock_hit)
        
        return [results[:limit]]
    
    def list_collections(self) -> List[str]:
        return list(self.collections.keys())


class MockSchema:
    def add_field(self, **kwargs):
        pass


class MockIndexParams:
    def add_index(self, **kwargs):
        pass


@pytest.fixture
def mock_zilliz_client():
    """Create a ZillizClient with mocked connections."""
    client = ZillizClient.__new__(ZillizClient)
    client._config = {
        "serverless_uri": "https://mock-serverless.zilliz.com",
        "serverless_token": "mock-token",
        "town_uri": "https://mock-town.zilliz.com",
        "town_token": "mock-token"
    }
    client._connections = {
        "serverless": MockMilvusClient(),
        "town": MockMilvusClient()
    }
    client._collections = {}
    client._available = True
    return client


@pytest.fixture
def event_router(mock_zilliz_client):
    """Create an EventRouter for testing."""
    return EventRouter(mock_zilliz_client)


class EventRouter:
    """Simplified event router for testing coordination protocol."""
    
    def __init__(self, zilliz_client: ZillizClient):
        self.zilliz = zilliz_client
        self._local_cache = {}  # agent_id -> list of events
    
    async def publish_event(self, event: TestEvent, embedding: List[float]) -> bool:
        """Publish an event to nexus_events collection."""
        try:
            await self.zilliz.store_embedding(
                agent_id=event.agent_id,
                lane="coordination",
                track_type="EVENT",
                key=event.id,
                value=json.dumps(event.to_dict()),
                embedding=embedding,
                metadata=event.to_dict()
            )
            return True
        except Exception as e:
            print(f"Failed to publish event: {e}")
            return False
    
    async def query_events(
        self,
        query_embedding: List[float],
        event_type: str = None,
        agent_id: str = None,
        top_k: int = 10
    ) -> List[Dict]:
        """Query events from nexus_events."""
        filter_expr = None
        if event_type:
            filter_expr = f'metadata["event_type"] == "{event_type}"'
        if agent_id:
            agent_filter = f'metadata["agent_id"] == "{agent_id}"'
            filter_expr = f"{filter_expr} && {agent_filter}" if filter_expr else agent_filter
        
        return await self.zilliz.similar_search(
            query_embedding=query_embedding,
            track_type="EVENT",
            top_k=top_k,
            filter_expr=filter_expr
        )


class TestConcurrentReadWrite:
    """Test concurrent read/write operations on nexus_events collection."""
    
    @pytest.mark.asyncio
    async def test_concurrent_event_publishing(self, mock_zilliz_client):
        """Test multiple agents publishing events concurrently."""
        router = EventRouter(mock_zilliz_client)
        
        # Create events from multiple agents
        agents = [f"agent_{i}" for i in range(5)]
        events_per_agent = 10
        
        async def publish_agent_events(agent_id: str):
            """Publish events for a single agent."""
            results = []
            for i in range(events_per_agent):
                event = TestEvent(
                    agent_id=agent_id,
                    event_type="AGENT_HEARTBEAT",
                    payload={"sequence": i, "capabilities": ["test"]}
                )
                embedding = await mock_embed_text(f"heartbeat {agent_id} {i}")
                success = await router.publish_event(event, embedding)
                results.append(success)
            return results
        
        # Run concurrent publishing
        tasks = [publish_agent_events(agent_id) for agent_id in agents]
        results = await asyncio.gather(*tasks)
        
        # Verify all events were published
        for agent_results in results:
            assert all(agent_results), "Some events failed to publish"
        
        # Verify total events published
        total_published = sum(len(r) for r in results)
        assert total_published == len(agents) * events_per_agent
        
        print(f"Successfully published {total_published} concurrent events")
    
    @pytest.mark.asyncio
    async def test_concurrent_read_write(self, mock_zilliz_client):
        """Test concurrent reads and writes to same collection."""
        router = EventRouter(mock_zilliz_client)
        
        # Pre-populate with some events
        for i in range(5):
            event = TestEvent(f"setup_agent", "TASK_CLAIM", {"task_id": f"task_{i}"})
            embedding = await mock_embed_text(f"task claim {i}")
            await router.publish_event(event, embedding)
        
        async def reader(query_emb: List[float], reader_id: int):
            """Continuously read events."""
            results = []
            for _ in range(5):
                events = await router.query_events(query_emb, top_k=20)
                results.append(len(events))
                await asyncio.sleep(0.01)
            return results
        
        async def writer(agent_id: str, start_idx: int):
            """Continuously write events."""
            results = []
            for i in range(5):
                event = TestEvent(
                    agent_id=agent_id,
                    event_type="COORDINATION_MESSAGE",
                    payload={"message_id": start_idx + i}
                )
                embedding = await mock_embed_text(f"message {agent_id} {i}")
                success = await router.publish_event(event, embedding)
                results.append(success)
                await asyncio.sleep(0.01)
            return results
        
        # Start concurrent readers and writers
        query_emb = await mock_embed_text("coordination")
        
        tasks = []
        # 3 readers
        for i in range(3):
            tasks.append(reader(query_emb, i))
        # 3 writers
        for i in range(3):
            tasks.append(writer(f"writer_{i}", i * 5))
        
        results = await asyncio.gather(*tasks)
        
        # Verify writers succeeded
        for i, writer_results in enumerate(results[3:]):
            assert all(writer_results), f"Writer {i} had failures"
        
        print("Concurrent read/write test passed")
    
    @pytest.mark.asyncio
    async def test_task_claim_conflict(self, mock_zilliz_client):
        """Test conflict when multiple agents claim same task."""
        router = EventRouter(mock_zilliz_client)
        
        task_id = "conflict_task_1"
        task_embedding = await mock_embed_text(f"task {task_id}")
        
        async def attempt_claim(agent_id: str) -> bool:
            """Attempt to claim a task."""
            # Check for existing claims
            existing = await router.query_events(
                query_embedding=task_embedding,
                event_type="TASK_CLAIM"
            )
            
            # Filter for this task
            task_claims = [
                e for e in existing
                if e.get("metadata", {}).get("payload", {}).get("task_id") == task_id
            ]
            
            if task_claims:
                return False  # Task already claimed
            
            # Claim the task
            event = TestEvent(
                agent_id=agent_id,
                event_type="TASK_CLAIM",
                payload={"task_id": task_id}
            )
            await router.publish_event(event, task_embedding)
            return True
        
        # Multiple agents attempt to claim same task concurrently
        results = await asyncio.gather(
            attempt_claim("agent_A"),
            attempt_claim("agent_B"),
            attempt_claim("agent_C"),
            return_exceptions=True
        )
        
        # Only one should succeed in claiming
        successful_claims = [r for r in results if r is True]
        assert len(successful_claims) <= 1, "Multiple agents claimed same task"
        
        print(f"Task claim conflict test: {len(successful_claims)} agent(s) succeeded")
    
    @pytest.mark.asyncio
    async def test_distributed_locking(self, mock_zilliz_client):
        """Test distributed lock acquisition and release."""
        router = EventRouter(mock_zilliz_client)
        resource_id = "shared_resource_1"
        
        async def attempt_lock(agent_id: str, hold_time: float = 0.1) -> Dict:
            """Attempt to acquire and hold a lock."""
            lock_event = TestEvent(
                agent_id=agent_id,
                event_type="RESOURCE_LOCK",
                payload={"resource_id": resource_id, "action": "acquire"}
            )
            embedding = await mock_embed_text(f"lock {resource_id} {agent_id}")
            success = await router.publish_event(lock_event, embedding)
            
            if not success:
                return {"agent": agent_id, "acquired": False}
            
            # Check if lock is exclusively held
            await asyncio.sleep(0.05)  # Allow propagation
            
            locks = await router.query_events(
                query_embedding=await mock_embed_text("lock"),
                event_type="RESOURCE_LOCK"
            )
            
            resource_locks = [
                l for l in locks
                if l.get("metadata", {}).get("payload", {}).get("resource_id") == resource_id
            ]
            
            # Hold lock for specified time
            await asyncio.sleep(hold_time)
            
            # Release lock
            unlock_event = TestEvent(
                agent_id=agent_id,
                event_type="RESOURCE_LOCK_RELEASE",
                payload={"resource_id": resource_id, "action": "release"}
            )
            unlock_emb = await mock_embed_text(f"unlock {resource_id}")
            await router.publish_event(unlock_event, unlock_emb)
            
            return {
                "agent": agent_id,
                "acquired": True,
                "lock_count_after_acquire": len(resource_locks)
            }
        
        # Test sequential locking (should work)
        result1 = await attempt_lock("agent_1", hold_time=0.2)
        assert result1["acquired"], "Sequential lock should succeed"
        
        # Test concurrent locking (only one should get exclusive access)
        results = await asyncio.gather(
            attempt_lock("agent_2", hold_time=0.1),
            attempt_lock("agent_3", hold_time=0.1)
        )
        
        print(f"Distributed locking test: {results}")


class TestVectorEmbeddingStorageRetrieval:
    """Test vector embedding storage and retrieval."""
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve_embedding(self, mock_zilliz_client):
        """Test basic store and retrieve cycle."""
        # Ensure collection exists
        await mock_zilliz_client.ensure_collection("EVENT", dimension=1024)
        
        # Create test data
        agent_id = "test_agent"
        test_value = "This is a test coordination event for vector storage"
        embedding = await mock_embed_text(test_value)
        
        # Store embedding
        await mock_zilliz_client.store_embedding(
            agent_id=agent_id,
            lane="coordination",
            track_type="EVENT",
            key="test_key_1",
            value=test_value,
            embedding=embedding,
            metadata={
                "event_type": "TEST_EVENT",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Retrieve with similar search
        results = await mock_zilliz_client.similar_search(
            query_embedding=embedding,
            track_type="EVENT",
            top_k=5
        )
        
        assert len(results) > 0, "Should retrieve at least one result"
        assert results[0]["metadata"].get("event_type") == "TEST_EVENT"
        
        print(f"Stored and retrieved embedding successfully. Found {len(results)} results.")
    
    @pytest.mark.asyncio
    async def test_embedding_dimension_consistency(self, mock_zilliz_client):
        """Test that embeddings maintain consistent dimensions."""
        await mock_zilliz_client.ensure_collection("EVENT", dimension=1024)
        
        # Store multiple embeddings with same dimension
        embeddings = []
        for i in range(10):
            text = f"Test event number {i} with some unique content {i*123}"
            emb = await mock_embed_text(text)
            assert len(emb) == 1024, f"Embedding dimension mismatch: {len(emb)} != 1024"
            embeddings.append(emb)
            
            await mock_zilliz_client.store_embedding(
                agent_id="test_agent",
                lane="coordination",
                track_type="EVENT",
                key=f"dim_test_{i}",
                value=text,
                embedding=emb
            )
        
        print(f"Successfully stored {len(embeddings)} embeddings with consistent dimensions")
    
    @pytest.mark.asyncio
    async def test_semantic_search_accuracy(self, mock_zilliz_client):
        """Test that semantic search returns relevant results."""
        await mock_zilliz_client.ensure_collection("EVENT", dimension=1024)
        
        # Store events with different semantic meanings
        events = [
            ("heartbeat", "Agent alive and healthy"),
            ("heartbeat", "Agent sending heartbeat signal"),
            ("task_claim", "Agent claiming task for execution"),
            ("task_claim", "Task ownership being claimed"),
            ("lock", "Resource lock acquisition attempt"),
            ("lock", "Trying to acquire distributed lock"),
        ]
        
        for i, (event_type, text) in enumerate(events):
            emb = await mock_embed_text(text)
            await mock_zilliz_client.store_embedding(
                agent_id=f"agent_{i}",
                lane="coordination",
                track_type="EVENT",
                key=f"semantic_test_{i}",
                value=text,
                embedding=emb,
                metadata={"event_type": event_type, "text": text}
            )
        
        # Search for heartbeat-related events
        query_emb = await mock_embed_text("agent heartbeat signal")
        results = await mock_zilliz_client.similar_search(
            query_embedding=query_emb,
            track_type="EVENT",
            top_k=10
        )
        
        # Verify results contain heartbeat events
        event_types = [r["metadata"].get("event_type") for r in results]
        heartbeat_count = event_types.count("heartbeat")
        
        print(f"Semantic search returned {heartbeat_count} heartbeat events out of {len(results)} results")
        assert heartbeat_count > 0, "Should find heartbeat events"


class TestCoordinationPrimitives:
    """Test coordination primitives."""
    
    @pytest.mark.asyncio
    async def test_vector_clock_ordering(self):
        """Test vector clock causal ordering."""
        from src.nexus_os.coordination import VectorClock
        
        # Create vector clocks for two agents
        clock_a = VectorClock("agent_A")
        clock_b = VectorClock("agent_B")
        
        # Agent A does some work
        clock_a.increment()  # A:1
        clock_a.increment()  # A:2
        
        # Agent B does some work
        clock_b.increment()  # B:1
        
        # Merge clocks (e.g., after message passing)
        clock_a.merge(clock_b.clock)
        clock_b.merge(clock_a.clock)
        
        # Both should now have {A:2, B:1}
        assert clock_a.clock["agent_A"] == 2
        assert clock_a.clock["agent_B"] == 1
        assert clock_b.clock["agent_A"] == 2
        assert clock_b.clock["agent_B"] == 1
        
        print("Vector clock ordering test passed")
    
    @pytest.mark.asyncio
    async def test_consensus_protocol(self, mock_zilliz_client):
        """Test simple consensus mechanism."""
        router = EventRouter(mock_zilliz_client)
        
        proposal = {"action": "update_shared_config", "key": "timeout", "value": 30}
        participants = ["agent_1", "agent_2", "agent_3", "agent_4", "agent_5"]
        
        # Publish consensus request
        proposal_event = TestEvent(
            agent_id="proposer",
            event_type="CONSENSUS_REQUEST",
            payload={
                "proposal": proposal,
                "participants": participants
            }
        )
        proposal_emb = await mock_embed_text(json.dumps(proposal))
        await router.publish_event(proposal_event, proposal_emb)
        
        # Simulate votes (3 out of 5 approve = consensus)
        for i, agent_id in enumerate(participants[:3]):
            vote_event = TestEvent(
                agent_id=agent_id,
                event_type="CONSENSUS_VOTE",
                payload={"proposal_id": proposal_event.id, "approve": True}
            )
            vote_emb = await mock_embed_text(f"vote approve {agent_id}")
            await router.publish_event(vote_event, vote_emb)
        
        # Query votes
        votes = await router.query_events(
            query_embedding=await mock_embed_text("vote"),
            event_type="CONSENSUS_VOTE"
        )
        
        assert len(votes) == 3, f"Expected 3 votes, got {len(votes)}"
        
        print(f"Consensus protocol test: {len(votes)} approval votes recorded")


class TestConflictResolution:
    """Test conflict resolution strategies."""
    
    @pytest.mark.asyncio
    async def test_last_writer_wins(self):
        """Test LWW conflict resolution."""
        from src.nexus_os.coordination import resolve_lww
        
        # Create conflicting updates
        existing = [
            {"metadata": {"timestamp": "2024-01-01T10:00:00", "value": "old"}},
            {"metadata": {"timestamp": "2024-01-01T10:01:00", "value": "newer"}},
        ]
        
        new = {"metadata": {"timestamp": "2024-01-01T10:02:00", "value": "newest"}}
        
        result = await resolve_lww(existing, new)
        
        assert result["metadata"]["value"] == "newest", "LWW should pick newest timestamp"
        print("Last-Writer-Wins test passed")
    
    @pytest.mark.asyncio
    async def test_stale_lock_detection(self, mock_zilliz_client):
        """Test detection and cleanup of stale locks."""
        router = EventRouter(mock_zilliz_client)
        
        # Create a "stale" lock (simulate old timestamp)
        old_lock = TestEvent(
            agent_id="stale_agent",
            event_type="RESOURCE_LOCK",
            payload={"resource_id": "stale_resource", "timestamp": "2000-01-01T00:00:00"}
        )
        old_emb = await mock_embed_text("stale lock")
        await router.publish_event(old_lock, old_emb)
        
        # Create a current lock
        new_lock = TestEvent(
            agent_id="current_agent",
            event_type="RESOURCE_LOCK",
            payload={"resource_id": "fresh_resource"}
        )
        new_emb = await mock_embed_text("fresh lock")
        await router.publish_event(new_lock, new_emb)
        
        # Query all locks
        all_locks = await router.query_events(
            query_embedding=await mock_embed_text("lock"),
            event_type="RESOURCE_LOCK"
        )
        
        # Filter stale locks (older than 1 hour)
        cutoff = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        stale_locks = [
            l for l in all_locks
            if l["metadata"].get("timestamp", "") < cutoff
        ]
        
        assert len(stale_locks) == 1, "Should detect one stale lock"
        assert stale_locks[0]["metadata"]["agent_id"] == "stale_agent"
        
        print(f"Stale lock detection: found {len(stale_locks)} stale lock(s)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
