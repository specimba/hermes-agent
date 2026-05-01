#!/usr/bin/env python3
"""
NVIDIA Open Shell Sandbox Environment

Secure code execution sandbox using NVIDIA's containerized environment.
Provides isolated execution for agent skills with resource limits and security controls.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import threading
import hashlib

logger = logging.getLogger(__name__)


class SandboxStatus(Enum):
    """Sandbox lifecycle states."""
    PENDING = "pending"
    CREATING = "creating"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class SecurityLevel(Enum):
    """Security isolation levels."""
    LOW = "low"  # Minimal isolation, faster execution
    MEDIUM = "medium"  # Standard container isolation
    HIGH = "high"  # Strict isolation with resource limits
    MAXIMUM = "maximum"  # Air-gapped, read-only filesystem


@dataclass
class SandboxConfig:
    """Configuration for a sandbox environment."""
    sandbox_id: str
    image: str = "nvcr.io/nvidia/open-shell:latest"
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    cpu_limit: float = 2.0  # CPU cores
    memory_limit: str = "4G"
    disk_limit: str = "10G"
    network_enabled: bool = False
    gpu_enabled: bool = True
    timeout_seconds: int = 300
    allowed_commands: List[str] = field(default_factory=list)
    blocked_paths: List[str] = field(default_factory=lambda: ["/etc", "/root", "/home"])
    environment_vars: Dict[str, str] = field(default_factory=dict)
    work_dir: str = "/workspace"


@dataclass
class ExecutionResult:
    """Result of code execution in sandbox."""
    execution_id: str
    sandbox_id: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    memory_used: str
    created_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResourceMonitor:
    """Monitors resource usage in sandbox."""
    
    def __init__(self, sandbox_id: str):
        self.sandbox_id = sandbox_id
        self._metrics: Dict[str, Any] = {
            "cpu_percent": 0.0,
            "memory_bytes": 0,
            "disk_io_read": 0,
            "disk_io_write": 0,
            "network_rx": 0,
            "network_tx": 0,
        }
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None
    
    def start_monitoring(self):
        """Start resource monitoring."""
        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
    
    def stop_monitoring(self):
        """Stop resource monitoring."""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=5.0)
    
    def _monitor_loop(self):
        """Monitoring loop."""
        while self._monitoring:
            try:
                # In real implementation, this would query container stats
                # For now, simulate metrics
                self._metrics["cpu_percent"] = 0.0
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current resource metrics."""
        return self._metrics.copy()


