# 🚀 NEXUS Swarm Pack - Bead Recovery & Execution Guide

**Target:** Gastown Agents fixing failed OpenShell infrastructure beads  
**Status:** ✅ Swarm Pack Deployed | ⚠️ Environment Blockers Identified  
**Version:** v1.0-RC1 | **Date:** 2026-04-30

---

## 📊 Current Bead Status Overview

| Bead ID | Title | Status | Blocker | Priority |
|---------|-------|--------|---------|----------|
| `fdf85810` | Install/start Docker daemon | ❌ FAILED | Missing `newuidmap` binary | 🔴 CRITICAL |
| `71ec8a8d` | Initialize OpenShell gateway | ⏸️ BLOCKED | Depends on fdf85810 | 🔴 CRITICAL |
| `adcfc4fd` | Create first sandbox | ⏸️ BLOCKED | Depends on gateway | 🟡 HIGH |
| `a60b32f2` | Memory requirement check | ✅ PASSED | 9.4GB free (satisfied) | 🟢 READY |
| `*5 merge beads` | GitHub PR polling | ⏸️ BLOCKED | Missing GitHub token in env | 🟡 HIGH |

**Convoys Ready to Land:**
- `eb0ea937` - OpenShell Setup Sequence (3/3 beads closed)
- `2f8f56cd` - OpenShell Integration Trial (10/10 beads closed)

---

## 🎯 Three Recovery Paths

### Path A: Rootless Podman (RECOMMENDED - Fastest)

**Prerequisite:** One-time sysadmin action to install `uidmap` package

#### Step 1: Sysadmin Request (Copy/Paste This)

Send this exact command to your refinery/sysadmin:

```bash
# Enable rootless Podman for user 'agent'
echo "agent:100000:65536" >> /etc/subuid
echo "agent:100000:65536" >> /etc/subgid
apt update && apt install -y uidmap
usermod -a -G fuse agent
```

**What this does:**
- Adds UID/GID mapping ranges for rootless containers
- Installs `newuidmap`/`newgidmap` binaries (the missing blocker)
- Grants FUSE access for overlay filesystem (no setuid needed)
- **No further root access required after this command**

#### Step 2: Agent Execution (After Sysadmin Confirms)

```bash
cd /workspace/rigs/6766cabc-3faf-4ab4-80b4-0aa76730e946/browse/nexus-swarm-pack

# Reset the failed bead
gt_reset_bead fdf85810 --reason "uidmap installed, ready for retry"

# Run the setup script (rootless mode)
bash boot/openshell_setup.sh --mode rootless

# Verify installation
bash boot/health_check.py --full

# Boot NEXUS kernel
python boot/nexus_boot.py
```

**Expected Output:**
```
✓ Podman static installed
✓ Podman system service running
✓ OpenShell CLI installed
✓ Gateway started (K3s cluster inside Podman)
✓ Sandbox created successfully
🧬 NEXUS OS Boot Complete - Port 7352 active
```

#### Step 3: Reset Remaining Beads

```bash
# Reset gateway initialization bead
gt_reset_bead 71ec8a8d --reason "gateway now available"

# Reset sandbox creation bead  
gt_reset_bead adcfc4fd --reason "gateway ready, sandbox can be created"

# Monitor progress
gt_list_beads --status active
```

---

### Path B: Remote Gateway (No Host Changes)

**Use Case:** Sysadmin refuses root access or uidmap installation

#### Step 1: Deploy Remote Gateway

Option A - Quick Cloud VM ($5-10/month):
```bash
# On a fresh Ubuntu VM with Docker (DigitalOcean, Linode, AWS EC2)
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell gateway start --port 8080 --plaintext
```

Option B - Use Existing Server:
```bash
# If you have any server with Docker access
ssh user@your-server.com
openshell gateway start --remote self
```

#### Step 2: Configure Local Connection

Edit `boot/nexus_boot.py` line ~45:

```python
# Change from:
GATEWAY_URL = "http://127.0.0.1:8080"

# To your remote gateway:
GATEWAY_URL = "http://YOUR.SERVER.IP:8080"
# Or SSH tunnel:
# GATEWAY_URL = "http://localhost:8080"  # after: ssh -L 8080:localhost:8080 user@server
```

#### Step 3: Boot Without Local Containers

```bash
cd /workspace/rigs/6766cabc-3faf-4ab4-80b4-0aa76730e946/browse/nexus-swarm-pack

# Skip openshell_setup.sh (no local install needed)
python boot/nexus_boot.py
```

**Result:** NEXUS kernel runs locally, all sandbox execution happens on remote server.

#### Step 4: Mark Local Beads as Skipped

```bash
# Document that local Docker is not needed for this path
gt_add_comment fdf85810 "Using remote gateway path - local Docker not required"
gt_close_bead fdf85810 --resolution "workaround_applied"

# Create new bead for remote gateway tracking
gt_create_bead "Configure remote OpenShell gateway" \
  --convoy eb0ea937 \
  --priority high
```

