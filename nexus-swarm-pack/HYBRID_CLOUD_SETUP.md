# NEXUS Hybrid Cloud Setup Guide

**Windows (Local) + Ubuntu VM (Sandbox) + Zilliz (Memory) + Supabase (State)**

This guide sets up the complete hybrid architecture where:
- **Windows**: Runs NEXUS Kernel (governance, decisions, audit)
- **Ubuntu VM**: Runs OpenShell sandboxes (code execution, isolation)
- **Zilliz**: Dual-cluster vector memory (HOT events + COLD governance)
- **Supabase**: Relational state mirror (dashboards, SQL queries)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    YOUR LOCAL WINDOWS MACHINE                     │
│  ┌────────────────┐     ┌─────────────────┐     ┌─────────────┐  │
│  │ NEXUS Kernel   │────▶│ Cloud Edge Mgr  │────▶│ PowerShell  │  │
│  │ Port 7352      │     │ (Sync Layer)    │     │ CLI         │  │
│  │ - KAIJU        │     │                 │     │             │  │
│  │ - VAP Chain    │     └────────┬────────┘     └─────────────┘  │
│  │ - TokenGuard   │              │                                │
│  │ - Archivist    │              │ HTTPS                          │
│  └────────────────┘              │                                │
└──────────────────────────────────┼────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
    ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
    │ Zilliz HOT       │ │ Zilliz COLD      │ │ Supabase         │
    │ nexus-serverless │ │ nexus-os-town    │ │ nexus-gspp       │
    │ AWS EU-CENTRAL   │ │ AWS EU-CENTRAL   │ │ AWS EU-CENTRAL   │
    │ - EVENT track    │ │ - TRUST track    │ │ - trust_scores   │
    │ - FAILURE track  │ │ - GOV track      │ │ - governance_log │
    └──────────────────┘ └──────────────────┘ └──────────────────┘
              ▲
              │ SSH
              │
    ┌──────────────────────────────────────────────────────────────┐
    │              UBUNTU VM (SANDBOX EXECUTION)                    │
    │  ┌────────────────┐     ┌─────────────────┐                  │
    │  │ OpenShell      │────▶│ Podman/Docker    │                  │
    │  │ Gateway        │     │ - Code Exec      │                  │
    │  │ Port 8080      │     │ - File Isolation │                  │
    │  └────────────────┘     │ - Network Rules  │                  │
    │                         └─────────────────┘                  │
    └──────────────────────────────────────────────────────────────┘
```

---

## Part 1: Windows Local Setup (NEXUS Kernel)

### Step 1.1: Clone Repository

```powershell
cd C:\Users\speci.000\Documents\HERMES
git clone -b main https://github.com/specimba/hermes-agent.git
cd hermes-agent\nexus-swarm-pack
```

### Step 1.2: Install Python Dependencies

```powershell
pip install pymilvus supabase
```

### Step 1.3: Configure Environment

Create `.env` file in `nexus-swarm-pack/`:

```bash
# Zilliz HOT (nexus-serverless) - For Events & Failures
ZILLIZ_HOT_URI=https://in05-2a4b7e6226ae27e.serverless.aws-eu-central-1.cloud.zilliz.com
ZILLIZ_HOT_TOKEN=your_username:your_password

# Zilliz COLD (nexus-os-town) - For Trust & Governance
ZILLIZ_COLD_URI=https://in03-db7a5bcd01da539.serverless.aws-eu-central-1.cloud.zilliz.com
ZILLIZ_COLD_TOKEN=your_username:your_password

# Supabase (nexus-gspp) - For Dashboard State
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

**Get Your Tokens:**
1. **Zilliz**: Go to Zilliz Cloud Console → Clusters → Connect → Copy URI and Token (format: `user:password`)
2. **Supabase**: Go to Project Settings → API → Copy URL and `anon` key

### Step 1.4: Test Cloud Edge Connection

```powershell
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

### Step 1.5: Boot NEXUS Kernel

```powershell
python boot/nexus_boot.py
```

Expected output:
```
🧬 NEXUS OS v1.0-RC1 Boot Sequence
==================================================
[1/4] Initializing Kernel (Port 7352)...
✓ KAIJU Governor loaded
✓ VAP Audit Chain initialized
✓ TokenGuard ready
✓ Archivist v5.0 ready

[2/4] Registering Execution Runtimes...
✓ 4 runtimes registered

[3/4] Cloud Edge Integration...
✅ Zilliz HOT connected (nexus-serverless)
✅ Zilliz COLD connected (nexus-os-town)
✅ Supabase connected (nexus-gspp)

[4/4] Running Integration Test...
✓ KAIJU decision: GateDecision.DENY
✓ VAP chain length: 1
✓ Event stored in Zilliz HOT
✓ Governance logged to Zilliz COLD + Supabase

==================================================
🎉 NEXUS OS Boot Complete - Ready for Swarm Operations
==================================================
```

---

## Part 2: Ubuntu VM Setup (OpenShell Sandbox)

### Option A: Create Free Ubuntu VM

**Oracle Cloud Free Tier** (Recommended - Always Free):
- 4 ARM cores, 24GB RAM
- 200GB storage
- No credit card required (sometimes)

**Google Cloud Free Tier**:
- e2-micro instance (shared CPU)
- 30GB storage
- $300 free credit for 90 days

**AWS Free Tier**:
- t2.micro or t3.micro
- 750 hours/month for 12 months

### Step 2.1: SSH into VM

```powershell
ssh ubuntu@your-vm-ip
```

### Step 2.2: Install Docker & OpenShell

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install OpenShell CLI
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh

# Logout and login again for group changes
exit
```

