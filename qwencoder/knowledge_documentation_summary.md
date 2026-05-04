# Knowledge Documentation Summary

## Created Notes (7 unique)

| # | Note Name | Note ID | Repos Covered | Trigger Scope |
|---|-----------|---------|---------------|---------------|
| 1 | **NEXUS OS Ecosystem — Architecture & Development Guide** | `note-3252ba55` | nexusalpha, nexusdashboards, nexux-os-Chimera, DoppelGround | NEXUS OS governance, trust scoring, GMR, VAP, token management |
| 2 | **Hermes Agent — Architecture & Development Guide** | `note-2e9262c3` | hermes-agent | Multi-agent orchestration, CLI, gateway, tool registry, skin engine |
| 3 | **Claw Code Parity — Rust Port Development Guide** | `note-83cf29f7` | claw-code-parity | Rust port of Claude Code, parity analysis, CLI agent runtime |
| 4 | **Microsoft Agent Framework — Development Guide** | `note-f45c1198` | agent-framework | Graph-based agent workflows, Python/.NET, DevUI |
| 5 | **ML Intern — Autonomous ML Engineer Agent Guide** | `note-4551c683` | ml-intern | Autonomous ML agent, HF ecosystem, litellm workflows |
| 6 | **ISC-Bench — LLM Safety Evaluation Benchmark Guide** | `note-590df1b4` | ISC-Bench | Internal Safety Collapse eval, TVD framework, safety scoring |
| 7 | **specimba Organization — Repository Map & Cross-Repo Relationships** | `note-38e900ef` | All 10 repos | Starting any specimba task, cross-repo context |

## Coverage Per Repository

| Repository | Status | Covered By Note(s) |
|------------|--------|---------------------|
| specimba/nexusalpha | Active (674+ tests) | Notes #1, #7 |
| specimba/nexusdashboards | Active (9/9 tests) | Notes #1, #7 |
| specimba/nexux-os-Chimera | Early stage | Notes #1, #7 |
| specimba/DoppelGround | Empty repo | Notes #1, #7 |
| specimba/hermes-agent | Active (~3000 tests) | Notes #2, #7 |
| specimba/claw-code-parity | Active (Rust) | Notes #3, #7 |
| specimba/agent-framework | Fork (Python/.NET) | Notes #4, #7 |
| specimba/ml-intern | Active (Python) | Notes #5, #7 |
| specimba/ISC-Bench | Active (Python) | Notes #6, #7 |
| specimba/clawcode | No access (403) | Note #7 (listed as restricted) |

## What Each Note Contains

### Note 1: NEXUS OS Ecosystem
- Complete module map (Bridge, Engine, Governor, Vault, GMR, Swarm, Monitor, Skillsmith, StressLab, Relay, Config, Observability)
- System boundaries (Nexus OS, DoppelGround, TWAVE, GeniusTurtle, Model Arena)
- Setup & installation for nexusalpha and nexusdashboards
- Test commands (pytest suite, diagnostic scripts, NEXUS-TEST.py)
- Trust Scoring v2.1 lane parameters
- GMR Engine tier system and model stack
- TokenGuard budget enforcement
- GSPP proposal protocol
- VAP proof chain architecture
- Git rules and commit format
- Quick start code examples

### Note 2: Hermes Agent
- Full project structure with file dependency chain
- AIAgent core loop (run_conversation) architecture
- Setup with uv and configuration
- Testing commands (~3000 tests)
- 3-file pattern for adding tools
- Slash command registration system
- Configuration system (config.yaml + .env)
- Skin/theme engine
- Critical policies (prompt caching, working directory, known pitfalls)
- Gateway notification system

### Note 3: Claw Code Parity
- Repository shape (Rust workspace + Python src)
- Verification commands (cargo fmt/clippy/test)
- Parity status vs upstream TypeScript (6 major gaps)
- Implemented Rust tools list
- Critical bug fixes
- Working agreement

### Note 4: Microsoft Agent Framework
- Python and .NET installation
- Full project structure (packages, providers, schemas)
- Key features (graph workflows, AF Labs, DevUI, middleware)
- Documentation links (Microsoft Learn)
- Migration guides (from Semantic Kernel, from AutoGen)

### Note 5: ML Intern
- Setup with uv sync
- Usage modes (interactive, headless, custom model)
- Architecture diagram (submission loop, agentic loop, ToolRouter, Doom Loop Detector)
- Core loop flow
- Project structure
- Dependencies
- Event system
- Tool and MCP server addition

### Note 6: ISC-Bench
- ISC concept explanation
- Prerequisites and setup
- 4-step pipeline (build, run, extract, judge) with commands
- Harmfulness scoring scale (1-5)
- Project structure
- Contributing workflow
- ICL mode explanation
- Impact statistics

### Note 7: Organization Overview
- ASCII ecosystem diagram showing all repo relationships
- Quick reference table (language, purpose, test command)
- Python version requirements per repo
- Package manager mapping
- Common git rules
- API keys commonly needed
- Key ports
- Cross-repo relationship explanations

## Duplicates To Delete

4 duplicate notes were created due to permission approval retries. Please delete these from https://app.devin.ai/settings/knowledge:
- `note-7a9cc7bb5e1e4335afc0c19aee43688b` — NEXUS OS duplicate #2
- `note-b58847ab35404f59a7c0fe74e41f7189` — NEXUS OS duplicate #3
- `note-27fceb76d07f41be84c4e08cd45ccd29` — ISC-Bench duplicate
- `note-0c5c8dffc4404552863ef070fff89b25` — ML Intern duplicate

## Access Notes
- `specimba/clawcode`: Returns 403 (Forbidden) — no documentation could be extracted
- `specimba/DoppelGround`: Empty repository — documented as placeholder in ecosystem note
