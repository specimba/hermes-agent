# Rig Initialization Template

Use this template to initialize a new Rig in a Gastown Town. Copy this template and replace all `<placeholder>` values with actual values.

## Rig Identity

```yaml
# rig-config.yaml - Main Rig Configuration
rig:
  id: <rig-id-uuid>  # e.g., 32c6c066-3630-409b-9f13-9c84dec5f780
  name: "<rig-name>"  # e.g., "Production-Rig-East-01"
  town_id: <town-id-uuid>  # e.g., 3bb00369-82cf-45ab-94af-3eac43516d9d
  region: "<region>"  # e.g., "us-east-1"
  created_at: "<timestamp>"  # ISO 8601 format
  environment: "<env>"  # production|staging|development
  
specs:
  compute:
    vcpu: <num-cpus>  # e.g., 4
    memory_gb: <memory>  # e.g., 16
    disk_gb: <disk>  # e.g., 100
  
  software:
    python_version: "3.11"
    hermes_version: "<version>"  # e.g., "0.12.0"
    os: "<os>"  # e.g., "Ubuntu 22.04"
```

## Directory Structure

```bash
# Create the Rig directory structure
RIG_ID="<rig-id-uuid>"
TOWN_ID="<town-id-uuid>"
RIG_HOME="$HOME/.gastown/rigs/${RIG_ID}"

mkdir -p "${RIG_HOME}"/{worktrees,locks,logs,data,config}

# Directory layout after setup:
# ${RIG_HOME}/
# ├── browse/              # Read-only browsable repo copy
# ├── repo/                # Git repository
# ├── worktrees/           # Agent worktrees
# │   ├── gt__sage__<bead-id>/
# │   ├── gt__clover__<bead-id>/
# │   └── ...
# ├── locks/               # Agent lock files
# ├── logs/                # Rig-level logs
# ├── data/                # Persistent data (Zilliz cache, etc.)
# ├── config/              # Rig-specific configs
# │   ├── rig-config.yaml
# │   └── agents.yaml
# ├── .env                 # Credentials (gitignored)
# └── README.md           # Rig documentation
```

## Environment Configuration

Create `.env` file in the Rig root:

```bash
# .env - Rig Environment Variables
# DO NOT COMMIT THIS FILE

# === Core Identity ===
RIG_ID=<rig-id-uuid>
TOWN_ID=<town-id-uuid>
RIG_NAME=<rig-name>

# === API Keys ===
HERMES_API_KEY=<hermes-api-key>
OPENAI_API_KEY=<openai-key>  # or ANTHROPIC_API_KEY, etc.
ZILLIZ_API_KEY=<zilliz-api-key>
ZILLIZ_CLUSTER_ID=<zilliz-cluster-id>

# === GitHub Access ===
GITHUB_TOKEN=<github-token>

# === Model Configuration ===
DEFAULT_MODEL=<model>  # e.g., "gpt-4o", "claude-3-5-sonnet-20241022"
API_BASE_URL=<custom-endpoint>  # optional
API_MODE=chat_completions  # chat_completions|codex_responses|...

# === Tool Configuration ===
TERMINAL_CWD=/workspace/rigs/<rig-id>/worktrees
ENABLED_TOOLSETS=core,web,research,mlops
DISABLED_TOOLSETS=

# === Agent Defaults ===
MAX_ITERATIONS=90
SAVE_TRAJECTORIES=true
SKIP_MEMORY=false
SKIP_CONTEXT_FILES=false

# === Gateway Configuration ===
GATEWAY_ENABLED=true
GATEWAY_PLATFORMS=cli,telegram
TELEGRAM_BOT_TOKEN=<telegram-token>  # if using Telegram
DISCORD_BOT_TOKEN=<discord-token>    # if using Discord

# === Profile (for multi-instance) ===
# HERMES_HOME=${RIG_HOME}/data/.hermes
# Or use default: ~/.hermes

# === Logging ===
LOG_LEVEL=INFO  # DEBUG|INFO|WARNING|ERROR
LOG_DIR=${RIG_HOME}/logs
```

## Git Repository Setup

```bash
# Clone or update the repository
RIG_HOME="$HOME/.gastown/rigs/<rig-id-uuid>"
REPO_URL="<git-repository-url>"

# Initial clone
git clone "${REPO_URL}" "${RIG_HOME}/repo"

# Or if repo exists, update it
cd "${RIG_HOME}/repo"
git fetch origin
git reset --hard origin/main

# Create browsable copy (read-only)
git worktree add --detach "${RIG_HOME}/browse" origin/main
```

