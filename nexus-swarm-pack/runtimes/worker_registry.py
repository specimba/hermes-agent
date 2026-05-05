"""
Worker Runtime Registry - Phase C
Dynamic selection and management of execution environments
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import threading


class RuntimeType(Enum):
    """Supported runtime types"""
    NATIVE = "native"  # Direct execution (no isolation)
    FOUNDRY = "foundry"  # Filesystem sandbox
    OPENSHELL = "openshell"  # Full container isolation
    WRAPPER = "wrapper"  # API-based execution


@dataclass
class RuntimeConfig:
    """Configuration for a registered runtime"""
    runtime_type: RuntimeType
    config: Dict[str, Any]
    capabilities: List[str] = field(default_factory=list)
    health_status: str = "unknown"  # unknown, healthy, degraded, offline
    active_sessions: int = 0
    max_concurrent: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_type": self.runtime_type.value,
            "config": self.config,
            "capabilities": self.capabilities,
            "health_status": self.health_status,
            "active_sessions": self.active_sessions,
            "max_concurrent": self.max_concurrent
        }


class WorkerRegistry:
    """
    Singleton registry for managing execution runtimes
    Selects optimal runtime based on task requirements and availability
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.runtimes: Dict[str, RuntimeConfig] = {}
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'WorkerRegistry':
        """Get singleton instance"""
        return cls()
    
    def register_runtime(
        self,
        name: str,
        config: Dict[str, Any],
        capabilities: Optional[List[str]] = None,
        max_concurrent: int = 10
    ) -> bool:
        """
        Register a new runtime environment
        
        Args:
            name: Unique runtime identifier
            config: Runtime configuration dict
            capabilities: List of capability tags this runtime supports
            max_concurrent: Maximum concurrent sessions
        
        Returns:
            True if registration successful
        """
        try:
            runtime_type = RuntimeType(config.get("type", "native"))
            self.runtimes[name] = RuntimeConfig(
                runtime_type=runtime_type,
                config=config,
                capabilities=capabilities or [],
                max_concurrent=max_concurrent
            )
            return True
        except Exception as e:
            print(f"Failed to register runtime {name}: {e}")
            return False
    
    def unregister_runtime(self, name: str) -> bool:
        """Remove a runtime from the registry"""
        if name in self.runtimes:
            del self.runtimes[name]
            return True
        return False
    
    def get_runtime(self, name: str) -> Optional[RuntimeConfig]:
        """Get runtime configuration by name"""
        return self.runtimes.get(name)
    
    def list_runtimes(self) -> List[str]:
        """List all registered runtime names"""
        return list(self.runtimes.keys())
    
    def select_runtime(
        self,
        required_capabilities: List[str],
        security_level: str = "full",
        prefer_type: Optional[RuntimeType] = None
    ) -> Optional[str]:
        """
        Select optimal runtime for task requirements
        
        Args:
            required_capabilities: List of required capability tags
            security_level: Minimum security level (none, filesystem, network, full)
            prefer_type: Preferred runtime type if available
        
        Returns:
            Name of selected runtime or None if no match
        """
        candidates = []
        
        for name, runtime in self.runtimes.items():
            # Check health
            if runtime.health_status == "offline":
                continue
            
            # Check capacity
            if runtime.active_sessions >= runtime.max_concurrent:
                continue
            
            # Check capabilities
            if not all(cap in runtime.capabilities for cap in required_capabilities):
                continue
            
            # Check security level
            isolation = runtime.config.get("isolation", "none")
            security_order = ["none", "filesystem", "network", "full"]
            if security_order.index(isolation) < security_order.index(security_level):
                continue
            
            # Calculate score
            score = 0
            if prefer_type and runtime.runtime_type == prefer_type:
                score += 100
            score += len(runtime.capabilities)  # Prefer more capable runtimes
            score -= runtime.active_sessions  # Prefer less loaded runtimes
            
            candidates.append((name, score))
        
        if not candidates:
            return None
        
        # Return highest scored candidate
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def allocate_session(self, runtime_name: str) -> bool:
        """Increment active session count for a runtime"""
        if runtime_name in self.runtimes:
            self.runtimes[runtime_name].active_sessions += 1
            return True
        return False
    
    def release_session(self, runtime_name: str) -> bool:
        """Decrement active session count"""
        if runtime_name in self.runtimes:
            runtime = self.runtimes[runtime_name]
            if runtime.active_sessions > 0:
                runtime.active_sessions -= 1
                return True
        return False
    
    def update_health(self, runtime_name: str, status: str) -> bool:
        """Update runtime health status"""
        if runtime_name in self.runtimes:
            self.runtimes[runtime_name].health_status = status
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            "total_runtimes": len(self.runtimes),
            "healthy_runtimes": sum(1 for r in self.runtimes.values() if r.health_status == "healthy"),
            "total_active_sessions": sum(r.active_sessions for r in self.runtimes.values()),
            "runtimes": {name: config.to_dict() for name, config in self.runtimes.items()}
        }


# Global registry instance
_registry_instance: Optional[WorkerRegistry] = None


def get_registry() -> WorkerRegistry:
    """Get global registry instance"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = WorkerRegistry()
    return _registry_instance