### Step 2.3: Start OpenShell Gateway

```bash
# Reconnect after group change
ssh ubuntu@your-vm-ip

# Start gateway (creates K3s cluster inside Docker)
openshell gateway start --port 8080 --plaintext

# Verify it's running
openshell status
```

Expected output:
```
Gateway: http://your-vm-ip:8080
Status: Healthy
Cluster: k3s running in Docker
```

### Step 2.4: Configure Firewall

Allow port 8080 for NEXUS Kernel connection:

**Oracle Cloud:**
- Go to Networking → Virtual Cloud Networks → Security Lists
- Add Ingress Rule: TCP 8080 from 0.0.0.0/0

**AWS:**
- Go to EC2 → Security Groups
- Add Inbound Rule: Custom TCP 8080 from 0.0.0.0/0

**Google Cloud:**
- Go to VPC Network → Firewall
- Create Rule: Allow TCP 8080 from 0.0.0.0/0

---

## Part 3: Connect Windows Kernel to Ubuntu Sandbox

### Step 3.1: Update Windows Configuration

Edit `nexus-swarm-pack/boot/nexus_boot.py` on Windows:

```python
# Find the OpenShell gateway URL section
OPENSHELL_GATEWAY_URL = "http://your-vm-ip:8080"
```

### Step 3.2: Test Connection from Windows

```powershell
# Test if Windows can reach Ubuntu VM
Test-NetConnection -ComputerName your-vm-ip -Port 8080
```

Expected output:
```
TcpTestSucceeded : True
```

### Step 3.3: Run Full Integration Test

```powershell
python boot/nexus_boot.py --full
```

This will:
1. Boot NEXUS Kernel on Windows
2. Connect to Ubuntu OpenShell gateway
3. Create a test sandbox
4. Execute code in sandbox
5. Log results to Zilliz + Supabase

---

## Part 4: Verify End-to-End Flow

### Check Zilliz Collections

```python
from cloud_edge import CloudEdgeManager

manager = CloudEdgeManager()
manager.initialize()

# Query recent events
col = manager.zilliz.get_collection("event_track", purpose="hot")
if col:
    results = col.query(expr="timestamp > 0", limit=5)
    print(f"Recent events: {len(results)}")

# Query governance logs
col = manager.zilliz.get_collection("governance_track", purpose="cold")
if col:
    results = col.query(expr="timestamp > 0", limit=5)
    print(f"Governance decisions: {len(results)}")
```

### Check Supabase Tables

Go to Supabase Dashboard → Table Editor:
- `trust_scores`: Should show agent trust updates
- `governance_log`: Should show KAIJU decisions

Or query via API:
```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
response = supabase.table("governance_log").select("*").limit(5).execute()
print(f"Recent decisions: {response.data}")
```

---

## Troubleshooting

### Windows Cannot Connect to Ubuntu VM

**Check firewall:**
```bash
# On Ubuntu VM
sudo ufw status
sudo ufw allow 8080/tcp
```

**Check OpenShell is running:**
```bash
# On Ubuntu VM
docker ps | grep gateway
openshell status
```

### Zilliz Connection Fails

**Verify credentials:**
- Token format must be `username:password` (no spaces)
- Check cluster is "Running" in Zilliz Console
- Ensure no IP whitelist blocking your location

**Test manually:**
```python
from pymilvus import connections
connections.connect(
    uri="https://in05-2a4b7e6226ae27e.serverless.aws-eu-central-1.cloud.zilliz.com",
    token="user:pass"
)
```

### Supabase Connection Fails

**Check project status:**
- Go to supabase.com/dashboard
- Ensure project is "Active" (not paused)
- Verify URL is correct (includes `.supabase.co`)

**Test manually:**
```python
from supabase import create_client
client = create_client("https://xyz.supabase.co", "your-key")
client.table("test").select("*").execute()
```

---

## Cost Breakdown

| Service | Tier | Monthly Cost | Notes |
|---------|------|--------------|-------|
| **Windows Local** | N/A | $0 | Your existing machine |
| **Ubuntu VM** | Oracle Free | $0 | 4 cores, 24GB RAM always free |
| **Zilliz HOT** | Serverless | $0 | Pay-per-use, free tier generous |
| **Zilliz COLD** | Free | $0 | Free tier includes 1M vectors |
| **Supabase** | Free | $0 | 500MB DB, 2GB bandwidth |
| **TOTAL** | | **$0/month** | Fully functional hybrid cloud |

---

## Next Steps

1. **Deploy Agent Swarms**: Use `python boot/nexus_boot.py` to start accepting agent proposals
2. **Configure Dashboards**: Connect PowerBI/Tableau to Supabase for real-time monitoring
3. **Enable Auto-Scaling**: Set up multiple Ubuntu VMs behind load balancer for high throughput
4. **Add Zo Computer**: Integrate Zo Computer bridge for additional remote execution capacity

---

## Security Best Practices

- **Never commit `.env`** to Git (already in `.gitignore`)
- **Use separate tokens** for dev/staging/production
- **Enable VM firewall** to only allow your Windows IP
- **Rotate Zilliz tokens** monthly via Zilliz Console
- **Monitor Supabase usage** to stay within free tier limits

---

**Your NEXUS Hybrid Cloud is now operational!** 🎉

Windows brain + Ubuntu muscle + Cloud memory = Infinite scale at zero cost.
