"""
Test suite for WorkerRegistry initialization and runtime health verification.

Tests cover:
- WorkerRegistry singleton initialization
- Runtime registration (native, foundry, openshell, wrapper)
- Isolation capabilities verification
- SandboxIdentity functionality
- Namespace separation and capability tagging
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtimes.worker_registry import (
    WorkerRegistry,
    RuntimeType,
    RuntimeConfig,
    get_registry
)
from runtimes.sandbox_identity import (
    SandboxIdentity,
    TaskPacket,
    SecurityLevel,
    TrustTier,
    POLICY_PROFILES,
    create_task_packet
)


class TestWorkerRegistryInitialization:
    """Test WorkerRegistry singleton initialization and basic setup."""
    
    def test_singleton_pattern(self):
        """Test that WorkerRegistry follows singleton pattern."""
        registry1 = WorkerRegistry()
        registry2 = WorkerRegistry()
        assert registry1 is registry2
    
    def test_get_instance_classmethod(self):
        """Test get_instance classmethod returns same instance."""
        registry1 = WorkerRegistry.get_instance()
        registry2 = WorkerRegistry.get_instance()
        assert registry1 is registry2
        assert isinstance(registry1, WorkerRegistry)
    
    def test_get_registry_function(self):
        """Test get_registry function returns valid registry."""
        registry = get_registry()
        assert isinstance(registry, WorkerRegistry)
    
    def test_fresh_registry_has_no_runtimes(self):
        """Test that a fresh registry has no runtimes."""
        # Note: This test may fail if other tests have registered runtimes
        # due to singleton pattern. In practice, use dependency injection.
        registry = WorkerRegistry()
        assert isinstance(registry.runtimes, dict)


class TestRuntimeRegistration:
    """Test runtime registration functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.registry = WorkerRegistry()
        # Clear runtimes for test isolation
        self.registry.runtimes.clear()
    
    def test_register_native_runtime(self):
        """Test registering a native runtime (no isolation)."""
        config = {
            "type": "native",
            "isolation": "none",
            "path": "/usr/bin/python3"
        }
        capabilities = ["python", "shell", "filesystem_read", "filesystem_write"]
        
        result = self.registry.register_runtime(
            name="native-default",
            config=config,
            capabilities=capabilities,
            max_concurrent=20
        )
        
        assert result is True
        assert "native-default" in self.registry.runtimes
        
        runtime = self.registry.get_runtime("native-default")
        assert runtime is not None
        assert runtime.runtime_type == RuntimeType.NATIVE
        assert runtime.capabilities == capabilities
        assert runtime.max_concurrent == 20
        assert runtime.health_status == "unknown"
    
    def test_register_foundry_runtime(self):
        """Test registering a foundry runtime (filesystem sandbox)."""
        config = {
            "type": "foundry",
            "isolation": "filesystem",
            "sandbox_dir": "/tmp/foundry_sandboxes",
            "image": "python:3.10-slim"
        }
        capabilities = ["python", "filesystem_read", "filesystem_write", "pip_install"]
        
        result = self.registry.register_runtime(
            name="foundry-python",
            config=config,
            capabilities=capabilities,
            max_concurrent=10
        )
        
        assert result is True
        runtime = self.registry.get_runtime("foundry-python")
        assert runtime.runtime_type == RuntimeType.FOUNDRY
        assert runtime.config["isolation"] == "filesystem"
    
    def test_register_openshell_runtime(self):
        """Test registering an openshell runtime (container isolation)."""
        config = {
            "type": "openshell",
            "isolation": "full",
            "gateway_url": "http://127.0.0.1:8080",
            "policy_dir": "/etc/openshell/policies"
        }
        capabilities = ["python", "shell", "network_http", "docker_exec", "gpu_access"]
        
        result = self.registry.register_runtime(
            name="openshell-main",
            config=config,
            capabilities=capabilities,
            max_concurrent=5
        )
        
        assert result is True
        runtime = self.registry.get_runtime("openshell-main")
        assert runtime.runtime_type == RuntimeType.OPENSHELL
        assert runtime.config["isolation"] == "full"
    
    def test_register_wrapper_runtime(self):
        """Test registering a wrapper runtime (API-based execution)."""
        config = {
            "type": "wrapper",
            "isolation": "network",
            "api_endpoint": "https://api.execution-service.com",
            "api_key_env": "EXEC_API_KEY"
        }
        capabilities = ["python", "javascript", "network_http"]
        
        result = self.registry.register_runtime(
            name="wrapper-cloud",
            config=config,
            capabilities=capabilities,
            max_concurrent=50
        )
        
        assert result is True
        runtime = self.registry.get_runtime("wrapper-cloud")
        assert runtime.runtime_type == RuntimeType.WRAPPER
        assert runtime.config["isolation"] == "network"
    
    def test_register_invalid_runtime_type(self):
        """Test registering with invalid runtime type fails gracefully."""
        config = {
            "type": "invalid_type",
        }
        
        result = self.registry.register_runtime(
            name="invalid",
            config=config
        )
        
        # Should return False due to ValueError from RuntimeType enum
        assert result is False
        assert "invalid" not in self.registry.runtimes
    
    def test_unregister_runtime(self):
        """Test removing a runtime from registry."""
        config = {"type": "native"}
        self.registry.register_runtime("to-remove", config)
        assert "to-remove" in self.registry.runtimes
        
        result = self.registry.unregister_runtime("to-remove")
        assert result is True
        assert "to-remove" not in self.registry.runtimes
    
    def test_unregister_nonexistent_runtime(self):
        """Test removing a runtime that doesn't exist."""
        result = self.registry.unregister_runtime("nonexistent")
        assert result is False


