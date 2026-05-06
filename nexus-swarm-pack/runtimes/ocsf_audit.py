"""
OCSF (Open Cybersecurity Schema Framework) Audit Formatter
Converts audit events to OCSF-compliant format for security analysis
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import json


@dataclass
class OCSFAuditEvent:
    """OCSF-compliant audit event"""
    # OCSF Base Event Fields
    class_uid: int = 1001  # Base event class
    class_name: str = "System Activity"
    category_uid: int = 1  # System Activity category
    category_name: str = "System Activity"
    
    # Event identity
    time: str  # ISO 8601 timestamp
    msg: str  # Event message
    severity: str = "Informational"  # Informational, Low, Medium, High, Critical
    
    # Event metadata
    type_uid: int = 1  # Event type
    type_name: str = "System Activity: General"
    
    # Actor (agent)
    actor: Dict[str, Any] = field(default_factory=lambda: {
        "type": "agent",
        "id": "",
        "name": ""
    })
    
    # Resource (sandbox/task)
    resource: Dict[str, Any] = field(default_factory=dict)
    
    # Outcome
    status: str = "Success"  # Success, Failure, Pending
    status_detail: Optional[str] = None
    
    # OCSFExtensions
    extensions: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to OCSF-compliant dictionary"""
        return {
            "class_uid": self.class_uid,
            "class_name": self.class_name,
            "category_uid": self.category_uid,
            "category_name": self.category_name,
            "time": self.time,
            "msg": self.msg,
            "severity": self.severity,
            "type_uid": self.type_uid,
            "type_name": self.type_name,
            "actor": self.actor,
            "resource": self.resource,
            "status": self.status,
            "status_detail": self.status_detail,
            "extensions": self.extensions,
        }
    
    def to_json(self) -> str:
        """Serialize to OCSF JSON"""
        return json.dumps(self.to_dict(), indent=2)


class OCSFAuditFormatter:
    """Formats NEXUS audit events to OCSF format"""
    
    # Severity mapping
    SEVERITY_MAP = {
        "informational": "Informational",
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical",
    }
    
    # Event type mapping
    EVENT_TYPES = {
        "gate_decision": (1001, "System Activity: Gate Decision"),
        "agent_action": (1002, "System Activity: Agent Action"),
        "trust_update": (1003, "System Activity: Trust Update"),
        "sandbox_create": (1004, "System Activity: Sandbox Created"),
        "sandbox_execute": (1005, "System Activity: Sandbox Execution"),
        "sandbox_destroy": (1006, "System Activity: Sandbox Destroyed"),
        "policy_violation": (2001, "Security: Policy Violation"),
        "unauthorized_access": (2002, "Security: Unauthorized Access"),
    }
    
    @classmethod
    def format_gate_decision(cls, gate_result: Any) -> OCSFAuditEvent:
        """Format KAIJU gate decision to OCSF"""
        from nexus_kernel.kaiju import GateResult, GateDecision, ViolationType
        
        # Determine severity based on decision
        if gate_result.decision == GateDecision.HARD_STOP:
            severity = "Critical"
        elif gate_result.decision == GateDecision.DENY:
            severity = "High"
        elif gate_result.decision == GateDecision.REQUIRE_REVIEW:
            severity = "Medium"
        else:
            severity = "Informational"
        
        # Determine event type
        if gate_result.violation_type:
            type_uid, type_name = 2001, "Security: Policy Violation"
        else:
            type_uid, type_name = 1001, "System Activity: Gate Decision"
        
        event = OCSFAuditEvent(
            time=datetime.utcnow().isoformat() + "Z",
            msg=f"Gate decision: {gate_result.decision.value} - {gate_result.reason}",
            severity=severity,
            type_uid=type_uid,
            type_name=type_name,
            actor={
                "type": "agent",
                "id": gate_result.agent_id,
                "name": f"agent_{gate_result.agent_id[:8]}"
            },
            resource={
                "type": "task",
                "proposal_hash": gate_result.proposal_hash,
                "trust_score": gate_result.trust_score.overall if gate_result.trust_score else None,
            },
            status="Success" if gate_result.decision == GateDecision.APPROVE else "Failure",
            status_detail=gate_result.reason,
            extensions={
                "nexus": {
                    "violation_type": gate_result.violation_type.value if gate_result.violation_type else None,
                    "required_budget": gate_result.required_budget,
                    "available_budget": gate_result.available_budget,
                }
            }
        )
        
        return event
    
    @classmethod
    def format_sandbox_event(
        cls,
        event_type: str,
        agent_id: str,
        sandbox_id: str,
        policy_profile: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> OCSFAuditEvent:
        """Format sandbox execution event to OCSF"""
        
        type_uid, type_name = cls.EVENT_TYPES.get(
            event_type, (1001, "System Activity: General")
        )
        
        event = OCSFAuditEvent(
            time=datetime.utcnow().isoformat() + "Z",
            msg=f"Sandbox {event_type}: {sandbox_id} - {'Success' if success else 'Failure'}",
            severity="Informational" if success else "High",
            type_uid=type_uid,
            type_name=type_name,
            actor={
                "type": "agent",
                "id": agent_id,
                "name": f"agent_{agent_id[:8]}"
            },
            resource={
                "type": "sandbox",
                "sandbox_id": sandbox_id,
                "policy_profile": policy_profile,
                **(details or {})
            },
            status="Success" if success else "Failure",
            extensions={
                "nexus": {
                    "event_type": event_type,
                    **(details or {})
                }
            }
        )
        
        return event
    
    @classmethod
    def format_audit_hash(cls, event: OCSFAuditEvent) -> str:
        """Generate audit hash for OCSF event"""
        import hashlib
        
        # Create deterministic string from key fields
        content = f"{event.time}:{event.actor.get('id')}:{event.resource.get('sandbox_id', '')}:{event.status}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


def attach_audit_hash(sandbox_result: Any, ocsf_event: OCSFAuditEvent) -> None:
    """
    Attach OCSF audit hash to SandboxResult.
    This integrates OCSF auditing with OpenShell executor results.
    """
    audit_hash = OCSFAuditFormatter.format_audit_hash(ocsf_event)
    
    if hasattr(sandbox_result, 'audit_hash'):
        sandbox_result.audit_hash = audit_hash
