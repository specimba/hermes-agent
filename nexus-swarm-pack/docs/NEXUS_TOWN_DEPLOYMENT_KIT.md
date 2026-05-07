🏗️ NEXUS Town Deployment Kit (Unified)
Version: 1.0-RC1
Target: Gastown Towns & Rigs
Branch: QWENcoder
🚀 Part 1: Unified Mega-Task (Options 1 + 2 Combined)
Copy this entire section into the "Task" field when creating a new Town or Rig.
Role: NEXUS Swarm Operator
Mission: Deploy NEXUS Swarm Pack v1.0-RC1, Execute Intelligence Scan, Harden Infrastructure, and Scale to Multi-Node.
Mode: Full Autonomous Execution (Chain A → C → B)
🛠️ Pre-Flight Check
Ensure these Environment Variables are set in your Town/Rig context:
ZILLIZ_SERVERLESS_URI
ZILLIZ_SERVERLESS_USER
ZILLIZ_SERVERLESS_PASSWORD
ZILLIZ_TOWN_URI
ZILLIZ_TOWN_TOKEN
GITHUB_TOKEN (For PR creation)
🟢 PHASE A: Intelligence & Governance
Scan: Navigate to hermes-agent/hermes_cli. Scan for functions missing docstrings. Identify top 3 critical gaps.
Log Memory: Use memory.zilliz_client to log findings to nexus_events collection.
Run this command:
python -c "from memory.zilliz_client import get_client; c = get_client(); print('Logged to:', c.list_collections())"
Governance: Draft a KAIJU proposal to fix the top 3 issues. Submit as a Pull Request to QWENcoder.
Checkpoint: Report VAP Hash and PR URL.
🟡 PHASE C: Infrastructure Hardening
Install OpenShell:
Run this command:
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh && export PATH="$HOME/.local/bin:$PATH"
Verify: Run openshell --version and openshell doctor check.
(If Podman missing: sudo apt-get install -y podman uidmap)
Health Check: Run python boot/health_check.py --full. Target: 6/7 Passed.
🔵 PHASE B: Swarm Scaling
Spawn Nodes: Simulate two workers:
Node Alpha (Security): Scan for 5 bug patterns (path traversal, input validation). Log to nexus_events.
Node Beta (Docs): Generate docstrings for Phase A findings. Create a patch file.
Sync Memory: Verify both nodes can read/write to the shared nexus_events and nexus_governance collections.
📝 Final Report Template
Output this exact block upon completion:
🏁 NEXUS Completion Report
Phase A: [Count] functions scanned. [List] missing docstrings. PR: [Link]
Phase C: OpenShell [Version]. Health: [X/7].
Phase B: Alpha [Status], Beta [Status]. Shared Memory: [Yes/No].
System: Kernel [Active/Dead], Memory [Synced/Drift], VAP Length [X].
Conclusion: NEXUS Swarm Pack v1.0-RC1 is [Operational/Failed].
🏘️ Part 2: New Rig Deployment Template
Use this template when adding a new Rig to an existing Town (e.g., nexus-town-03).
📋 Rig Configuration
Rig Name: nexus-rig-[ROLE] (e.g., nexus-rig-security, nexus-rig-docs)
Git URL: https://github.com/specimba/hermes-agent.git
Branch: QWENcoder
Platform Integration: (Leave default/None unless specific cloud needed)
🧬 Initialization Task
Paste this into the Rig's first task:
"You are a new worker node in the NEXUS Swarm.
Clone: git clone --branch QWENcoder --depth 1 https://github.com/specimba/hermes-agent.git
Setup: cd hermes-agent/nexus-swarm-pack && pip install pymilvus python-dotenv
Connect: Ensure .env contains the Town's Zilliz credentials.
Sync: python -c "from memory.zilliz_client import get_client; print(get_client().list_collections())"
Report: Confirm you are connected to the Town's nexus_events and nexus_governance collections and ready for assignments."
🔗 Topology Verification
After creation, verify in the Town Dashboard:
System Topology: Should show hermes-agent (Mayor) connected to nexus-rig-[ROLE] (Worker).
Status: Green "Connected" indicator.
Activity: Watch for the initial "Sync" log entry in the Feed.
⚠️ Troubleshooting
Error
Solution
Connection Refused
Check firewall allows outbound HTTPS to Zilliz AWS endpoints.
Auth Failed
Rotate Zilliz tokens in Cloud Console and update Env Vars.
Git Clone Fail
Verify GITHUB_TOKEN has repo scope.
End of Deployment Kit