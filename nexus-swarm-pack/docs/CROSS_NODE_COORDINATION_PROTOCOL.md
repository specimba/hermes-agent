# Cross-Node Coordination Protocol Design

## Overview

This document specifies the coordination protocol for autonomous multi-agent swarms using shared Zilliz vector memory. The protocol enables distributed agents to coordinate actions, share state, and resolve conflicts through the `nexus_events` collection and supporting infrastructure.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Swarm Network                          │
├─────────────────────────────────────────────────────────────────┤
│  Agent A          Agent B          Agent C          Agent D     │
│    │                │                │                │          │
│    └────────────────┴────────────────┴────────────────┘          │
│                         │                                       │
│                    ┌────▼────┐                                 │
│                    │ Event   │                                 │
│                    │ Router  │                                 │
│                    └────┬────┘                                 │
├─────────────────────────┼───────────────────────────────────────┤
│                         │                                       │
│            ┌────────────▼────────────┐                         │
│            │  Zilliz Shared Memory  │                         │
│            │  (nexus-serverless)    │                         │
│            ├────────────────────────┤                         │
│            │  nexus_events         │  ← Coordination Hub      │
│            │  nexus_failure_pattern│  ← Failure Learning     │
│            └────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

## 1. Coordination Primitives

### 1.1 Event Types (nexus_events collection)

| Event Type | Purpose | TTL | Priority |
|------------|---------|-----|----------|
| `AGENT_HEARTBEAT` | Signal liveness, share capabilities | 60s | LOW |
| `TASK_CLAIM` | Claim ownership of a task | 300s | HIGH |
| `TASK_RELEASE` | Release task ownership | - | HIGH |
| `TASK_COMPLETE` | Signal task completion | 3600s | HIGH |
| `RESOURCE_LOCK` | Acquire distributed lock | 30s | CRITICAL |
| `RESOURCE_LOCK_RELEASE` | Release distributed lock | - | CRITICAL |
| `COORDINATION_MESSAGE` | Cross-agent communication | 600s | MEDIUM |
| `CONFLICT_DETECTED` | Signal coordination conflict | 1800s | HIGH |
| `CONSENSUS_REQUEST` | Request consensus on decision | 300s | HIGH |
| `CONSENSUS_VOTE` | Vote in consensus process | 300s | HIGH |

### 1.2 Event Schema

```python
event_schema = {
    "id": "agent_id_event_type_timestamp",
    "embedding": "<vector representation of event>",
    "metadata": {
        "agent_id": "agent identifier",
        "event_type": "AGENT_HEARTBEAT | TASK_CLAIM | ...",
        "lane": "execution lane (implementation/coordination/tool_usage)",
        "timestamp": "ISO 8601 timestamp",
        "payload": {
            # Event-specific data
        },
        "ttl": "time to live in seconds",
        "priority": "CRITICAL | HIGH | MEDIUM | LOW",
        "correlation_id": "for tracking related events",
        "vector_clock": {"agent_id": counter}  # Causal ordering
    }
}
```

### 1.3 Vector Clock Implementation

```python
class VectorClock:
    """Causal ordering for distributed events."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.clock: Dict[str, int] = {agent_id: 0}
    
    def increment(self):
        """Increment own counter."""
        self.clock[self.agent_id] += 1
    
    def merge(self, other: Dict[str, int]):
        """Merge with another vector clock (takes max)."""
        for agent_id, counter in other.items():
            self.clock[agent_id] = max(self.clock.get(agent_id, 0), counter)
    
    def happens_before(self, other: Dict[str, int]) -> bool:
        """Check if this clock happens before other."""
        for agent_id, counter in self.clock.items():
            if counter > other.get(agent_id, 0):
                return False
        return True
```

## 2. Core Protocol Operations

### 2.1 Agent Discovery & Heartbeats

