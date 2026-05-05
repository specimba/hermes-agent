# 🚀 NEXUS Swarm Pack: Mega-Task Directive (Autonomous Run)

**Target:** Gastown Mayor & Polecat Agents  
**Branch:** `QWENcoder`  
**Priority:** CRITICAL  
**Mode:** Full Autonomous Execution (Chain A → C → B)  
**Version:** 1.0-RC1  

---

## 📋 Mission Overview
You are tasked with deploying, hardening, and scaling the **NEXUS Swarm Pack v1.0-RC1**. This is a multi-phase autonomous run. Do not stop for clarification unless a **CRITICAL BLOCKER** occurs. Follow the phases sequentially.

**Execution Order:**
1.  **Phase A:** First Intelligence Task (Validate Memory & Governance)
2.  **Phase C:** Infrastructure Hardening (Install OpenShell Sandbox)
3.  **Phase B:** Swarm Scaling (Spawn 2 Additional Nodes)

---

## 🛠️ Pre-Flight Check
Ensure these Environment Variables are active in your context:
- `ZILLIZ_SERVERLESS_URI`
- `ZILLIZ_SERVERLESS_USER`
- `ZILLIZ_SERVERLESS_PASSWORD`
- `ZILLIZ_TOWN_URI`
- `ZILLIZ_TOWN_TOKEN`
- `GITHUB_TOKEN` (For PR creation)

---

## 🟢 PHASE A: First Intelligence Task (Memory & Governance Validation)
**Goal:** Prove the Hybrid Memory Layer works by logging real data and submitting a governance proposal.

### Step A1: Repository Scan
1. Navigate to `hermes-agent/hermes_cli`.
2. Scan all `.py` files for functions missing docstrings.
3. Identify the **top 3** most critical functions lacking documentation.

### Step A2: Log to Zilliz Memory (Serverless Cluster)
Write a Python script using `memory.zilliz_client` to log your findings:
- Import `get_client` from `memory.zilliz_client`.
- Create an event data dictionary: `{"type": "CODE_SCAN", "findings": ["func_1", "func_2", "func_3"], "timestamp": "2026-05-05T..."}`.
- Insert into `nexus_events` collection.
- Record the ID or Hash of this logged event.

### Step A3: Submit Governance Proposal
1. Draft a `KAIJU` proposal to fix the top 3 issues.
2. Action: `create_pull_request`.
3. Target: `hermes-agent:QWENcoder`.
4. Body: "Automated docstring fix by NEXUS Swarm Agent."
5. Submit the proposal via the Governor.

**🛑 CHECKPOINT A:** Report the **VAP Hash** of your logged event and the **PR URL** before proceeding to Phase C.

---

## 🟡 PHASE C: Infrastructure Hardening (OpenShell Installation)
**Goal:** Eliminate the "OpenShell CLI not found" warning.

### Step C1: Install OpenShell CLI
Run: `curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh`
Then: `export PATH="$HOME/.local/bin:$PATH"`

### Step C2: Verify Installation
Run: `openshell --version` and `openshell doctor check`.
If `doctor` reports missing Docker/Podman, install Podman rootless: `sudo apt-get update && sudo apt-get install -y podman uidmap` then `podman system service --time=0 &`.

### Step C3: Re-Run Health Check
Run: `python boot/health_check.py --full` from the `nexus-swarm-pack` directory.
**Success Criteria:** `OpenShell CLI` check must now show ✅ PASS.

**🛑 CHECKPOINT C:** Confirm OpenShell is installed.

---

## 🔵 PHASE B: Swarm Scaling (Spawn 2 Additional Nodes)
**Goal:** Demonstrate multi-agent coordination.

### Step B1: Define Worker Roles
1. **Node Alpha (Code Reviewer):** Focus on `hermes_cli` logic errors.
2. **Node Beta (Documentation Specialist):** Focus on `docs/` and README updates.

### Step B2: Initialize Nodes with Shared Memory
In both node scripts:
- Import `get_client` from `memory.zilliz_client`.
- Call `client.list_collections()`.
- Assert `nexus_events` is present.

### Step B3: Assign Parallel Tasks
- **Task Alpha:** Find 5 potential bug patterns in `hermes_cli` and log them to `nexus_events` with tag `BUG_CANDIDATE`.
- **Task Beta:** Generate docstrings for the 3 functions identified in Phase A and prepare a patch.

---

## 📝 Final Master Report Template
Once all phases are complete, output this exact block:

# 🏁 NEXUS Mega-Task Completion Report

## Phase A: Intelligence
- **Functions Scanned:** [Count]
- **Missing Docstrings:** [List Top 3]
- **Zilliz Event ID:** [ID/Hash]
- **Governance PR URL:** [Link]

## Phase C: Hardening
- **OpenShell Version:** [Version]
- **Health Check Status:** [X/7 Passed]
- **Sandbox Mode:** [Enabled/Disabled]

## Phase B: Scaling
- **Node Alpha Status:** [Complete]
- **Node Beta Status:** [Complete]
- **Shared Memory Verified:** [Yes/No]
- **Total Events Logged:** [Count]

## 🧬 System State
- **Kernel:** Active (Port 7352)
- **Memory:** Dual-Cluster Synced
- **Governance:** KAIJU Active
- **Audit Chain:** VAP Length [X]

**Conclusion:** NEXUS Swarm Pack v1.0-RC1 is fully operational, hardened, and scaled.

---

## ⚠️ Error Handling Protocol
- **If Zilliz Connection Fails:** Retry once, then check env vars. If still failing, abort and report.
- **If OpenShell Install Fails:** Log error, skip to Phase B (non-fatal), note in final report.
- **If Git Push Fails:** Check `GITHUB_TOKEN`. Retry with `--force` only if safe.

**BEGIN EXECUTION NOW.**

Regards,
speci