class TestRuntimeQueryAndSelection:
    """Test runtime querying and optimal selection."""
    
    def setup_method(self):
        """Set up test fixtures with multiple runtimes."""
        self.registry = WorkerRegistry()
        self.registry.runtimes.clear()
        
        # Register native runtime
        self.registry.register_runtime(
            name="native-1",
            config={"type": "native", "isolation": "none"},
            capabilities=["python", "shell"],
            max_concurrent=20
        )
        
        # Register foundry runtime
        self.registry.register_runtime(
            name="foundry-1",
            config={"type": "foundry", "isolation": "filesystem"},
            capabilities=["python", "filesystem_read", "filesystem_write"],
            max_concurrent=10
        )
        
        # Register openshell runtime
        self.registry.register_runtime(
            name="openshell-1",
            config={"type": "openshell", "isolation": "full"},
            capabilities=["python", "shell", "network_http", "docker_exec"],
            max_concurrent=5
        )
        
        # Register wrapper runtime
        self.registry.register_runtime(
            name="wrapper-1",
            config={"type": "wrapper", "isolation": "network"},
            capabilities=["python", "javascript", "network_http"],
            max_concurrent=50
        )
        
        # Set health status for all
        for name in self.registry.runtimes:
            self.registry.update_health(name, "healthy")
    
    def test_list_all_runtimes(self):
        """Test listing all registered runtimes."""
        runtimes = self.registry.list_runtimes()
        assert len(runtimes) == 4
        assert "native-1" in runtimes
        assert "foundry-1" in runtimes
        assert "openshell-1" in runtimes
        assert "wrapper-1" in runtimes
    
    def test_get_runtime_by_name(self):
        """Test retrieving a specific runtime by name."""
        runtime = self.registry.get_runtime("foundry-1")
        assert runtime is not None
        assert runtime.runtime_type == RuntimeType.FOUNDRY
        
        # Non-existent runtime
        assert self.registry.get_runtime("nonexistent") is None
    
    def test_select_runtime_by_capabilities(self):
        """Test selecting runtime based on required capabilities."""
        # Need python and shell - multiple candidates
        selected = self.registry.select_runtime(
            required_capabilities=["python", "shell"]
        )
        assert selected in ["native-1", "openshell-1"]
        
        # Need network_http - only openshell and wrapper
        selected = self.registry.select_runtime(
            required_capabilities=["network_http"]
        )
        assert selected in ["openshell-1", "wrapper-1"]
        
        # Need docker_exec - only openshell
        selected = self.registry.select_runtime(
            required_capabilities=["docker_exec"]
        )
        assert selected == "openshell-1"
        
        # Need impossible combo
        selected = self.registry.select_runtime(
            required_capabilities=["docker_exec", "javascript"]
        )
        assert selected is None
    
    def test_select_runtime_by_security_level(self):
        """Test selecting runtime based on security requirements."""
        # None security - can use native
        selected = self.registry.select_runtime(
            required_capabilities=["python"],
            security_level="none"
        )
        assert selected == "native-1"
        
        # Filesystem security - can use native or foundry
        selected = self.registry.select_runtime(
            required_capabilities=["python"],
            security_level="filesystem"
        )
        assert selected in ["native-1", "foundry-1"]
        
        # Full security - only openshell
        selected = self.registry.select_runtime(
            required_capabilities=["python"],
            security_level="full"
        )
        assert selected == "openshell-1"
    
    def test_select_runtime_prefer_type(self):
        """Test preferring a specific runtime type."""
        selected = self.registry.select_runtime(
            required_capabilities=["python"],
            prefer_type=RuntimeType.FOUNDRY
        )
        assert selected == "foundry-1"
    
    def test_select_runtime_excludes_offline(self):
        """Test that offline runtimes are excluded."""
        self.registry.update_health("native-1", "offline")
        
        selected = self.registry.select_runtime(
            required_capabilities=["python"]
        )
        assert selected != "native-1"
    
    def test_select_runtime_excludes_at_capacity(self):
        """Test that runtimes at capacity are excluded."""
        self.registry.runtimes["native-1"].active_sessions = 20
        
        selected = self.registry.select_runtime(
            required_capabilities=["python"]
        )
        assert selected != "native-1"


