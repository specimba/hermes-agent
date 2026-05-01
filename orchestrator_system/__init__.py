#!/usr/bin/env python3
"""
Hermes Multi-Agent Orchestration System

A comprehensive system for managing and orchestrating multiple AI agents,
with robust governance, coordination, and monitoring features.

Architecture:
- Orchestrator: Central coordinator for agent lifecycle and task delegation
- Governance Specialist: Policy enforcement, security, and compliance
- Coordinator: Workflow management and inter-agent communication
- Dashboard: Real-time monitoring and control interface
- Feedback Loop: Continuous improvement through performance analysis
"""

__version__ = "1.0.0"
__author__ = "Hermes AI Team"

from .orchestrator.core import AgentOrchestrator
from .governance.core import GovernanceEngine
from .coordinator.core import WorkflowCoordinator
from .dashboard.server import DashboardServer
from .feedback.loop import FeedbackEngine

__all__ = [
    "AgentOrchestrator",
    "GovernanceEngine", 
    "WorkflowCoordinator",
    "DashboardServer",
    "FeedbackEngine",
]