## Agent Worktree Initialization

For each Polecat agent in the Rig:

```bash
#!/bin/bash
# init_agent_worktree.sh - Initialize worktree for an agent

RIG_HOME="$HOME/.gastown/rigs/<rig-id-uuid>"
AGENT_NAME="<agent-name>"  # e.g., "sage", "clover"
BEAD_ID="<bead-id>"  # Current bead assigned, or "none" if idle
AGENT_BRANCH="gt__${AGENT_NAME}__${BEAD_ID}"

cd "${RIG_HOME}/repo"

# Create worktree for agent
git worktree add "${RIG_HOME}/worktrees/gt__${AGENT_NAME}__${BEAD_ID}" \
  -b "${AGENT_BRANCH}"

# Initialize agent-specific config
mkdir -p "${RIG_HOME}/worktrees/gt__${AGENT_NAME}__${BEAD_ID}/.kilo/agent"

cat > "${RIG_HOME}/worktrees/gt__${AGENT_NAME}__${BEAD_ID}/.kilo/agent/${AGENT_NAME}.md" <<EOF
# Agent: ${AGENT_NAME}

## Identity
- ID: <agent-uuid>  # Generate with: python -c "import uuid; print(uuid.uuid4())"
- Role: polecat
- Name: ${AGENT_NAME}
- Rig: <rig-id-uuid>
- Town: <town-id-uuid>

## Current State
- Status: idle
- Current Hooked Bead: ${BEAD_ID}
- Last Activity: none

## Capabilities
- Enabled Toolsets: core, web, research, mlops
- Loaded Skills: []
- Max Iterations: 90
- Memory Provider: honcho

## Configuration
- Model: ${DEFAULT_MODEL}
- API Mode: ${API_MODE}
- Save Trajectories: true
- Skip Memory: false
EOF

echo "Worktree initialized at: ${RIG_HOME}/worktrees/gt__${AGENT_NAME}__${BEAD_ID}"
```

## Agent Registry

Create `config/agents.yaml` to track all agents in the Rig:

```yaml
# config/agents.yaml - Agent Registry
rig_id: <rig-id-uuid>
town_id: <town-id-uuid>

agents:
  - name: sage
    id: <sage-uuid>
    worktree: worktrees/gt__sage__<bead-id>
    status: idle  # idle|working|blocked|offline
    hooked_bead: null
    capabilities:
      toolsets: [core, web, research, mlops]
      skills: [research-paper-writing, llm-wiki]
    config_file: .kilo/agent/sage.md
    
  - name: clover
    id: <clover-uuid>
    worktree: worktrees/gt__clover__<bead-id>
    status: idle
    hooked_bead: null
    capabilities:
      toolsets: [core, web, mlops, security]
      skills: [security-scanning, forensics]
    config_file: .kilo/agent/clover.md
    
  - name: maple
    id: <maple-uuid>
    worktree: worktrees/gt__maple__<bead-id>
    status: idle
    hooked_bead: null
    capabilities:
      toolsets: [core, web, mlops]
      skills: [kaiju-governance, pipeline-automation]
    config_file: .kilo/agent/maple.md

# Add more agents as needed
```

## Initialization Script

Save this as `init_rig.sh` in the Rig root:

