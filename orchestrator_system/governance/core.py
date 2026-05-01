#!/usr/bin/env python3
"""
Governance Engine Core

Central governance system for enforcing policies, security measures,
and compliance requirements across all agent activities.
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import threading

logger = logging.getLogger(__name__)


class PolicyAction(Enum):
    """Actions that can be taken by policy engine."""
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"
    MODIFY = "modify"


class SecurityLevel(Enum):
    """Security classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class Policy:
    """Represents a governance policy."""
    policy_id: str
    name: str
    description: str
    action: PolicyAction
    conditions: Dict[str, Any]
    priority: int = 0
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityContext:
    """Security context for an operation."""
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    sensitivity_level: SecurityLevel = SecurityLevel.INTERNAL
    required_permissions: Set[str] = field(default_factory=set)
    ip_address: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AuditEvent:
    """Represents an audit log event."""
    event_id: str
    event_type: str
    timestamp: datetime
    actor_id: Optional[str]
    target_id: Optional[str]
    action: str
    result: str
    details: Dict[str, Any] = field(default_factory=dict)
    security_context: Optional[SecurityContext] = None


class PolicyEngine:
    """
    Policy evaluation engine.
    
    Evaluates policies against requests and determines allowed actions.
    """
    
    def __init__(self):
        self._policies: Dict[str, Policy] = {}
        self._lock = threading.RLock()
        self._load_default_policies()
    
    def _load_default_policies(self):
        """Load default governance policies."""
        default_policies = [
            Policy(
                policy_id="pol-001",
                name="No Recursive Delegation",
                description="Prevent agents from delegating to themselves",
                action=PolicyAction.DENY,
                conditions={"type": "delegation", "target_equals_source": True},
                priority=100,
            ),
            Policy(
                policy_id="pol-002",
                name="Block Dangerous Tools",
                description="Block execution of dangerous system commands",
                action=PolicyAction.DENY,
                conditions={
                    "type": "tool_execution",
                    "tool_in": ["rm -rf /", "chmod -R 777", "dd if=/dev/zero"],
                },
                priority=100,
            ),
            Policy(
                policy_id="pol-003",
                name="Rate Limiting",
                description="Limit API calls per minute per agent",
                action=PolicyAction.REVIEW,
                conditions={"type": "api_call", "rate_limit": 60},
                priority=50,
            ),
            Policy(
                policy_id="pol-004",
                name="Data Exfiltration Prevention",
                description="Block large data transfers to external endpoints",
                action=PolicyAction.DENY,
                conditions={"type": "network", "max_data_size_mb": 100},
                priority=90,
            ),
        ]
        
        for policy in default_policies:
            self._policies[policy.policy_id] = policy
        
        logger.info(f"Loaded {len(default_policies)} default policies")
    
    def add_policy(self, policy: Policy) -> bool:
        """Add a new policy."""
        with self._lock:
            if policy.policy_id in self._policies:
                return False
            self._policies[policy.policy_id] = policy
            logger.info(f"Policy {policy.policy_id} added")
            return True
    
    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy."""
        with self._lock:
            if policy_id not in self._policies:
                return False
            del self._policies[policy_id]
            logger.info(f"Policy {policy_id} removed")
            return True
    
    def evaluate(self, request_type: str, request_data: Dict[str, Any]) -> PolicyAction:
        """Evaluate policies against a request."""
        with self._lock:
            applicable_policies = []
            
            for policy in self._policies.values():
                if not policy.enabled:
                    continue
                
                # Check if policy applies to this request type
                policy_type = policy.conditions.get("type")
                if policy_type and policy_type != request_type:
                    continue
                
                # Evaluate conditions
                if self._evaluate_conditions(policy.conditions, request_data):
                    applicable_policies.append(policy)
            
            # Sort by priority (higher first)
            applicable_policies.sort(key=lambda p: -p.priority)
            
            # Return highest priority action
            if applicable_policies:
                return applicable_policies[0].action
            
            return PolicyAction.ALLOW
    
    def _evaluate_conditions(self, conditions: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Evaluate policy conditions against request data."""
        for key, expected in conditions.items():
            if key == "type":
                continue
            
            if key.endswith("_in"):
                # Check if value is in list
                field_name = key[:-3]
                if data.get(field_name) not in expected:
                    return False
            
            elif key.endswith("_equals"):
                # Check equality between two fields
                field1, field2 = expected.split("=")
                if data.get(field1) != data.get(field2):
                    return False
            
            elif key.startswith("max_"):
                # Maximum value check
                field_name = key[4:]
                if data.get(field_name, 0) > expected:
                    return False
            
            elif key.startswith("min_"):
                # Minimum value check
                field_name = key[4:]
                if data.get(field_name, 0) < expected:
                    return False
            
            else:
                # Direct equality check
                if data.get(key) != expected:
                    return False
        
        return True
    
    def get_all_policies(self) -> List[Policy]:
        """Get all policies."""
        with self._lock:
            return list(self._policies.values())