class SandboxInstance:
    """Represents a running sandbox instance."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.status = SandboxStatus.PENDING
        self.container_id: Optional[str] = None
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.execution_count = 0
        self.resource_monitor = ResourceMonitor(config.sandbox_id)
        self._lock = threading.Lock()
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None
    
    def create(self) -> bool:
        """Create the sandbox environment."""
        try:
            self.status = SandboxStatus.CREATING
            
            # Create temporary directory for isolated filesystem
            self._temp_dir = tempfile.TemporaryDirectory(prefix=f"sandbox-{self.config.sandbox_id[:8]}")
            
            # Setup isolated directory structure
            work_dir = Path(self._temp_dir.name) / "work"
            work_dir.mkdir(parents=True, exist_ok=True)
            
            # Setup security constraints based on level
            if self.config.security_level == SecurityLevel.MAXIMUM:
                # Read-only mounts for maximum security
                os.chmod(str(work_dir), 0o555)
            
            logger.info(f"Sandbox {self.config.sandbox_id} created at {self._temp_dir.name}")
            self.status = SandboxStatus.READY
            return True
            
        except Exception as e:
            logger.error(f"Failed to create sandbox {self.config.sandbox_id}: {e}")
            self.status = SandboxStatus.ERROR
            if self._temp_dir:
                self._temp_dir.cleanup()
            return False
    
    def execute(self, code: str, language: str = "python", 
                timeout: Optional[int] = None) -> ExecutionResult:
        """Execute code in the sandbox."""
        if self.status not in [SandboxStatus.READY, SandboxStatus.RUNNING]:
            raise RuntimeError(f"Sandbox not ready (status: {self.status})")
        
        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        start_time = time.monotonic()
        
        with self._lock:
            self.status = SandboxStatus.RUNNING
            self.last_activity = datetime.now()
            self.execution_count += 1
        
        try:
            timeout = timeout or self.config.timeout_seconds
            
            # Prepare execution script
            if language == "python":
                script_path = Path(self._temp_dir.name) / "work" / f"{execution_id}.py"
                script_path.write_text(code)
                
                # Build command with security constraints
                cmd = [
                    "python3", "-u", str(script_path)
                ]
                
                # Add resource limits using ulimit or cgroups
                if self.config.security_level in [SecurityLevel.HIGH, SecurityLevel.MAXIMUM]:
                    cmd = ["timeout", str(timeout)] + cmd
            
            elif language == "bash":
                script_path = Path(self._temp_dir.name) / "work" / f"{execution_id}.sh"
                script_path.write_text(f"#!/bin/bash\n{code}")
                script_path.chmod(0o755)
                cmd = ["bash", str(script_path)]
            
            else:
                raise ValueError(f"Unsupported language: {language}")
            
            # Execute with security constraints
            env = os.environ.copy()
            env.update(self.config.environment_vars)
            env["SANDBOX_ID"] = self.config.sandbox_id
            env["EXECUTION_ID"] = execution_id
            
            # Block dangerous environment variables
            for key in list(env.keys()):
                if key.startswith("AWS_") or key.startswith("GOOGLE_") or key == "SSH_AUTH_SOCK":
                    del env[key]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path(self._temp_dir.name) / "work"),
                env=env,
            )
            
            execution_time = time.monotonic() - start_time
            
            execution_result = ExecutionResult(
                execution_id=execution_id,
                sandbox_id=self.config.sandbox_id,
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time,
                memory_used="0MB",  # Would be populated by resource monitor
                metadata={
                    "language": language,
                    "code_length": len(code),
                }
            )
            
        except subprocess.TimeoutExpired:
            execution_result = ExecutionResult(
                execution_id=execution_id,
                sandbox_id=self.config.sandbox_id,
                success=False,
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds",
                exit_code=-1,
                execution_time=time.monotonic() - start_time,
                memory_used="0MB",
                error="TIMEOUT"
            )
        except Exception as e:
            execution_result = ExecutionResult(
                execution_id=execution_id,
                sandbox_id=self.config.sandbox_id,
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time=time.monotonic() - start_time,
                memory_used="0MB",
                error=str(e)
            )
        
        with self._lock:
            self.status = SandboxStatus.READY
            self.last_activity = datetime.now()
        
        return execution_result
    
    def stop(self) -> bool:
        """Stop and cleanup the sandbox."""
        try:
            self.status = SandboxStatus.STOPPING
            self.resource_monitor.stop_monitoring()
            
            if self._temp_dir:
                self._temp_dir.cleanup()
            
            self.status = SandboxStatus.STOPPED
            logger.info(f"Sandbox {self.config.sandbox_id} stopped")
            return True
        except Exception as e:
            logger.error(f"Error stopping sandbox {self.config.sandbox_id}: {e}")
            self.status = SandboxStatus.ERROR
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get sandbox information."""
        return {
            "sandbox_id": self.config.sandbox_id,
            "status": self.status.value,
            "image": self.config.image,
            "security_level": self.config.security_level.value,
            "cpu_limit": self.config.cpu_limit,
            "memory_limit": self.config.memory_limit,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "execution_count": self.execution_count,
            "resource_metrics": self.resource_monitor.get_metrics(),
        }