```python
async def publish_heartbeat(
    zilliz: ZillizClient,
    agent_id: str,
    capabilities: List[str],
    current_load: float
):
    """Publish agent heartbeat to nexus_events."""
    embedding = await embed_text(f"heartbeat {agent_id} {' '.join(capabilities)}")
    
    await zilliz.store_embedding(
        agent_id=agent_id,
        lane="coordination",
        track_type="EVENT",
        key=f"heartbeat_{int(time.time())}",
        value=json.dumps({
            "event_type": "AGENT_HEARTBEAT",
            "capabilities": capabilities,
            "current_load": current_load
        }),
        embedding=embedding,
        metadata={
            "event_type": "AGENT_HEARTBEAT",
            "lane": "coordination",
            "ttl": 60,
            "payload": {
                "capabilities": capabilities,
                "current_load": current_load
            }
        }
    )
```

### 2.2 Distributed Locking

```python
class DistributedLock:
    """Distributed lock using nexus_events collection."""
    
    def __init__(self, zilliz: ZillizClient, resource_id: str, agent_id: str):
        self.zilliz = zilliz
        self.resource_id = resource_id
        self.agent_id = agent_id
        self.lock_token = None
    
    async def acquire(self, timeout: int = 30) -> bool:
        """Attempt to acquire lock on resource."""
        # Check for existing locks
        existing_locks = await self._find_active_locks()
        
        if existing_locks:
            # Lock held by another agent
            return False
        
        # Attempt to acquire lock
        lock_id = f"{self.agent_id}_lock_{self.resource_id}"
        self.lock_token = lock_id
        
        embedding = await embed_text(f"lock {self.resource_id} {self.agent_id}")
        
        await self.zilliz.store_embedding(
            agent_id=self.agent_id,
            lane="coordination",
            track_type="EVENT",
            key=lock_id,
            value=json.dumps({"event_type": "RESOURCE_LOCK", "resource": self.resource_id}),
            embedding=embedding,
            metadata={
                "event_type": "RESOURCE_LOCK",
                "lane": "coordination",
                "ttl": timeout,
                "payload": {
                    "resource_id": self.resource_id,
                    "lock_token": lock_id,
                    "agent_id": self.agent_id
                }
            }
        )
        
        # Verify exclusive acquisition
        await asyncio.sleep(0.1)  # Allow propagation
        verify_locks = await self._find_active_locks()
        
        return len(verify_locks) == 1 and verify_locks[0]["metadata"]["lock_token"] == lock_id
    
    async def release(self):
        """Release the lock."""
        if self.lock_token:
            await self.zilliz.store_embedding(
                agent_id=self.agent_id,
                lane="coordination",
                track_type="EVENT",
                key=f"{self.agent_id}_unlock_{self.resource_id}",
                value=json.dumps({"event_type": "RESOURCE_LOCK_RELEASE"}),
                embedding=await embed_text(f"unlock {self.resource_id}"),
                metadata={
                    "event_type": "RESOURCE_LOCK_RELEASE",
                    "lane": "coordination",
                    "correlation_id": self.lock_token
                }
            )
            self.lock_token = None
```

### 2.3 Task Coordination

```python
async def claim_task(
    zilliz: ZillizClient,
    agent_id: str,
    task_id: str,
    task_embedding: List[float]
) -> bool:
    """Claim ownership of a task."""
    # Check for existing claims
    existing = await zilliz.similar_search(
        query_embedding=task_embedding,
        track_type="EVENT",
        filter_expr=f'metadata["event_type"] == "TASK_CLAIM" && metadata["payload"]["task_id"] == "{task_id}"',
        top_k=10
    )
    
    if existing:
        return False  # Task already claimed
    
    # Claim the task
    await zilliz.store_embedding(
        agent_id=agent_id,
        lane="coordination",
        track_type="EVENT",
        key=f"claim_{task_id}",
        value=json.dumps({"event_type": "TASK_CLAIM", "task_id": task_id}),
        embedding=task_embedding,
        metadata={
            "event_type": "TASK_CLAIM",
            "lane": "coordination",
            "payload": {"task_id": task_id, "agent_id": agent_id},
            "ttl": 300
        }
    )
    
    return True
```

