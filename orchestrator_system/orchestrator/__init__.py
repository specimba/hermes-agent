"""
Agent Orchestrator Module

Core orchestration logic for managing multiple AI agents, handling:
- Dynamic agent creation and lifecycle management
- Task delegation and distribution
- Resource allocation and load balancing
- Performance monitoring and metrics collection
"""

from .core import AgentOrchestrator
from .agent_registry import AgentRegistry
from .task_manager import TaskManager
from .resource_allocator import ResourceAllocator

__all__ = [
    "AgentOrchestrator",
    "AgentRegistry",
    "TaskManager",
    "ResourceAllocator",
]
