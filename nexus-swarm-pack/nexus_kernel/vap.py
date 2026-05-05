"""
VAP Chain - Cryptographic Audit Trail

Implements the Verifiable Audit Proof chain with SHA-256 hashing for:
- Gate decision logging
- Agent action provenance
- Immutable audit records
- Compliance verification
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import hashlib
import json


@dataclass
class VAPEntry:
    """A single entry in the VAP audit chain."""
    entry_id: str
    timestamp: datetime
    event_type: str
    agent_id: str
    action_hash: str
    previous_hash: str
    current_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "action_hash": self.action_hash,
            "previous_hash": self.previous_hash,
            "current_hash": self.current_hash,
            "metadata": self.metadata,
            "signature": self.signature,
        }


@dataclass
class GateDecisionRecord:
    """Record of a KAIJU gate decision for VAP logging."""
    decision: str
    agent_id: str
    proposal_hash: str
    violation_type: Optional[str]
    reason: str
    trust_score: Optional[float]
    required_budget: int
    available_budget: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class VAPChain:
    """
    Verifiable Audit Proof Chain for NEXUS OS.
    
    Creates an immutable, cryptographically-linked chain of all governance
    decisions and agent actions. Each entry includes:
    - SHA-256 hash of content
    - Hash of previous entry (blockchain-style linking)
    - Timestamp proof
    - Digital signature (when keys are available)
    
    Used for:
    - Compliance auditing
    - Dispute resolution
    - Agent behavior analysis
    - Regulatory reporting
    """
    
    def __init__(self, storage_backend=None):
        """
        Initialize VAP Chain.
        
        Args:
            storage_backend: Optional persistent storage (Zilliz, Cloudflare R2, etc.)
        """
        self.storage_backend = storage_backend
        self._chain: List[VAPEntry] = []
        self._entry_counter = 0
        self._genesis_hash = self._compute_genesis_hash()
    
    def _compute_genesis_hash(self) -> str:
        """Compute the genesis block hash."""
        genesis_data = {
            "type": "genesis",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0-rc1",
            "system": "NEXUS_OS"
        }
        return hashlib.sha256(json.dumps(genesis_data, sort_keys=True).encode()).hexdigest()
    
    def _generate_entry_id(self) -> str:
        """Generate unique entry ID."""
        self._entry_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"vap_{timestamp}_{self._entry_counter:06d}"
    
    def _compute_hash(
        self,
        entry_data: Dict[str, Any],
        previous_hash: str
    ) -> str:
        """
        Compute SHA-256 hash for an entry.
        
        Args:
            entry_data: Entry content dictionary
            previous_hash: Hash of previous entry
            
        Returns:
            SHA-256 hex digest
        """
        # Include previous hash in current hash computation
        content = {
            **entry_data,
            "previous_hash": previous_hash,
            "chain_version": "1.0"
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _get_previous_hash(self) -> str:
        """Get hash of the most recent entry or genesis hash."""
        if not self._chain:
            return self._genesis_hash
        return self._chain[-1].current_hash
    
    async def log_gate_decision(self, gate_result: Any) -> VAPEntry:
        """
        Log a KAIJU gate decision to the VAP chain.
        
        Args:
            gate_result: GateResult from KAIJU governor
            
        Returns:
            Created VAPEntry
        """
        # Extract data from gate result
        record = GateDecisionRecord(
            decision=gate_result.decision.value,
            agent_id=gate_result.agent_id,
            proposal_hash=gate_result.proposal_hash,
            violation_type=gate_result.violation_type.value if gate_result.violation_type else None,
            reason=gate_result.reason,
            trust_score=gate_result.trust_score.overall if gate_result.trust_score else None,
            required_budget=gate_result.required_budget,
            available_budget=gate_result.available_budget,
        )
        
        return await self._log_event(
            event_type="gate_decision",
            agent_id=gate_result.agent_id,
            action_hash=gate_result.proposal_hash,
            metadata=record.__dict__
        )
    
    async def log_agent_action(
        self,
        agent_id: str,
        action_type: str,
        action_params: Dict[str, Any],
        result_hash: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VAPEntry:
        """
        Log an agent action execution to the VAP chain.
        
        Args:
            agent_id: Executing agent ID
            action_type: Type of action performed
            action_params: Action parameters
            result_hash: Hash of action result
            metadata: Additional metadata
            
        Returns:
            Created VAPEntry
        """
        action_content = {
            "action_type": action_type,
            "params_hash": hashlib.sha256(
                json.dumps(action_params, sort_keys=True).encode()
            ).hexdigest()[:16],
            "result_hash": result_hash,
        }
        
        return await self._log_event(
            event_type="agent_action",
            agent_id=agent_id,
            action_hash=action_content["params_hash"],
            metadata={**action_content, **(metadata or {})}
        )
    
    async def log_trust_update(
        self,
        agent_id: str,
        old_score: float,
        new_score: float,
        reason: str,
        violation_type: Optional[str] = None
    ) -> VAPEntry:
        """
        Log a trust score update to the VAP chain.
        
        Args:
            agent_id: Agent whose trust was updated
            old_score: Previous trust score
            new_score: New trust score
            reason: Reason for update
            violation_type: Associated violation type if any
            
        Returns:
            Created VAPEntry
        """
        metadata = {
            "old_score": old_score,
            "new_score": new_score,
            "delta": new_score - old_score,
            "reason": reason,
        }
        if violation_type:
            metadata["violation_type"] = violation_type
        
        action_hash = hashlib.sha256(
            f"{agent_id}:{old_score}:{new_score}".encode()
        ).hexdigest()[:16]
        
        return await self._log_event(
            event_type="trust_update",
            agent_id=agent_id,
            action_hash=action_hash,
            metadata=metadata
        )
    
    async def _log_event(
        self,
        event_type: str,
        agent_id: str,
        action_hash: str,
        metadata: Dict[str, Any]
    ) -> VAPEntry:
        """
        Internal method to create and store a VAP entry.
        
        Args:
            event_type: Type of event being logged
            agent_id: Associated agent ID
            action_hash: Hash of the action/content
            metadata: Event metadata
            
        Returns:
            Created VAPEntry
        """
        previous_hash = self._get_previous_hash()
        entry_id = self._generate_entry_id()
        timestamp = datetime.utcnow()
        
        # Convert any non-serializable objects in metadata
        serializable_metadata = self._make_serializable(metadata)
        
        # Create entry data
        entry_data = {
            "entry_id": entry_id,
            "event_type": event_type,
            "agent_id": agent_id,
            "action_hash": action_hash,
            "metadata": serializable_metadata,
            "timestamp": timestamp.isoformat(),
        }
        
        # Compute current hash
        current_hash = self._compute_hash(entry_data, previous_hash)
        
        # Create entry
        entry = VAPEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            event_type=event_type,
            agent_id=agent_id,
            action_hash=action_hash,
            previous_hash=previous_hash,
            current_hash=current_hash,
            metadata=serializable_metadata,
        )
        
        # Store in memory chain
        self._chain.append(entry)
        
        # Persist to storage backend if available
        if self.storage_backend:
            await self.storage_backend.store_entry(entry)
        
        return entry
    
    def _make_serializable(self, obj: Any) -> Any:
        """Convert objects to JSON-serializable format."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            return self._make_serializable(obj.__dict__)
        elif isinstance(obj, Enum):
            return obj.value
        else:
            return obj
    
    def verify_chain_integrity(self) -> bool:
        """
        Verify the integrity of the entire VAP chain.
        
        Returns:
            True if all hashes link correctly, False otherwise
        """
        if not self._chain:
            return True
        
        # Verify genesis link
        if self._chain[0].previous_hash != self._genesis_hash:
            return False
        
        # Verify each link
        for i in range(1, len(self._chain)):
            prev_entry = self._chain[i - 1]
            curr_entry = self._chain[i]
            
            # Check hash linkage
            if curr_entry.previous_hash != prev_entry.current_hash:
                return False
            
            # Recompute hash and verify
            entry_data = {
                "entry_id": curr_entry.entry_id,
                "event_type": curr_entry.event_type,
                "agent_id": curr_entry.agent_id,
                "action_hash": curr_entry.action_hash,
                "metadata": curr_entry.metadata,
                "timestamp": curr_entry.timestamp.isoformat(),
            }
            recomputed_hash = self._compute_hash(entry_data, curr_entry.previous_hash)
            
            if recomputed_hash != curr_entry.current_hash:
                return False
        
        return True
    
    def get_chain_length(self) -> int:
        """Get current chain length."""
        return len(self._chain)
    
    def get_entries_by_agent(self, agent_id: str) -> List[VAPEntry]:
        """Get all entries for a specific agent."""
        return [e for e in self._chain if e.agent_id == agent_id]
    
    def get_entries_by_type(self, event_type: str) -> List[VAPEntry]:
        """Get all entries of a specific event type."""
        return [e for e in self._chain if e.event_type == event_type]
    
    def get_recent_entries(self, limit: int = 100) -> List[VAPEntry]:
        """Get most recent entries."""
        return self._chain[-limit:]
    
    def export_chain(self) -> List[Dict[str, Any]]:
        """Export entire chain for external audit."""
        return [entry.to_dict() for entry in self._chain]
    
    def get_audit_summary(self) -> Dict[str, Any]:
        """Generate audit summary statistics."""
        total_entries = len(self._chain)
        
        # Count by event type
        event_counts: Dict[str, int] = {}
        for entry in self._chain:
            event_counts[entry.event_type] = event_counts.get(entry.event_type, 0) + 1
        
        # Count by agent
        agent_counts: Dict[str, int] = {}
        for entry in self._chain:
            agent_counts[entry.agent_id] = agent_counts.get(entry.agent_id, 0) + 1
        
        # Count violations
        violation_count = sum(
            1 for e in self._chain 
            if e.event_type == "gate_decision" and e.metadata.get("violation_type")
        )
        
        return {
            "total_entries": total_entries,
            "chain_integrity": self.verify_chain_integrity(),
            "event_breakdown": event_counts,
            "agent_activity": agent_counts,
            "violation_count": violation_count,
            "genesis_hash": self._genesis_hash,
            "latest_hash": self._chain[-1].current_hash if self._chain else self._genesis_hash,
        }