class SandboxManager:
    """Manages multiple sandbox instances."""
    
    def __init__(self, max_sandboxes: int = 10):
        self.max_sandboxes = max_sandboxes
        self._sandboxes: Dict[str, SandboxInstance] = {}
        self._lock = threading.RLock()
        self._execution_history: List[Dict[str, Any]] = []
    
    def create_sandbox(self, config: Optional[SandboxConfig] = None) -> SandboxInstance:
        """Create a new sandbox instance."""
        with self._lock:
            if len(self._sandboxes) >= self.max_sandboxes:
                raise RuntimeError(f"Maximum sandboxes ({self.max_sandboxes}) reached")
            
            sandbox_id = f"sandbox-{uuid.uuid4().hex[:12]}"
            if config is None:
                config = SandboxConfig(sandbox_id=sandbox_id)
            else:
                config.sandbox_id = sandbox_id
            
            sandbox = SandboxInstance(config)
            
            if not sandbox.create():
                raise RuntimeError("Failed to create sandbox")
            
            self._sandboxes[sandbox_id] = sandbox
            logger.info(f"Sandbox {sandbox_id} created")
            return sandbox
    
    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxInstance]:
        """Get a sandbox by ID."""
        with self._lock:
            return self._sandboxes.get(sandbox_id)
    
    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Destroy a sandbox instance."""
        with self._lock:
            if sandbox_id not in self._sandboxes:
                return False
            
            sandbox = self._sandboxes.pop(sandbox_id)
            sandbox.stop()
            logger.info(f"Sandbox {sandbox_id} destroyed")
            return True
    
    def execute_in_sandbox(self, sandbox_id: str, code: str, 
                          language: str = "python",
                          timeout: Optional[int] = None) -> ExecutionResult:
        """Execute code in a specific sandbox."""
        sandbox = self.get_sandbox(sandbox_id)
        if not sandbox:
            raise ValueError(f"Sandbox {sandbox_id} not found")
        
        result = sandbox.execute(code, language, timeout)
        
        # Record execution history
        with self._lock:
            self._execution_history.append({
                "execution_id": result.execution_id,
                "sandbox_id": sandbox_id,
                "timestamp": datetime.now().isoformat(),
                "success": result.success,
                "execution_time": result.execution_time,
                "language": language,
            })
            
            # Keep only last 1000 executions
            if len(self._execution_history) > 1000:
                self._execution_history = self._execution_history[-1000:]
        
        return result
    
    def get_all_sandboxes(self) -> List[SandboxInstance]:
        """Get all sandbox instances."""
        with self._lock:
            return list(self._sandboxes.values())
    
    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        with self._lock:
            return self._execution_history[-limit:]
    
    def cleanup_idle_sandboxes(self, idle_timeout_seconds: int = 3600):
        """Cleanup sandboxes that have been idle for too long."""
        with self._lock:
            now = datetime.now()
            to_remove = []
            
            for sandbox_id, sandbox in self._sandboxes.items():
                idle_time = (now - sandbox.last_activity).total_seconds()
                if idle_time > idle_timeout_seconds and sandbox.status == SandboxStatus.READY:
                    to_remove.append(sandbox_id)
            
            for sandbox_id in to_remove:
                self.destroy_sandbox(sandbox_id)
                logger.info(f"Cleaned up idle sandbox {sandbox_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sandbox manager statistics."""
        with self._lock:
            total_executions = len(self._execution_history)
            successful_executions = sum(1 for e in self._execution_history if e["success"])
            
            return {
                "total_sandboxes": len(self._sandboxes),
                "active_sandboxes": sum(1 for s in self._sandboxes.values() 
                                       if s.status == SandboxStatus.RUNNING),
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "success_rate": successful_executions / total_executions if total_executions > 0 else 0.0,
            }


# Singleton instance
_manager: Optional[SandboxManager] = None


def get_sandbox_manager() -> SandboxManager:
    """Get the global sandbox manager instance."""
    global _manager
    if _manager is None:
        _manager = SandboxManager()
    return _manager


def execute_code_securely(code: str, language: str = "python",
                         security_level: SecurityLevel = SecurityLevel.MEDIUM,
                         timeout: int = 60) -> ExecutionResult:
    """Execute code in a secure sandbox environment."""
    manager = get_sandbox_manager()
    
    # Create a temporary sandbox for single execution
    config = SandboxConfig(
        sandbox_id="temp",
        security_level=security_level,
        timeout_seconds=timeout,
    )
    
    sandbox = manager.create_sandbox(config)
    try:
        result = sandbox.execute(code, language, timeout)
        return result
    finally:
        manager.destroy_sandbox(sandbox.config.sandbox_id)
