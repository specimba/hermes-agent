# NEXUS TOWN DEPLOYMENT KIT

## Overview

The Nexus Town Deployment Kit provides comprehensive guidance for deploying and managing Gastown multi-agent systems. A **Town** is a logical grouping of **Rigs** (worker nodes), each running multiple **Polecat agents** that process **Beads** (work items).

## Architecture

```
Town (3bb00369-82cf-45ab-94af-3eac43516d9d)
├── Rig (32c6c066-3630-409b-9f13-9c84dec5f780)
│   ├── Polecat: Sage (aeb30ffd-74eb-4288-b94e-7730b39bf628)
│   ├── Polecat: Clover (...)
│   └── Polecat: Maple (...)
├── Rig (...)
│   └── Polecat: ...
└── Shared Infrastructure
    ├── Zilliz Vector Database (nexus_events, nexus_governance)
    ├── KAIJU Governance Pipeline
    └── OpenShell Gateway
```

## Prerequisites

### System Requirements
- Linux-based OS (Ubuntu 20.04+ recommended)
- Python 3.11+
- Docker (optional, for containerized deployment)
- Git
- Minimum 4GB RAM per Rig
- Network access between Town members

### Required Credentials
- `HERMES_API_KEY` - Primary API authentication
- `ZILLIZ_SERVERLESS_URI` - Vector database cluster
- `ZILLIZ_SERVERLESS_TOKEN` - Vector database access
- `OPENAI_API_KEY` or equivalent model provider key
- `GITHUB_TOKEN` - For repository access (if private)

## Deployment Steps

### 1. Town Initialization

Create a new Town to serve as the coordination hub:

```bash
# Initialize town configuration
mkdir -p ~/.hermes/towns/<town-id>
cd ~/.hermes/towns/<town-id>

# Create town configuration
cat > town-config.yaml <<EOF
town:
  id: <town-id>
  name: "Production Town"
  region: "us-east-1"
  created: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
  
infrastructure:
  zilliz:
    cluster_id: ${ZILLIZ_SERVERLESS_URI}
    collections:
      - nexus_events
      - nexus_governance
  
  governance:
    kaiju_enabled: true
    vap_audit: true
  
  gateway:
    openshell_enabled: true
    platforms: ["cli", "telegram", "discord"]
EOF
```

### 2. Rig Setup

Deploy a Rig within the Town:

```bash
# Clone the rig repository
git clone <repository-url> ~/.hermes/rigs/<rig-id>
cd ~/.hermes/rigs/<rig-id>

# Initialize worktree for agent
git worktree add worktrees/gt__<agent-name>__<bead-id> -b gt__<agent-name>__<bead-id>

# Create environment configuration
cp .env.example .env
# Edit .env with required credentials
```

### 3. Agent Configuration

Configure each Polecat agent in the Rig:

```bash
# Agent configuration structure
mkdir -p .kilo/agent/

cat > .kilo/agent/<agent-name>.md <<EOF
# Agent: <agent-name>

## Identity
- ID: <agent-uuid>
- Role: polecat
- Rig: <rig-id>
- Town: <town-id>

## Capabilities
- Tools: all
- Skills: research, mlops, security
- Max Iterations: 90

## Hooks
- Hooked Bead: null
- Status: idle
EOF
```

### 4. Verification

Run the deployment verification script:

```bash
# Validate rig setup and run tests
scripts/run_tests.sh

# Verify Zilliz connection (use Python client directly)
# Example: python -c "from pymilvus import connections; connections.connect(uri=os.getenv('ZILLIZ_SERVERLESS_URI'), token=os.getenv('ZILLIZ_SERVERLESS_TOKEN'))"
```

## Troubleshooting Scenarios

### Scenario 1: Agent Fails to Initialize

**Symptoms:**
- Agent status remains "initializing"
- No heartbeat detected in town dashboard
- Error: "Failed to acquire agent lock"

**Root Causes:**
1. Stale lock file from previous session
2. Insufficient permissions on worktree
3. Missing environment variables

**Resolution:**
```bash
# Check for stale locks
ls -la ~/.hermes/rigs/<rig-id>/locks/

# Remove stale lock if agent is not running
rm -f ~/.hermes/rigs/<rig-id>/locks/<agent-name>.lock

# Verify environment
source .env && env | grep -E "(HERMES_|ZILLIZ_|OPENAI_)"

# Fix permissions
chmod -R u+w ~/.hermes/rigs/<rig-id>/worktrees/gt__<agent-name>__<bead-id>/
```

