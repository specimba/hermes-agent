#!/usr/bin/env python3
"""
Performance Analyzer for Agent Feedback

Analyzes agent performance based on feedback and metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class PerformanceRecord:
    """Represents a performance record."""
    record_id: str
    agent_id: str
    timestamp: datetime
    score: float
    metrics: Dict[str, Any] = field(default_factory=dict)


class PerformanceAnalyzer:
    """Analyzes agent performance."""
    
    def __init__(self):
        self._records: List[PerformanceRecord] = []
    
    def add_record(self, record: PerformanceRecord):
        """Add a performance record."""
        self._records.append(record)
    
    def get_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """Get performance analysis for an agent."""
        records = [r for r in self._records if r.agent_id == agent_id]
        
        if not records:
            return {"agent_id": agent_id, "average_score": 0.0, "trend": "stable"}
        
        scores = [r.score for r in records]
        avg_score = sum(scores) / len(scores)
        
        # Calculate trend
        if len(records) >= 2:
            mid = len(records) // 2
            first_half_avg = sum(r.score for r in records[:mid]) / mid
            second_half_avg = sum(r.score for r in records[mid:]) / (len(records) - mid)
            
            if second_half_avg > first_half_avg + 0.1:
                trend = "improving"
            elif second_half_avg < first_half_avg - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "agent_id": agent_id,
            "average_score": round(avg_score, 2),
            "total_records": len(records),
            "trend": trend,
        }
