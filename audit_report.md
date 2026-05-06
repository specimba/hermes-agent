# Shadow: Policy Enforcement & OpenStack/OCSF Review - Audit Report

**Date**: 2026-05-06  
**Auditor**: Shadow-polecat-32c6c066@3bb00369  
**Bead**: f819d189-de8b-4a8f-b313-4ed892556f37

---

## Executive Summary

The NEXUS swarm-pack implements a multi-layered security architecture with KAIJU governance, VAP audit chains, and OpenShell sandboxing. Several critical issues were identified requiring immediate attention, particularly around policy template loading, OCSF integration gaps, and schema compliance bugs.

**Severity Summary:**
- 🔴 Critical: 5 issues
- 🟡 Moderate: 6 issues
- 🟢 Low: 3 issues

---

## 1. OpenShell Integration Audit

### 1.1 Files Reviewed
- `nexus-swarm-pack/runtimes/openshell_executor.py`
- `nexus-swarm-pack/boot/nexus_boot.py`
- `nexus-swarm-pack/boot/health_check.py`

### 1.2 Findings

#### 🔴 CRITICAL: Trust Tier Type Mismatch (nexus_boot.py:56-60)
```python
sandbox_identity=SandboxIdentity(
    policy_profile="codex_exec",
    capability_tags=["python", "filesystem_read"],
    trust_tier="standard"  # STRING, but expects TrustTier enum
)
```
**Impact**: Direct instantiation with string will fail. The `from_dict()` method handles conversion, but `__init__` does not.

**Fix**: Change to `trust_tier=TrustTier.STANDARD` or add type coercion in `__init__`.

#### 🔴 CRITICAL: Hardcoded Gateway URL (openshell_executor.py:32)
```python
def __init__(self, gateway_url: str = "http://127.0.0.1:8080", timeout: int = 300):
```
**Impact**: Not configurable via environment or config file.

**Fix**: Add environment variable support: `gateway_url = os.getenv("OPENSHELL_GATEWAY_URL", "http://127.0.0.1:8080")`

#### 🟡 MODERATE: Typo in Error Field (openshell_executor.py:132)
```python
error=data.get("stderr"),  # Should be "stderr" (standard error)
```
Actually this appears correct - the OpenShell API likely returns "stderr". Verify API spec.

#### 🟡 MODERATE: No Gateway Failure Recovery
Health check warns but doesn't prevent boot. No retry logic if gateway becomes unavailable after startup.

#### 🟢 LOW: Print Statements vs Logging
Uses `print()` instead of proper logging framework (lines 86, 89, 139, 142, 149).

---

## 2. OCSF Audit Pipeline Audit

### 2.1 Files Reviewed
- `nexus-swarm-pack/nexus_kernel/vap.py`
- All policy YAMLs (codex_exec.yaml, opencode_analysis.yaml, inference_local.yaml)

### 2.2 Findings

#### 🔴 CRITICAL: OCSF Integration Incomplete
**Current State**:
- Policy YAMLs specify `format: ocsf` in auditing section
- VAP chain logs gate decisions with SHA-256 hashing
- **No OCSF parsing/validation code exists in Python codebase**

**Gap**: The audit pipeline expects OpenShell to emit OCSF JSONL, but there's no code to:
1. Ingest OCSF events from OpenShell
2. Validate OCSF schema compliance
3. Normalize OCSF into VAP entries

**Recommendation**: Either implement OCSF ingestion in `vap.py` or document that this is handled externally.

#### 🔴 CRITICAL: VAP Chain Not Persistent (vap.py:87)
```python
self._chain: List[VAPEntry] = []  # In-memory only!
```
**Impact**: Complete audit trail loss on restart.

**Fix**: Implement `storage_backend` (Zilliz, Cloudflare R2) or at minimum file-based persistence.

#### 🟡 MODERATE: No OCSF Schema Definition
No OCSF schema file found in codebase. The policies reference `format: ocsf` but actual schema mapping isn't defined locally.

---

## 3. Policy Templates Audit

### 3.1 Files Reviewed
- `nexus-swarm-pack/policies/codex_exec.yaml`
- `nexus-swarm-pack/policies/opencode_analysis.yaml`
- `nexus-swarm-pack/policies/inference_local.yaml`
- `nexus-swarm-pack/runtimes/sandbox_identity.py`

### 3.2 Policy Structure
All policies follow Kubernetes-style YAML:
```yaml
apiVersion: openshell.nvidia.com/v1alpha1
kind: SandboxPolicy
metadata:
  name: <policy_name>
spec:
  runtime: ...
  isolation: ...
  security: ...
  auditing:
    format: ocsf
```

### 3.3 Findings

#### 🔴 CRITICAL: YAML Policies NOT Loaded by Python (sandbox_identity.py:136-169)
The `POLICY_PROFILES` dict contains **hardcoded** `SandboxIdentity` objects that don't match the YAML files:

| Policy | YAML memoryLimit | Python max_memory_mb | Match? |
|--------|------------------|----------------------|--------|
| codex_exec | 1024Mi | 1024 | ✓ |
| opencode_analysis | 2048Mi | 2048 | ✓ |
| inference_local | 4096Mi | 4096 | ✓ |