### Scenario 2: Zilliz Connection Failures

**Symptoms:**
- "Connection timeout to Zilliz cluster"
- "Unauthorized: Invalid API key"
- Vector search operations failing

**Root Causes:**
1. Incorrect cluster ID or API key
2. Network connectivity issues
3. Collection not initialized

**Resolution:**
```bash
# Test connectivity
curl -X GET "${ZILLIZ_SERVERLESS_URI}/v1/health" \
  -H "Authorization: Bearer ${ZILLIZ_SERVERLESS_TOKEN}"

# Verify collections exist
python -c "
import os
from pymilvus import connections, has_collection
connections.connect(
    uri=os.getenv('ZILLIZ_SERVERLESS_URI'),
    token=os.getenv('ZILLIZ_SERVERLESS_TOKEN')
)
print('nexus_events:', has_collection('nexus_events'))
print('nexus_governance:', has_collection('nexus_governance'))
"
```

### Scenario 3: Bead Dispatch Failures

**Symptoms:**
- Beads stuck in "pending" state
- No agent picks up work
- Error: "No available agents in rig"

**Root Causes:**
1. All agents busy or offline
2. Bead priority/affinity mismatch
3. Rig capacity exceeded

**Resolution:**
```bash
# Check agent status
gt_status  # If inside agent session
# Or query via API
curl http://localhost:8080/api/rigs/<rig-id>/agents/status

# Use Gastown CLI tools to dispatch beads and manage rig capacity
# gt_dispatch, gt_scale, etc.
```

### Scenario 4: Git Worktree Corruption

**Symptoms:**
- "fatal: not a valid object name"
- Worktree shows detached HEAD
- Unable to pull latest changes

**Root Causes:**
1. Force push to main branch
2. Worktree not properly initialized
3. Disk I/O errors

**Resolution:**
```bash
# Remove corrupted worktree
git worktree remove worktrees/gt__<agent-name>__<bead-id> --force

# Recreate worktree from latest main
git fetch origin
git worktree add worktrees/gt__<agent-name>__<bead-id> -b gt__<agent-name>__<bead-id> origin/main

# If branch conflicts, create fresh
git worktree add worktrees/gt__<agent-name>__<bead-id> -b gt__<agent-name>__<bead-id>-$(date +%s)
```

### Scenario 5: KAIJU Governance Pipeline Errors

**Symptoms:**
- Proposals not generating
- VAP audit failures
- Governance decisions not applied

**Root Causes:**
1. KAIJU service not running
2. VAP chain integrity compromised
3. Policy template missing

**Resolution:**
```bash
# Check KAIJU status via Gastown CLI or API
# Use hermes CLI commands to manage KAIJU governance

# Verify VAP chain and policies using existing tools
scripts/run_tests.sh

# Restart KAIJU governance via systemd/docker or platform tools
```

## Success Metrics

### Deployment Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Rig Initialization Time | < 5 minutes | Time from `git clone` to `gt_status` ready |
| Agent Spawn Success Rate | > 99% | (Successful spawns / Total spawn attempts) × 100 |
| Town Connectivity | 100% | All rigs reachable within 30s heartbeat |
| Zilliz Integration | 100% | Both collections accessible with < 100ms latency |

### Operational Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Bead Processing Rate | > 50 beads/hour/rig | Beads completed per hour |
| Mean Time to Dispatch | < 30 seconds | Time from bead creation to agent hook |
| Agent Utilization | 70-90% | (Active time / Total uptime) × 100 |
| Error Rate | < 1% | (Failed beads / Total beads) × 100 |

### Quality Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Code Coverage (new tests) | > 90% | `scripts/run_tests.sh` output |
| Documentation Completeness | 100% | All templates and checklists present |
| Security Scan Pass Rate | 100% | Zero HIGH/CRITICAL vulnerabilities |
| Cross-Node Consistency | 100% | Zilliz vector sync verification |

## Automated Validation Steps

### Validation Script: `validate_deployment.py`

