"""
Validation tests for WorkerRegistry, runtime registration, and SandboxIdentity
"""

import sys
import os
import unittest
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from runtimes import (
    WorkerRegistry, RuntimeType, RuntimeConfig, get_registry,
    SandboxIdentity, TaskPacket, SecurityLevel, TrustTier,
    POLICY_PROFILES, create_task_packet
)


class TestWorkerRegistryInitialization(unittest.TestCase):
    """Validate WorkerRegistry singleton initialization"""

    def setUp(self):
        """Reset registry before each test"""
        self.registry = get_registry()
        self.registry.runtimes.clear()

    def test_singleton_pattern(self):
        """Verify WorkerRegistry is a singleton"""
        registry1 = WorkerRegistry.get_instance()
        registry2 = WorkerRegistry.get_instance()
        self.assertIs(registry1, registry2)
        self.assertIs(registry1, self.registry)

    def test_initial_empty(self):
        """Verify registry starts empty"""
        self.assertEqual(len(self.registry.list_runtimes()), 0)
        self.assertEqual(self.registry.get_stats()["total_runtimes"], 0)


class TestRuntimeRegistration(unittest.TestCase):
    """Validate registration of all runtime types"""

    def setUp(self):
        self.registry = get_registry()
        self.registry.runtimes.clear()

    def _register_all_runtimes(self) -> Dict[str, RuntimeConfig]:
        """Register all four runtime types with sample configs"""
        runtimes = {}

        # Native runtime (no isolation)
        native_config = {
            "type": "native",
            "isolation": "none",
            "path": "/usr/bin/native-worker"
        }
        self.registry.register_runtime(
            name="native-worker",
            config=native_config,
            capabilities=["python", "bash", "filesystem_read"],
            max_concurrent=20
        )
        runtimes["native"] = self.registry.get_runtime("native-worker")

        # Foundry runtime (filesystem sandbox)
        foundry_config = {
            "type": "foundry",
            "isolation": "filesystem",
            "root": "/var/sandboxes/foundry",
            "image": "foundry-base:latest"
        }
        self.registry.register_runtime(
            name="foundry-worker",
            config=foundry_config,
            capabilities=["python", "filesystem_read", "filesystem_write", "pip_install"],
            max_concurrent=10
        )
        runtimes["foundry"] = self.registry.get_runtime("foundry-worker")

        # OpenShell runtime (full container isolation)
        openshell_config = {
            "type": "openshell",
            "isolation": "full",
            "gateway_url": "http://127.0.0.1:8080",
            "policy_dir": "/etc/openshell/policies"
        }
        self.registry.register_runtime(
            name="openshell-worker",
            config=openshell_config,
            capabilities=["python", "bash", "network_http", "filesystem_read", "filesystem_write", "gpu_access"],
            max_concurrent=5
        )
        runtimes["openshell"] = self.registry.get_runtime("openshell-worker")

        # Wrapper runtime (API-based execution)
        wrapper_config = {
            "type": "wrapper",
            "isolation": "network",
            "api_endpoint": "https://api.wrapper-service/v1/execute",
            "auth_token_env": "WRAPPER_TOKEN"
        }
        self.registry.register_runtime(
            name="wrapper-worker",
            config=wrapper_config,
            capabilities=["python", "javascript", "network_http", "api_call"],
            max_concurrent=15
        )
        runtimes["wrapper"] = self.registry.get_runtime("wrapper-worker")

        return runtimes

    def test_register_all_runtime_types(self):
        """Test registration of native, foundry, openshell, wrapper runtimes"""
        runtimes = self._register_all_runtimes()

        # Verify all four runtimes are registered
        self.assertEqual(len(self.registry.list_runtimes()), 4)
        self.assertIn("native-worker", self.registry.list_runtimes())
        self.assertIn("foundry-worker", self.registry.list_runtimes())
        self.assertIn("openshell-worker", self.registry.list_runtimes())
        self.assertIn("wrapper-worker", self.registry.list_runtimes())

        # Verify runtime types
        self.assertEqual(runtimes["native"].runtime_type, RuntimeType.NATIVE)
        self.assertEqual(runtimes["foundry"].runtime_type, RuntimeType.FOUNDRY)
        self.assertEqual(runtimes["openshell"].runtime_type, RuntimeType.OPENSHELL)
        self.assertEqual(runtimes["wrapper"].runtime_type, RuntimeType.WRAPPER)

    def test_isolation_capabilities(self):
        """Test isolation levels for each runtime"""
        self._register_all_runtimes()

        # Check isolation levels from config
        native = self.registry.get_runtime("native-worker")
        self.assertEqual(native.config["isolation"], "none")

        foundry = self.registry.get_runtime("foundry-worker")
        self.assertEqual(foundry.config["isolation"], "filesystem")

        openshell = self.registry.get_runtime("openshell-worker")
        self.assertEqual(openshell.config["isolation"], "full")

        wrapper = self.registry.get_runtime("wrapper-worker")
        self.assertEqual(wrapper.config["isolation"], "network")

    def test_runtime_selection_by_security_level(self):
        """Test select_runtime filters by isolation/security level"""
        self._register_all_runtimes()

        # Request full isolation (should only select openshell)
        selected = self.registry.select_runtime(
            required_capabilities=["python"],
            security_level="full"
        )
        self.assertEqual(selected, "openshell-worker")

        # Request network isolation (openshell or wrapper)
        selected = self.registry.select_runtime(
            required_capabilities=["python"],
            security_level="network"
        )
        self.assertIn(selected, ["openshell-worker", "wrapper-worker"])

        # Request filesystem isolation (foundry, openshell, wrapper)
        selected = self.registry.select_runtime(
            required_capabilities=["python"],
            security_level="filesystem"
        )
        self.assertIn(selected, ["foundry-worker", "openshell-worker", "wrapper-worker"])

        # Request no isolation (all runtimes)
        selected = self.registry.select_runtime(
            required_capabilities=["python"],
            security_level="none"
        )
        self.assertIn(selected, ["native-worker", "foundry-worker", "openshell-worker", "wrapper-worker"])

    def test_capability_tagging(self):
        """Test capability tagging and filtering"""
        self._register_all_runtimes()

        # Find runtime with gpu_access capability
        selected = self.registry.select_runtime(
            required_capabilities=["gpu_access"],
            security_level="full"
        )
        self.assertEqual(selected, "openshell-worker")

        # Find runtime with api_call capability
        selected = self.registry.select_runtime(
            required_capabilities=["api_call"],
            security_level="network"
        )
        self.assertEqual(selected, "wrapper-worker")

        # No runtime has "invalid_cap" capability
        selected = self.registry.select_runtime(
            required_capabilities=["invalid_cap"],
            security_level="none"
        )
        self.assertIsNone(selected)

    def test_unregister_runtime(self):
        """Test runtime removal"""
        self._register_all_runtimes()
        self.assertEqual(len(self.registry.list_runtimes()), 4)

        result = self.registry.unregister_runtime("native-worker")
        self.assertTrue(result)
        self.assertEqual(len(self.registry.list_runtimes()), 3)
        self.assertNotIn("native-worker", self.registry.list_runtimes())

        # Unregister non-existent runtime
        result = self.registry.unregister_runtime("non-existent")
        self.assertFalse(result)


