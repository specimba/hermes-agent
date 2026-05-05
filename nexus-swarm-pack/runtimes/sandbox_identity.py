"""
Sandbox Identity Schema - Phase C
Defines execution context for governed task packets
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
from datetime import datetime


class SecurityLevel(Enum):
    """Isolation levels for sandbox execution"""
    NONE = "none"  # Native execution
    FILESYSTEM = "filesystem"  # FS isolation only
    NETWORK = "network"  # Network isolation
    FULL = "full"  # Complete container isolation


class TrustTier(Enum):
    """Agent trust tiers for capability gating"""
    UNTRUSTED = "untrusted"  # No capabilities
    STANDARD = "standard"  # Basic capabilities
    ELEVATED = "elevated"  # Advanced capabilities
    GOVERNANCE = "governance"  # System-level access


@dataclass
class SandboxIdentity:
    """
    Execution identity attached to every TaskPacket
    Defines the sandbox context, policy profile, and capability constraints
    """
    # Unique identifier for this sandbox instance
    sandbox_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Policy profile name (maps to OpenShell YAML config)
    policy_profile: str = "default"
    
    # Capability tags required for execution
    capability_tags: List[str] = field(default_factory=list)
    
    # Trust tier required (gates premium capabilities)
    trust_tier: TrustTier = TrustTier.STANDARD
    
    # Security isolation level
    security_level: SecurityLevel = SecurityLevel.FULL
    
    # Resource constraints
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    timeout_seconds: int = 300
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    agent_id: Optional[str] = None
    task_ref: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON transport"""
        return {
            "sandbox_id": self.sandbox_id,
            "policy_profile": self.policy_profile,
            "capability_tags": self.capability_tags,
            "trust_tier": self.trust_tier.value,
            "security_level": self.security_level.value,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "agent_id": self.agent_id,
            "task_ref": self.task_ref
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SandboxIdentity':
        """Deserialize from dictionary"""
        data = data.copy()
        if "trust_tier" in data:
            data["trust_tier"] = TrustTier(data["trust_tier"])
        if "security_level" in data:
            data["security_level"] = SecurityLevel(data["security_level"])
        return cls(**data)


@dataclass
class TaskPacket:
    """
    Complete task definition with embedded sandbox identity
    Submitted to KAIJU for authorization before execution
    """
    # Core task definition
    agent_id: str
    action: str
    payload: Dict[str, Any]
    
    # Execution context
    sandbox_identity: SandboxIdentity
    
    # Optional metadata
    priority: int = 5  # 1-10 scale
    deadline: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    
    # Result tracking
    result: Optional[Any] = None
    status: str = "pending"  # pending, approved, rejected, executing, completed, failed
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "agent_id": self.agent_id,
            "action": self.action,
            "payload": self.payload,
            "sandbox_identity": self.sandbox_identity.to_dict(),
            "priority": self.priority,
            "deadline": self.deadline,
            "dependencies": self.dependencies,
            "result": self.result,
            "status": self.status,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskPacket':
        """Deserialize from dictionary"""
        data = data.copy()
        if "sandbox_identity" in data:
            data["sandbox_identity"] = SandboxIdentity.from_dict(data["sandbox_identity"])
        return cls(**data)


# Predefined policy profiles for common use cases
POLICY_PROFILES = {
    "codex_exec": SandboxIdentity(
        policy_profile="codex_exec",
        capability_tags=["python", "filesystem_read", "filesystem_write"],
        trust_tier=TrustTier.STANDARD,
        security_level=SecurityLevel.FILESYSTEM,
        max_memory_mb=1024,
        timeout_seconds=600
    ),
    "opencode_analysis": SandboxIdentity(
        policy_profile="opencode_analysis",
        capability_tags=["read_code", "static_analysis"],
        trust_tier=TrustTier.STANDARD,
        security_level=SecurityLevel.NETWORK,
        max_memory_mb=2048,
        timeout_seconds=300
    ),
    "inference_local": SandboxIdentity(
        policy_profile="inference_local",
        capability_tags=["model_inference", "gpu_access"],
        trust_tier=TrustTier.ELEVATED,
        security_level=SecurityLevel.FULL,
        max_memory_mb=4096,
        timeout_seconds=120
    ),
    "web_search": SandboxIdentity(
        policy_profile="web_search",
        capability_tags=["network_http", "dns_lookup"],
        trust_tier=TrustTier.STANDARD,
        security_level=SecurityLevel.NETWORK,
        max_memory_mb=512,
        timeout_seconds=60
    )
}


def create_task_packet(
    agent_id: str,
    action: str,
    payload: Dict[str, Any],
    policy_name: str = "default",
    **kwargs
) -> TaskPacket:
    """
    Factory function to create TaskPacket with predefined policy
    
    Args:
        agent_id: ID of requesting agent
        action: Action type (execute_code, analyze, search, etc.)
        payload: Action parameters
        policy_name: Name of predefined policy profile
        **kwargs: Override sandbox identity fields
    
    Returns:
        TaskPacket ready for KAIJU submission
    """
    if policy_name in POLICY_PROFILES:
        base_identity = POLICY_PROFILES[policy_name]
        # Apply overrides
        for key, value in kwargs.items():
            if hasattr(base_identity, key):
                setattr(base_identity, key, value)
        sandbox_identity = base_identity
    else:
        sandbox_identity = SandboxIdentity(policy_profile=policy_name, **kwargs)
    
    sandbox_identity.agent_id = agent_id
    return TaskPacket(
        agent_id=agent_id,
        action=action,
        payload=payload,
        sandbox_identity=sandbox_identity
    )