```python
#!/usr/bin/env python3
"""
Automated validation for Nexus Town deployment.
Run after initial setup and periodically for health checks.
"""

import os
import sys
import yaml
import subprocess
from typing import List, Dict, Tuple

class DeploymentValidator:
    def __init__(self, town_id: str, rig_id: str):
        self.town_id = town_id
        self.rig_id = rig_id
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def validate_all(self) -> bool:
        """Run all validation checks."""
        checks = [
            self.validate_environment,
            self.validate_git_setup,
            self.validate_agent_configs,
            self.validate_zilliz_connection,
            self.validate_kaiju_pipeline,
            self.validate_rig_health,
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                self.errors.append(f"{check.__name__} failed: {str(e)}")
        
        return len(self.errors) == 0
    
    def validate_environment(self):
        """Validate required environment variables."""
        required_vars = [
            'HERMES_API_KEY',
            'ZILLIZ_SERVERLESS_URI',
            'ZILLIZ_SERVERLESS_TOKEN',
        ]
        for var in required_vars:
            if not os.getenv(var):
                self.errors.append(f"Missing environment variable: {var}")
    
    def validate_git_setup(self):
        """Validate git repository and worktrees."""
        result = subprocess.run(
            ['git', 'worktree', 'list'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            self.errors.append("Git worktree configuration invalid")
        
        # Check worktrees for each agent
        worktrees = result.stdout.strip().split('\n')
        if len(worktrees) < 2:  # Main + at least one worktree
            self.warnings.append("Less than 2 worktrees found")
    
    def validate_agent_configs(self):
        """Validate agent configuration files."""
        agent_dir = '.kilo/agent/'
        if not os.path.exists(agent_dir):
            self.errors.append(f"Agent config directory missing: {agent_dir}")
            return
        
        for fname in os.listdir(agent_dir):
            if fname.endswith('.md'):
                with open(os.path.join(agent_dir, fname)) as f:
                    content = f.read()
                    if 'agent-uuid' not in content.lower():
                        self.warnings.append(f"Agent config may be incomplete: {fname}")
    
    def validate_zilliz_connection(self):
        """Test Zilliz vector database connectivity."""
        try:
            from pymilvus import connections
            connections.connect(
                uri=os.getenv('ZILLIZ_SERVERLESS_URI'),
                token=os.getenv('ZILLIZ_SERVERLESS_TOKEN')
            )
        except Exception as e:
            self.errors.append(f"Zilliz connection failed: {str(e)}")
    
    def validate_kaiju_pipeline(self):
        """Verify KAIJU governance pipeline is operational."""
        # Check if governance collections exist
        pass  # Implementation depends on KAIJU API
    
    def validate_rig_health(self):
        """Check rig health via status endpoint."""
        rig_status_file = f"~/.hermes/rigs/{self.rig_id}/status.json"
        if not os.path.exists(os.path.expanduser(rig_status_file)):
            self.warnings.append("Rig status file not found")
    
    def report(self):
        """Print validation report."""
        print("=" * 60)
        print("DEPLOYMENT VALIDATION REPORT")
        print("=" * 60)
        
        if self.errors:
            print("\n❌ ERRORS:")
            for err in self.errors:
                print(f"  - {err}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warn in self.warnings:
                print(f"  - {warn}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All validation checks passed!")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    town_id = os.getenv('TOWN_ID', '<town-id>')
    rig_id = os.getenv('RIG_ID', '<rig-id>')
    
    validator = DeploymentValidator(town_id, rig_id)
    success = validator.validate_all()
    validator.report()
    
    sys.exit(0 if success else 1)
```

### Running Validation

```bash
# Initial deployment validation
python scripts/validate_deployment.py

# Continuous health check (every 5 minutes)
*/5 * * * * cd /path/to/rig && python scripts/validate_deployment.py || echo "Validation failed" | mail -s "Rig Health Alert" admin@example.com

# Integration test suite
scripts/run_tests.sh
```

## Security Considerations

1. **API Key Management**: Never commit `.env` files. Use secret management or environment variables.
2. **Network Isolation**: Rigs should communicate over TLS. Use VPN or private network when possible.
3. **Agent Permissions**: Follow principle of least privilege. Restrict agent capabilities to required tools only.
4. **Audit Logging**: Enable VAP audit trail for all governance decisions.
5. **Regular Updates**: Keep hermes-agent and dependencies updated.

## Next Steps

After successful deployment:
1. Complete the [Town Onboarding Checklist](#town-onboarding-checklist)
2. Initialize each rig using the [Rig Initialization Template](#rig-initialization-template)
3. Run the full test suite: `scripts/run_tests.sh`
4. Monitor the dashboard for initial operations
5. Scale up gradually: add more rigs/agents as needed

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/NousResearch/hermes-agent/issues)
- Discord: [Join the community](https://discord.gg/NousResearch)
- Documentation: [Full docs](https://hermes-agent.nousresearch.com/docs/)
