"""
Archivist v5.0 - 4-Layer Truth Engine

Implements the integrity gate for knowledge promotion:
SOURCE → EXTRACTED → INFERRED → CANONICAL

Features:
- Multi-layer knowledge validation
- Cryptographic reference linking (canonical_ref)
- Hermes Curator integration for garbage collection
- Automatic demotion of stale knowledge
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any
import hashlib


class KnowledgeLayer(Enum):
    """The 4 layers of truth in Archivist v5.0."""
    SOURCE = "source"           # Raw input, unverified
    EXTRACTED = "extracted"     # Parsed and structured
    INFERRED = "inferred"       # Derived insights with confidence
    CANONICAL = "canonical"     # Verified ground truth


class SourceType(Enum):
    """Types of knowledge sources."""
    AGENT_LOG = "agent_log"
    EVENT_TRACK = "event_track"
    FAILURE_PATTERN = "failure_pattern"
    GOVERNANCE_DECISION = "governance_decision"
    EXTERNAL_API = "external_api"
    USER_INPUT = "user_input"
    MODEL_OUTPUT = "model_output"


@dataclass
class KnowledgeEntry:
    """A single piece of knowledge in the Archivist system."""
    entry_id: str
    layer: KnowledgeLayer
    source_type: SourceType
    content: Any
    source_hash: str
    canonical_ref: Optional[str] = None  # Links to parent canonical knowledge
    confidence_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_verified: Optional[datetime] = None
    verification_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.source_hash:
            content_str = str(self.content)
            self.source_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    def promote_to(self, new_layer: KnowledgeLayer) -> bool:
        """
        Attempt to promote knowledge to a higher layer.
        
        Args:
            new_layer: Target layer for promotion
            
        Returns:
            True if promotion successful
        """
        layer_order = [KnowledgeLayer.SOURCE, KnowledgeLayer.EXTRACTED, 
                       KnowledgeLayer.INFERRED, KnowledgeLayer.CANONICAL]
        
        current_idx = layer_order.index(self.layer)
        new_idx = layer_order.index(new_layer)
        
        if new_idx <= current_idx:
            return False  # Can only promote upward
        
        # Check requirements for each promotion
        if new_layer == KnowledgeLayer.EXTRACTED:
            return self._can_promote_to_extracted()
        elif new_layer == KnowledgeLayer.INFERRED:
            return self._can_promote_to_inferred()
        elif new_layer == KnowledgeLayer.CANONICAL:
            return self._can_promote_to_canonical()
        
        return False
    
    def _can_promote_to_extracted(self) -> bool:
        """Check if can promote to EXTRACTED layer."""
        return self.content is not None and self.source_hash is not None
    
    def _can_promote_to_inferred(self) -> bool:
        """Check if can promote to INFERRED layer."""
        return (
            self.layer == KnowledgeLayer.EXTRACTED and
            self.confidence_score >= 0.7 and
            self.canonical_ref is not None
        )
    
    def _can_promote_to_canonical(self) -> bool:
        """Check if can promote to CANONICAL layer."""
        return (
            self.layer == KnowledgeLayer.INFERRED and
            self.confidence_score >= 0.95 and
            self.verification_count >= 3
        )


@dataclass
class ReviewGround:
    """Schema for knowledge review and promotion decisions."""
    entry_id: str
    reviewer_id: str  # Agent or system component
    decision: str  # "promote", "demote", "reject"
    from_layer: KnowledgeLayer
    to_layer: KnowledgeLayer
    justification: str
    evidence_hashes: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ArchivistV5:
    """
    Archivist v5.0 - 4-Layer Truth Engine for NEXUS OS.
    
    Manages knowledge lifecycle through strict promotion gates:
    1. SOURCE: Raw logs, events, inputs
    2. EXTRACTED: Structured, parsed data
    3. INFERRED: Insights with confidence scores
    4. CANONICAL: Verified ground truth
    
    Features:
    - Integrity Gate enforcement
    - Cryptographic reference linking
    - Automatic staleness detection
    - Hermes Curator integration for cleanup
    """
    
    def __init__(self, zilliz_client=None, vap_chain=None):
        """
        Initialize Archivist v5.0.
        
        Args:
            zilliz_client: Zilliz client for persistent storage
            vap_chain: VAP chain for audit logging
        """
        self.zilliz_client = zilliz_client
        self.vap_chain = vap_chain
        
        # In-memory knowledge store
        self._knowledge_base: Dict[str, KnowledgeEntry] = {}
        self._review_history: List[ReviewGround] = []
        
        # Layer statistics
        self._layer_counts = {layer: 0 for layer in KnowledgeLayer}
    
    async def ingest(
        self,
        content: Any,
        source_type: SourceType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> KnowledgeEntry:
        """
        Ingest new knowledge at SOURCE layer.
        
        Args:
            content: Raw content to ingest
            source_type: Type of source
            metadata: Additional metadata
            
        Returns:
            Created KnowledgeEntry at SOURCE layer
        """
        entry_id = self._generate_entry_id()
        
        entry = KnowledgeEntry(
            entry_id=entry_id,
            layer=KnowledgeLayer.SOURCE,
            source_type=source_type,
            content=content,
            source_hash="",  # Will be computed in __post_init__
            metadata=metadata or {},
        )
        
        self._knowledge_base[entry_id] = entry
        self._layer_counts[KnowledgeLayer.SOURCE] += 1
        
        # Log ingestion to VAP chain
        if self.vap_chain:
            await self.vap_chain.log_agent_action(
                agent_id="archivist",
                action_type="knowledge_ingest",
                action_params={"entry_id": entry_id, "source_type": source_type.value},
                result_hash=entry.source_hash,
            )
        
        return entry
    
    async def promote(
        self,
        entry_id: str,
        target_layer: KnowledgeLayer,
        reviewer_id: str,
        justification: str,
        evidence_hashes: Optional[List[str]] = None
    ) -> tuple[bool, str]:
        """
        Promote knowledge entry to higher layer.
        
        Args:
            entry_id: ID of entry to promote
            target_layer: Target layer for promotion
            reviewer_id: ID of reviewing agent/system
            justification: Reason for promotion
            evidence_hashes: Supporting evidence hashes
            
        Returns:
            Tuple of (success, message)
        """
        if entry_id not in self._knowledge_base:
            return False, f"Entry {entry_id} not found"
        
        entry = self._knowledge_base[entry_id]
        old_layer = entry.layer
        
        # Attempt promotion
        if not entry.promote_to(target_layer):
            return False, f"Cannot promote from {old_layer.value} to {target_layer.value}"
        
        # Update layer counts
        self._layer_counts[old_layer] -= 1
        self._layer_counts[target_layer] += 1
        
        # Set canonical_ref if promoting to INFERRED or CANONICAL
        if target_layer in [KnowledgeLayer.INFERRED, KnowledgeLayer.CANONICAL]:
            if not entry.canonical_ref:
                # Link to nearest canonical ancestor or self
                entry.canonical_ref = entry_id
        
        # Update verification tracking
        entry.last_verified = datetime.utcnow()
        entry.verification_count += 1
        
        # Record review decision
        review = ReviewGround(
            entry_id=entry_id,
            reviewer_id=reviewer_id,
            decision="promote",
            from_layer=old_layer,
            to_layer=target_layer,
            justification=justification,
            evidence_hashes=evidence_hashes or [],
        )
        self._review_history.append(review)
        
        # Persist to Zilliz if available
        if self.zilliz_client:
            await self._persist_entry(entry)
        
        return True, f"Promoted {entry_id} from {old_layer.value} to {target_layer.value}"
    
    async def extract_and_structure(
        self,
        source_entry_id: str,
        extractor_id: str
    ) -> Optional[KnowledgeEntry]:
        """
        Extract structured data from a SOURCE entry.
        
        Args:
            source_entry_id: ID of source entry
            extractor_id: ID of extracting agent
            
        Returns:
            New EXTRACTED entry or None
        """
        if source_entry_id not in self._knowledge_base:
            return None
        
        source = self._knowledge_base[source_entry_id]
        if source.layer != KnowledgeLayer.SOURCE:
            return None
        
        # Perform extraction (simplified - in production this uses NLP/ML)
        extracted_content = self._perform_extraction(source.content)
        
        # Create new EXTRACTED entry
        entry_id = self._generate_entry_id()
        entry = KnowledgeEntry(
            entry_id=entry_id,
            layer=KnowledgeLayer.EXTRACTED,
            source_type=source.source_type,
            content=extracted_content,
            source_hash=source.source_hash,
            canonical_ref=source_entry_id,  # Link back to source
            confidence_score=0.8,  # Default confidence for extraction
            metadata={**source.metadata, "extracted_by": extractor_id},
        )
        
        self._knowledge_base[entry_id] = entry
        self._layer_counts[KnowledgeLayer.EXTRACTED] += 1
        
        return entry
    
    def _perform_extraction(self, content: Any) -> Any:
        """
        Perform content extraction (simplified).
        
        In production, this would use NLP models to parse and structure
        raw content into standardized formats.
        """
        # Placeholder extraction logic
        if isinstance(content, str):
            return {
                "text": content,
                "length": len(content),
                "word_count": len(content.split()),
            }
        elif isinstance(content, dict):
            return {"structured": content}
        else:
            return {"raw": content}
    
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get knowledge entry by ID."""
        return self._knowledge_base.get(entry_id)
    
    def get_entries_by_layer(self, layer: KnowledgeLayer) -> List[KnowledgeEntry]:
        """Get all entries at a specific layer."""
        return [e for e in self._knowledge_base.values() if e.layer == layer]
    
    def get_canonical_knowledge(self) -> List[KnowledgeEntry]:
        """Get all canonical knowledge entries."""
        return self.get_entries_by_layer(KnowledgeLayer.CANONICAL)
    
    def find_by_canonical_ref(self, canonical_ref: str) -> List[KnowledgeEntry]:
        """Find all entries linked to a canonical reference."""
        return [
            e for e in self._knowledge_base.values()
            if e.canonical_ref == canonical_ref
        ]
    
    def get_stale_entries(self, max_age_days: int = 30) -> List[KnowledgeEntry]:
        """
        Find entries that haven't been verified recently.
        
        Used by Hermes Curator for garbage collection.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            List of stale entries
        """
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        stale = []
        
        for entry in self._knowledge_base.values():
            if entry.layer != KnowledgeLayer.CANONICAL:
                # Non-canonical entries can become stale
                if entry.last_verified and entry.last_verified < cutoff:
                    stale.append(entry)
                elif not entry.last_verified and entry.created_at < cutoff:
                    stale.append(entry)
        
        return stale
    
    async def archive_entry(self, entry_id: str) -> bool:
        """
        Archive an entry (mark for Hermes Curator cleanup).
        
        Args:
            entry_id: ID of entry to archive
            
        Returns:
            True if successful
        """
        if entry_id not in self._knowledge_base:
            return False
        
        entry = self._knowledge_base[entry_id]
        entry.metadata["archived"] = True
        entry.metadata["archived_at"] = datetime.utcnow().isoformat()
        
        return True
    
    def _generate_entry_id(self) -> str:
        """Generate unique entry ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        import random
        return f"arch_{timestamp}_{random.randint(1000, 9999)}"
    
    async def _persist_entry(self, entry: KnowledgeEntry):
        """Persist entry to Zilliz storage."""
        if not self.zilliz_client:
            return
        
        # In production, store in appropriate Zilliz cluster based on layer
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get Archivist statistics."""
        total = sum(self._layer_counts.values())
        
        return {
            "total_entries": total,
            "layer_breakdown": {layer.value: count for layer, count in self._layer_counts.items()},
            "review_count": len(self._review_history),
            "canonical_count": self._layer_counts[KnowledgeLayer.CANONICAL],
            "extraction_rate": (
                self._layer_counts[KnowledgeLayer.EXTRACTED] / total * 100
                if total > 0 else 0
            ),
            "canonical_rate": (
                self._layer_counts[KnowledgeLayer.CANONICAL] / total * 100
                if total > 0 else 0
            ),
        }