class SecurityManager:
    """
    Security management for the multi-agent system.
    
    Handles authentication, authorization, encryption, and threat detection.
    """
    
    def __init__(self):
        self._api_keys: Dict[str, Dict[str, Any]] = {}
        self._permissions: Dict[str, Set[str]] = {}
        self._blocked_ips: Set[str] = set()
        self._rate_limits: Dict[str, List[datetime]] = {}
        self._lock = threading.RLock()
        self._encryption_key = self._get_or_create_encryption_key()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for sensitive data."""
        key_file = Path.home() / ".hermes" / "governance_key"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        
        # Generate new key
        key = os.urandom(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        with open(key_file, 'wb') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        
        return key
    
    def register_api_key(self, key: str, owner: str, permissions: Set[str]) -> bool:
        """Register an API key."""
        with self._lock:
            if key in self._api_keys:
                return False
            
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            self._api_keys[key_hash] = {
                "owner": owner,
                "created_at": datetime.now(),
                "last_used": None,
                "enabled": True,
            }
            self._permissions[key_hash] = permissions
            
            logger.info(f"API key registered for {owner}")
            return True
    
    def validate_api_key(self, key: str) -> Optional[str]:
        """Validate an API key and return owner if valid."""
        with self._lock:
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            
            if key_hash not in self._api_keys:
                return None
            
            key_info = self._api_keys[key_hash]
            if not key_info["enabled"]:
                return None
            
            key_info["last_used"] = datetime.now()
            return key_info["owner"]
    
    def check_permission(self, key_hash: str, permission: str) -> bool:
        """Check if a key has a specific permission."""
        with self._lock:
            if key_hash not in self._permissions:
                return False
            return permission in self._permissions[key_hash]
    
    def block_ip(self, ip: str, reason: str = ""):
        """Block an IP address."""
        with self._lock:
            self._blocked_ips.add(ip)
            logger.warning(f"IP {ip} blocked: {reason}")
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP is blocked."""
        with self._lock:
            return ip in self._blocked_ips
    
    def check_rate_limit(self, identifier: str, max_requests: int, window_seconds: int) -> bool:
        """Check if rate limit is exceeded."""
        with self._lock:
            now = datetime.now()
            
            if identifier not in self._rate_limits:
                self._rate_limits[identifier] = []
            
            # Clean old entries
            cutoff = now.timestamp() - window_seconds
            self._rate_limits[identifier] = [
                ts for ts in self._rate_limits[identifier]
                if ts.timestamp() > cutoff
            ]
            
            # Check limit
            if len(self._rate_limits[identifier]) >= max_requests:
                return False
            
            # Record this request
            self._rate_limits[identifier].append(now)
            return True
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data (simple XOR for demonstration)."""
        # In production, use proper encryption like AES
        data_bytes = data.encode('utf-8')
        key_cycle = (self._encryption_key * ((len(data_bytes) // len(self._encryption_key)) + 1))[:len(data_bytes)]
        encrypted = bytes(a ^ b for a, b in zip(data_bytes, key_cycle))
        return encrypted.hex()
    
    def decrypt_sensitive_data(self, encrypted_hex: str) -> str:
        """Decrypt sensitive data."""
        encrypted = bytes.fromhex(encrypted_hex)
        key_cycle = (self._encryption_key * ((len(encrypted) // len(self._encryption_key)) + 1))[:len(encrypted)]
        decrypted = bytes(a ^ b for a, b in zip(encrypted, key_cycle))
        return decrypted.decode('utf-8')
    
    def scan_for_threats(self, data: Dict[str, Any]) -> List[str]:
        """Scan data for potential security threats."""
        threats = []
        
        # Check for sensitive patterns
        sensitive_patterns = [
            (r'password\s*[=:]\s*\S+', 'Potential password exposure'),
            (r'api[_-]?key\s*[=:]\s*\S+', 'Potential API key exposure'),
            (r'secret\s*[=:]\s*\S+', 'Potential secret exposure'),
            (r'token\s*[=:]\s*\S+', 'Potential token exposure'),
        ]
        
        data_str = json.dumps(data).lower()
        for pattern, threat_msg in sensitive_patterns:
            if re.search(pattern, data_str, re.IGNORECASE):
                threats.append(threat_msg)
        
        return threats


class AuditLogger:
    """
    Comprehensive audit logging system.
    
    Logs all significant events for compliance, forensics, and analysis.
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = Path(log_dir) if log_dir else Path.home() / ".hermes" / "audits"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._event_buffer: List[AuditEvent] = []
        self._buffer_size = 100
        
        # Setup dedicated audit logger
        self._audit_logger = logging.getLogger("hermes.audit")
        self._audit_logger.setLevel(logging.INFO)
        
        # File handler
        log_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        ))
        self._audit_logger.addHandler(file_handler)
    
    def log_event(self, event_type: str, action: str, result: str,
                  actor_id: Optional[str] = None, target_id: Optional[str] = None,
                  details: Optional[Dict] = None, security_context: Optional[SecurityContext] = None):
        """Log an audit event."""
        event_id = f"evt-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(4).hex()}"
        
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now(),
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            result=result,
            details=details or {},
            security_context=security_context,
        )
        
        with self._lock:
            self._event_buffer.append(event)
            
            # Flush buffer if full
            if len(self._event_buffer) >= self._buffer_size:
                self._flush_buffer()
        
        # Log immediately
        log_entry = {
            "event_id": event_id,
            "type": event_type,
            "action": action,
            "result": result,
            "actor": actor_id,
            "target": target_id,
        }
        if details:
            log_entry["details"] = details
        
        self._audit_logger.info(json.dumps(log_entry))
    
    def _flush_buffer(self):
        """Flush event buffer to persistent storage."""
        if not self._event_buffer:
            return
        
        # Write to daily file
        today = datetime.now().strftime('%Y%m%d')
        file_path = self.log_dir / f"audit_events_{today}.jsonl"
        
        with self._lock:
            with open(file_path, 'a') as f:
                for event in self._event_buffer:
                    event_dict = {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "timestamp": event.timestamp.isoformat(),
                        "actor_id": event.actor_id,
                        "target_id": event.target_id,
                        "action": event.action,
                        "result": event.result,
                        "details": event.details,
                    }
                    f.write(json.dumps(event_dict) + '\n')
            
            self._event_buffer.clear()
        
        logger.debug(f"Flushed {len(self._event_buffer)} audit events to {file_path}")
    
    def query_events(self, event_type: Optional[str] = None,
                     actor_id: Optional[str] = None,
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None,
                     limit: int = 100) -> List[AuditEvent]:
        """Query audit events."""
        events = []
        
        # Search current buffer
        with self._lock:
            for event in self._event_buffer:
                if event_type and event.event_type != event_type:
                    continue
                if actor_id and event.actor_id != actor_id:
                    continue
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue
                events.append(event)
                
                if len(events) >= limit:
                    break
        
        # Search files if needed
        if len(events) < limit:
            # Find relevant files
            date_pattern = "audit_events_*.jsonl"
            for log_file in self.log_dir.glob(date_pattern):
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            event_dict = json.loads(line.strip())
                            
                            if event_type and event_dict.get("event_type") != event_type:
                                continue
                            if actor_id and event_dict.get("actor_id") != actor_id:
                                continue
                            
                            event_timestamp = datetime.fromisoformat(event_dict["timestamp"])
                            if start_time and event_timestamp < start_time:
                                continue
                            if end_time and event_timestamp > end_time:
                                continue
                            
                            event = AuditEvent(**event_dict)
                            events.append(event)
                            
                            if len(events) >= limit:
                                break
                except Exception as e:
                    logger.error(f"Error reading audit file {log_file}: {e}")
                
                if len(events) >= limit:
                    break
        
        return events[:limit]
    
    def export_audit_trail(self, output_path: str,
                           start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None):
        """Export complete audit trail to a file."""
        events = self.query_events(start_time=start_time, end_time=end_time, limit=100000)
        
        with open(output_path, 'w') as f:
            json.dump([
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp.isoformat(),
                    "actor_id": e.actor_id,
                    "target_id": e.target_id,
                    "action": e.action,
                    "result": e.result,
                    "details": e.details,
                }
                for e in events
            ], f, indent=2)
        
        logger.info(f"Exported {len(events)} audit events to {output_path}")