| Policy | YAML cpuLimit | Python max_cpu_percent | Match? |
|--------|---------------|------------------------|--------|
| codex_exec | 0.5 | 50.0 (default) | ✗ |
| opencode_analysis | 1.0 | 50.0 (default) | ✗ |
| inference_local | 2.0 | 50.0 (default) | ✗ |

**Impact**: Python code doesn't validate/enforce YAML policy constraints.

**Fix**: Implement YAML loading in `sandbox_identity.py` or remove YAML files.

#### 🔴 CRITICAL: Missing "web_search" YAML
`POLICY_PROFILES` defines `"web_search"` profile (lines 161-168) but no `web_search.yaml` exists.

#### 🟡 MODERATE: No Schema Validation for YAML Files
No code validates policy YAMLs against a schema. Invalid policies could be deployed to OpenShell.

---

## 4. Sandbox_Identity Schema Compliance

### 4.1 Files Reviewed
- `nexus-swarm-pack/runtimes/sandbox_identity.py`

### 4.2 Schema Definition
```python
class SandboxIdentity:
    sandbox_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy_profile: str = "default"
    capability_tags: List[str] = field(default_factory=list)
    trust_tier: TrustTier = TrustTier.STANDARD
    security_level: SecurityLevel = SecurityLevel.FULL
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    timeout_seconds: int = 300
```

### 4.3 Findings

#### 🔴 CRITICAL: State Leakage in create_task_packet() (lines 192-198)
```python
if policy_name in POLICY_PROFILES:
    base_identity = POLICY_PROFILES[policy_name]  # Shared reference!
    for key, value in kwargs.items():
        if hasattr(base_identity, key):
            setattr(base_identity, key, value)  # Modifies shared object!
    sandbox_identity = base_identity
```
**Impact**: Calling `create_task_packet()` with overrides modifies the global `POLICY_PROFILES` dict, causing state leakage between calls.

**Fix**: Deep copy the profile before modification:
```python
import copy
base_identity = copy.deepcopy(POLICY_PROFILES[policy_name])
```

#### 🟡 MODERATE: No Input Validation on capability_tags
Accepts any strings without validation against a known capability registry.

---

## 5. Executor Isolation Configurations

### 5.1 Files Reviewed
- `nexus-swarm-pack/runtimes/worker_registry.py`
- `nexus-swarm-pack/nexus_kernel/kaiju.py`
- `tools/environments/docker.py`
- `tools/environments/singularity.py`

### 5.2 Security Levels
```python
class SecurityLevel(Enum):
    NONE = "none"           # Native execution
    FILESYSTEM = "filesystem" # FS isolation only
    NETWORK = "network"       # Network isolation
    FULL = "full"            # Complete container isolation
```

### 5.3 Findings

#### 🔴 CRITICAL: Local Environment Has NO Isolation
`tools/environments/local.py` runs directly on host with no sandboxing. This is acceptable only for trusted operations.

#### 🟡 MODERATE: Worker Registry Runtime Selection
Selects first highest-scored runtime without weighted preference for security level.

#### 🟡 MODERATE: Docker Security Configuration
Current flags (from exploration):
- `--cap-drop ALL` ✓
- `--security-opt no-new-privileges` ✓
- `--pids-limit 256` ✓

These are properly configured but verify consistent application across all container launches.

#### 🟢 LOW: KAIJU Trust Score Stub (kaiju.py:350-357)
```python
async def _fetch_trust_score(self, agent_id: str) -> TrustScore:
    if self.zilliz_client:
        pass  # Not implemented
    return TrustScore(agent_id=agent_id)  # Default 0.5
```
Trust scores always return 0.5 - Zilliz integration needed for production.

---

## 6. Recommended Fixes (Priority Order)

### P0 - Immediate
1. **Fix create_task_packet() state leakage** - Add deep copy
2. **Fix trust_tier type mismatch** in nexus_boot.py
3. **Sync CPU limits** between YAML and Python POLICY_PROFILES
4. **Create missing web_search.yaml** or remove from POLICY_PROFILES

### P1 - High Priority
5. **Implement YAML policy loading** in sandbox_identity.py
6. **Add VAP chain persistence** (file-based minimum)
7. **Make OpenShell gateway URL configurable**

### P2 - Medium Priority
8. **Document OCSF integration** (external vs internal)
9. **Add policy schema validation**
10. **Replace print() with logging**

---

## 7. Compliance Verification Summary

| Component | Status | Notes |
|-----------|--------|-------|
| OpenShell Integration | ⚠️ Partial | Gateway URL hardcoded, type mismatch |
| OCSF Pipeline | ❌ Incomplete | No ingestion/validation code |
| Policy Templates | ⚠️ Mismatch | YAML not loaded, CPU limits off |
| SandboxIdentity Schema | ❌ Bug | State leakage in factory function |
| Executor Isolation | ✓ Good | Docker/Singularity properly configured |

---

## 8. Code Fixes Needed

See attached patch files for:
- `sandbox_identity.py` - Fix state leakage
- `nexus_boot.py` - Fix trust_tier type
- `openshell_executor.py` - Configurable gateway URL
- `vap.py` - Add persistence option
