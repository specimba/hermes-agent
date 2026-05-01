#!/usr/bin/env python3
"""
Agent Memory Layer and Cache System

Provides persistent memory storage for agents with intelligent caching
to reduce token usage and improve response times.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
import threading
from collections import OrderedDict
import pickle
import sqlite3

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of agent memory."""
    SHORT_TERM = "short_term"  # Recent conversation context
    LONG_TERM = "long_term"    # Persistent knowledge
    EPISODIC = "episodic"      # Specific events/experiences
    SEMANTIC = "semantic"      # Facts and concepts
    PROCEDURAL = "procedural"  # Skills and how-to knowledge


class CacheStrategy(Enum):
    """Caching strategies."""
    LRU = "lru"           # Least Recently Used
    LFU = "lfu"           # Least Frequently Used
    TTL = "ttl"           # Time-To-Live based
    HYBRID = "hybrid"     # Combination of strategies


@dataclass
class MemoryEntry:
    """Represents a single memory entry."""
    memory_id: str
    agent_id: str
    memory_type: MemoryType
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    importance_score: float = 0.0
    expiration: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "memory_id": self.memory_id,
            "agent_id": self.agent_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "importance_score": self.importance_score,
            "expiration": self.expiration.isoformat() if self.expiration else None,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            memory_id=data["memory_id"],
            agent_id=data["agent_id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            accessed_at=datetime.fromisoformat(data["accessed_at"]),
            access_count=data.get("access_count", 0),
            importance_score=data.get("importance_score", 0.0),
            expiration=datetime.fromisoformat(data["expiration"]) if data.get("expiration") else None,
            tags=data.get("tags", []),
        )