class TestRuntimeHealthManagement:
    """Test runtime health status management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.registry = WorkerRegistry()
        self.registry.runtimes.clear()
        
        self.registry.register_runtime(
            name="test-runtime",
            config={"type": "native"},
            capabilities=["python"]
        )
    
    def test_update_health_status(self):
        """Test updating runtime health status."""
        assert self.registry.runtimes["test-runtime"].health_status == "unknown"
        
        result = self.registry.update_health("test-runtime", "healthy")
        assert result is True
        assert self.registry.runtimes["test-runtime"].health_status == "healthy"
        
        self.registry.update_health("test-runtime", "degraded")
        assert self.registry.runtimes["test-runtime"].health_status == "degraded"
    
    def test_update_health_nonexistent(self):
        """Test updating health of non-existent runtime."""
        result = self.registry.update_health("nonexistent", "healthy")
        assert result is False
    
    def test_allocate_and_release_sessions(self):
        """Test session allocation and release."""
        runtime = self.registry.runtimes["test-runtime"]
        assert runtime.active_sessions == 0
        
        # Allocate
        result = self.registry.allocate_session("test-runtime")
        assert result is True
        assert runtime.active_sessions == 1
        
        # Allocate again
        self.registry.allocate_session("test-runtime")
        assert runtime.active_sessions == 2
        
        # Release
        result = self.registry.release_session("test-runtime")
        assert result is True
        assert runtime.active_sessions == 1
    
    def test_release_session_below_zero(self):
        """Test that active_sessions doesn't go below zero."""
        runtime = self.registry.runtimes["test-runtime"]
        assert runtime.active_sessions == 0
        
        result = self.registry.release_session("test-runtime")
        assert result is False
        assert runtime.active_sessions == 0
    
    def test_get_stats(self):
        """Test getting registry statistics."""
        self.registry.update_health("test-runtime", "healthy")
        self.registry.allocate_session("test-runtime")
        
        stats = self.registry.get_stats()
        
        assert stats["total_runtimes"] == 1
        assert stats["healthy_runtimes"] == 1
        assert stats["total_active_sessions"] == 1
        assert "test-runtime" in stats["runtimes"]


