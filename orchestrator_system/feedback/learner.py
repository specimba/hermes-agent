#!/usr/bin/env python3
"""
Agent Learner - Uses feedback to improve agent behavior over time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AgentInsight:
    """Represents an insight about agent behavior."""
    insight_id: str
    agent_id: str
    description: str
    confidence: float
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ImprovementSuggestion:
    """Suggestion for improving agent performance."""
    suggestion_id: str
    agent_id: str
    category: str
    description: str
    priority: str  # low, medium, high
    expected_impact: float


class AgentLearner:
    """Learns from feedback to improve agent behavior."""
    
    def __init__(self):
        self._insights: List[AgentInsight] = []
        self._suggestions: List[ImprovementSuggestion] = []
    
    def analyze_feedback(self, feedback_data: List[Dict]) -> List[ImprovementSuggestion]:
        """Analyze feedback and generate improvement suggestions."""
        suggestions = []
        
        # Simple analysis - in production would use ML
        if len(feedback_data) > 5:
            avg_rating = sum(f.get('rating', 3) for f in feedback_data) / len(feedback_data)
            
            if avg_rating < 3:
                suggestions.append(ImprovementSuggestion(
                    suggestion_id=f"sugg-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    agent_id=feedback_data[0].get('agent_id', 'unknown'),
                    category='performance',
                    description='Consider reviewing agent configuration and constraints',
                    priority='high',
                    expected_impact=0.3,
                ))
        
        return suggestions
    
    def get_insights_for_agent(self, agent_id: str) -> List[AgentInsight]:
        """Get insights for a specific agent."""
        return [i for i in self._insights if i.agent_id == agent_id]
