"""
Test suite for Worker Registry system.

Tests cover:
- Singleton pattern
- Runtime registration/deregistration
- Runtime selection logic
- Session management
- Health tracking
- Statistics reporting
"""

import os
import sys
import pytest
from unittest.mock import patch
from runtimes.worker_registry import (
    WorkerRegistry, RuntimeType, RuntimeConfig, get_registry
)
from threading import Lock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWorkerRegistrySingleton:
    """Test singleton pattern enforcement."""
    
    def setup_method(self):
        """Reset singleton between tests."""
        WorkerRegistry._instance = None
        WorkerRegistry._lock = Lock()
    
    def test_get_instance_returns_singleton(self):
        """Test get_instance returns same object."""
        reg1 = WorkerRegistry.get_instance()
        reg2 = WorkerRegistry.get_instance()
        assert reg1 is reg2
    
    def test_direct_init_returns_singleton(self):
        """Test direct instantiation returns singleton."""
        reg1 = WorkerRegistry.get_instance()
        reg2 = WorkerRegistry()
        assert reg1 is reg2
    
    def test_global_get_registry(self):
        """Test global get_registry function."""
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2
        assert reg1 is WorkerRegistry.get_instance()


class TestRuntimeRegistration:
    """Test runtime registration and removal."""
    
    def setup_method(self):
        WorkerRegistry._instance = None
        self.registry = WorkerRegistry.get_instance()
    
    def test_register_runtime_success(self):
        """Test successful runtime registration."""
        result = self.registry.register_runtime(
            name="native",
            config={"type": "native", "isolation": "none"},
            capabilities=["code_execution", "file_read"],
            max_concurrent=5
        )
        assert result is True
        assert "native" in self.registry.runtimes
        
        runtime = self.registry.get_runtime("native")
        assert runtime.runtime_type == RuntimeType.NATIVE
        assert "code_execution" in runtime.capabilities
        assert runtime.max_concurrent == 5
        assert runtime.health_status == "unknown"
    
    def test_register_invalid_runtime_type(self):
        """Test registration with invalid config type."""
        result = self.registry.register_runtime(
            name="invalid",
            config={"type": "invalid_type"},
            capabilities=[]
        )
        assert result is False
        assert "invalid" not in self.registry.runtimes
    
    def test_unregister_runtime(self):
        """Test runtime removal."""
        self.registry.register_runtime(
            name="test_runtime",
            config={"type": "wrapper"},
            capabilities=[]
        )
        assert "test_runtime" in self.registry.runtimes
        
        result = self.registry.unregister_runtime("test_runtime")
        assert result is True
        assert "test_runtime" not in self.registry.runtimes
    
    def test_unregister_nonexistent(self):
        """Test unregistering non-existent runtime."""
        result = self.registry.unregister_runtime("nonexistent")
        assert result is False


class TestRuntimeSelection:
    """Test runtime selection logic."""
    
    def setup_method(self):
        WorkerRegistry._instance = None
        self.registry = WorkerRegistry.get_instance()
        
        # Register test runtimes
        self.registry.register_runtime(
            name="native",
            config={"type": "native", "isolation": "none"},
            capabilities=["code_execution"],
            max_concurrent=10
        )
        self.registry.register_runtime(
            name="openshell",
            config={"type": "openshell", "isolation": "full"},
            capabilities=["code_execution", "network", "file_write"],
            max_concurrent=5
        )
        self.registry.register_runtime(
            name="foundry",
            config={"type": "foundry", "isolation": "filesystem"},
            capabilities=["code_execution", "file_read", "file_write"],
            max_concurrent=8
        )
        
        # Set health to healthy
        for name in ["native", "openshell", "foundry"]:
            self.registry.update_health(name, "healthy")
    
    def test_select_by_capabilities(self):
        """Test selection based on required capabilities."""
        selected = self.registry.select_runtime(
            required_capabilities=["network"]
        )
        assert selected == "openshell"
    
    def test_select_by_security_level(self):
        """Test selection based on security level."""
        selected = self.registry.select_runtime(
            required_capabilities=["code_execution"],
            security_level="full"
        )
        assert selected == "openshell"
    
    def test_select_prefer_type(self):
        """Test selection with preferred runtime type."""
        selected = self.registry.select_runtime(
            required_capabilities=["code_execution"],
            prefer_type=RuntimeType.FOUNDRY
        )
        assert selected == "foundry"
    
    def test_select_skip_offline(self):
        """Test offline runtimes are skipped."""
        self.registry.update_health("openshell", "offline")
        selected = self.registry.select_runtime(
            required_capabilities=["network"]
        )
        assert selected is None
    
    def test_select_skip_at_capacity(self):
        """Test runtimes at capacity are skipped."""
        self.registry.runtimes["openshell"].active_sessions = 5  # max_concurrent=5
        selected = self.registry.select_runtime(
            required_capabilities=["network"]
        )
        assert selected is None
    
    def test_select_no_match(self):
        """Test no selection when capabilities don't match."""
        selected = self.registry.select_runtime(
            required_capabilities=["gpu_access"]
        )
        assert selected is None


