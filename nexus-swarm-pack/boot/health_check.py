#!/usr/bin/env python3
"""NEXUS Swarm Pack Health Check - Windows & Linux Compatible"""

import sys
import os
import subprocess
import shutil

# Inject local paths for standalone execution
script_dir = os.path.dirname(os.path.abspath(__file__))
pack_dir = os.path.dirname(script_dir)
if pack_dir not in sys.path:
    sys.path.insert(0, pack_dir)

# Windows compatibility for pwd module
try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False

def check_python_version():
    """Check Python version compatibility"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor} (requires 3.8+)"

def check_nexus_kernel():
    """Check if Nexus Kernel modules can be imported"""
    try:
        from nexus_kernel import kaiju, vap, token_guard, archivist
        return True, "All kernel modules loaded"
    except ImportError as e:
        return False, f"Kernel import failed: {str(e)}"

def check_openshell_cli():
    """Check if OpenShell CLI is available"""
    if shutil.which("openshell"):
        return True, "OpenShell CLI found"
    return False, "OpenShell CLI not found in PATH"

def check_podman():
    """Check if Podman is available"""
    if shutil.which("podman"):
        return True, "Podman found"
    return False, "Podman not found (required for rootless mode)"

def check_subuid_subgid():
    """Check subuid/subgid configuration (Linux only)"""
    if os.name == 'nt':  # Windows
        return True, "Windows detected (subuid/subgid not applicable)"
    
    if not HAS_PWD:
        return False, "pwd module not available"
    
    try:
        uid = os.getuid()
        username = pwd.getpwuid(uid).pw_name if HAS_PWD else "unknown"
        
        # Check /etc/subuid
        subuid_file = "/etc/subuid"
        if os.path.exists(subuid_file):
            with open(subuid_file, 'r') as f:
                content = f.read()
                if username in content:
                    return True, f"subuid/subgid configured for {username}"
        
        return False, f"No subuid entry found for {username}"
    except Exception as e:
        return False, f"Error checking subuid/subgid: {str(e)}"

def check_policy_templates():
    """Check if policy templates exist"""
    policies_dir = os.path.join(pack_dir, "policies")
    required_files = ["codex_exec.yaml", "opencode_analysis.yaml", "inference_local.yaml"]
    
    missing = []
    for file in required_files:
        if not os.path.exists(os.path.join(policies_dir, file)):
            missing.append(file)
    
    if missing:
        return False, f"Missing policies: {', '.join(missing)}"
    return True, "All policy templates found"

def check_runtime_registry():
    """Check if runtime registry can be imported"""
    try:
        from runtimes import worker_registry
        return True, "Runtime registry loaded"
    except ImportError as e:
        return False, f"Runtime registry error: {str(e)}"

def run_health_check(full=False):
    """Run all health checks"""
    print("🔍 NEXUS Swarm Pack Health Check\n")
    print("=" * 60)
    
    checks = [
        ("Python Version", check_python_version),
        ("Nexus Kernel", check_nexus_kernel),
        ("OpenShell CLI", check_openshell_cli),
        ("Podman", check_podman),
        ("SubUID/SubGID", check_subuid_subgid),
        ("Policy Templates", check_policy_templates),
        ("Runtime Registry", check_runtime_registry),
    ]
    
    passed = 0
    failed = 0
    
    for name, check_func in checks:
        try:
            success, message = check_func()
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} | {name}: {message}")
            if success:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ FAIL | {name}: Unexpected error - {str(e)}")
            failed += 1
    
    print("=" * 60)
    print(f"\nResults: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\n⚠️  Some checks failed. Review BEAD_RECOVERY_GUIDE.md for solutions.")
        return False
    else:
        print("\n🎉 All checks passed! System ready for deployment.")
        return True

if __name__ == "__main__":
    full_check = "--full" in sys.argv
    success = run_health_check(full=full_check)
    sys.exit(0 if success else 1)