## 3. Conflict Resolution Strategies

### 3.1 Last-Writer-Wins (LWW)

For non-critical state updates where eventual consistency is acceptable.

```python
async def resolve_lww(existing: List[Dict], new: Dict) -> Dict:
    """Last-Writer-Wins resolution."""
    all_records = existing + [new]
    return max(all_records, key=lambda x: x["metadata"]["timestamp"])
```

### 3.2 Vector Clock Ordering

For causal consistency requirements.

```python
async def resolve_causal(events: List[Dict]) -> List[Dict]:
    """Order events using vector clocks."""
    # Sort by vector clock ordering
    events.sort(key=lambda x: json.dumps(x["metadata"].get("vector_clock", {})))
    return events
```

### 3.3 Consensus-Based Resolution

For critical decisions requiring majority agreement.

```python
class ConsensusProtocol:
    """Simple consensus for conflict resolution."""
    
    async def request_consensus(
        self,
        zilliz: ZillizClient,
        proposal: Dict,
        participants: List[str],
        timeout: int = 60
    ) -> bool:
        """Request consensus on a proposal."""
        proposal_id = f"consensus_{int(time.time())}"
        
        # Publish consensus request
        await zilliz.store_embedding(
            agent_id=self.agent_id,
            lane="coordination",
            track_type="EVENT",
            key=proposal_id,
            value=json.dumps({"event_type": "CONSENSUS_REQUEST", "proposal": proposal}),
            embedding=await embed_text(json.dumps(proposal)),
            metadata={
                "event_type": "CONSENSUS_REQUEST",
                "payload": {"proposal": proposal, "participants": participants},
                "ttl": timeout
            }
        )
        
        # Wait for votes
        await asyncio.sleep(timeout)
        
        # Tally votes
        votes = await zilliz.similar_search(
            query_embedding=await embed_text("consensus vote"),
            track_type="EVENT",
            filter_expr=f'metadata["correlation_id"] == "{proposal_id}"',
            top_k=len(participants)
        )
        
        approvals = sum(1 for v in votes if v["metadata"]["payload"].get("approve", False))
        return approvals > len(participants) / 2
```

### 3.4 Conflict Detection & Resolution Matrix

| Conflict Type | Detection Method | Resolution Strategy | Example |
|---------------|-----------------|-------------------|---------|
| Simultaneous Task Claim | Query TASK_CLAIM events | First-to-claim wins | Two agents claim same task |
| Stale Lock | Check TTL on RESOURCE_LOCK | Lock expiry + reclaim | Agent crashes with held lock |
| Divergent State | Vector clock comparison | Causal ordering | Agents update shared state |
| Policy Violation | KAIJU gate evaluation | VAP audit + rollback | Unauthorized action attempted |
| Resource Exhaustion | TokenGuard budget check | Priority preemption | Low-priority task yields |

## 4. Concurrency Control

### 4.1 Optimistic Concurrency

```python
async def optimistic_update(
    zilliz: ZillizClient,
    agent_id: str,
    record_id: str,
    update_fn: callable,
    max_retries: int = 3
) -> bool:
    """Optimistic concurrency control pattern."""
    
    for attempt in range(max_retries):
        # Read current state
        current = await zilliz.similar_search(
            query_embedding=await embed_text(record_id),
            track_type="EVENT",
            filter_expr=f'id == "{record_id}"',
            top_k=1
        )
        
        if not current:
            return False
        
        # Apply update
        updated = update_fn(current[0])
        
        # Attempt atomic write (check vector clock)
        existing_clock = current[0]["metadata"].get("vector_clock", {})
        new_clock = updated["metadata"].get("vector_clock", {})
        
        # In production, use Zilliz's conditional update
        # For now, use vector clock comparison
        
        return True
    
    return False
```

### 4.2 Event Sourcing Pattern

All state changes are appended as events. Current state is derived by replaying events in vector clock order.

