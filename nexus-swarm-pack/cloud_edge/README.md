# NEXUS Cloud Edge Integration

Hybrid cloud/local memory layer connecting NEXUS Kernel to:
- **Zilliz Dual-Cluster**: Asymmetric vector memory (HOT/COLD)
- **Supabase**: Relational state mirror for dashboards
- **Zo Computer**: Remote execution bridge (coming soon)

## Architecture

```
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
```

## Quick Start

### 1. Install Dependencies

```bash
pip install pymilvus supabase
```

### 2. Configure Environment

Create `.env` file in `nexus-swarm-pack/`:

```bash
# Zilliz HOT (nexus-serverless)
ZILLIZ_HOT_URI=https://in05-2a4b7e6226ae27e.serverless.aws-eu-central-1.cloud.zilliz.com
ZILLIZ_HOT_TOKEN=your_user:your_password

# Zilliz COLD (nexus-os-town)
ZILLIZ_COLD_URI=https://in03-db7a5bcd01da539.serverless.aws-eu-central-1.cloud.zilliz.com
ZILLIZ_COLD_TOKEN=your_user:your_password

# Supabase (nexus-gspp)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
```

### 3. Test Connection

```bash
cd nexus-swarm-pack
python cloud_edge/manager.py
```

Expected output:
```
🌩️  Testing NEXUS Cloud Edge Integration...
✅ Connected to Zilliz HOT (nexus-serverless)
✅ Connected to Zilliz COLD (nexus-os-town)
✅ Connected to Supabase (nexus-gspp)
✅ Cloud Edge initialized successfully
```

## Usage

### Python API

```python
from cloud_edge import CloudEdgeManager

# Initialize
manager = CloudEdgeManager()
manager.initialize()

# Store an event (HOT cluster - high throughput)
embedding = [0.1] * 768  # Your embedding vector
metadata = {
    "agent_id": "agent-123",
    "action": "code.execute",
    "outcome": "success"
}
manager.record_event("evt_001", embedding, metadata)

# Store governance decision (COLD cluster + Supabase mirror)
gov_metadata = {
    "agent_id": "agent-123",
    "action": "vault.store_track",
    "decision": "allow",
    "reason": "trust_score > 0.8"
}
manager.record_governance("gov_001", embedding, gov_metadata)
```

### Integration with KAIJU Governor

The Cloud Edge Manager automatically syncs governance decisions to both Zilliz (for semantic search) and Supabase (for SQL queries from dashboards).

```python
# In nexus_kernel/kaiju.py
from cloud_edge import CloudEdgeManager

cloud = CloudEdgeManager()
cloud.initialize()

def propose_action(agent_id, action, context):
    decision = make_decision(agent_id, action, context)
    
    # Record to cloud edge
    if cloud.is_ready():
        embedding = generate_embedding(f"{agent_id}:{action}:{decision}")
        cloud.record_governance(
            f"gov_{agent_id}_{action}",
            embedding,
            {
                "agent_id": agent_id,
                "action": action,
                "decision": decision.decision,
                "reason": decision.reason
            }
        )
    
    return decision
```

## Memory Tracks

### HOT Cluster (nexus-serverless)
High-throughput, serverless scaling for volatile data:
- **EVENT Track**: Agent execution logs, A2A message streams
- **FAILURE_PATTERN Track**: Error signatures, retry patterns

### COLD Cluster (nexus-os-town)
Steady-state, free tier for permanent governance:
- **TRUST Track**: Bayesian reputation scores per lane
- **GOVERNANCE Track**: KAIJU policy decisions, audit logs
- **CAPABILITY Track**: Agent skill registry, model mappings

### Supabase Mirror
Relational tables for dashboard queries:
- `trust_scores`: agent_id, lane, score, updated_at
- `governance_log`: id, agent_id, action, decision, logged_at

## Zo Computer Integration (Coming Soon)

Remote execution bridge for offloading non-GPU tasks:

```python
# Future API
from cloud_edge import ZoBridge

zo = ZoBridge(api_key="your_zo_key")
result = await zo.execute_remote({
    "task": "code_analysis",
    "code": "...",
    "callback": "http://localhost:7352/task/complete"
})
```

## Troubleshooting

### Connection Errors
- Verify tokens are in `user:password` format for Zilliz
- Check firewall allows outbound HTTPS to AWS EU-CENTRAL-1
- Ensure Supabase project is active and key has correct permissions

### Missing Collections
Collections are auto-created on first use. If manual creation needed:
```python
from cloud_edge.manager import ZillizDualCluster, get_cloud_config

config = get_cloud_config()
zilliz = ZillizDualCluster(config["zilliz_hot"], config["zilliz_cold"])
zilliz.connect()
col = zilliz.get_collection("event_track", purpose="hot")
```

## Security Notes

- **Local-First**: All KAIJU gates run locally before cloud sync
- **Privacy**: Only decision metadata cached, no raw prompts
- **Encryption**: Zilliz uses TLS; Supabase encrypts at rest
- **Audit Trail**: Cloud writes logged to local VAP chain first