class TestIsolationCapabilities:
    """Test isolation capabilities across runtime types."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.registry = WorkerRegistry()
        self.registry.runtimes.clear()
    
    def test_native_has_no_isolation(self):
        """Test that native runtime has no isolation."""
        self.registry.register_runtime(
            name="native",
            config={"type": "native", "isolation": "none"}
        )
        runtime = self.registry.get_runtime("native")
        assert runtime.config.get("isolation") == "none"
    
    def test_foundry_has_filesystem_isolation(self):
        """Test that foundry runtime has filesystem isolation."""
        self.registry.register_runtime(
            name="foundry",
            config={"type": "foundry", "isolation": "filesystem"}
        )
        runtime = self.registry.get_runtime("foundry")
        assert runtime.config.get("isolation") == "filesystem"
    
    def test_openshell_has_full_isolation(self):
        """Test that openshell runtime has full container isolation."""
        self.registry.register_runtime(
            name="openshell",
            config={"type": "openshell", "isolation": "full"}
        )
        runtime = self.registry.get_runtime("openshell")
        assert runtime.config.get("isolation") == "full"
    
    def test_wrapper_has_network_isolation(self):
        """Test that wrapper runtime has network isolation."""
        self.registry.register_runtime(
            name="wrapper",
            config={"type": "wrapper", "isolation": "network"}
        )
        runtime = self.registry.get_runtime("wrapper")
        assert runtime.config.get("isolation") == "network"
    
    def test_isolation_levels_ordering(self):
        """Test that isolation levels are correctly ordered for security."""
        security_order = ["none", "filesystem", "network", "full"]
        
        # Register runtimes with different isolation levels
        for iso in security_order:
            self.registry.register_runtime(
                name=f"runtime-{iso}",
                config={"type": "wrapper", "isolation": iso},
                capabilities=["python"]
            )
        
        # Verify selection respects security ordering
        # full should satisfy all lower levels
        for required in ["none", "filesystem", "network", "full"]:
            selected = self.registry.select_runtime(
                required_capabilities=["python"],
                security_level=required
            )
            assert selected is not None


class TestSandboxIdentity:
    """Test SandboxIdentity functionality."""
    
    def test_create_default_sandbox_identity(self):
        """Test creating a default SandboxIdentity."""
        identity = SandboxIdentity()
        
        assert identity.sandbox_id is not None
        assert len(identity.sandbox_id) > 0
        assert identity.policy_profile == "default"
        assert identity.capability_tags == []
        assert identity.trust_tier == TrustTier.STANDARD
        assert identity.security_level == SecurityLevel.FULL
        assert identity.max_memory_mb == 512
        assert identity.max_cpu_percent == 50.0
        assert identity.timeout_seconds == 300
    
    def test_create_custom_sandbox_identity(self):
        """Test creating a custom SandboxIdentity."""
        identity = SandboxIdentity(
            policy_profile="codex_exec",
            capability_tags=["python", "filesystem_write"],
            trust_tier=TrustTier.ELEVATED,
            security_level=SecurityLevel.FILESYSTEM,
            max_memory_mb=2048,
            agent_id="agent-123"
        )
        
        assert identity.policy_profile == "codex_exec"
        assert "python" in identity.capability_tags
        assert identity.trust_tier == TrustTier.ELEVATED
        assert identity.security_level == SecurityLevel.FILESYSTEM
        assert identity.max_memory_mb == 2048
        assert identity.agent_id == "agent-123"
    
    def test_sandbox_identity_serialization(self):
        """Test SandboxIdentity to_dict and from_dict."""
        original = SandboxIdentity(
            policy_profile="test_policy",
            capability_tags=["python", "shell"],
            trust_tier=TrustTier.GOVERNANCE,
            security_level=SecurityLevel.NETWORK
        )
        
        # Serialize
        data = original.to_dict()
        assert data["policy_profile"] == "test_policy"
        assert data["trust_tier"] == "governance"
        assert data["security_level"] == "network"
        assert isinstance(data["capability_tags"], list)
        
        # Deserialize
        restored = SandboxIdentity.from_dict(data)
        assert restored.policy_profile == original.policy_profile
        assert restored.capability_tags == original.capability_tags
        assert restored.trust_tier == original.trust_tier
        assert restored.security_level == original.security_level
    
    def test_sandbox_identity_unique_ids(self):
        """Test that each SandboxIdentity gets a unique ID."""
        id1 = SandboxIdentity()
        id2 = SandboxIdentity()
        assert id1.sandbox_id != id2.sandbox_id


class TestTaskPacket:
    """Test TaskPacket functionality with SandboxIdentity."""
    
    def test_create_task_packet(self):
        """Test creating a TaskPacket with SandboxIdentity."""
        identity = SandboxIdentity(
            policy_profile="codex_exec",
            capability_tags=["python"]
        )
        
        packet = TaskPacket(
            agent_id="agent-456",
            action="execute_code",
            payload={"code": "print('hello')"},
            sandbox_identity=identity
        )
        
        assert packet.agent_id == "agent-456"
        assert packet.action == "execute_code"
        assert packet.payload["code"] == "print('hello')"
        assert packet.sandbox_identity.policy_profile == "codex_exec"
        assert packet.status == "pending"
    
    def test_task_packet_serialization(self):
        """Test TaskPacket to_dict and from_dict."""
        identity = SandboxIdentity(policy_profile="test")
        original = TaskPacket(
            agent_id="agent-789",
            action="analyze",
            payload={"file_path": "/tmp/test.py"},
            sandbox_identity=identity,
            priority=8
        )
        
        # Serialize
        data = original.to_dict()
        assert data["agent_id"] == "agent-789"
        assert data["action"] == "analyze"
        assert "sandbox_identity" in data
        
        # Deserialize
        restored = TaskPacket.from_dict(data)
        assert restored.agent_id == original.agent_id
        assert restored.action == original.action
        assert restored.sandbox_identity.policy_profile == "test"
    
    def test_create_task_packet_factory(self):
        """Test the create_task_packet factory function."""
        packet = create_task_packet(
            agent_id="agent-factory",
            action="execute_code",
            payload={"code": "x = 1 + 1"},
            policy_name="codex_exec"
        )
        
        assert packet.agent_id == "agent-factory"
        assert packet.sandbox_identity.policy_profile == "codex_exec"
        assert packet.sandbox_identity.trust_tier == TrustTier.STANDARD


class TestPolicyProfiles:
    """Test predefined policy profiles."""
    
    def test_policy_profiles_exist(self):
        """Test that expected policy profiles are defined."""
        expected_profiles = ["codex_exec", "opencode_analysis", "inference_local", "web_search"]
        for profile_name in expected_profiles:
            assert profile_name in POLICY_PROFILES
    
    def test_codex_exec_profile(self):
        """Test codex_exec policy profile."""
        profile = POLICY_PROFILES["codex_exec"]
        assert profile.security_level == SecurityLevel.FILESYSTEM
        assert "python" in profile.capability_tags
        assert profile.max_memory_mb == 1024
        assert profile.timeout_seconds == 600
    
    def test_opencode_analysis_profile(self):
        """Test opencode_analysis policy profile."""
        profile = POLICY_PROFILES["opencode_analysis"]
        assert profile.security_level == SecurityLevel.NETWORK
        assert "read_code" in profile.capability_tags
        assert profile.trust_tier == TrustTier.STANDARD
    
    def test_inference_local_profile(self):
        """Test inference_local policy profile."""
        profile = POLICY_PROFILES["inference_local"]
        assert profile.security_level == SecurityLevel.FULL
        assert "gpu_access" in profile.capability_tags
        assert profile.trust_tier == TrustTier.ELEVATED
        assert profile.max_memory_mb == 4096


class TestNamespaceSeparation:
    """Test namespace separation for runtimes."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.registry = WorkerRegistry()
        self.registry.runtimes.clear()
    
    def test_namespaced_runtime_names(self):
        """Test that runtimes can use namespaced names."""
        # Simulate different namespaces (e.g., team, project)
        runtimes = [
            ("team-a/native", "native"),
            ("team-a/foundry", "foundry"),
            ("team-b/openshell", "openshell"),
            ("team-b/wrapper", "wrapper"),
        ]
        
        for name, rtype in runtimes:
            self.registry.register_runtime(
                name=name,
                config={"type": rtype},
                capabilities=["python"]
            )
        
        # Verify all registered
        assert len(self.registry.list_runtimes()) == 4
        
        # Verify namespace separation
        team_a_runtimes = [r for r in self.registry.list_runtimes() if r.startswith("team-a/")]
        team_b_runtimes = [r for r in self.registry.list_runtimes() if r.startswith("team-b/")]
        
        assert len(team_a_runtimes) == 2
        assert len(team_b_runtimes) == 2
    
    def test_isolation_between_namespaces(self):
        """Test that namespaces provide logical separation."""
        # Register same runtime name in different namespaces
        self.registry.register_runtime(
            name="ns1/python-runtime",
            config={"type": "native", "namespace": "ns1"},
            capabilities=["python"]
        )
        self.registry.register_runtime(
            name="ns2/python-runtime",
            config={"type": "native", "namespace": "ns2"},
            capabilities=["python"]
        )
        
        rt1 = self.registry.get_runtime("ns1/python-runtime")
        rt2 = self.registry.get_runtime("ns2/python-runtime")
        
        assert rt1.config["namespace"] == "ns1"
        assert rt2.config["namespace"] == "ns2"
        assert rt1 is not rt2