class TestSandboxIdentity(unittest.TestCase):
    """Validate SandboxIdentity functionality"""

    def test_default_creation(self):
        """Test default SandboxIdentity creation"""
        identity = SandboxIdentity()
        self.assertIsNotNone(identity.sandbox_id)
        self.assertEqual(identity.policy_profile, "default")
        self.assertEqual(identity.trust_tier, TrustTier.STANDARD)
        self.assertEqual(identity.security_level, SecurityLevel.FULL)
        self.assertEqual(len(identity.capability_tags), 0)

    def test_custom_creation(self):
        """Test SandboxIdentity with custom parameters"""
        identity = SandboxIdentity(
            policy_profile="codex_exec",
            capability_tags=["python", "filesystem_write"],
            trust_tier=TrustTier.ELEVATED,
            security_level=SecurityLevel.FILESYSTEM,
            max_memory_mb=2048,
            agent_id="agent-123"
        )
        self.assertEqual(identity.policy_profile, "codex_exec")
        self.assertEqual(identity.capability_tags, ["python", "filesystem_write"])
        self.assertEqual(identity.trust_tier, TrustTier.ELEVATED)
        self.assertEqual(identity.security_level, SecurityLevel.FILESYSTEM)
        self.assertEqual(identity.max_memory_mb, 2048)
        self.assertEqual(identity.agent_id, "agent-123")

    def test_serialization_deserialization(self):
        """Test SandboxIdentity to_dict and from_dict"""
        original = SandboxIdentity(
            policy_profile="test_policy",
            capability_tags=["test_cap"],
            trust_tier=TrustTier.GOVERNANCE,
            security_level=SecurityLevel.NETWORK,
            agent_id="agent-456"
        )

        # Serialize
        data = original.to_dict()
        self.assertEqual(data["policy_profile"], "test_policy")
        self.assertEqual(data["trust_tier"], "governance")
        self.assertEqual(data["security_level"], "network")

        # Deserialize
        restored = SandboxIdentity.from_dict(data)
        self.assertEqual(restored.policy_profile, original.policy_profile)
        self.assertEqual(restored.capability_tags, original.capability_tags)
        self.assertEqual(restored.trust_tier, original.trust_tier)
        self.assertEqual(restored.security_level, original.security_level)
        self.assertEqual(restored.agent_id, original.agent_id)

    def test_predefined_policy_profiles(self):
        """Test predefined POLICY_PROFILES"""
        self.assertIn("codex_exec", POLICY_PROFILES)
        self.assertIn("opencode_analysis", POLICY_PROFILES)
        self.assertIn("inference_local", POLICY_PROFILES)
        self.assertIn("web_search", POLICY_PROFILES)

        # Check codex_exec profile
        codex_profile = POLICY_PROFILES["codex_exec"]
        self.assertEqual(codex_profile.security_level, SecurityLevel.FILESYSTEM)
        self.assertIn("python", codex_profile.capability_tags)
        self.assertIn("filesystem_write", codex_profile.capability_tags)


