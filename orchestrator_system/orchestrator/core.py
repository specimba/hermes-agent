#!/usr/bin/env python3
"""
Agent Orchestrator Core

The central coordinator for the multi-agent system. Manages agent lifecycle,
task delegation, resource allocation, and overall system coordination.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, Future

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent lifecycle states."""
    IDLE = "idle"
    BUSY = "busy"
    CREATING = "creating"
    STOPPING = "stopping"
    ERROR = "error"
    OFFLINE = "offline"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentGroup:
    """Represents a group of agents organized by criteria."""
    group_id: str
    name: str
    description: str = ""
    criteria: Dict[str, Any] = field(default_factory=dict)  # task_type, strictness, deployment_date, etc.
    agent_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "name": self.name,
            "description": self.description,
            "criteria": self.criteria,
            "agent_ids": self.agent_ids,
            "agent_count": len(self.agent_ids),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AgentConfig:
    """Configuration for an AI agent."""
    agent_id: str
    model: str = "anthropic/claude-opus-4.6"
    toolsets: List[str] = field(default_factory=lambda: ["terminal", "file", "web"])
    max_iterations: int = 50
    max_tokens: Optional[int] = None
    quiet_mode: bool = True
    enabled: bool = True
    strictness_level: str = "medium"  # low, medium, high, maximum
    task_type: str = "general"  # general, coding, analysis, creative, automation
    deployment_date: Optional[datetime] = None
    groups: List[str] = field(default_factory=list)  # Group IDs this agent belongs to
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Represents a task to be executed by an agent."""
    task_id: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    assigned_agent_id: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_task_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)


@dataclass
class AgentMetrics:
    """Performance metrics for an agent."""
    agent_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    success_rate: float = 0.0
    tokens_used: int = 0
    api_calls: int = 0
    last_active: Optional[datetime] = None


class AgentInstance:
    """Represents a running agent instance."""
    
    def __init__(self, config: AgentConfig, orchestrator: "AgentOrchestrator"):
        self.config = config
        self.orchestrator = orchestrator
        self.status = AgentStatus.CREATING
        self.current_task: Optional[Task] = None
        self.metrics = AgentMetrics(agent_id=config.agent_id)
        self.created_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self._agent_object = None
        self._lock = threading.Lock()
        
    def initialize(self) -> bool:
        """Initialize the agent instance."""
        try:
            from run_agent import AIAgent
            
            self._agent_object = AIAgent(
                model=self.config.model,
                max_iterations=self.config.max_iterations,
                enabled_toolsets=self.config.toolsets,
                max_tokens=self.config.max_tokens,
                quiet_mode=self.config.quiet_mode,
                session_id=f"agent-{self.config.agent_id}",
            )
            self.status = AgentStatus.IDLE
            logger.info(f"Agent {self.config.agent_id} initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize agent {self.config.agent_id}: {e}")
            self.status = AgentStatus.ERROR
            return False
    
    def execute_task(self, task: Task) -> Future:
        """Execute a task asynchronously."""
        if self.status != AgentStatus.IDLE:
            raise RuntimeError(f"Agent {self.config.agent_id} is not idle (status: {self.status})")
        
        with self._lock:
            self.status = AgentStatus.BUSY
            self.current_task = task
            task.status = "running"
            task.started_at = datetime.now()
            task.assigned_agent_id = self.config.agent_id
        
        def _run_task():
            start_time = time.monotonic()
            try:
                if self._agent_object is None:
                    raise RuntimeError("Agent not initialized")
                
                result = self._agent_object.run_conversation(task.description)
                
                execution_time = time.monotonic() - start_time
                
                with self._lock:
                    task.status = "completed"
                    task.completed_at = datetime.now()
                    task.result = result
                    self.status = AgentStatus.IDLE
                    self.current_task = None
                    
                    # Update metrics
                    self.metrics.tasks_completed += 1
                    self.metrics.total_execution_time += execution_time
                    self.metrics.average_execution_time = (
                        self.metrics.total_execution_time / self.metrics.tasks_completed
                    )
                    self.metrics.last_active = datetime.now()
                    
                    if hasattr(self._agent_object, 'session_prompt_tokens'):
                        self.metrics.tokens_used += getattr(self._agent_object, 'session_prompt_tokens', 0)
                    if hasattr(self._agent_object, 'session_completion_tokens'):
                        self.metrics.tokens_used += getattr(self._agent_object, 'session_completion_tokens', 0)
                    if hasattr(self._agent_object, 'api_calls'):
                        self.metrics.api_calls += getattr(self._agent_object, 'api_calls', 0)
                
                logger.info(f"Task {task.task_id} completed by agent {self.config.agent_id}")
                return result
                
            except Exception as e:
                execution_time = time.monotonic() - start_time
                
                with self._lock:
                    task.status = "failed"
                    task.completed_at = datetime.now()
                    task.error = str(e)
                    self.status = AgentStatus.IDLE
                    self.current_task = None
                    
                    self.metrics.tasks_failed += 1
                    self.metrics.total_execution_time += execution_time
                    self.metrics.last_active = datetime.now()
                
                logger.error(f"Task {task.task_id} failed on agent {self.config.agent_id}: {e}")
                raise
        
        executor = ThreadPoolExecutor(max_workers=1)
        return executor.submit(_run_task)
    
    def stop(self) -> bool:
        """Stop the agent instance."""
        try:
            self.status = AgentStatus.STOPPING
            # Cleanup resources if needed
            self.status = AgentStatus.OFFLINE
            logger.info(f"Agent {self.config.agent_id} stopped")
            return True
        except Exception as e:
            logger.error(f"Error stopping agent {self.config.agent_id}: {e}")
            self.status = AgentStatus.ERROR
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "agent_id": self.config.agent_id,
            "model": self.config.model,
            "status": self.status.value,
            "current_task": self.current_task.task_id if self.current_task else None,
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "success_rate": self.metrics.success_rate,
                "average_execution_time": self.metrics.average_execution_time,
                "tokens_used": self.metrics.tokens_used,
                "last_active": self.metrics.last_active.isoformat() if self.metrics.last_active else None,
            },
            "created_at": self.created_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }


class AgentRegistry:
    """Registry for managing agent instances with grouping support."""
    
    def __init__(self):
        self._agents: Dict[str, AgentInstance] = {}
        self._groups: Dict[str, AgentGroup] = {}
        self._lock = threading.RLock()
    
    def register(self, agent: AgentInstance) -> bool:
        """Register an agent instance."""
        with self._lock:
            if agent.config.agent_id in self._agents:
                logger.warning(f"Agent {agent.config.agent_id} already registered")
                return False
            self._agents[agent.config.agent_id] = agent
            logger.info(f"Agent {agent.config.agent_id} registered")
            
            # Auto-assign to groups based on criteria
            self._auto_assign_to_groups(agent)
            
            return True
    
    def _auto_assign_to_groups(self, agent: AgentInstance):
        """Auto-assign agent to groups based on criteria."""
        for group_id, group in self._groups.items():
            if self._matches_group_criteria(agent, group.criteria):
                if agent.config.agent_id not in group.agent_ids:
                    group.agent_ids.append(agent.config.agent_id)
                    if agent.config.agent_id not in agent.config.groups:
                        agent.config.groups.append(group_id)
                    group.updated_at = datetime.now()
                    logger.debug(f"Agent {agent.config.agent_id} auto-assigned to group {group_id}")
    
    def _matches_group_criteria(self, agent: AgentInstance, criteria: Dict[str, Any]) -> bool:
        """Check if agent matches group criteria."""
        if not criteria:
            return True
        
        for key, value in criteria.items():
            if key == "task_type":
                if agent.config.task_type != value:
                    return False
            elif key == "strictness_level":
                if agent.config.strictness_level != value:
                    return False
            elif key == "min_strictness":
                strictness_order = {"low": 1, "medium": 2, "high": 3, "maximum": 4}
                agent_level = strictness_order.get(agent.config.strictness_level, 2)
                min_level = strictness_order.get(value, 1)
                if agent_level < min_level:
                    return False
            elif key == "deployment_after":
                if not agent.config.deployment_date or agent.config.deployment_date < value:
                    return False
            elif key == "deployment_before":
                if not agent.config.deployment_date or agent.config.deployment_date > value:
                    return False
        
        return True
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent instance."""
        with self._lock:
            if agent_id not in self._agents:
                return False
            agent = self._agents.pop(agent_id)
            
            # Remove from groups
            for group in self._groups.values():
                if agent_id in group.agent_ids:
                    group.agent_ids.remove(agent_id)
                    group.updated_at = datetime.now()
            
            agent.stop()
            logger.info(f"Agent {agent_id} unregistered")
            return True
    
    def get(self, agent_id: str) -> Optional[AgentInstance]:
        """Get an agent instance by ID."""
        with self._lock:
            return self._agents.get(agent_id)
    
    def get_all(self) -> List[AgentInstance]:
        """Get all registered agents."""
        with self._lock:
            return list(self._agents.values())
    
    def get_idle_agents(self) -> List[AgentInstance]:
        """Get all idle agents."""
        with self._lock:
            return [a for a in self._agents.values() if a.status == AgentStatus.IDLE]
    
    def get_available_agents(self, required_toolsets: Optional[List[str]] = None) -> List[AgentInstance]:
        """Get available agents, optionally filtered by required toolsets."""
        with self._lock:
            available = [a for a in self._agents.values() 
                        if a.status == AgentStatus.IDLE and a.config.enabled]
            
            if required_toolsets:
                available = [a for a in available 
                            if all(ts in a.config.toolsets for ts in required_toolsets)]
            
            return available
    
    def get_agents_by_group(self, group_id: str) -> List[AgentInstance]:
        """Get all agents in a specific group."""
        with self._lock:
            if group_id not in self._groups:
                return []
            group = self._groups[group_id]
            return [self._agents[aid] for aid in group.agent_ids if aid in self._agents]
    
    def get_agents_by_criteria(self, **criteria) -> List[AgentInstance]:
        """Get agents matching specified criteria."""
        with self._lock:
            results = []
            for agent in self._agents.values():
                if self._matches_group_criteria(agent, criteria):
                    results.append(agent)
            return results
    
    # Group management methods
    def create_group(self, name: str, description: str = "", 
                    criteria: Optional[Dict[str, Any]] = None,
                    group_id: Optional[str] = None) -> AgentGroup:
        """Create a new agent group."""
        import uuid
        with self._lock:
            if group_id is None:
                group_id = f"group-{uuid.uuid4().hex[:8]}"
            
            group = AgentGroup(
                group_id=group_id,
                name=name,
                description=description,
                criteria=criteria or {},
            )
            
            self._groups[group_id] = group
            
            # Auto-populate with existing matching agents
            for agent in self._agents.values():
                if self._matches_group_criteria(agent, group.criteria):
                    group.agent_ids.append(agent.config.agent_id)
                    if group_id not in agent.config.groups:
                        agent.config.groups.append(group_id)
            
            logger.info(f"Group {group_id} created with {len(group.agent_ids)} agents")
            return group
    
    def get_group(self, group_id: str) -> Optional[AgentGroup]:
        """Get a group by ID."""
        with self._lock:
            return self._groups.get(group_id)
    
    def get_all_groups(self) -> List[AgentGroup]:
        """Get all groups."""
        with self._lock:
            return list(self._groups.values())
    
    def update_group(self, group_id: str, **updates) -> bool:
        """Update a group's properties."""
        with self._lock:
            if group_id not in self._groups:
                return False
            
            group = self._groups[group_id]
            
            if "name" in updates:
                group.name = updates["name"]
            if "description" in updates:
                group.description = updates["description"]
            if "criteria" in updates:
                group.criteria = updates["criteria"]
                # Re-evaluate agent membership
                old_agent_ids = set(group.agent_ids)
                group.agent_ids = []
                for agent in self._agents.values():
                    if self._matches_group_criteria(agent, group.criteria):
                        group.agent_ids.append(agent.config.agent_id)
                
                # Update agent group memberships
                new_agent_ids = set(group.agent_ids)
                for aid in old_agent_ids - new_agent_ids:
                    if aid in self._agents and group_id in self._agents[aid].config.groups:
                        self._agents[aid].config.groups.remove(group_id)
                for aid in new_agent_ids - old_agent_ids:
                    if aid in self._agents and group_id not in self._agents[aid].config.groups:
                        self._agents[aid].config.groups.append(group_id)
            
            group.updated_at = datetime.now()
            return True
    
    def delete_group(self, group_id: str) -> bool:
        """Delete a group."""
        with self._lock:
            if group_id not in self._groups:
                return False
            
            # Remove group reference from agents
            for agent in self._agents.values():
                if group_id in agent.config.groups:
                    agent.config.groups.remove(group_id)
            
            del self._groups[group_id]
            logger.info(f"Group {group_id} deleted")
            return True
    
    def add_agent_to_group(self, agent_id: str, group_id: str) -> bool:
        """Manually add an agent to a group."""
        with self._lock:
            if group_id not in self._groups or agent_id not in self._agents:
                return False
            
            group = self._groups[group_id]
            agent = self._agents[agent_id]
            
            if agent_id not in group.agent_ids:
                group.agent_ids.append(agent_id)
            if group_id not in agent.config.groups:
                agent.config.groups.append(group_id)
            
            group.updated_at = datetime.now()
            return True
    
    def remove_agent_from_group(self, agent_id: str, group_id: str) -> bool:
        """Remove an agent from a group."""
        with self._lock:
            if group_id not in self._groups:
                return False
            
            group = self._groups[group_id]
            
            if agent_id in group.agent_ids:
                group.agent_ids.remove(agent_id)
            if agent_id in self._agents and group_id in self._agents[agent_id].config.groups:
                self._agents[agent_id].config.groups.remove(group_id)
            
            group.updated_at = datetime.now()
            return True
    
    def count(self) -> int:
        """Get total number of registered agents."""
        with self._lock:
            return len(self._agents)


