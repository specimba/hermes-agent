# NEXUS-OS: Unified Agent Platform — Architecture Proposal

## Repo Analysis

### What Each Repo Does

| Repo | Role | Language | Key Features |
|------|------|----------|--------------|
| **hermes-agent** | Full AI agent system with CLI + multi-platform gateway | Python | Tool registry, MCP client, 30+ tools, session DB, skin engine, RL training, multi-platform gateway (Telegram/Discord/Slack/WhatsApp/Signal), prompt caching, context compression, ~3000 tests |
| **agent-framework** | Microsoft's multi-agent workflow framework (fork) | Python + .NET | Graph-based DAG workflows, streaming, checkpointing, human-in-the-loop, time-travel, DevUI, OpenTelemetry observability, multi-provider LLM support |
| **claw-code-parity** | Clean-room Python rewrite of Claude Code's harness patterns | Python + Rust | Tool/command registries, permission system, session store, runtime routing, query engine, execution registry, context management, parity auditing |
| **awesome-free-llm-apiss** | Structured catalog of free LLM API providers | JSON + JS | `data.json` with provider metadata (base URLs, models, rate limits, context windows), script to generate README |
| **free-llm-api-resources** | Auto-fetcher for free LLM model availability | Python | Scripts that query live APIs (Groq, OpenRouter, Google, HuggingFace, etc.) to build an up-to-date provider catalog |
| **free-for-dev** | Curated list of free dev infrastructure services | Markdown | 1600+ contributors, covers hosting, CI/CD, databases, monitoring, DNS, email, storage, etc. ⚠️ Does NOT accept AI contributions |
| **clawcode** | Claude Code source snapshot (research reference) | TypeScript | Original TypeScript harness code from Anthropic (read-only research reference) — could not clone (403) |

---

## Connection Map

```
                    ┌─────────────────────────────────────────────────┐
                    │           AGENT EXECUTION LAYER                 │
                    │                                                 │
  hermes-agent ─────┤  Tool registry, CLI, gateway, agent loop,      │
                    │  MCP client, session management, RL training    │
                    │                                                 │
  claw-code-parity ─┤  Harness patterns, permission system,          │
                    │  command routing, execution registry            │
                    │                                                 │
  agent-framework ──┤  Graph-based workflow orchestration,            │
                    │  checkpointing, human-in-the-loop, DevUI       │
                    └────────────────────┬────────────────────────────┘
                                         │
                                         │ needs providers
                                         ▼
                    ┌─────────────────────────────────────────────────┐
                    │           PROVIDER INTELLIGENCE LAYER           │
                    │                                                 │
  awesome-free-     │  Static catalog: base URLs, rate limits,        │
  llm-apiss ────────┤  context windows, pricing tiers                 │
                    │                                                 │
  free-llm-api-     │  Dynamic fetcher: live model availability,      │
  resources ────────┤  auto-updated provider data                     │
                    │                                                 │
  free-for-dev ─────┤  Infrastructure catalog: hosting, CI/CD,        │
                    │  databases, monitoring for deployment           │
                    └─────────────────────────────────────────────────┘
```

### Specific Overlaps & Synergies

1. **hermes-agent ↔ claw-code-parity**: Both implement tool registries (`tools/registry.py` vs `src/tools.py`), command dispatchers, session stores, permission systems, and MCP clients. Hermes is the more complete runtime; claw-code-parity has cleaner harness abstractions (permission contexts, execution registries, parity auditing).

2. **hermes-agent ↔ agent-framework**: Hermes has a simple sequential agent loop; agent-framework has sophisticated graph-based DAG workflows with checkpointing and time-travel. Combining them = hermes tools + agent-framework orchestration.

3. **hermes-agent ↔ awesome-free-llm-apiss + free-llm-api-resources**: Hermes already uses OpenRouter, and has `agent/models_dev.py` for model metadata. The two free-LLM repos provide the comprehensive provider catalog that could power smart auto-routing (cheapest provider, fastest provider, within rate limits).

4. **claw-code-parity ↔ clawcode**: Parity repo is the Python rewrite of the TypeScript snapshot. The Rust port in `rust/` adds a compiled runtime option.

5. **free-for-dev ↔ deployment**: The infrastructure catalog informs where NEXUS-OS itself can be deployed for free.

---

## Proposed Unified Project: **NEXUS-OS**

### Vision
A single platform that combines multi-agent orchestration, a rich tool ecosystem, smart LLM provider routing, and multi-platform delivery — all powered by a curated knowledge base of free resources.

### Architecture

