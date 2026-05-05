# 🧬 NEXUS Swarm Pack

**Phase C Complete** - OpenShell Integration with Nexus OS Governance

## Quick Start

```bash
cd nexus-swarm-pack
python boot/health_check.py --full
bash boot/openshell_setup.sh --mode rootless
python boot/nexus_boot.py
```

## What's Inside

### 🚀 Boot Automation
- `nexus_boot.py` - Initialize Nexus Kernel + OpenShell Gateway
- `openshell_setup.sh` - 3-mode deployment (rootless/remote/standalone)
- `health_check.py` - Pre-flight verification

### 📋 Policy Templates
- `codex_exec.yaml` - Code execution sandbox
- `opencode_analysis.yaml` - Analysis worker (no network)
- `inference_local.yaml` - Local inference gateway

### 🔧 Runtime Integration
- Worker Registry (native/foundry/openshell/wrapper)
- OCSF Audit Pipeline
- Sandbox Identity Schema

## Deployment Modes

### Mode 1: Rootless Podman (Recommended)
Requires sysadmin to run once:
```bash
echo agent:100000:65536 >> /etc/subuid
echo agent:100000:65536 >> /etc/subgid
apt install -y uidmap
usermod -a -G fuse agent
```

Then run: `bash boot/openshell_setup.sh --mode rootless`

### Mode 2: Remote Gateway
Deploy OpenShell on cloud VM, connect via SSH.
Run: `bash boot/openshell_setup.sh --mode remote`

### Mode 3: Standalone Binary
Manual gateway deployment without K3s.
Run: `bash boot/openshell_setup.sh --mode standalone`

## Architecture

```
┌─────────────────┐
│  Gastown Agent  │
└────────┬────────┘
         │ Task Packet + SandboxIdentity
         ▼
┌─────────────────┐
│  KAIJU Governor │ → Selects Worker Runtime
└────────┬────────┘
         │ Approved Proposal
         ▼
┌─────────────────┐
│ OpenShellExecutor│ → Enforces Policy
└────────┬────────┘
         │ OCSF Event Log
         ▼
┌─────────────────┐
│  VAP Audit Chain│ → SHA-256 Hash
└─────────────────┘
```

## Test Results

- **Phase A**: 9/9 tests (Kernel components)
- **Phase B**: 14/14 tests (OpenShell trials)
- **Phase C**: 18/18 tests (Integration)
- **Total**: 41/41 passing ✅

## For Gastown Agents

When fixing failed OpenShell beads:

1. Run health check: `python boot/health_check.py --full`
2. Follow BASE_MODE_GUIDE.md for your deployment mode
3. Verify policies: `ls policies/*.yaml`
4. Execute task through Nexus governance

## Documentation

- **Deployment Guide:** `docs/BASE_MODE_GUIDE.md`
- **Trial Results:** `/workspace/hermes-agent/nexus-experiment/TRIAL_REPORT.md`
- **Architecture:** `/workspace/nexus-os/ARCHITECTURE.md`

## Support

Created for NEXUS OS v4.1 integration with Gastown swarm coordination.