class TaskManager:
    """Manages task queue and execution."""
    
    def __init__(self, orchestrator: "AgentOrchestrator"):
        self.orchestrator = orchestrator
        self._tasks: Dict[str, Task] = {}
        self._pending_queue: List[Task] = []
        self._lock = threading.RLock()
        self._task_futures: Dict[str, Future] = {}
        
    def create_task(self, description: str, priority: TaskPriority = TaskPriority.NORMAL,
                   metadata: Optional[Dict] = None, parent_task_id: Optional[str] = None) -> Task:
        """Create a new task."""
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        task = Task(
            task_id=task_id,
            description=description,
            priority=priority,
            metadata=metadata or {},
            parent_task_id=parent_task_id,
        )
        
        with self._lock:
            self._tasks[task_id] = task
            self._pending_queue.append(task)
            self._pending_queue.sort(key=lambda t: (-t.priority.value, t.created_at))
            
            # Update parent task if exists
            if parent_task_id and parent_task_id in self._tasks:
                self._tasks[parent_task_id].subtasks.append(task_id)
        
        logger.info(f"Task {task_id} created with priority {priority.name}")
        return task
    
    def get_next_task(self) -> Optional[Task]:
        """Get the next task to execute."""
        with self._lock:
            if not self._pending_queue:
                return None
            return self._pending_queue.pop(0)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks."""
        with self._lock:
            return list(self._tasks.values())
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.status in ["completed", "failed", "cancelled"]:
                return False
            
            task.status = "cancelled"
            task.completed_at = datetime.now()
            
            # Remove from pending queue
            self._pending_queue = [t for t in self._pending_queue if t.task_id != task_id]
            
            logger.info(f"Task {task_id} cancelled")
            return True
    
    def get_pending_count(self) -> int:
        """Get number of pending tasks."""
        with self._lock:
            return len(self._pending_queue)


class ResourceAllocator:
    """Allocates resources to agents and tasks."""
    
    def __init__(self):
        self._allocations: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
    def allocate(self, agent_id: str, task_id: str, resources: Dict[str, Any]) -> bool:
        """Allocate resources to an agent-task pair."""
        with self._lock:
            key = f"{agent_id}:{task_id}"
            if key in self._allocations:
                return False
            
            self._allocations[key] = {
                "agent_id": agent_id,
                "task_id": task_id,
                "resources": resources,
                "allocated_at": datetime.now(),
            }
            return True
    
    def release(self, agent_id: str, task_id: str) -> bool:
        """Release allocated resources."""
        with self._lock:
            key = f"{agent_id}:{task_id}"
            if key not in self._allocations:
                return False
            
            del self._allocations[key]
            return True
    
    def get_allocation(self, agent_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Get resource allocation for an agent-task pair."""
        with self._lock:
            key = f"{agent_id}:{task_id}"
            return self._allocations.get(key)