```
nexus-os/
├── core/                          # Agent runtime (from hermes-agent)
│   ├── agent.py                   # AIAgent class — core conversation loop
│   ├── tool_registry.py           # Unified tool registry (hermes + claw-code patterns)
│   ├── command_registry.py        # Slash command system
│   ├── permission_engine.py       # Permission system (from claw-code-parity)
│   ├── session_store.py           # SQLite session persistence
│   ├── context_manager.py         # Context compression + prompt caching
│   └── execution_registry.py      # Execution dispatch (from claw-code-parity)
│
├── orchestration/                 # Multi-agent workflows (from agent-framework)
│   ├── workflow_engine.py         # Graph-based DAG orchestration
│   ├── checkpoint.py              # State checkpointing + time-travel
│   ├── human_in_loop.py           # Human-in-the-loop hooks
│   └── streaming.py               # Streaming execution
│
├── providers/                     # LLM provider intelligence
│   ├── catalog.py                 # Static provider catalog (from awesome-free-llm-apiss)
│   ├── fetcher.py                 # Live model availability (from free-llm-api-resources)
│   ├── router.py                  # Smart routing (cost, speed, availability)
│   ├── rate_limiter.py            # Per-provider rate limit tracking
│   └── data/
│       ├── providers.json         # Merged provider data
│       └── infrastructure.json    # Free infra catalog (curated from free-for-dev)
│
├── tools/                         # Tool implementations (from hermes-agent)
│   ├── terminal_tool.py
│   ├── file_tools.py
│   ├── web_tools.py
│   ├── browser_tool.py
│   ├── mcp_tool.py
│   ├── delegate_tool.py
│   ├── code_execution_tool.py
│   └── ...
│
├── gateway/                       # Multi-platform delivery (from hermes-agent)
│   ├── platforms/
│   │   ├── telegram.py
│   │   ├── discord.py
│   │   ├── slack.py
│   │   ├── whatsapp.py
│   │   └── signal.py
│   └── session.py
│
├── cli/                           # Interactive CLI (from hermes-agent)
│   ├── main.py
│   ├── commands.py
│   ├── skin_engine.py
│   └── setup.py
│
├── dashboard/                     # Web UI (from hermes-agent orchestrator)
│   └── server.py
│
├── harness/                       # Harness engineering (from claw-code-parity)
│   ├── parity_audit.py            # Parity tracking
│   ├── bootstrap_graph.py
│   └── port_manifest.py
│
├── scripts/                       # Automation
│   ├── update_providers.py        # Refresh provider catalog from live APIs
│   └── generate_docs.py
│
├── tests/
├── docs/
├── pyproject.toml
└── README.md
```

### Key Integrations

| From Repo | What Gets Unified | How |
|-----------|-------------------|-----|
| hermes-agent | Agent loop, 30+ tools, CLI, gateway, session DB, skin engine | Becomes `core/`, `tools/`, `cli/`, `gateway/` |
| agent-framework | Graph workflows, checkpointing, DevUI patterns | Becomes `orchestration/` — replaces hermes's simple sequential loop for complex tasks |
| claw-code-parity | Permission engine, execution registry, parity auditing, harness patterns | Merges into `core/permission_engine.py`, `core/execution_registry.py`, `harness/` |
| awesome-free-llm-apiss | `data.json` provider catalog | Becomes `providers/data/providers.json` — the static truth source |
| free-llm-api-resources | `pull_available_models.py` live fetcher | Becomes `providers/fetcher.py` + `scripts/update_providers.py` |
| free-for-dev | Infrastructure knowledge | Curated subset → `providers/data/infrastructure.json` (reference only, respecting no-AI-edit policy) |
| clawcode | TypeScript reference patterns | Architecture patterns already captured in claw-code-parity's Python rewrite |

### Smart Provider Routing (New Capability)

The killer feature of combining these repos: **automatic LLM provider selection**.

```python
from nexus_os.providers import ProviderRouter

router = ProviderRouter()

# Find the best free provider for a task
provider = router.select(
    task_type="code_generation",
    min_context=128_000,
    prefer="speed",           # or "cost", "quality"
    fallback_chain=True,      # auto-failover if rate-limited
)
# Returns: Provider(name="Cerebras", model="llama3.1-8b", base_url="https://api.cerebras.ai/v1", ...)
```

This combines:
- Static data from `awesome-free-llm-apiss` (rate limits, context windows)
- Live availability from `free-llm-api-resources` (which models are actually up)
- Runtime rate limit tracking (how much quota you've used)