@dataclass
class CacheEntry:
    """Represents a cached item."""
    cache_key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl_seconds is None:
            return False
        expiration = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiration
    
    def touch(self):
        """Update access time and count."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class LRUCache:
    """Least Recently Used cache implementation."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set item in cache."""
        with self._lock:
            # Calculate size
            try:
                size_bytes = len(pickle.dumps(value))
            except Exception:
                size_bytes = 0
            
            entry = CacheEntry(
                cache_key=key,
                value=value,
                ttl_seconds=ttl_seconds,
                size_bytes=size_bytes,
            )
            
            if key in self._cache:
                del self._cache[key]
            
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = entry
    
    def delete(self, key: str) -> bool:
        """Delete item from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "memory_bytes": sum(e.size_bytes for e in self._cache.values()),
            }
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


class SemanticCache:
    """Semantic similarity-based cache for reducing token usage."""
    
    def __init__(self, similarity_threshold: float = 0.95):
        self.similarity_threshold = similarity_threshold
        self._entries: Dict[str, Tuple[str, Any, List[float]]] = {}
        self._lock = threading.RLock()
    
    def _compute_embedding(self, text: str) -> List[float]:
        """Compute simple hash-based embedding (placeholder for real embeddings)."""
        # In production, use actual embedding model
        hash_val = hashlib.sha256(text.encode()).hexdigest()
        return [int(hash_val[i:i+2], 16) / 256.0 for i in range(0, 32, 2)]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def get_similar(self, query: str) -> Optional[Any]:
        """Get cached response for semantically similar query."""
        query_embedding = self._compute_embedding(query)
        
        with self._lock:
            best_match = None
            best_similarity = 0.0
            
            for key, (original_query, value, embedding) in self._entries.items():
                similarity = self._cosine_similarity(query_embedding, embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = (key, value)
            
            if best_similarity >= self.similarity_threshold and best_match:
                logger.debug(f"Semantic cache hit with similarity {best_similarity:.3f}")
                return best_match[1]
            
            return None
    
    def set(self, query: str, value: Any):
        """Cache a query-response pair."""
        embedding = self._compute_embedding(query)
        
        with self._lock:
            # Limit cache size
            if len(self._entries) >= 500:
                # Remove oldest entry
                if self._entries:
                    oldest_key = next(iter(self._entries))
                    del self._entries[oldest_key]
            
            self._entries[query] = (query, value, embedding)
    
    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._entries.clear()


class MemoryStore:
    """Persistent memory storage for agents."""
    
    def __init__(self, db_path: str = "agent_memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                accessed_at TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                importance_score REAL DEFAULT 0.0,
                expiration TIMESTAMP,
                tags TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_agent_id ON memories(agent_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_tags ON memories(tags)
        ''')
        
        conn.commit()
        conn.close()
    
    def store(self, entry: MemoryEntry) -> bool:
        """Store a memory entry."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO memories 
                (memory_id, agent_id, memory_type, content, metadata, 
                 created_at, updated_at, accessed_at, access_count, 
                 importance_score, expiration, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.memory_id,
                entry.agent_id,
                entry.memory_type.value,
                json.dumps(entry.content) if not isinstance(entry.content, str) else entry.content,
                json.dumps(entry.metadata),
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
                entry.accessed_at.isoformat(),
                entry.access_count,
                entry.importance_score,
                entry.expiration.isoformat() if entry.expiration else None,
                json.dumps(entry.tags),
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return False
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM memories WHERE memory_id = ?', (memory_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return MemoryEntry(
                    memory_id=row[0],
                    agent_id=row[1],
                    memory_type=MemoryType(row[2]),
                    content=json.loads(row[3]) if row[3].startswith('{') or row[3].startswith('[') else row[3],
                    metadata=json.loads(row[4]) if row[4] else {},
                    created_at=datetime.fromisoformat(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                    accessed_at=datetime.fromisoformat(row[7]),
                    access_count=row[8],
                    importance_score=row[9],
                    expiration=datetime.fromisoformat(row[10]) if row[10] else None,
                    tags=json.loads(row[11]) if row[11] else [],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve memory: {e}")
            return None
    
    def search(self, agent_id: Optional[str] = None,
               memory_type: Optional[MemoryType] = None,
               tags: Optional[List[str]] = None,
               limit: int = 100) -> List[MemoryEntry]:
        """Search memories with filters."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM memories WHERE 1=1"
            params = []
            
            if agent_id:
                query += " AND agent_id = ?"
                params.append(agent_id)
            
            if memory_type:
                query += " AND memory_type = ?"
                params.append(memory_type.value)
            
            if tags:
                for tag in tags:
                    query += " AND tags LIKE ?"
                    params.append(f'%{tag}%')
            
            query += " ORDER BY importance_score DESC, accessed_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                entry = MemoryEntry(
                    memory_id=row[0],
                    agent_id=row[1],
                    memory_type=MemoryType(row[2]),
                    content=json.loads(row[3]) if row[3].startswith('{') or row[3].startswith('[') else row[3],
                    metadata=json.loads(row[4]) if row[4] else {},
                    created_at=datetime.fromisoformat(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                    accessed_at=datetime.fromisoformat(row[7]),
                    access_count=row[8],
                    importance_score=row[9],
                    expiration=datetime.fromisoformat(row[10]) if row[10] else None,
                    tags=json.loads(row[11]) if row[11] else [],
                )
                results.append(entry)
            
            return results
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM memories WHERE memory_id = ?', (memory_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False
    
    def update_access(self, memory_id: str):
        """Update access timestamp and count for a memory."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE memories 
                SET accessed_at = ?, access_count = access_count + 1
                WHERE memory_id = ?
            ''', (datetime.now().isoformat(), memory_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update memory access: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM memories')
            total = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT agent_id) FROM memories')
            agents = cursor.fetchone()[0]
            
            cursor.execute('SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type')
            by_type = dict(cursor.fetchall())
            
            conn.close()
            
            return {
                "total_memories": total,
                "total_agents": agents,
                "memories_by_type": by_type,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


class AgentMemoryManager:
    """Manages agent memory with caching for token optimization."""
    
    def __init__(self, agent_id: str, 
                 cache_strategy: CacheStrategy = CacheStrategy.HYBRID,
                 cache_size: int = 1000,
                 db_path: str = "agent_memory.db"):
        self.agent_id = agent_id
        self.cache_strategy = cache_strategy
        
        # Initialize caches
        self.response_cache = LRUCache(max_size=cache_size)
        self.semantic_cache = SemanticCache(similarity_threshold=0.9)
        
        # Initialize persistent store
        self.memory_store = MemoryStore(db_path=db_path)
        
        # Short-term memory (conversation context)
        self.short_term_memory: List[MemoryEntry] = []
        self.max_short_term_length = 50
        
        # Lock for thread safety
        self._lock = threading.RLock()
    
    def cache_response(self, query: str, response: Any, 
                      ttl_seconds: int = 3600) -> str:
        """Cache a query-response pair."""
        cache_key = hashlib.sha256(f"{self.agent_id}:{query}".encode()).hexdigest()[:16]
        
        # Store in LRU cache
        self.response_cache.set(cache_key, response, ttl_seconds=ttl_seconds)
        
        # Store in semantic cache for fuzzy matching
        self.semantic_cache.set(query, response)
        
        logger.debug(f"Cached response for query: {query[:50]}...")
        return cache_key
    
    def get_cached_response(self, query: str) -> Optional[Any]:
        """Get cached response for a query."""
        # Try exact match first
        cache_key = hashlib.sha256(f"{self.agent_id}:{query}".encode()).hexdigest()[:16]
        cached = self.response_cache.get(cache_key)
        
        if cached:
            logger.debug(f"Exact cache hit for query: {query[:50]}...")
            return cached
        
        # Try semantic match
        cached = self.semantic_cache.get_similar(query)
        if cached:
            logger.debug(f"Semantic cache hit for query: {query[:50]}...")
            return cached
        
        return None
    
    def add_memory(self, content: Any, memory_type: MemoryType,
                   metadata: Optional[Dict] = None,
                   tags: Optional[List[str]] = None,
                   importance: float = 0.5,
                   ttl_hours: Optional[int] = None) -> str:
        """Add a new memory."""
        import uuid
        
        # Ensure memory_type is a MemoryType enum
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)
        
        memory_id = f"mem-{uuid.uuid4().hex[:12]}"
        
        expiration = None
        if ttl_hours:
            expiration = datetime.now() + timedelta(hours=ttl_hours)
        
        entry = MemoryEntry(
            memory_id=memory_id,
            agent_id=self.agent_id,
            memory_type=memory_type,
            content=content,
            metadata=metadata or {},
            importance_score=importance,
            expiration=expiration,
            tags=tags or [],
        )
        
        # Store persistently
        self.memory_store.store(entry)
        
        # Add to short-term memory if appropriate
        if memory_type == MemoryType.SHORT_TERM:
            with self._lock:
                self.short_term_memory.append(entry)
                # Trim if too long
                if len(self.short_term_memory) > self.max_short_term_length:
                    self.short_term_memory = self.short_term_memory[-self.max_short_term_length:]
        
        logger.debug(f"Added {memory_type.value} memory: {memory_id}")
        return memory_id
    
    def get_memories(self, memory_type: Optional[MemoryType] = None,
                     tags: Optional[List[str]] = None,
                     limit: int = 50) -> List[MemoryEntry]:
        """Retrieve memories with optional filters."""
        return self.memory_store.search(
            agent_id=self.agent_id,
            memory_type=memory_type,
            tags=tags,
            limit=limit,
        )
    
    def get_context_for_prompt(self, max_tokens: int = 4000) -> str:
        """Build optimized context string for prompts using cached memories."""
        # Get relevant memories sorted by importance and recency
        memories = self.get_memories(limit=100)
        
        # Sort by importance and recency
        memories.sort(
            key=lambda m: (m.importance_score, m.accessed_at),
            reverse=True
        )
        
        # Build context string
        context_parts = []
        current_tokens = 0
        
        for memory in memories:
            # Simple token estimation (4 chars ≈ 1 token)
            content_str = str(memory.content)
            estimated_tokens = len(content_str) // 4
            
            if current_tokens + estimated_tokens > max_tokens:
                break
            
            context_parts.append(f"[{memory.memory_type.value}]: {content_str}")
            current_tokens += estimated_tokens
            
            # Update access time
            self.memory_store.update_access(memory.memory_id)
        
        return "\n".join(context_parts)
    
    def consolidate_memories(self):
        """Consolidate and compress memories to save space."""
        # Get old, low-importance memories
        old_memories = self.get_memories(limit=500)
        
        # Group by type and find consolidation opportunities
        consolidated = {}
        for memory in old_memories:
            if memory.importance_score < 0.3:
                mem_type = memory.memory_type
                if mem_type not in consolidated:
                    consolidated[mem_type] = []
                consolidated[mem_type].append(memory)
        
        # Create consolidated memories
        for mem_type, memories in consolidated.items():
            if len(memories) > 10:
                # Create summary memory
                summary_content = f"Summary of {len(memories)} {mem_type.value} memories"
                self.add_memory(
                    content=summary_content,
                    memory_type=mem_type,
                    importance=0.5,
                    tags=["consolidated"],
                )
                
                # Delete old low-importance memories
                for memory in memories[:-5]:  # Keep last 5
                    self.memory_store.delete(memory.memory_id)
        
        logger.info(f"Consolidated memories for agent {self.agent_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory manager statistics."""
        return {
            "agent_id": self.agent_id,
            "short_term_count": len(self.short_term_memory),
            "response_cache_stats": self.response_cache.get_stats(),
            "memory_store_stats": self.memory_store.get_stats(),
        }
    
    def clear_cache(self):
        """Clear all caches."""
        self.response_cache.clear()
        self.semantic_cache.clear()
        logger.info(f"Cleared caches for agent {self.agent_id}")


# Global memory managers registry
_memory_managers: Dict[str, AgentMemoryManager] = {}
_memory_lock = threading.Lock()


def get_memory_manager(agent_id: str, **kwargs) -> AgentMemoryManager:
    """Get or create a memory manager for an agent."""
    global _memory_managers
    
    with _memory_lock:
        if agent_id not in _memory_managers:
            _memory_managers[agent_id] = AgentMemoryManager(agent_id, **kwargs)
        return _memory_managers[agent_id]


def cleanup_old_memories(days_old: int = 30):
    """Cleanup memories older than specified days."""
    cutoff = datetime.now() - timedelta(days=days_old)
    
    # This would be implemented in MemoryStore
    logger.info(f"Cleaning up memories older than {days_old} days")