class TestTaskPacket(unittest.TestCase):
    """Validate TaskPacket functionality"""

    def test_create_task_packet(self):
        """Test task packet creation with factory function"""
        packet = create_task_packet(
            agent_id="agent-789",
            action="execute_code",
            payload={"code": "print('hello')", "language": "python"},
            policy_name="codex_exec"
        )

        self.assertEqual(packet.agent_id, "agent-789")
        self.assertEqual(packet.action, "execute_code")
        self.assertEqual(packet.payload["code"], "print('hello')")
        self.assertEqual(packet.sandbox_identity.policy_profile, "codex_exec")
        self.assertEqual(packet.status, "pending")

    def test_task_packet_serialization(self):
        """Test TaskPacket to_dict and from_dict"""
        original = create_task_packet(
            agent_id="agent-999",
            action="analyze",
            payload={"file_path": "/src/main.py"},
            policy_name="opencode_analysis"
        )
        original.priority = 8
        original.status = "approved"

        # Serialize
        data = original.to_dict()
        self.assertEqual(data["agent_id"], "agent-999")
        self.assertEqual(data["action"], "analyze")
        self.assertEqual(data["priority"], 8)
        self.assertEqual(data["status"], "approved")

        # Deserialize
        restored = TaskPacket.from_dict(data)
        self.assertEqual(restored.agent_id, original.agent_id)
        self.assertEqual(restored.action, original.action)
        self.assertEqual(restored.priority, original.priority)
        self.assertEqual(restored.status, original.status)
        self.assertEqual(
            restored.sandbox_identity.policy_profile,
            original.sandbox_identity.policy_profile
        )


