# Town Onboarding Checklist

Use this checklist when setting up a new Town in the Gastown multi-agent system. Complete all items before declaring the Town operational.

## Pre-Onboarding Setup

### Infrastructure Planning
- [ ] Define Town ID (UUID format recommended: `3bb00369-82cf-45ab-94af-3eac43516d9d`)
- [ ] Choose Town name and region (e.g., "Production East", "us-east-1")
- [ ] Determine initial Rig count (start with 1-3 Rigs)
- [ ] Allocate compute resources per Rig (minimum 4GB RAM, 2 vCPUs)
- [ ] Plan network topology (VPC, subnets, firewall rules)

### Credential Preparation
- [ ] Generate `HERMES_API_KEY` for authentication
- [ ] Provision Zilliz cluster and note `ZILLIZ_CLUSTER_ID`
- [ ] Generate `ZILLIZ_API_KEY` for vector database access
- [ ] Obtain model provider API key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.)
- [ ] Create GitHub personal access token (`GITHUB_TOKEN`) with repo scope
- [ ] Document all credentials in secure password manager

## Phase 1: Town Infrastructure

### Zilliz Vector Database
- [ ] Create Zilliz cluster in chosen region
- [ ] Configure cluster with appropriate capacity (start small, scale as needed)
- [ ] Create `nexus_events` collection with schema:
  ```json
  {
    "fields": [
      {"name": "id", "type": "VARCHAR", "max_length": 256, "is_primary": true},
      {"name": "vector", "type": "FLOAT_VECTOR", "dim": 1536},
      {"name": "timestamp", "type": "INT64"},
      {"name": "event_type", "type": "VARCHAR", "max_length": 128},
      {"name": "rig_id", "type": "VARCHAR", "max_length": 128},
      {"name": "metadata", "type": "JSON"}
    ],
    "indexes": [
      {"field_name": "vector", "index_type": "IVF_FLAT", "metric_type": "L2"}
    ]
  }
  ```
- [ ] Create `nexus_governance` collection with schema:
  ```json
  {
    "fields": [
      {"name": "id", "type": "VARCHAR", "max_length": 256, "is_primary": true},
      {"name": "vector", "type": "FLOAT_VECTOR", "dim": 1536},
      {"name": "timestamp", "type": "INT64"},
      {"name": "proposal_type", "type": "VARCHAR", "max_length": 128},
      {"name": "status", "type": "VARCHAR", "max_length": 64},
      {"name": "vap_chain", "type": "JSON"}
    ]
  }
  ```
- [ ] Verify collections are accessible with API key
- [ ] Run connectivity test: `python scripts/test_zilliz.py`

### KAIJU Governance Setup
- [ ] Enable KAIJU governance pipeline in town config
- [ ] Configure VAP (Verification, Approval, Publishing) audit settings
- [ ] Load policy templates from `nexus-swarm-pack/policies/`
- [ ] Verify policy template loading: `python scripts/verify_policies.py`
- [ ] Test proposal generation with sample bead
- [ ] Validate VAP chain integrity: `python scripts/verify_vap_chain.py`

### OpenShell Gateway Configuration
- [ ] Enable OpenShell gateway in town config
- [ ] Configure supported platforms (cli, telegram, discord, slack, etc.)
- [ ] Set up platform-specific credentials (bot tokens, webhooks)
- [ ] Test gateway connectivity from Rig
- [ ] Verify OCSF (Open Cybersecurity Schema Framework) audit pipeline

## Phase 2: Rig Deployment

### For Each Rig (repeat for each):
- [ ] Generate Rig ID (UUID format: `32c6c066-3630-409b-9f13-9c84dec5f780`)
- [ ] Provision compute instance (VM, container, or bare metal)
- [ ] Install prerequisites:
  - [ ] Python 3.11+
  - [ ] Git
  - [ ] Docker (if using containerized deployment)
  - [ ] `uv` package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] Clone repository: `git clone <repo-url> ~/.gastown/rigs/<rig-id>`
- [ ] Create Python virtual environment: `uv venv ~/.gastown/rigs/<rig-id>/venv --python 3.11`
- [ ] Install dependencies: `source venv/bin/activate && uv pip install -e ".[all,dev]"`

### Rig Configuration
- [ ] Copy `.env.example` to `.env`
- [ ] Populate `.env` with all required credentials:
  ```bash
  HERMES_API_KEY=<your-key>
  ZILLIZ_CLUSTER_ID=<your-cluster>
  ZILLIZ_API_KEY=<your-zilliz-key>
  OPENAI_API_KEY=<your-openai-key>
  GITHUB_TOKEN=<your-github-token>
  TOWN_ID=<town-id>
  RIG_ID=<rig-id>
  ```
- [ ] Copy `cli-config.yaml.example` to `cli-config.yaml`
- [ ] Customize configuration for rig's role
- [ ] Verify config loads: `python -c "from hermes_cli.config import load_config; print(load_config())"`

## Phase 3: Agent Setup

### For Each Polecat Agent (repeat for each):
- [ ] Generate Agent UUID: `python -c "import uuid; print(uuid.uuid4())"`
- [ ] Choose agent name (e.g., "Sage", "Clover", "Maple")
- [ ] Create worktree: `git worktree add worktrees/<agent-name> -b <agent-name>/main`
- [ ] Create agent config: `.kilo/agent/<agent-name>.md`
- [ ] Configure agent capabilities:
  - [ ] Toolsets to enable/disable
  - [ ] Skills to load
  - [ ] Max iteration limit
  - [ ] Memory provider selection