```bash
#!/bin/bash
# init_rig.sh - Automated Rig Initialization
set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/.env"

RIG_HOME="${SCRIPT_DIR}"
REPO_URL="<repository-url>"

echo "=== Initializing Rig: ${RIG_NAME} ==="
echo "Rig ID: ${RIG_ID}"
echo "Town ID: ${TOWN_ID}"
echo ""

# Step 1: Verify prerequisites
echo "[1/6] Checking prerequisites..."
command -v git >/dev/null 2>&1 || { echo "git is required but not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required but not installed."; exit 1; }
echo "✓ Prerequisites satisfied"

# Step 2: Clone/update repository
echo "[2/6] Setting up repository..."
if [ ! -d "${RIG_HOME}/repo" ]; then
    git clone "${REPO_URL}" "${RIG_HOME}/repo"
else
    cd "${RIG_HOME}/repo"
    git fetch origin && git reset --hard origin/main
fi
echo "✓ Repository ready"

# Step 3: Create browsable copy
echo "[3/6] Creating browsable worktree..."
if [ ! -d "${RIG_HOME}/browse" ]; then
    git -C "${RIG_HOME}/repo" worktree add --detach "${RIG_HOME}/browse" origin/main
fi
echo "✓ Browse worktree created"

# Step 4: Set up Python environment
echo "[4/6] Setting up Python environment..."
if [ ! -d "${RIG_HOME}/repo/.venv" ]; then
    cd "${RIG_HOME}/repo"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[all,dev]"
fi
echo "✓ Python environment ready"

# Step 5: Initialize agent worktrees
echo "[5/6] Initializing agent worktrees..."
# Add agent initialization calls here
# ./init_agent_worktree.sh "sage" "<bead-id>"
# ./init_agent_worktree.sh "clover" "<bead-id>"
echo "✓ Agent worktrees initialized"

# Step 6: Validate deployment
echo "[6/6] Running validation..."
if [ -f "${RIG_HOME}/repo/scripts/validate_deployment.py" ]; then
    cd "${RIG_HOME}/repo"
    source .venv/bin/activate
    python scripts/validate_deployment.py
fi
echo "✓ Validation complete"

echo ""
echo "=== Rig Initialization Complete ==="
echo "Rig Home: ${RIG_HOME}"
echo "Next steps:"
echo "  1. Review config/agents.yaml"
echo "  2. Start agents: ./start_agents.sh"
echo "  3. Check status: cat logs/rig_status.json"
```

## Validation Checklist

After initialization, verify:

```bash
# Basic checks
[ -d "$HOME/.gastown/rigs/<rig-id>" ] && echo "✓ Rig directory exists"
[ -f "$HOME/.gastown/rigs/<rig-id>/.env" ] && echo "✓ Environment configured"
[ -d "$HOME/.gastown/rigs/<rig-id>/repo/.git" ] && echo "✓ Repository cloned"
[ -d "$HOME/.gastown/rigs/<rig-id>/browse" ] && echo "✓ Browse worktree created"

# Agent checks
[ -d "$HOME/.gastown/rigs/<rig-id>/worktrees" ] && echo "✓ Worktrees directory exists"
# Check each agent worktree
for agent in sage clover maple; do
  if [ -d "$HOME/.gastown/rigs/<rig-id>/worktrees/gt__${agent}__*" ]; then
    echo "✓ Agent ${agent} worktree exists"
  fi
done

# Connectivity checks
cd $HOME/.gastown/rigs/<rig-id>/repo
source .venv/bin/activate

# Test Zilliz
python -c "
import os
print('Testing Zilliz connection...')
# Add actual test here
print('✓ Zilliz connection successful')
"

# Test model API
python -c "
import os
print('Testing model API...')
# Add actual test here
print('✓ Model API accessible')
"

# Run full validation
python scripts/validate_deployment.py
```

## Quick Start Commands

```bash
# Start all agents in the Rig
cd $HOME/.gastown/rigs/<rig-id>
./start_agents.sh

# Check Rig status
./check_rig_status.sh

# View agent logs
tail -f logs/sage.log
tail -f logs/clover.log

# Stop all agents
./stop_agents.sh

# Update repository and all worktrees
./update_rig.sh
```

## Troubleshooting

### Worktree Already Exists
```bash
# List existing worktrees
git -C $HOME/.gastown/rigs/<rig-id>/repo worktree list

# Remove stale worktree
git -C $HOME/.gastown/rigs/<rig-id>/repo worktree remove $HOME/.gastown/rigs/<rig-id>/worktrees/gt__<agent>__<bead> --force
```

### Python Environment Issues
```bash
# Recreate virtual environment
cd $HOME/.gastown/rigs/<rig-id>/repo
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
```

### Agent Fails to Start
```bash
# Check agent lock
ls -la $HOME/.gastown/rigs/<rig-id>/locks/

# Remove stale lock
rm -f $HOME/.gastown/rigs/<rig-id>/locks/<agent>.lock

# Check agent logs
cat $HOME/.gastown/rigs/<rig-id>/logs/<agent>.log
```

## Next Steps

1. Complete the [Town Onboarding Checklist](TOWN_ONBOARDING_CHECKLIST.md)
2. Review the [Nexus Town Deployment Kit](NEXUS_TOWN_DEPLOYMENT_KIT.md)
3. Run the full test suite: `cd repo && scripts/run_tests.sh`
4. Set up monitoring dashboard
5. Begin processing beads