class TestNamespaceSeparation(unittest.TestCase):
    """Verify namespace separation between runtimes"""

    def setUp(self):
        self.registry = get_registry()
        self.registry.runtimes.clear()

    def test_runtime_config_isolation(self):
        """Test that each runtime has independent configuration"""
        # Register two runtimes with same capability but different configs
        self.registry.register_runtime(
            name="runtime-a",
            config={"type": "native", "isolation": "none", "version": "1.0"},
            capabilities=["python"]
        )
        self.registry.register_runtime(
            name="runtime-b",
            config={"type": "native", "isolation": "none", "version": "2.0"},
            capabilities=["python"]
        )

        runtime_a = self.registry.get_runtime("runtime-a")
        runtime_b = self.registry.get_runtime("runtime-b")

        # Verify independent configs
        self.assertEqual(runtime_a.config["version"], "1.0")
        self.assertEqual(runtime_b.config["version"], "2.0")

        # Modify one runtime's config should not affect the other
        runtime_a.config["modified"] = True
        self.assertNotIn("modified", runtime_b.config)

    def test_session_count_isolation(self):
        """Test that session counts are per-runtime"""
        self.registry.register_runtime(
            name="runtime-x",
            config={"type": "native", "isolation": "none"},
            capabilities=["bash"],
            max_concurrent=5
        )
        self.registry.register_runtime(
            name="runtime-y",
            config={"type": "native", "isolation": "none"},
            capabilities=["bash"],
            max_concurrent=5
        )

        # Allocate sessions to runtime-x
        self.registry.allocate_session("runtime-x")
        self.registry.allocate_session("runtime-x")

        # runtime-y should have 0 sessions
        self.assertEqual(self.registry.get_runtime("runtime-x").active_sessions, 2)
        self.assertEqual(self.registry.get_runtime("runtime-y").active_sessions, 0)

        # Release session from runtime-x
        self.registry.release_session("runtime-x")
        self.assertEqual(self.registry.get_runtime("runtime-x").active_sessions, 1)


class TestHealthStatus(unittest.TestCase):
    """Validate runtime health status tracking"""

    def setUp(self):
        self.registry = get_registry()
        self.registry.runtimes.clear()

    def test_update_health_status(self):
        """Test health status updates"""
        self.registry.register_runtime(
            name="test-runtime",
            config={"type": "native", "isolation": "none"},
            capabilities=[]
        )

        # Default status is "unknown"
        runtime = self.registry.get_runtime("test-runtime")
        self.assertEqual(runtime.health_status, "unknown")

        # Update to healthy
        self.registry.update_health("test-runtime", "healthy")
        self.assertEqual(runtime.health_status, "healthy")

        # Update to offline
        self.registry.update_health("test-runtime", "offline")
        self.assertEqual(runtime.health_status, "offline")

        # Offline runtimes should not be selected
        selected = self.registry.select_runtime(
            required_capabilities=[],
            security_level="none"
        )
        self.assertIsNone(selected)

    def test_get_stats(self):
        """Test registry statistics"""
        self.registry.register_runtime(
            name="runtime-1",
            config={"type": "native", "isolation": "none"},
            capabilities=[],
            max_concurrent=10
        )
        self.registry.update_health("runtime-1", "healthy")
        self.registry.allocate_session("runtime-1")

        self.registry.register_runtime(
            name="runtime-2",
            config={"type": "foundry", "isolation": "filesystem"},
            capabilities=[],
            max_concurrent=5
        )
        self.registry.update_health("runtime-2", "degraded")

        stats = self.registry.get_stats()
        self.assertEqual(stats["total_runtimes"], 2)
        self.assertEqual(stats["healthy_runtimes"], 1)
        self.assertEqual(stats["total_active_sessions"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