```python
async def reconstruct_state(
    zilliz: ZillizClient,
    aggregate_id: str
) -> Dict:
    """Reconstruct state from event stream."""
    events = await zilliz.similar_search(
        query_embedding=await embed_text(aggregate_id),
        track_type="EVENT",
        filter_expr=f'metadata["payload"]["aggregate_id"] == "{aggregate_id}"',
        top_k=1000
    )
    
    # Sort by vector clock for causal ordering
    events = resolve_causal(events)
    
    # Fold events into state
    state = {}
    for event in events:
        state = apply_event(state, event)
    
    return state
```

## 5. Integration with Existing Infrastructure

### 5.1 KAIJU Governor Integration

All coordination events pass through KAIJU gate evaluation:

```python
# Before publishing coordination event
if not kaiju.evaluate_coordination_event(event, agent_trust):
    await zilliz.store_embedding(
        agent_id=agent_id,
        lane="coordination",
        track_type="FAILURE_PATTERN",
        key=f"policy_violation_{int(time.time())}",
        value=json.dumps(event),
        embedding=await embed_text("policy violation"),
        metadata={"event_type": "POLICY_VIOLATION", "original_event": event}
    )
    raise CoordinationError("Event blocked by KAIJU governor")
```

### 5.2 VAP Chain Integration

All coordination actions are logged to VAP chain for audit:

```python
await vap_chain.append(
    event_type="coordination_action",
    agent_id=agent_id,
    payload={"action": "task_claim", "task_id": task_id},
    timestamp=datetime.utcnow().isoformat()
)
```

### 5.3 TokenGuard Integration

Coordination operations consume tokens from agent's budget:

```python
if not token_guard.check_budget(agent_id, "coordination", estimated_tokens=100):
    raise ResourceExhaustionError("Insufficient token budget for coordination")
```

## 6. Failure Handling

### 6.1 Stale Event Cleanup

```python
async def cleanup_stale_events(zilliz: ZillizClient, older_than: int = 3600):
    """Remove events past their TTL."""
    # In production, use Zilliz TTL feature
    # For now, query and delete expired events
    pass
```

### 6.2 Dead Agent Detection

```python
async def detect_dead_agents(zilliz: ZillizClient, timeout: int = 120) -> List[str]:
    """Detect agents with no recent heartbeat."""
    cutoff = (datetime.utcnow() - timedelta(seconds=timeout)).isoformat()
    
    heartbeats = await zilliz.similar_search(
        query_embedding=await embed_text("heartbeat"),
        track_type="EVENT",
        filter_expr=f'metadata["event_type"] == "AGENT_HEARTBEAT" && metadata["created_at"] < "{cutoff}"',
        top_k=100
    )
    
    # Group by agent and find stale ones
    agent_last_seen = {}
    for hb in heartbeats:
        agent_id = hb["metadata"]["agent_id"]
        timestamp = hb["metadata"]["created_at"]
        if agent_id not in agent_last_seen or timestamp > agent_last_seen[agent_id]:
            agent_last_seen[agent_id] = timestamp
    
    return [agent_id for agent_id, last_seen in agent_last_seen.items()
            if (datetime.utcnow() - datetime.fromisoformat(last_seen)).seconds > timeout]
```

## 7. Monitoring & Observability

### 7.1 Coordination Metrics

| Metric | Description | Collection Method |
|--------|-------------|-------------------|
| `coordination_events_per_second` | Rate of coordination events | Count EVENT-type inserts |
| `lock_contention_rate` | How often lock acquisition fails | Failed acquire / total acquire |
| `consensus_latency` | Time to reach consensus | Timestamp diff: request → majority |
| `conflict_resolution_time` | Time to resolve conflicts | Detection → resolution event |
| `agent_liveness` | Active agent count | Unique agents with recent heartbeat |

### 7.2 Dashboard Queries

```python
# Active agents in last 60 seconds
await zilliz.similar_search(
    query_embedding=await embed_text("heartbeat"),
    track_type="EVENT",
    filter_expr=f'metadata["event_type"] == "AGENT_HEARTBEAT" && metadata["created_at"] > "{cutoff}"',
    top_k=100
)
```