- [ ] Set agent identity in config:
  ```yaml
  agent:
    id: <agent-uuid>
    name: <agent-name>
    role: polecat
    rig_id: <rig-id>
    town_id: <town-id>
  ```

### Agent Validation
- [ ] Start agent: `python run_agent.py --config .kilo/agent/<agent-name>.md`
- [ ] Verify agent status: Check dashboard or `gt_status`
- [ ] Test agent responds to messages
- [ ] Verify agent can access tools
- [ ] Confirm agent can read/write Zilliz collections
- [ ] Test agent can pick up and process beads

## Phase 4: Integration Testing

### Cross-Rig Communication
- [ ] Verify all Rigs can reach each other (ping/test connectivity)
- [ ] Test bead dispatch across Rigs
- [ ] Verify Zilliz sync across all Rigs (write from Rig A, read from Rig B)
- [ ] Test KAIJU governance proposal from one Rig, approval from another

### End-to-End Workflow
- [ ] Create test bead in Town
- [ ] Verify bead appears in rig's pending queue
- [ ] Agent hooks bead and processes it
- [ ] Verify Zilliz `nexus_events` logged the activity
- [ ] Check KAIJU governance recorded the decision (if applicable)
- [ ] Confirm bead transitions to `in_review` or `completed` state
- [ ] Verify notifications sent to appropriate channels

### Performance Baseline
- [ ] Measure bead processing rate (target: > 50 beads/hour/rig)
- [ ] Measure mean time to dispatch (target: < 30 seconds)
- [ ] Measure agent utilization (target: 70-90%)
- [ ] Record baseline metrics for future comparison

## Phase 5: Security & Compliance

### Security Hardening
- [ ] Run security scan: `python scripts/security_scan.py`
- [ ] Review and address all HIGH/CRITICAL vulnerabilities
- [ ] Verify API keys stored securely (not in repo, use env vars or secret manager)
- [ ] Enable audit logging for all agent actions
- [ ] Configure firewall rules (allow only necessary ports)
- [ ] Set up TLS for inter-Rig communication
- [ ] Review OCSF audit pipeline captures all required events

### Access Control
- [ ] Define which agents can access which toolsets
- [ ] Configure command approval workflows for sensitive operations
- [ ] Set up DM pairing for privileged commands
- [ ] Document who has access to what (credential inventory)

## Phase 6: Monitoring & Alerting

### Dashboard Setup
- [ ] Deploy Gastown dashboard
- [ ] Configure Town view showing all Rigs
- [ ] Add agent status widgets
- [ ] Add bead queue depth visualization
- [ ] Add Zilliz collection stats
- [ ] Add KAIJU governance status panel

### Alerts Configuration
- [ ] Set up alert for agent offline > 5 minutes
- [ ] Set up alert for bead stuck in `pending` > 10 minutes
- [ ] Set up alert for Zilliz connection failure
- [ ] Set up alert for KAIJU pipeline failure
- [ ] Configure notification channels (email, Slack, webhook)

### Logging
- [ ] Centralize logs from all Rigs
- [ ] Configure log rotation (agent.log, errors.log, gateway.log)
- [ ] Set up log analysis for error patterns
- [ ] Verify profile-aware logging works correctly

## Phase 7: Documentation

### Town Documentation
- [ ] Create `TOWN_README.md` with:
  - [ ] Town ID and name
  - [ ] List of Rigs and their purposes
  - [ ] Agent roster with specializations
  - [ ] Contact information for maintainers
- [ ] Document custom configurations
- [ ] Record all credentials locations (not the credentials themselves)
- [ ] Create architecture diagram

### Runbooks
- [ ] Create `RUNBOOK_TOWN_OPERATIONS.md`:
  - [ ] How to add a new Rig
  - [ ] How to add a new agent
  - [ ] How to rotate API keys
  - [ ] How to handle agent failures
  - [ ] How to scale up/down
- [ ] Create `RUNBOOK_TROUBLESHOOTING.md`:
  - [ ] Common issues and solutions
  - [ ] Escalation procedures
  - [ ] Emergency contacts

## Sign-Off

### Final Validation
- [ ] Run full test suite: `scripts/run_tests.sh`
- [ ] Run deployment validation: `python scripts/validate_deployment.py`
- [ ] Verify all success metrics from NEXUS_TOWN_DEPLOYMENT_KIT.md are met
- [ ] Complete security scan with zero HIGH/CRITICAL issues

### Approval
- [ ] Town Architect: _________________ Date: _________
- [ ] Security Officer: _________________ Date: _________
- [ ] Operations Lead: _________________ Date: _________

## Post-Onboarding

### First 24 Hours
- [ ] Monitor dashboard continuously
- [ ] Watch for any agent failures or stuck beads
- [ ] Verify Zilliz collections growing as expected
- [ ] Check KAIJU governance making correct decisions

### First Week
- [ ] Review performance metrics daily
- [ ] Tune agent configurations based on observed behavior
- [ ] Scale Rigs/agents if processing backlog grows
- [ ] Document any issues encountered for future Towns

### Ongoing
- [ ] Weekly review of success metrics
- [ ] Monthly security scan
- [ ] Quarterly disaster recovery test
- [ ] Continuous improvement of runbooks based on incidents