class GovernanceEngine:
    """
    Central governance engine coordinating policy, security, and audit.
    
    Provides unified interface for:
    - Policy enforcement
    - Security validation
    - Audit logging
    - Compliance checking
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = self._load_config()
        
        self.policy_engine = PolicyEngine()
        self.security_manager = SecurityManager()
        self.audit_logger = AuditLogger()
        
        self._lock = threading.RLock()
        
        logger.info("GovernanceEngine initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load governance configuration."""
        default_config = {
            "enable_policy_enforcement": True,
            "enable_security_checks": True,
            "enable_audit_logging": True,
            "max_api_calls_per_minute": 60,
            "max_task_duration_seconds": 3600,
            "allowed_models": [],
            "blocked_tools": ["execute_code"],
            "require_approval_for": [],
        }
        
        if self.config_path and Path(self.config_path).exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    default_config.update(file_config)
            except Exception as e:
                logger.warning(f"Failed to load governance config: {e}")
        
        return default_config
    
    def validate_agent_creation(self, agent_config) -> bool:
        """Validate agent creation against governance policies."""
        if not self.config["enable_policy_enforcement"]:
            return True
        
        request_data = {
            "type": "agent_creation",
            "model": getattr(agent_config, 'model', ''),
            "toolsets": getattr(agent_config, 'toolsets', []),
        }
        
        action = self.policy_engine.evaluate("agent_creation", request_data)
        
        # Audit
        self.audit_logger.log_event(
            event_type="agent_lifecycle",
            action="create_agent",
            result="approved" if action == PolicyAction.ALLOW else "denied",
            details={"config": str(agent_config)},
        )
        
        return action == PolicyAction.ALLOW
    
    def validate_task_delegation(self, task) -> bool:
        """Validate task delegation against governance policies."""
        if not self.config["enable_policy_enforcement"]:
            return True
        
        request_data = {
            "type": "task_delegation",
            "priority": getattr(task, 'priority', '').name if hasattr(task.priority, 'name') else str(task.priority),
            "description_length": len(getattr(task, 'description', '')),
        }
        
        action = self.policy_engine.evaluate("task_delegation", request_data)
        
        # Audit
        self.audit_logger.log_event(
            event_type="task_management",
            action="delegate_task",
            result="approved" if action == PolicyAction.ALLOW else "denied",
            target_id=getattr(task, 'task_id', None),
            details={"priority": request_data["priority"]},
        )
        
        return action == PolicyAction.ALLOW
    
    def validate_tool_execution(self, tool_name: str, arguments: Dict[str, Any],
                                agent_id: Optional[str] = None) -> bool:
        """Validate tool execution against security policies."""
        if not self.config["enable_security_checks"]:
            return True
        
        # Check blocked tools
        if tool_name in self.config.get("blocked_tools", []):
            self.audit_logger.log_event(
                event_type="security",
                action="block_tool",
                result="denied",
                actor_id=agent_id,
                details={"tool": tool_name, "reason": "blocked_by_policy"},
            )
            return False
        
        # Scan for threats
        threats = self.security_manager.scan_for_threats(arguments)
        if threats:
            self.audit_logger.log_event(
                event_type="security",
                action="threat_detected",
                result="blocked",
                actor_id=agent_id,
                details={"tool": tool_name, "threats": threats},
            )
            return False
        
        return True
    
    def check_rate_limit(self, identifier: str) -> bool:
        """Check if rate limit is exceeded."""
        max_requests = self.config.get("max_api_calls_per_minute", 60)
        return self.security_manager.check_rate_limit(
            identifier, max_requests, window_seconds=60
        )
    
    def log_security_event(self, event_type: str, action: str, result: str,
                          actor_id: Optional[str] = None, details: Optional[Dict] = None):
        """Log a security-related event."""
        self.audit_logger.log_event(
            event_type=f"security_{event_type}",
            action=action,
            result=result,
            actor_id=actor_id,
            details=details,
        )
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate compliance report."""
        # Get recent events
        now = datetime.now()
        events_24h = self.audit_logger.query_events(
            start_time=datetime(now.year, now.month, now.day),
            limit=1000
        )
        
        # Categorize events
        categories = {
            "agent_lifecycle": 0,
            "task_management": 0,
            "security": 0,
            "policy_violation": 0,
        }
        
        denied_count = 0
        for event in events_24h:
            if event.event_type in categories:
                categories[event.event_type] += 1
            if event.result in ["denied", "blocked"]:
                denied_count += 1
        
        return {
            "timestamp": now.isoformat(),
            "period": "last_24_hours",
            "total_events": len(events_24h),
            "events_by_category": categories,
            "denied_actions": denied_count,
            "compliance_status": "compliant" if denied_count == 0 else "violations_detected",
            "active_policies": len(self.policy_engine.get_all_policies()),
        }
    
    def export_audit(self, output_path: str):
        """Export complete audit trail."""
        self.audit_logger.export_audit_trail(output_path)
