# 🚀 Gastown Autonomous Deployment Guide

**Target:** NEXUS Swarm Pack v1.0-RC1 (Hybrid Memory Layer)  
**Branch:** QWENcoder  
**Runtime:** Linux/Ubuntu (Gastown Sandbox)

---

## 📋 Pre-Requisites
Ensure your Gastown task has these **Environment Variables** set:
- ZILLIZ_SERVERLESS_URI
- ZILLIZ_SERVERLESS_USER
- ZILLIZ_SERVERLESS_PASSWORD
- ZILLIZ_TOWN_URI
- ZILLIZ_TOWN_TOKEN

---

## 🚀 Deployment Steps (Copy-Paste One-Liners for Linux Agent)

### Phase 1: Clone Repository
git clone --branch QWENcoder --depth 1 https://github.com/specimba/hermes-agent.git /tmp/nexus-test && cd /tmp/nexus-test/nexus-swarm-pack

### Phase 2: Install Dependencies
pip install --quiet pymilvus supabase python-dotenv && echo "✅ Dependencies installed"

### Phase 3: Create .env File
cat > .env <<EOF
ZILLIZ_SERVERLESS_URI=$ZILLIZ_SERVERLESS_URI
ZILLIZ_SERVERLESS_USER=$ZILLIZ_SERVERLESS_USER
ZILLIZ_SERVERLESS_PASSWORD=$ZILLIZ_SERVERLESS_PASSWORD
ZILLIZ_TOWN_URI=$ZILLIZ_TOWN_URI
ZILLIZ_TOWN_TOKEN=$ZILLIZ_TOWN_TOKEN
EOF

### Phase 4: Run Health Check
python boot/health_check.py --full

### Phase 5: Test Zilliz Connections
python boot/test_zilliz_connection.py

### Phase 6: Boot NEXUS Kernel
python boot/nexus_boot.py

---

## 📊 Expected Output
- **Health Check:** 5/7 passed (OpenShell/Podman warnings expected)
- **Zilliz Test:** Both 
exus_events and 
exus_governance collections found
- **Boot:** "Ready for Swarm Operations"

---

## 🐛 Troubleshooting
| Error | Fix |
|-------|-----|
| ModuleNotFoundError: pymilvus | Re-run Phase 2 |
| UNAUTHENTICATED | Check env vars in Phase 3 |
| Connection timed out | Verify firewall allows outbound HTTPS |

---

## 📝 Report Template
**Deployment Status:** ✅ SUCCESS / ❌ FAILED  
**Health Check:** X/7 passed  
**Zilliz Collections:** [list found collections]  
**Boot Status:** [Complete/Failed]  
**Logs:** [Paste any error messages]
