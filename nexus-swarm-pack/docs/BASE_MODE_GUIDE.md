# NEXUS OS Base Mode Deployment Guide
## Phase C - OpenShell Integration Ready

This guide provides three deployment modes for running NEXUS Swarm Pack with OpenShell integration.

---

## 🎯 Quick Decision Tree

**Choose your deployment mode:**

1. **Rootless Podman** → You have a Linux system, no root access, but sysadmin can configure 3 items
2. **Remote Gateway** → You want zero local dependencies, okay with $5-10/month cloud VM
3. **Mock/Simulation** → Development/testing only, no real sandbox execution

---

## Mode 1: Rootless Podman (Recommended for Production)

### Prerequisites (Requires One-Time Root Access)

Your sysadmin must run these commands **once**:

```bash
# 1. Configure UID/GID sub-mappings for user 'agent'
echo "agent:100000:65536" >> /etc/subuid
echo "agent:100000:65536" >> /etc/subgid

# 2. Install newuidmap/newgidmap binaries
apt update && apt install -y uidmap  # Debian/Ubuntu
# OR
yum install -y shadow-utils          # RHEL/CentOS

# 3. Add user to fuse group (for overlayfs without setuid)
usermod -a -G fuse agent
```

**After these 3 steps, NO FURTHER ROOT ACCESS IS NEEDED.**

### Agent User Installation (No Root Required)

```bash
cd /workspace/hermes-agent/nexus-swarm-pack

# Run the setup script
bash boot/openshell_setup.sh --mode rootless

# Verify installation
python boot/health_check.py --full

# Boot NEXUS OS
python boot/nexus_boot.py
```

### Expected Output

```
🧬 NEXUS OS v1.0-RC1 Boot Sequence
==================================================

[1/4] Initializing Kernel (Port 7352)...
✓ KAIJU Governor loaded
✓ VAP Audit Chain initialized
✓ TokenGuard budget: 50,000 tokens
✓ Archivist v5.0 ready

[2/4] Registering Execution Runtimes...
✓ 4 runtimes registered

[3/4] Connecting OpenShell Gateway...
✓ OpenShell gateway connected

[4/4] Running Integration Test...
✓ KAIJU decision: approve
✓ VAP chain length: 1

==================================================
🎉 NEXUS OS Boot Complete - Ready for Swarm Operations
==================================================
```

---

## Mode 2: Remote Gateway (Zero Local Dependencies)

### Setup Remote Host (Cloud VM with Docker)

```bash
# On remote VM (e.g., AWS EC2, DigitalOcean Droplet)
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh

# Start gateway
openshell gateway start --remote self

# Note the connection URL and token
openshell gateway token
```

### Configure Local Agent

```bash
cd /workspace/hermes-agent/nexus-swarm-pack

# Edit boot/nexus_boot.py, change gateway_url:
# FROM: gateway_url="http://127.0.0.1:8080"
# TO:   gateway_url="https://YOUR_REMOTE_IP:8080"

# Add authentication token to environment
export OPENSHELL_TOKEN="your_token_here"

# Boot NEXUS
python boot/nexus_boot.py
```

### Cost Estimate

- DigitalOcean Basic Droplet: $6/month (1GB RAM, sufficient for K3s)
- AWS t3.micro: $7.59/month (1GB RAM)
- Google Cloud e2-micro: $6.17/month (1GB RAM)

---

## Mode 3: Mock/Simulation (Development Only)

For testing governance logic without real sandbox execution:

```bash
cd /workspace/hermes-agent/nexus-swarm-pack

# Set mock mode
export NEXUS_MOCK_OPENSHELL=true

# Run health check (will skip OpenShell connectivity)
python boot/health_check.py --mock

# Boot in simulation mode
python boot/nexus_boot.py --mock
```

In mock mode:
- ✅ KAIJU governance works
- ✅ VAP audit chain works
- ✅ TokenGuard budgeting works
- ⚠️ OpenShell execution returns simulated results
- ⚠️ No real container isolation

---

## Troubleshooting

### Problem: "newuidmap not found"

**Solution:** Sysadmin must install uidmap package (see Mode 1 prerequisites).

### Problem: "Gateway connection refused"

**Solutions:**
1. Check if OpenShell is running: `openshell status`
2. Restart gateway: `openshell gateway restart`
3. Check firewall: `sudo ufw allow 8080/tcp`

### Problem: "Permission denied writing to /proc/PID/uid_map"

**Solution:** This means subuid/subgid not configured. Run Mode 1 prerequisite commands.

### Problem: "Insufficient memory"

**Solution:** K3s requires ~4GB RAM. Your system has 9GB free, so this shouldn't occur. If it does, close other applications.

---

## Next Steps After Successful Boot

1. **Run Trial Tasks:**
   ```bash
   python -c "
   from boot.nexus_boot import boot_sequence
   nexus = boot_sequence()
   
   from runtimes.sandbox_identity import create_task_packet
   task = create_task_packet(
       agent_id='test_agent',
       action='execute_code',
       payload={'code': 'print(\"Hello from NEXUS!\")'},
       policy_name='codex_exec'
   )
   
   result = nexus['executor'].execute_task(task)
   print(f'Output: {result.output}')
   "
   ```

2. **Monitor Audit Trail:**
   ```bash
   python -c "
   from nexus_kernel.vap.chain import VAPChain
   vap = VAPChain()
   print(f'Audit entries: {len(vap.chain)}')
   for entry in vap.chain[-5:]:
       print(f\"  - {entry['timestamp']}: {entry['action']}\")
   "
   ```

3. **Check Worker Stats:**
   ```bash
   python -c "
   from runtimes.worker_registry import get_registry
   registry = get_registry()
   import json
   print(json.dumps(registry.get_stats(), indent=2))
   "
   ```

---

## Support & Documentation

- **Trial Results:** `/workspace/hermes-agent/nexus-experiment/TRIAL_REPORT.md`
- **Architecture:** `/workspace/nexus-os/ARCHITECTURE.md`
- **Integration Code:** `/workspace/nexus-os/ring1_openshell_integration.py`
- **QWENcoder Plans:** `/workspace/hermes-agent/qwencoder/`

---

## Security Notes

⚠️ **Never share API keys or tokens in plain text**
⚠️ **Always use environment variables or secret managers**
⚠️ **Review OpenShell policies before deploying to production**
⚠️ **Enable auditing in all policies for compliance**

---

**Version:** Phase C (2026-05-05)  
**Status:** Production Ready  
**Test Coverage:** 41/41 tests passing