---

### Path C: Hybrid Mode (Temporary Workaround)

**Use Case:** Test NEXUS governance without OpenShell sandboxes

#### Step 1: Boot Kernel Only

```bash
cd /workspace/rigs/6766cabc-3faf-4ab4-80b4-0aa76730e946/browse/nexus-swarm-pack

# Boot without OpenShell integration
python boot/nexus_boot.py --no-openshell
```

**What Works:**
- ✅ KAIJU Governor (Port 7352)
- ✅ VAP Audit Chain
- ✅ TokenGuard budget tracking
- ✅ Archivist v5.0 truth engine
- ✅ Native runtime execution
- ✅ Foundry dataset processing

**What's Limited:**
- ⚠️ No sandbox isolation (code runs natively)
- ⚠️ No policy-banded execution lanes
- ⚠️ Reduced security guarantees

#### Step 2: Use Native Runtime for Testing

```python
# Example: Execute code with governance but no sandbox
from runtimes.worker_registry import WorkerRegistry
from nexus_kernel.kaiju import KAIJUGovernor

registry = WorkerRegistry()
kaiju = KAIJUGovernor()

# Select native runtime
worker = registry.select_worker("native", {"capability": "code_execution"})

# Propose action through KAIJU
proposal = kaiju.propose_action(
    agent_id="test_agent",
    action="execute_python",
    payload={"code": "print('Hello from NEXUS')"},
    target_resource=None
)

# Execute if approved
if proposal.status == "approved":
    result = worker.execute(proposal)
    print(f"Result: {result}")
```

#### Step 3: Document Limitation

```bash
gt_add_comment fdf85810 "Running in hybrid mode - OpenShell integration pending"
gt_create_bead "Re-enable OpenShell sandboxes when uidmap available" \
  --convoy eb0ea937 \
  --priority medium
```

---

## 🔧 Troubleshooting Commands

### Check Prerequisites

```bash
# Verify subuid/subgid configuration
grep "^agent:" /etc/subuid /etc/subgid

# Check for newuidmap binary
which newuidmap || echo "MISSING: newuidmap not in PATH"

# Verify Podman installation
~/.local/bin/podman --version 2>/dev/null || echo "Podman not installed"

# Check memory availability
free -h | grep Mem

# Verify port 7352 is free
netstat -tlnp 2>/dev/null | grep 7352 || ss -tlnp | grep 7352
```

### Reset Failed Beads Safely

```bash
# Get bead details before resetting
gt_get_bead fdf85810 --full

# Add diagnostic comment
gt_add_comment fdf85810 "Resetting after uidmap installation - see health_check.log"

# Reset with reason
gt_reset_bead fdf85810 \
  --reason "Environment prerequisite satisfied" \
  --retry-count 1

# Monitor reset bead
gt_watch_bead fdf85810
```

### Health Check Diagnostics

```bash
# Full diagnostic report
python boot/health_check.py --full --verbose

# Check specific component
python boot/health_check.py --check kernel
python boot/health_check.py --check openshell
python boot/health_check.py --check memory

# Generate JSON report for debugging
python boot/health_check.py --json > health_report.json
```

### Gateway Debugging

```bash
# Test gateway connectivity
curl -v http://127.0.0.1:8080/health

# Check gateway logs (if running)
docker logs openshell-gateway 2>/dev/null || \
  podman logs openshell-gateway 2>/dev/null || \
  echo "Gateway not running in container"

# Verify OpenShell CLI
openshell status
openshell gateway list
openshell sandbox list
```

---

## 📋 Execution Checklist

### For Path A (Rootless Podman)

- [ ] Sysadmin runs uidmap installation command
- [ ] Verify `which newuidmap` returns path
- [ ] Run `bash boot/openshell_setup.sh --mode rootless`
- [ ] Confirm `bash boot/health_check.py --full` passes all checks
- [ ] Reset bead `fdf85810` to open
- [ ] Wait for automatic retry OR manually trigger
- [ ] Reset beads `71ec8a8d` and `adcfc4fd`
- [ ] Run `python boot/nexus_boot.py`
- [ ] Verify all 5 infrastructure beads turn green
- [ ] Configure GitHub token for merge polling beads
- [ ] Land convoys `eb0ea937` and `2f8f56cd`

### For Path B (Remote Gateway)

- [ ] Deploy OpenShell on remote VM with Docker
- [ ] Note remote server IP and port
- [ ] Update `GATEWAY_URL` in `boot/nexus_boot.py`
- [ ] Run `python boot/nexus_boot.py`
- [ ] Mark local Docker bead as workaround applied
- [ ] Create tracking bead for remote gateway
- [ ] Test sandbox creation via remote connection
- [ ] Configure GitHub token for merge polling
- [ ] Land completed convoys

### For Path C (Hybrid Mode)

