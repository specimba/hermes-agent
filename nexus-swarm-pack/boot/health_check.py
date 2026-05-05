#!/usr/bin/env python3
"""
NEXUS Swarm Pack - Health Check Tool
Pre-flight verification for OpenShell integration
"""

import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Verify Python 3.10+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        return False, f"Python 3.10+ required, found {version.major}.{version.minor}"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"

def check_nexus_kernel():
    """Verify Nexus OS kernel components"""
    try:
        from nexus_kernel.kaiju import KAIJUGovernor
        from nexus_kernel.vap import VAPChain
        from nexus_kernel.token_guard import TokenGuard
        from nexus_kernel.archivist import ArchivistV5
        return True, "All kernel modules imported successfully"
    except ImportError as e:
        return False, f"Kernel import failed: {e}"

def check_openshell_cli():
    """Check if OpenShell CLI is available"""
    openshell_path = shutil.which('openshell')
    if openshell_path:
        try:
            result = subprocess.run(['openshell', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return True, f"OpenShell CLI found: {result.stdout.strip()}"
        except Exception as e:
            return True, f"OpenShell CLI found but version check failed: {e}"
    return False, "OpenShell CLI not found in PATH"

def check_podman():
    """Check Podman availability for rootless mode"""
    podman_path = shutil.which('podman')
    if podman_path:
        try:
            result = subprocess.run(['podman', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return True, f"Podman found: {result.stdout.strip()}"
        except Exception as e:
            return True, f"Podman found but version check failed: {e}"
    return False, "Podman not found (required for rootless mode)"

def check_subuid():
    """Check if subuid/subgid are configured"""
    import pwd
    username = pwd.getpwuid(os.getuid()).pw_name
    
    try:
        with open('/etc/subuid', 'r') as f:
            for line in f:
                if line.startswith(f'{username}:'):
                    with open('/etc/subgid', 'r') as g:
                        for gid_line in g:
                            if gid_line.startswith(f'{username}:'):
                                return True, f"subuid/subgid configured for {username}"
        return False, f"No subuid/subgid entries for user {username}"
    except FileNotFoundError:
        return False, "/etc/subuid or /etc/subgid not found"

def check_policies():
    """Verify policy templates exist"""
    policies_dir = Path(__file__).parent.parent / 'policies'
    required_policies = ['codex_exec.yaml', 'opencode_analysis.yaml', 'inference_local.yaml']
    
    missing = []
    for policy in required_policies:
        if not (policies_dir / policy).exists():
            missing.append(policy)
    
    if missing:
        return False, f"Missing policies: {', '.join(missing)}"
    return True, f"All {len(required_policies)} policy templates found"

def check_runtimes():
    """Verify runtime registry"""
    try:
        from runtimes.openshell_executor import OpenShellExecutor
        from runtimes import WorkerRegistry
        registry = WorkerRegistry.get_instance()
        workers = registry.list_workers()
        return True, f"Worker registry initialized with {len(workers)} workers"
    except Exception as e:
        return False, f"Runtime registry error: {e}"

def run_full_check():
    """Run all health checks"""
    import os
    
    checks = [
        ("Python Version", check_python_version),
        ("Nexus Kernel", check_nexus_kernel),
        ("OpenShell CLI", check_openshell_cli),
        ("Podman", check_podman),
        ("SubUID/SubGID", check_subuid),
        ("Policy Templates", check_policies),
        ("Runtime Registry", check_runtimes),
    ]
    
    print("🔍 NEXUS Swarm Pack Health Check\n")
    print("=" * 60)
    
    all_passed = True
    for name, check_func in checks:
        try:
            passed, message = check_func()
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} | {name}: {message}")
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"❌ FAIL | {name}: Error - {e}")
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All checks passed! System ready for deployment.")
        print("\nNext steps:")
        print("  1. bash boot/openshell_setup.sh --mode rootless")
        print("  2. python boot/nexus_boot.py")
        return 0
    else:
        print("\n⚠️  Some checks failed. Review BASE_MODE_GUIDE.md for solutions.")
        return 1

if __name__ == '__main__':
    sys.exit(run_full_check())