class AgentOrchestrator:
    """
    Central orchestrator for multi-agent system.
    
    Responsibilities:
    - Agent lifecycle management (create, start, stop, monitor)
    - Task distribution and load balancing
    - Resource allocation
    - Performance monitoring
    - Integration with governance and coordination systems
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = self._load_config()
        
        self.registry = AgentRegistry()
        self.task_manager = TaskManager(self)
        self.resource_allocator = ResourceAllocator()
        
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._governance_engine = None
        self._workflow_coordinator = None
        self._feedback_engine = None
        
        # Callbacks
        self._on_task_complete_callbacks: List[Callable] = []
        self._on_agent_error_callbacks: List[Callable] = []
        
        logger.info("AgentOrchestrator initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        default_config = {
            "max_agents": 10,
            "default_model": "anthropic/claude-opus-4.6",
            "default_toolsets": ["terminal", "file", "web"],
            "default_max_iterations": 50,
            "task_poll_interval": 1.0,
            "heartbeat_interval": 30.0,
            "enable_auto_scaling": True,
            "min_idle_agents": 2,
            "max_idle_agents": 5,
        }
        
        if self.config_path and Path(self.config_path).exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    default_config.update(file_config)
                    logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {self.config_path}: {e}")
        
        return default_config
    
    def set_governance_engine(self, engine):
        """Set the governance engine for policy enforcement."""
        self._governance_engine = engine
    
    def set_workflow_coordinator(self, coordinator):
        """Set the workflow coordinator."""
        self._workflow_coordinator = coordinator
    
    def set_feedback_engine(self, engine):
        """Set the feedback engine for continuous improvement."""
        self._feedback_engine = engine
    
    def create_agent(self, config: Optional[AgentConfig] = None) -> Optional[AgentInstance]:
        """Create a new agent instance."""
        if config is None:
            agent_id = f"agent-{uuid.uuid4().hex[:8]}"
            config = AgentConfig(
                agent_id=agent_id,
                model=self.config["default_model"],
                toolsets=self.config["default_toolsets"],
                max_iterations=self.config["default_max_iterations"],
            )
        
        # Check with governance if agent creation is allowed
        if self._governance_engine:
            if not self._governance_engine.validate_agent_creation(config):
                logger.warning(f"Governance rejected agent creation for {config.agent_id}")
                return None
        
        # Check max agents limit
        if self.registry.count() >= self.config["max_agents"]:
            logger.warning(f"Maximum agent limit ({self.config['max_agents']}) reached")
            return None
        
        agent = AgentInstance(config, self)
        if not agent.initialize():
            return None
        
        if not self.registry.register(agent):
            return None
        
        logger.info(f"Agent {config.agent_id} created successfully")
        return agent
    
    def destroy_agent(self, agent_id: str) -> bool:
        """Destroy an agent instance."""
        agent = self.registry.get(agent_id)
        if not agent:
            return False
        
        # Cancel current task if any
        if agent.current_task:
            self.task_manager.cancel_task(agent.current_task.task_id)
        
        success = self.registry.unregister(agent_id)
        
        if self._feedback_engine and agent.metrics.tasks_completed > 0:
            self._feedback_engine.record_agent_lifecycle(agent)
        
        return success
    
    def delegate_task(self, description: str, priority: TaskPriority = TaskPriority.NORMAL,
                     required_toolsets: Optional[List[str]] = None,
                     preferred_agent_id: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> Optional[Task]:
        """Delegate a task to an appropriate agent."""
        
        # Create the task
        task = self.task_manager.create_task(
            description=description,
            priority=priority,
            metadata=metadata,
        )
        
        # Governance check
        if self._governance_engine:
            if not self._governance_engine.validate_task_delegation(task):
                logger.warning(f"Governance rejected task delegation: {task.task_id}")
                task.status = "cancelled"
                return task
        
        # Find an appropriate agent
        if preferred_agent_id:
            agent = self.registry.get(preferred_agent_id)
            if agent and agent.status == AgentStatus.IDLE:
                selected_agent = agent
            else:
                selected_agent = None
        else:
            available_agents = self.registry.get_available_agents(required_toolsets)
            if not available_agents:
                logger.warning("No available agents to handle task")
                # Auto-scale if enabled
                if self.config["enable_auto_scaling"]:
                    self._auto_scale_agents()
                    available_agents = self.registry.get_available_agents(required_toolsets)
            
            if available_agents:
                # Load balancing: select agent with lowest current load
                selected_agent = min(available_agents, 
                                   key=lambda a: (a.metrics.tasks_completed, -a.metrics.success_rate))
            else:
                selected_agent = None
        
        if selected_agent:
            # Allocate resources
            self.resource_allocator.allocate(
                selected_agent.config.agent_id,
                task.task_id,
                {"priority": priority.value}
            )
            
            # Execute task
            future = selected_agent.execute_task(task)
            self.task_manager._task_futures[task.task_id] = future
            
            # Add callback for completion
            def _on_complete(f):
                self._on_task_completed(task, f, selected_agent)
            future.add_done_callback(_on_complete)
            
            logger.info(f"Task {task.task_id} delegated to agent {selected_agent.config.agent_id}")
        else:
            logger.warning(f"Task {task.task_id} queued - no available agents")
        
        return task
    
    def _on_task_completed(self, task: Task, future: Future, agent: AgentInstance):
        """Handle task completion."""
        try:
            result = future.result()
            
            # Notify callbacks
            for callback in self._on_task_complete_callbacks:
                try:
                    callback(task, result, agent)
                except Exception as e:
                    logger.error(f"Error in task complete callback: {e}")
            
            # Feedback recording
            if self._feedback_engine:
                self._feedback_engine.record_task_execution(task, agent)
            
            # Release resources
            self.resource_allocator.release(agent.config.agent_id, task.task_id)
            
            # Update workflow if coordinator exists
            if self._workflow_coordinator:
                self._workflow_coordinator.on_task_completed(task, agent)
            
        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            
            for callback in self._on_agent_error_callbacks:
                try:
                    callback(task, e, agent)
                except Exception as ce:
                    logger.error(f"Error in error callback: {ce}")
            
            if self._feedback_engine:
                self._feedback_engine.record_task_failure(task, agent, str(e))
            
            self.resource_allocator.release(agent.config.agent_id, task.task_id)
    
    def _auto_scale_agents(self):
        """Automatically scale agent count based on demand."""
        if not self.config["enable_auto_scaling"]:
            return
        
        current_count = self.registry.count()
        idle_count = len(self.registry.get_idle_agents())
        pending_count = self.task_manager.get_pending_count()
        
        # Scale up if many pending tasks and few idle agents
        if pending_count > idle_count and current_count < self.config["max_agents"]:
            agents_to_create = min(
                self.config["max_agents"] - current_count,
                max(1, pending_count - idle_count)
            )
            for _ in range(agents_to_create):
                self.create_agent()
                logger.info(f"Auto-scaled: created new agent")
        
        # Scale down if too many idle agents
        elif idle_count > self.config["max_idle_agents"]:
            agents_to_remove = idle_count - self.config["max_idle_agents"]
            idle_agents = self.registry.get_idle_agents()
            for i in range(min(agents_to_remove, len(idle_agents))):
                # Remove oldest idle agent
                agent = min(idle_agents, key=lambda a: a.last_heartbeat)
                self.destroy_agent(agent.config.agent_id)
                logger.info(f"Auto-scaled: removed idle agent {agent.config.agent_id}")
    
    def on_task_complete(self, callback: Callable):
        """Register a callback for task completion."""
        self._on_task_complete_callbacks.append(callback)
    
    def on_agent_error(self, callback: Callable):
        """Register a callback for agent errors."""
        self._on_agent_error_callbacks.append(callback)
    
    def start(self):
        """Start the orchestrator."""
        if self._running:
            return
        
        self._running = True
        
        # Start scheduler thread
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        # Start monitor thread
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info("AgentOrchestrator started")
    
    def stop(self):
        """Stop the orchestrator."""
        self._running = False
        
        # Stop all agents
        for agent in self.registry.get_all():
            agent.stop()
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5.0)
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        
        logger.info("AgentOrchestrator stopped")
    
    def _scheduler_loop(self):
        """Background loop for task scheduling."""
        while self._running:
            try:
                # Process pending tasks
                while True:
                    task = self.task_manager.get_next_task()
                    if not task:
                        break
                    
                    # Re-queue if no agent available
                    available = self.registry.get_available_agents()
                    if not available:
                        self.task_manager._pending_queue.insert(0, task)
                        break
                    
                    # Select best agent
                    agent = min(available, key=lambda a: a.metrics.tasks_completed)
                    future = agent.execute_task(task)
                    self.task_manager._task_futures[task.task_id] = future
                    
                    def _on_complete(f, t=task, a=agent):
                        self._on_task_completed(t, f, a)
                    future.add_done_callback(_on_complete)
                
                time.sleep(self.config["task_poll_interval"])
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(1.0)
    
    def _monitor_loop(self):
        """Background loop for monitoring agents."""
        while self._running:
            try:
                # Update heartbeats
                for agent in self.registry.get_all():
                    agent.last_heartbeat = datetime.now()
                
                # Auto-scale check
                if self.config["enable_auto_scaling"]:
                    self._auto_scale_agents()
                
                time.sleep(self.config["heartbeat_interval"])
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(5.0)
    
    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        agents = self.registry.get_all()
        tasks = self.task_manager.get_all_tasks()
        
        return {
            "running": self._running,
            "total_agents": len(agents),
            "idle_agents": len([a for a in agents if a.status == AgentStatus.IDLE]),
            "busy_agents": len([a for a in agents if a.status == AgentStatus.BUSY]),
            "total_tasks": len(tasks),
            "pending_tasks": self.task_manager.get_pending_count(),
            "completed_tasks": len([t for t in tasks if t.status == "completed"]),
            "failed_tasks": len([t for t in tasks if t.status == "failed"]),
            "config": self.config,
            "agents": [a.get_info() for a in agents],
        }
    
    def export_metrics(self) -> Dict[str, Any]:
        """Export system metrics."""
        agents = self.registry.get_all()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_agents": len(agents),
            "agent_metrics": [
                {
                    "agent_id": a.config.agent_id,
                    "tasks_completed": a.metrics.tasks_completed,
                    "tasks_failed": a.metrics.tasks_failed,
                    "success_rate": a.metrics.tasks_completed / max(1, a.metrics.tasks_completed + a.metrics.tasks_failed),
                    "avg_execution_time": a.metrics.average_execution_time,
                    "tokens_used": a.metrics.tokens_used,
                }
                for a in agents
            ],
            "system_health": "healthy" if self._running else "stopped",
        }
