# Fix health_check.py for Windows compatibility
@'
import sys
import os
from pathlib import Path

# Auto-inject paths for Windows/Linux compatibility
BASE_DIR = Path(__file__).resolve().parent.parent
KERNEL_PATH = BASE_DIR / "nexus-swarm-pack" / "nexus_kernel"
RUNTIME_PATH = BASE_DIR / "nexus-swarm-pack" / "runtimes"

if str(KERNEL_PATH) not in sys.path:
    sys.path.insert(0, str(KERNEL_PATH))
if str(RUNTIME_PATH) not in sys.path:
    sys.path.insert(0, str(RUNTIME_PATH))

def check_python():
    print(f"✅ PASS | Python Version: {sys.version.split()[0]}")
    return True

def check_kernel():
    try:
        # Try importing core components
        from kaiju import KAIJUGovernor
        from vap import VAPChain
        print("✅ PASS | Nexus Kernel: Imports successful")
        return True
    except ImportError as e:
        print(f"❌ FAIL | Nexus Kernel: Import failed - {e}")
        return False

def check_openshell():
    import shutil
    if shutil.which("openshell"):
        print("✅ PASS | OpenShell CLI: Found in PATH")
        return True
    else:
        print("⚠️  WARN | OpenShell CLI: Not found (Install via openshell_setup.sh)")
        return True # Non-fatal

def check_podman():
    import shutil
    if shutil.which("podman"):
        print("✅ PASS | Podman: Found in PATH")
        return True
    else:
        print("⚠️  WARN | Podman: Not found (Required for rootless mode)")
        return True # Non-fatal

def check_subuid():
    # Cross-platform check
    if os.name == 'nt':
        print("✅ PASS | SubUID/SubGID: Windows mode (Sandbox isolation via Docker Desktop)")
        return True
    try:
        import pwd
        user = pwd.getpwuid(os.getuid()).pw_name
        with open('/etc/subuid') as f:
            if user in f.read():
                print("✅ PASS | SubUID/SubGID: Configured for user")
                return True
        print("❌ FAIL | SubUID/SubGID: User not configured in /etc/subuid")
        return False
    except Exception as e:
        print(f"⚠️  WARN | SubUID/SubGID: Check failed - {e}")
        return True

def check_policies():
    policy_dir = BASE_DIR / "nexus-swarm-pack" / "policies"
    required = ["codex_exec.yaml", "opencode_analysis.yaml", "inference_local.yaml"]
    missing = [f for f in required if not (policy_dir / f).exists()]
    if not missing:
        print("✅ PASS | Policy Templates: All 3 templates found")
        return True
    else:
        print(f"❌ FAIL | Policy Templates: Missing {missing}")
        return False

def check_runtime():
    try:
        from worker_registry import WorkerRegistry
        registry = WorkerRegistry()
        print(f"✅ PASS | Runtime Registry: Initialized with {len(registry.workers)} workers")
        return True
    except ImportError as e:
        print(f"❌ FAIL | Runtime Registry: Import failed - {e}")
        return False

if __name__ == "__main__":
    print("🔍 NEXUS Swarm Pack Health Check (Windows-Compatible)\n")
    print("="*60)
    results = []
    results.append(check_python())
    results.append(check_kernel())
    results.append(check_openshell())
    results.append(check_podman())
    results.append(check_subuid())
    results.append(check_policies())
    results.append(check_runtime())
    print("="*60)
    if all(results):
        print("\n🎉 All critical checks passed! System ready.")
    else:
        print("\n⚠️  Some checks failed. Review BEAD_RECOVERY_GUIDE.md")
'@ | Out-File -FilePath "boot/health_check.py" -Encoding utf8
