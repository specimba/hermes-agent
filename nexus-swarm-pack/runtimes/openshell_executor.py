"""
OpenShell Executor - Phase C
Bridges Nexus governance decisions to OpenShell sandbox execution
"""

from typing import Dict, Any, Optional, List
import requests
import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SandboxResult:
    """Result from OpenShell sandbox execution"""
    success: bool
    output: str
    error: Optional[str]
    exit_code: int
    duration_ms: int
    sandbox_id: str
    policy_profile: str
    audit_hash: Optional[str] = None


class OpenShellExecutor:
    """
    Executes governed tasks in OpenShell sandboxes
    Translates Nexus TaskPackets into OpenShell API calls
    """
    
    def __init__(self, gateway_url: str = "http://127.0.0.1:8080", timeout: int = 300):
        self.gateway_url = gateway_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def health_check(self) -> bool:
        """Check if OpenShell gateway is available"""
        try:
            response = self.session.get(
                f"{self.gateway_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def create_sandbox(
        self,
        policy_profile: str,
        task_id: str,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Create a new OpenShell sandbox with specified policy
        
        Args:
            policy_profile: Name of OpenShell YAML policy
            task_id: Unique task identifier
            environment_vars: Optional environment variables
        
        Returns:
            Sandbox ID or None if creation failed
        """
        payload = {
            "policy": policy_profile,
            "task_id": task_id,
            "environment": environment_vars or {}
        }
        
        try:
            response = self.session.post(
                f"{self.gateway_url}/api/v1/sandboxes",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                return data.get("sandbox_id")
            else:
                print(f"Failed to create sandbox: {response.text}")
                return None
        except Exception as e:
            print(f"Error creating sandbox: {e}")
            return None
    
    def execute_in_sandbox(
        self,
        sandbox_id: str,
        command: str,
        args: Optional[List[str]] = None,
        stdin: Optional[str] = None
    ) -> Optional[SandboxResult]:
        """
        Execute a command inside an existing sandbox
        
        Args:
            sandbox_id: ID of sandbox to execute in
            command: Command to run
            args: Command arguments
            stdin: Optional stdin input
        
        Returns:
            SandboxResult or None if execution failed
        """
        payload = {
            "command": command,
            "args": args or [],
            "stdin": stdin,
            "timeout_seconds": self.timeout
        }
        
        try:
            start_time = datetime.utcnow()
            response = self.session.post(
                f"{self.gateway_url}/api/v1/sandboxes/{sandbox_id}/execute",
                json=payload,
                timeout=self.timeout + 10
            )
            end_time = datetime.utcnow()
            
            if response.status_code == 200:
                data = response.json()
                return SandboxResult(
                    success=data.get("success", False),
                    output=data.get("stdout", ""),
                    error=data.get("stderr"),
                    exit_code=data.get("exit_code", -1),
                    duration_ms=int((end_time - start_time).total_seconds() * 1000),
                    sandbox_id=sandbox_id,
                    policy_profile=data.get("policy_profile", "unknown")
                )
            else:
                return SandboxResult(
                    success=False,
                    output="",
                    error=f"Execution failed: {response.text}",
                    exit_code=response.status_code,
                    duration_ms=0,
                    sandbox_id=sandbox_id,
                    policy_profile="unknown"
                )
        except Exception as e:
            return SandboxResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                duration_ms=0,
                sandbox_id=sandbox_id,
                policy_profile="unknown"
            )
    
    def execute_task(
        self,
        task_packet: 'TaskPacket',
        policy_override: Optional[str] = None
    ) -> SandboxResult:
        """
        Execute a complete Nexus TaskPacket in OpenShell
        
        Args:
            task_packet: Nexus TaskPacket with sandbox identity
            policy_override: Optional policy profile override
        
        Returns:
            SandboxResult with execution outcome
        """
        # Import here to avoid circular dependency
        from runtimes.sandbox_identity import TaskPacket
        
        policy = policy_override or task_packet.sandbox_identity.policy_profile
        
        # Create sandbox
        sandbox_id = self.create_sandbox(
            policy_profile=policy,
            task_id=task_packet.sandbox_identity.sandbox_id,
            environment_vars={
                "NEXUS_AGENT_ID": task_packet.agent_id,
                "NEXUS_TASK_ACTION": task_packet.action,
                "NEXUS_TRUST_TIER": task_packet.sandbox_identity.trust_tier.value
            }
        )
        
        if not sandbox_id:
            return SandboxResult(
                success=False,
                output="",
                error="Failed to create OpenShell sandbox",
                exit_code=-1,
                duration_ms=0,
                sandbox_id="none",
                policy_profile=policy
            )
        
        # Build execution command based on action type
        if task_packet.action == "execute_code":
            code = task_packet.payload.get("code", "")
            language = task_packet.payload.get("language", "python")
            
            if language == "python":
                command = "python3"
                stdin = code
            else:
                return SandboxResult(
                    success=False,
                    output="",
                    error=f"Unsupported language: {language}",
                    exit_code=-1,
                    duration_ms=0,
                    sandbox_id=sandbox_id,
                    policy_profile=policy
                )
        elif task_packet.action == "analyze":
            # File analysis task
            file_path = task_packet.payload.get("file_path", "")
            command = "cat"
            args = [file_path]
            stdin = None
        else:
            # Generic command execution
            command = task_packet.payload.get("command", "echo")
            args = task_packet.payload.get("args", [])
            stdin = task_packet.payload.get("stdin")
        
        # Execute
        result = self.execute_in_sandbox(
            sandbox_id=sandbox_id,
            command=command,
            args=args,
            stdin=stdin
        )
        
        # Attach policy profile to result
        result.policy_profile = policy
        
        return result
    
    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """Clean up a sandbox"""
        try:
            response = self.session.delete(
                f"{self.gateway_url}/api/v1/sandboxes/{sandbox_id}",
                timeout=10
            )
            return response.status_code == 204
        except Exception:
            return False
    
    def get_sandbox_status(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a sandbox"""
        try:
            response = self.session.get(
                f"{self.gateway_url}/api/v1/sandboxes/{sandbox_id}",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