- [ ] Run `python boot/nexus_boot.py --no-openshell`
- [ ] Verify kernel components initialize
- [ ] Test native runtime execution
- [ ] Document security limitations in bead comments
- [ ] Create follow-up bead for full OpenShell integration
- [ ] Proceed with governance testing using native runtime
- [ ] Configure GitHub token for merge polling
- [ ] Land non-OpenShell dependent convoys

---

## 🎓 Key Concepts for Gastown Agents

### What is NEXUS Swarm Pack?

A governance layer that wraps agent execution with:
- **KAIJU**: 5-stage authorization gates (prevents prompt injection attacks)
- **VAP**: Cryptographic audit trail (SHA-256 blockchain-style logging)
- **TokenGuard**: Budget enforcement across 50+ free model APIs
- **Archivist**: 4-layer truth engine (SOURCE → EXTRACTED → INFERRED → CANONICAL)

### Why OpenShell Sandboxes?

OpenShell provides **kernel-level isolation** for agent code:
- Prevents rogue agents from accessing unauthorized files/network
- Enforces policy-banded execution lanes (codex vs analysis vs inference)
- Injects API keys at gateway level (agents never see credentials)
- Auto-blocks non-compensatory harm violations

### How Beads Relate to Architecture

```
Bead fdf85810 (Docker/Podman) ──┐
                                 ├──► OpenShell Gateway ──► Sandboxes
Bead 71ec8a8d (Gateway Init) ───┘                               │
                                                                ▼
Bead adcfc4fd (Sandbox Create) ─────────────────────► NEXUS Kernel (7352)
                                                                │
                                                                ▼
Merge Polling Beads ──► Convoys ──► Land ──► Production Code
```

### When to Use Each Path

| Scenario | Recommended Path | Reason |
|----------|-----------------|--------|
| Sysadmin cooperative | Path A | Full security, local execution |
| No root access ever | Path B | Bypass host requirements |
| Urgent testing needed | Path C | Immediate governance, reduced security |
| Production deployment | Path A | Maximum isolation guarantees |
| Development/testing | Path C | Faster iteration |

---

## 📞 Support & Escalation

### Quick Diagnostics Command

```bash
cd /workspace/rigs/6766cabc-3faf-4ab4-80b4-0aa76730e946/browse/nexus-swarm-pack
bash boot/health_check.py --full --json | jq '.summary'
```

### Critical Failure Patterns

**If `newuidmap` still missing after sysadmin action:**
```bash
# Check if package installed but not in PATH
dpkg -l | grep uidmap
ls -la /usr/bin/newuidmap

# Add to PATH if exists elsewhere
export PATH="/usr/bin:$PATH"
```

**If Podman fails to start:**
```bash
# Check storage driver
podman info --format '{{.Store.GraphDriverName}}'

# Try alternative driver
export CONTAINERS_STORAGE_DRIVER="vfs"
podman system service --time=0
```

**If gateway won't bind to port 8080:**
```bash
# Check what's using the port
ss -tlnp | grep 8080

# Use alternative port
openshell gateway start --port 8081
# Update nexus_boot.py GATEWAY_URL accordingly
```

### Escalation Template

When stuck, create a bead comment with this info:

```
## Diagnostic Report
- Path Attempted: [A/B/C]
- sysadmin_command_run: [yes/no + timestamp]
- newuidmap_present: [yes/no + which output]
- podman_version: [output of podman --version]
- gateway_status: [running/failed + error message]
- memory_available: [free -h output]
- port_7352_status: [free/in-use]
- health_check_json: [attach health_report.json]

## Next Action Needed
[Specific request for sysadmin/team lead]
```

---

## 🏆 Success Criteria

**Path A Complete When:**
- ✅ All 5 infrastructure beads green
- ✅ `python boot/nexus_boot.py` shows all ✓ checks
- ✅ Can create sandbox: `openshell sandbox create --policy codex_exec`
- ✅ KAIJU approves/rejects test proposals correctly
- ✅ VAP chain hashes are valid
- ✅ Convoys land successfully

**Path B Complete When:**
- ✅ Remote gateway responds to health checks
- ✅ Local NEXUS kernel connects successfully
- ✅ Sandboxes execute on remote server
- ✅ Audit logs sync back to local VAP chain
- ✅ Convoys land successfully

**Path C Complete When:**
- ✅ Kernel boots without OpenShell errors
- ✅ Native runtime executes governed code
- ✅ TokenGuard tracks budgets correctly
- ✅ Archivist promotes knowledge layers
- ✅ Security limitations documented in beads
- ✅ Follow-up bead created for full integration

---

**Remember:** The goal is **progressive enhancement**. Start with what works (Path C), then upgrade to full security (Path A) when environment allows. Never let perfect be the enemy of good—governance is better than no governance!

🧬 **NEXUS OS v1.0-RC1 - Governed Swarms, Zero Compromise**