class TestSessionManagement:
    """Test session allocation and release."""
    
    def setup_method(self):
        WorkerRegistry._instance = None
        self.registry = WorkerRegistry.get_instance()
        self.registry.register_runtime(
            name="test_rt",
            config={"type": "native"},
            capabilities=[],
            max_concurrent=3
        )
        self.registry.update_health("test_rt", "healthy")
    
    def test_allocate_session(self):
        """Test session allocation."""
        result = self.registry.allocate_session("test_rt")
        assert result is True
        assert self.registry.runtimes["test_rt"].active_sessions == 1
    
    def test_allocate_nonexistent(self):
        """Test allocation for non-existent runtime."""
        result = self.registry.allocate_session("nonexistent")
        assert result is False
    
    def test_release_session(self):
        """Test session release."""
        self.registry.allocate_session("test_rt")
        self.registry.allocate_session("test_rt")
        assert self.registry.runtimes["test_rt"].active_sessions == 2
        
        result = self.registry.release_session("test_rt")
        assert result is True
        assert self.registry.runtimes["test_rt"].active_sessions == 1
    
    def test_release_nonexistent(self):
        """Test release for non-existent runtime."""
        result = self.registry.release_session("nonexistent")
        assert result is False
    
    def test_release_below_zero(self):
        """Test session count doesn't go below zero."""
        result = self.registry.release_session("test_rt")
        assert result is False
        assert self.registry.runtimes["test_rt"].active_sessions == 0


class TestHealthManagement:
    """Test runtime health tracking."""
    
    def setup_method(self):
        WorkerRegistry._instance = None
        self.registry = WorkerRegistry.get_instance()
        self.registry.register_runtime(
            name="test_rt",
            config={"type": "native"},
            capabilities=[]
        )
    
    def test_update_health(self):
        """Test health status update."""
        result = self.registry.update_health("test_rt", "healthy")
        assert result is True
        assert self.registry.get_runtime("test_rt").health_status == "healthy"
    
    def test_update_health_nonexistent(self):
        """Test update for non-existent runtime."""
        result = self.registry.update_health("nonexistent", "healthy")
        assert result is False


class TestRegistryStatistics:
    """Test statistics reporting."""
    
    def setup_method(self):
        WorkerRegistry._instance = None
        self.registry = WorkerRegistry.get_instance()
        
        self.registry.register_runtime(
            name="rt1",
            config={"type": "native"},
            capabilities=[],
            max_concurrent=5
        )
        self.registry.register_runtime(
            name="rt2",
            config={"type": "openshell"},
            capabilities=[],
            max_concurrent=3
        )
        
        self.registry.update_health("rt1", "healthy")
        self.registry.update_health("rt2", "degraded")
        
        self.registry.allocate_session("rt1")
        self.registry.allocate_session("rt1")
    
    def test_get_stats(self):
        """Test statistics generation."""
        stats = self.registry.get_stats()
        assert stats["total_runtimes"] == 2
        assert stats["healthy_runtimes"] == 1
        assert stats["total_active_sessions"] == 2
        assert "rt1" in stats["runtimes"]
        assert stats["runtimes"]["rt1"]["active_sessions"] == 2
        assert stats["runtimes"]["rt2"]["health_status"] == "degraded"
    
    def test_list_runtimes(self):
        """Test listing all runtime names."""
        runtimes = self.registry.list_runtimes()
        assert set(runtimes) == {"rt1", "rt2"}
    
    def test_get_runtime(self):
        """Test getting specific runtime config."""
        rt = self.registry.get_runtime("rt1")
        assert rt is not None
        assert rt.runtime_type == RuntimeType.NATIVE
        
        rt_nonexistent = self.registry.get_runtime("nonexistent")
        assert rt_nonexistent is None


class TestRuntimeConfig:
    """Test RuntimeConfig data model."""
    
    def test_to_dict(self):
        """Test RuntimeConfig serialization."""
        config = RuntimeConfig(
            runtime_type=RuntimeType.OPENSHELL,
            config={"isolation": "full"},
            capabilities=["network", "code_execution"],
            health_status="healthy",
            active_sessions=2,
            max_concurrent=10
        )
        
        result = config.to_dict()
        assert result["runtime_type"] == "openshell"
        assert result["config"]["isolation"] == "full"
        assert "network" in result["capabilities"]
        assert result["health_status"] == "healthy"
        assert result["active_sessions"] == 2
        assert result["max_concurrent"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
