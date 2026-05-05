# 🌉 Zilliz Cloud Integration Guide

## Overview

NEXUS OS now supports **hybrid vector memory** using Zilliz Cloud (Milvus-compatible) for semantic recall alongside local SQLite storage.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NEXUS Memory Layer                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌────────────────────┐        │
│  │  Local SQLite    │────────▶│  Zilliz Cloud      │        │
│  │  (Primary)       │  async  │  (Semantic Mirror) │        │
│  │  - Fast reads    │  sync   │  - Vector search   │        │
│  │  - Governance    │         │  - Similarity      │        │
│  └──────────────────┘         └────────────────────┘        │
│                                                              │
│  Dual-Cluster Strategy:                                      │
│  • nexus-serverless → EVENT & FAILURE_PATTERN (hot data)    │
│  • nexus-os-town    → TRUST & GOVERNANCE (cold data)        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

Add these to your `.env` file or system environment:

```bash
# Zilliz nexus-serverless cluster (EVENT, FAILURE_PATTERN)
ZILLIZ_SERVERLESS_URI=https://in05-2a4b7e6226ae27e.serverless.aws-eu-central-1.cloud.zilliz.com
ZILLIZ_SERVERLESS_TOKEN=<your_token_here>

# Zilliz nexus-os-town cluster (TRUST, GOVERNANCE, CAPABILITY)
ZILLIZ_TOWN_URI=https://in03-db7a5bcd01da539.serverless.aws-eu-central-1.cloud.zilliz.com
ZILLIZ_TOWN_TOKEN=<your_token_here>
```

### ⚠️ Security Warning

**DO NOT** commit tokens to version control. The archived experiment file `.nexus_pi/archive/...` contained hardcoded tokens - this new integration reads **ONLY** from environment variables.

If you used the old experiment, **rotate your Zilliz tokens immediately**:
1. Go to [Zilliz Cloud Console](https://cloud.zilliz.com/)
2. Navigate to each cluster
3. Generate new API tokens
4. Update your environment variables

## Installation

### Install pymilvus

```bash
pip install pymilvus
```

### Verify Installation

```bash
cd nexus-swarm-pack
python -c "from src.nexus_os.vault.zilliz_client import ZillizClient; print('✓ Zilliz ready')"
```

## Usage

### Basic Example

```python
import asyncio
from src.nexus_os.vault.zilliz_client import ZillizClient

async def main():
    # Initialize client
    zilliz = ZillizClient()
    
    if not zilliz.is_available():
        print("Zilliz not configured, using local-only mode")
        return
    
    # Store an embedding
    await zilliz.store_embedding(
        agent_id="agent_123",
        lane="code_generation",
        track_type="FAILURE_PATTERN",
        key="syntax_error_001",
        value="Agent attempted invalid Python syntax",
        embedding=[0.1, 0.2, 0.3, ...]  # 1024-dim vector
    )
    
    # Search for similar failures
    results = await zilliz.similar_search(
        query_embedding=[0.15, 0.25, 0.35, ...],
        track_type="FAILURE_PATTERN",
        top_k=5
    )
    
    for result in results:
        print(f"Similar failure: {result['metadata']['value']}")
        print(f"Distance: {result['distance']}")

asyncio.run(main())
```

### Integration with VaultManager

The Zilliz client is designed to work alongside `VaultManager`:

```python
from vault.manager import VaultManager
from src.nexus_os.vault.zilliz_client import ZillizClient

class HybridVault:
    def __init__(self):
        self.local = VaultManager()
        self.vector = ZillizClient()
    
    async def store_track(self, agent_id, lane, track_type, key, value):
        # Store in local SQLite (primary)
        await self.local.store_track(agent_id, lane, track_type, key, value)
        
        # Async mirror to Zilliz (if available)
        if self.vector.is_available():
            embedding = await self.generate_embedding(value)
            await self.vector.store_embedding(
                agent_id, lane, track_type, key, value, embedding
            )
    
    async def semantic_search(self, query, track_type=None, top_k=5):
        # Use Zilliz for semantic search
        if self.vector.is_available():
            query_embedding = await self.generate_embedding(query)
            return await self.vector.similar_search(
                query_embedding, track_type, top_k
            )
        
        # Fallback to keyword search in SQLite
        return await self.local.keyword_search(query, track_type, top_k)
```

## Track Type Routing

| Track Type | Cluster | Purpose | Velocity |
|------------|---------|---------|----------|
| **EVENT** | nexus-serverless | Live agent events, A2A streams | High |
| **FAILURE_PATTERN** | nexus-serverless | Agent mistakes, recovery patterns | High |
| **TRUST** | nexus-os-town | Agent reputation scores | Medium |
| **GOVERNANCE** | nexus-os-town | KAIJU policies, rules | Low |
| **CAPABILITY** | nexus-os-town | Agent skill registry | Low |

## Health Check

Run the health check to verify connectivity:

```python
import asyncio
from src.nexus_os.vault.zilliz_client import ZillizClient

async def check_health():
    zilliz = ZillizClient()
    status = await zilliz.health_check()
    
    print(f"Zilliz Available: {status['available']}")
    for cluster, info in status['clusters'].items():
        print(f"  {cluster}: {info['status']} ({info.get('collections', 0)} collections)")

asyncio.run(check_health())
```

Expected output:
```
Zilliz Available: True
  serverless: healthy (3 collections)
  town: healthy (5 collections)
```

## Testing

Run the test suite:

```bash
cd nexus-swarm-pack
python -m pytest tests/vault/test_zilliz_client.py -v
```

Tests cover:
- ✓ Configuration loading from environment
- ✓ Graceful degradation when unavailable
- ✓ Dual-cluster initialization
- ✓ Track type routing logic
- ✓ Health check functionality

## Troubleshooting

### "pymilvus not installed"
```bash
pip install pymilvus
```

### "Failed to connect to nexus-serverless"
1. Verify URI is correct (check Zilliz console)
2. Verify token is valid and not expired
3. Check network connectivity to AWS EU-CENTRAL
4. Ensure no firewall blocking outbound HTTPS

### "No collections created"
Collections are created on-demand when first storing embeddings. Run a `store_embedding()` call to trigger creation.

### Performance Issues
- Use smaller embedding dimensions (384 or 768 instead of 1024) if latency is high
- Batch insert multiple embeddings at once
- Use `top_k` parameter to limit search results

## Migration from Old Experiment

If you used the archived `test_zilliz_connection.py`:

1. **Delete the old file**: `rm .nexus_pi/archive/nexus-town/test_zilliz_connection.py`
2. **Rotate your tokens** (security best practice)
3. **Update configuration** to use environment variables
4. **Test with new client**: `python -c "from src.nexus_os.vault.zilliz_client import ZillizClient"`

## Next Steps

1. **Configure environment variables** with your Zilliz credentials
2. **Install pymilvus**: `pip install pymilvus`
3. **Run health check** to verify connectivity
4. **Integrate with VaultManager** for automatic mirroring
5. **Enable semantic search** in your agent workflows

## References

- [Zilliz Cloud Docs](https://docs.zilliz.com/)
- [Milvus Python SDK](https://milvus.io/docs/install-pymilvus.md)
- [NEXUS OS Architecture](../ARCHITECTURE.md)
- [Cloudflare Integration](./CLOUDFLARE_INTEGRATION.md)

---

*Document Version: v1.0*  
*Last Updated: May 2026*  
*NEXUS OS Team*