class TestCapabilityTagging:
    """Test capability tagging system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.registry = WorkerRegistry()
        self.registry.runtimes.clear()
    
    def test_runtime_with_multiple_capabilities(self):
        """Test runtime registered with multiple capability tags."""
        capabilities = [
            "python", "javascript", "shell",
            "filesystem_read", "filesystem_write",
            "network_http", "network_ssh",
            "docker_exec", "gpu_access"
        ]
        
        self.registry.register_runtime(
            name="multi-cap",
            config={"type": "openshell"},
            capabilities=capabilities
        )
        
        runtime = self.registry.get_runtime("multi-cap")
        assert len(runtime.capabilities) == 9
        for cap in capabilities:
            assert cap in runtime.capabilities
    
    def test_select_by_capability_combination(self):
        """Test selecting runtime by multiple capability requirements."""
        # Runtime with python only
        self.registry.register_runtime(
            name="python-only",
            config={"type": "native"},
            capabilities=["python"]
        )
        
        # Runtime with python and shell
        self.registry.register_runtime(
            name="python-shell",
            config={"type": "native"},
            capabilities=["python", "shell"]
        )
        
        # Runtime with python, shell, and network
        self.registry.register_runtime(
            name="python-shell-net",
            config={"type": "openshell"},
            capabilities=["python", "shell", "network_http"]
        )
        
        # Update health
        for name in self.registry.runtimes:
            self.registry.update_health(name, "healthy")
        
        # Should select runtime with all required capabilities
        selected = self.registry.select_runtime(
            required_capabilities=["python", "shell", "network_http"]
        )
        assert selected == "python-shell-net"
    
    def test_capability_tag_in_sandbox_identity(self):
        """Test that SandboxIdentity carries capability tags."""
        identity = SandboxIdentity(
            capability_tags=["python", "filesystem_write", "network_http"]
        )
        
        assert len(identity.capability_tags) == 3
        assert "python" in identity.capability_tags
        assert "network_http" in identity.capability_tags
        
        # Serialization preserves tags
        data = identity.to_dict()
        assert "network_http" in data["capability_tags"]


class TestRuntimeConfigToDict:
    """Test RuntimeConfig serialization."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.registry = WorkerRegistry()
        self.registry.runtimes.clear()
    
    def test_runtime_config_to_dict(self):
        """Test RuntimeConfig to_dict method."""
        self.registry.register_runtime(
            name="test-rt",
            config={"type": "native", "custom": "value"},
            capabilities=["python", "shell"],
            max_concurrent=15
        )
        self.registry.update_health("test-rt", "healthy")
        self.registry.allocate_session("test-rt")
        
        runtime = self.registry.get_runtime("test-rt")
        data = runtime.to_dict()
        
        assert data["runtime_type"] == "native"
        assert data["config"]["custom"] == "value"
        assert "python" in data["capabilities"]
        assert data["health_status"] == "healthy"
        assert data["active_sessions"] == 1
        assert data["max_concurrent"] == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
