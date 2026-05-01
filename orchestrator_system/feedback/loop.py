#!/usr/bin/env python3
"""
Agent Feedback Loop

Provides mechanism for collecting and processing user feedback on agent performance.
Feedback is used to adjust agent scores and alignment parameters.
"""

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    """Represents a single feedback entry."""
    feedback_id: str = field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:12]}")
    agent_id: str = ""
    task_id: str = ""
    rating: int = 0  # 1-5 scale
    comment: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    processed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
            "processed": self.processed,
            "metadata": self.metadata,
        }


class FeedbackEngine:
    """Manages feedback collection and processing."""
    
    def __init__(self, db_path: str = "feedback.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._pending_feedback: List[FeedbackEntry] = []
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        # Handle in-memory databases specially
        if self.db_path == ':memory:':
            conn = sqlite3.connect(':memory:', check_same_thread=False)
        else:
            conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP,
                processed INTEGER DEFAULT 0,
                metadata TEXT
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agent_id ON feedback(agent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_id ON feedback(task_id)')
        
        conn.commit()
        conn.close()
    
    def submit_feedback(self, entry: FeedbackEntry) -> bool:
        """Submit a new feedback entry."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO feedback 
                (feedback_id, agent_id, task_id, rating, comment, created_at, processed, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.feedback_id,
                entry.agent_id,
                entry.task_id,
                entry.rating,
                entry.comment,
                entry.created_at.isoformat(),
                1 if entry.processed else 0,
                json.dumps(entry.metadata),
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Feedback submitted: {entry.feedback_id} for agent {entry.agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            return False
    
    def get_feedback_for_agent(self, agent_id: str, limit: int = 100) -> List[FeedbackEntry]:
        """Get all feedback for a specific agent."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM feedback WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?',
                (agent_id, limit)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                entry = FeedbackEntry(
                    feedback_id=row[0],
                    agent_id=row[1],
                    task_id=row[2],
                    rating=row[3],
                    comment=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                    processed=bool(row[6]),
                    metadata=json.loads(row[7]) if row[7] else {},
                )
                results.append(entry)
            
            return results
        except Exception as e:
            logger.error(f"Failed to get feedback: {e}")
            return []
    
    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get feedback statistics for an agent."""
        feedback = self.get_feedback_for_agent(agent_id, limit=1000)
        
        if not feedback:
            return {
                "agent_id": agent_id,
                "total_feedback": 0,
                "average_rating": 0.0,
                "rating_distribution": {},
            }
        
        ratings = [f.rating for f in feedback]
        avg_rating = sum(ratings) / len(ratings)
        
        distribution = {}
        for r in range(1, 6):
            distribution[str(r)] = sum(1 for rating in ratings if rating == r)
        
        return {
            "agent_id": agent_id,
            "total_feedback": len(feedback),
            "average_rating": round(avg_rating, 2),
            "rating_distribution": distribution,
            "recent_trend": self._calculate_trend(feedback[:20]),
        }
    
    def _calculate_trend(self, recent_feedback: List[FeedbackEntry]) -> str:
        """Calculate rating trend from recent feedback."""
        if len(recent_feedback) < 2:
            return "stable"
        
        first_half = recent_feedback[len(recent_feedback)//2:]
        second_half = recent_feedback[:len(recent_feedback)//2]
        
        avg_first = sum(f.rating for f in first_half) / len(first_half)
        avg_second = sum(f.rating for f in second_half) / len(second_half)
        
        diff = avg_first - avg_second
        if diff > 0.5:
            return "improving"
        elif diff < -0.5:
            return "declining"
        return "stable"
    
    def get_alignment_adjustments(self, agent_id: str) -> Dict[str, Any]:
        """Get recommended alignment parameter adjustments based on feedback."""
        stats = self.get_agent_stats(agent_id)
        
        adjustments = {
            "agent_id": agent_id,
            "current_average": stats["average_rating"],
            "recommendations": [],
        }
        
        if stats["average_rating"] < 2.5:
            adjustments["recommendations"].append({
                "parameter": "strictness_level",
                "action": "increase",
                "reason": "Low ratings suggest agent may need stricter constraints",
            })
        elif stats["average_rating"] > 4.5:
            adjustments["recommendations"].append({
                "parameter": "autonomy_level",
                "action": "increase",
                "reason": "High ratings suggest agent can handle more autonomy",
            })
        
        # Check for specific patterns
        feedback = self.get_feedback_for_agent(agent_id, limit=100)
        low_ratings = [f for f in feedback if f.rating <= 2]
        
        if len(low_ratings) > 10:
            # Analyze common issues
            adjustments["recommendations"].append({
                "parameter": "review_required",
                "action": "enable",
                "reason": f"{len(low_ratings)} low ratings detected, manual review recommended",
            })
        
        return adjustments
    
    def process_pending_feedback(self) -> int:
        """Process pending feedback entries."""
        with self._lock:
            processed = 0
            for entry in self._pending_feedback:
                # Process feedback (update agent metrics, etc.)
                entry.processed = True
                self.submit_feedback(entry)
                processed += 1
            
            self._pending_feedback.clear()
            return processed


# Global instance
_engine: Optional[FeedbackEngine] = None


def get_feedback_engine(db_path: str = "feedback.db") -> FeedbackEngine:
    """Get or create the global feedback engine."""
    global _engine
    if _engine is None:
        _engine = FeedbackEngine(db_path=db_path)
    return _engine
