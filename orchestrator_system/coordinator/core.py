#!/usr/bin/env python3
"""
Workflow Coordinator Core

Coordinates complex multi-agent workflows, handles task dependencies,
and facilitates inter-agent communication.
"""

import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution states."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskDependencyType(Enum):
    """Types of task dependencies."""
    SEQUENTIAL = "sequential"  # Must complete in order
    PARALLEL = "parallel"      # Can run simultaneously
    CONDITIONAL = "conditional" # Depends on condition being met


@dataclass
class WorkflowTask:
    """A task within a workflow."""
    task_id: str
    name: str
    description: str
    agent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    dependency_type: TaskDependencyType = TaskDependencyType.SEQUENTIAL
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    """Represents a complete workflow."""
    workflow_id: str
    name: str
    description: str
    tasks: Dict[str, WorkflowTask] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_task(self, task: WorkflowTask):
        """Add a task to the workflow."""
        self.tasks[task.task_id] = task
    
    def get_ready_tasks(self) -> List[WorkflowTask]:
        """Get tasks that are ready to execute (dependencies met)."""
        ready = []
        for task in self.tasks.values():
            if task.status != "pending":
                continue
            
            # Check if all dependencies are completed
            deps_met = all(
                self.tasks.get(dep_id) and self.tasks[dep_id].status == "completed"
                for dep_id in task.dependencies
            )
            
            if deps_met:
                ready.append(task)
        
        return ready
    
    def is_complete(self) -> bool:
        """Check if all tasks are complete."""
        return all(
            t.status in ["completed", "failed", "cancelled"]
            for t in self.tasks.values()
        ) if self.tasks else False
    
    def has_failures(self) -> bool:
        """Check if any task has failed."""
        return any(t.status == "failed" for t in self.tasks.values())


class MessageBus:
    """
    Pub/sub message bus for inter-agent communication.
    
    Allows agents to communicate asynchronously through topics.
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_queue: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
    
    def subscribe(self, topic: str, callback: Callable) -> bool:
        """Subscribe to a topic."""
        with self._lock:
            self._subscribers[topic].append(callback)
            logger.info(f"Subscriber added to topic: {topic}")
            return True
    
    def unsubscribe(self, topic: str, callback: Callable) -> bool:
        """Unsubscribe from a topic."""
        with self._lock:
            if callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)
                logger.info(f"Subscriber removed from topic: {topic}")
                return True
            return False
    
    def publish(self, topic: str, message: Any, sender_id: Optional[str] = None) -> bool:
        """Publish a message to a topic."""
        msg = {
            "id": f"msg-{uuid.uuid4().hex[:12]}",
            "topic": topic,
            "sender_id": sender_id,
            "payload": message,
            "timestamp": datetime.now(),
        }
        
        with self._lock:
            self._message_queue.append(msg)
        
        logger.debug(f"Message published to {topic}: {msg['id']}")
        return True
    
    def start(self):
        """Start the message processor."""
        if self._running:
            return
        
        self._running = True
        self._processor_thread = threading.Thread(target=self._process_messages, daemon=True)
        self._processor_thread.start()
        logger.info("MessageBus started")
    
    def stop(self):
        """Stop the message processor."""
        self._running = False
        if self._processor_thread:
            self._processor_thread.join(timeout=5.0)
        logger.info("MessageBus stopped")
    
    def _process_messages(self):
        """Process messages from the queue."""
        while self._running:
            messages_to_process = []
            
            with self._lock:
                if self._message_queue:
                    messages_to_process = self._message_queue[:]
                    self._message_queue.clear()
            
            for msg in messages_to_process:
                topic = msg["topic"]
                subscribers = self._subscribers.get(topic, [])
                
                for callback in subscribers:
                    try:
                        callback(msg)
                    except Exception as e:
                        logger.error(f"Error in message callback for {topic}: {e}")
            
            time.sleep(0.01)  # Small delay to prevent busy waiting
    
    def get_topics(self) -> List[str]:
        """Get all active topics."""
        with self._lock:
            return list(self._subscribers.keys())
    
    def get_subscriber_count(self, topic: str) -> int:
        """Get number of subscribers for a topic."""
        with self._lock:
            return len(self._subscribers.get(topic, []))


class WorkflowEngine:
    """
    Engine for executing and managing workflows.
    
    Handles task scheduling, dependency resolution, and execution tracking.
    """
    
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self._workflows: Dict[str, Workflow] = {}
        self._lock = threading.RLock()
        self._execution_threads: Dict[str, threading.Thread] = {}
    
    def create_workflow(self, name: str, description: str,
                       created_by: Optional[str] = None) -> Workflow:
        """Create a new workflow."""
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            created_by=created_by,
        )
        
        with self._lock:
            self._workflows[workflow_id] = workflow
        
        logger.info(f"Workflow created: {workflow_id} - {name}")
        return workflow
    
    def add_task_to_workflow(self, workflow_id: str, task: WorkflowTask) -> bool:
        """Add a task to an existing workflow."""
        with self._lock:
            if workflow_id not in self._workflows:
                return False
            
            self._workflows[workflow_id].add_task(task)
            logger.info(f"Task {task.task_id} added to workflow {workflow_id}")
            return True
    
    def start_workflow(self, workflow_id: str) -> bool:
        """Start executing a workflow."""
        with self._lock:
            if workflow_id not in self._workflows:
                return False
            
            workflow = self._workflows[workflow_id]
            if workflow.status != WorkflowStatus.PENDING:
                return False
            
            workflow.status = WorkflowStatus.RUNNING
            workflow.started_at = datetime.now()
        
        # Start execution in background thread
        thread = threading.Thread(target=self._execute_workflow, args=(workflow_id,), daemon=True)
        self._execution_threads[workflow_id] = thread
        thread.start()
        
        logger.info(f"Workflow {workflow_id} started")
        return True
    
    def _execute_workflow(self, workflow_id: str):
        """Execute workflow tasks respecting dependencies."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return
        
        while workflow.status == WorkflowStatus.RUNNING:
            ready_tasks = workflow.get_ready_tasks()
            
            if not ready_tasks:
                if workflow.is_complete():
                    if workflow.has_failures():
                        workflow.status = WorkflowStatus.FAILED
                    else:
                        workflow.status = WorkflowStatus.COMPLETED
                    workflow.completed_at = datetime.now()
                    logger.info(f"Workflow {workflow_id} completed with status {workflow.status.name}")
                    break
                
                # No ready tasks but not complete - might be waiting
                time.sleep(0.5)
                continue
            
            # Execute ready tasks
            for task in ready_tasks:
                self._execute_task(workflow_id, task)
            
            time.sleep(0.1)
    
    def _execute_task(self, workflow_id: str, task: WorkflowTask):
        """Execute a single workflow task."""
        task.status = "running"
        task.started_at = datetime.now()
        
        try:
            if self.orchestrator and task.agent_id:
                # Delegate to orchestrator
                future = self.orchestrator.delegate_task(
                    description=task.description,
                    preferred_agent_id=task.agent_id,
                    metadata={"workflow_id": workflow_id, "task_id": task.task_id},
                )
                
                if future:
                    # Wait for completion (in real impl, use async)
                    task.result = future.result if hasattr(future, 'result') else None
                    task.status = "completed"
                else:
                    raise RuntimeError("Failed to delegate task")
            else:
                # Simulate task execution
                logger.info(f"Executing task {task.task_id}: {task.name}")
                time.sleep(0.1)  # Simulated work
                task.result = {"status": "simulated"}
                task.status = "completed"
            
            task.completed_at = datetime.now()
            logger.info(f"Task {task.task_id} completed")
            
        except Exception as e:
            task.error = str(e)
            task.retry_count += 1
            
            if task.retry_count < task.max_retries:
                task.status = "pending"  # Will be retried
                logger.warning(f"Task {task.task_id} failed, will retry ({task.retry_count}/{task.max_retries})")
            else:
                task.status = "failed"
                task.completed_at = datetime.now()
                logger.error(f"Task {task.task_id} failed permanently: {e}")
    
    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow."""
        with self._lock:
            if workflow_id not in self._workflows:
                return False
            
            workflow = self._workflows[workflow_id]
            if workflow.status != WorkflowStatus.RUNNING:
                return False
            
            workflow.status = WorkflowStatus.PAUSED
            logger.info(f"Workflow {workflow_id} paused")
            return True
    
    def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow."""
        with self._lock:
            if workflow_id not in self._workflows:
                return False
            
            workflow = self._workflows[workflow_id]
            if workflow.status != WorkflowStatus.PAUSED:
                return False
            
            workflow.status = WorkflowStatus.RUNNING
            
            # Restart execution thread
            thread = threading.Thread(target=self._execute_workflow, args=(workflow_id,), daemon=True)
            self._execution_threads[workflow_id] = thread
            thread.start()
            
            logger.info(f"Workflow {workflow_id} resumed")
            return True
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow."""
        with self._lock:
            if workflow_id not in self._workflows:
                return False
            
            workflow = self._workflows[workflow_id]
            workflow.status = WorkflowStatus.CANCELLED
            workflow.completed_at = datetime.now()
            
            # Cancel pending tasks
            for task in workflow.tasks.values():
                if task.status == "pending":
                    task.status = "cancelled"
                    task.completed_at = datetime.now()
            
            logger.info(f"Workflow {workflow_id} cancelled")
            return True
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed workflow status."""
        with self._lock:
            if workflow_id not in self._workflows:
                return None
            
            workflow = self._workflows[workflow_id]
            return {
                "workflow_id": workflow.workflow_id,
                "name": workflow.name,
                "status": workflow.status.value,
                "progress": {
                    "total": len(workflow.tasks),
                    "completed": sum(1 for t in workflow.tasks.values() if t.status == "completed"),
                    "failed": sum(1 for t in workflow.tasks.values() if t.status == "failed"),
                    "pending": sum(1 for t in workflow.tasks.values() if t.status == "pending"),
                    "running": sum(1 for t in workflow.tasks.values() if t.status == "running"),
                },
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "name": t.name,
                        "status": t.status,
                        "error": t.error,
                    }
                    for t in workflow.tasks.values()
                ],
                "created_at": workflow.created_at.isoformat(),
                "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
                "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            }
    
    def get_all_workflows(self) -> List[Workflow]:
        """Get all workflows."""
        with self._lock:
            return list(self._workflows.values())


class WorkflowCoordinator:
    """
    Central coordinator for workflow management.
    
    Integrates with orchestrator and provides unified workflow interface.
    """
    
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.workflow_engine = WorkflowEngine(orchestrator)
        self.message_bus = MessageBus()
        
        self._setup_default_topics()
        
        logger.info("WorkflowCoordinator initialized")
    
    def _setup_default_topics(self):
        """Setup default communication topics."""
        default_topics = [
            "system.events",
            "agent.status",
            "task.updates",
            "workflow.progress",
            "alerts",
        ]
        
        for topic in default_topics:
            self.message_bus.subscribe(topic, self._default_handler)
        
        logger.info(f"Setup {len(default_topics)} default topics")
    
    def _default_handler(self, message: Dict[str, Any]):
        """Default message handler."""
        logger.debug(f"Message on {message['topic']}: {message['id']}")
    
    def create_sequential_workflow(self, name: str, tasks: List[Dict[str, Any]],
                                   created_by: Optional[str] = None) -> Workflow:
        """Create a sequential workflow where tasks run one after another."""
        workflow = self.workflow_engine.create_workflow(name, f"Sequential: {name}", created_by)
        
        prev_task_id = None
        for i, task_data in enumerate(tasks):
            task_id = f"task-{i+1}-{uuid.uuid4().hex[:8]}"
            task = WorkflowTask(
                task_id=task_id,
                name=task_data.get("name", f"Task {i+1}"),
                description=task_data.get("description", ""),
                agent_id=task_data.get("agent_id"),
                dependencies=[prev_task_id] if prev_task_id else [],
                dependency_type=TaskDependencyType.SEQUENTIAL,
                max_retries=task_data.get("max_retries", 3),
            )
            self.workflow_engine.add_task_to_workflow(workflow.workflow_id, task)
            prev_task_id = task_id
        
        return workflow
    
    def create_parallel_workflow(self, name: str, tasks: List[Dict[str, Any]],
                                 created_by: Optional[str] = None) -> Workflow:
        """Create a parallel workflow where tasks can run simultaneously."""
        workflow = self.workflow_engine.create_workflow(name, f"Parallel: {name}", created_by)
        
        # All tasks depend on a virtual start
        for i, task_data in enumerate(tasks):
            task_id = f"task-{i+1}-{uuid.uuid4().hex[:8]}"
            task = WorkflowTask(
                task_id=task_id,
                name=task_data.get("name", f"Task {i+1}"),
                description=task_data.get("description", ""),
                agent_id=task_data.get("agent_id"),
                dependencies=[],  # No dependencies = parallel
                dependency_type=TaskDependencyType.PARALLEL,
                max_retries=task_data.get("max_retries", 3),
            )
            self.workflow_engine.add_task_to_workflow(workflow.workflow_id, task)
        
        return workflow
    
    def create_dag_workflow(self, name: str, task_definitions: Dict[str, Any],
                            created_by: Optional[str] = None) -> Workflow:
        """
        Create a DAG (Directed Acyclic Graph) workflow with complex dependencies.
        
        task_definitions format:
        {
            "task_id": {
                "name": "...",
                "description": "...",
                "dependencies": ["dep_task_id1", "dep_task_id2"],
                "agent_id": "...",
            }
        }
        """
        workflow = self.workflow_engine.create_workflow(name, f"DAG: {name}", created_by)
        
        for task_id, task_data in task_definitions.items():
            task = WorkflowTask(
                task_id=task_id,
                name=task_data.get("name", task_id),
                description=task_data.get("description", ""),
                agent_id=task_data.get("agent_id"),
                dependencies=task_data.get("dependencies", []),
                dependency_type=TaskDependencyType.SEQUENTIAL,
                max_retries=task_data.get("max_retries", 3),
            )
            self.workflow_engine.add_task_to_workflow(workflow.workflow_id, task)
        
        return workflow
    
    def on_task_completed(self, task, agent):
        """Callback when a task completes (called by orchestrator)."""
        # Publish to message bus
        self.message_bus.publish(
            "task.updates",
            {
                "event": "task_completed",
                "task_id": getattr(task, 'task_id', None),
                "agent_id": getattr(agent, 'config', {}).get('agent_id') if hasattr(agent, 'config') else None,
                "status": getattr(task, 'status', None),
            },
            sender_id="coordinator",
        )
        
        # Update workflow progress
        workflow_id = getattr(task, 'metadata', {}).get('workflow_id') if hasattr(task, 'metadata') else None
        if workflow_id:
            self.message_bus.publish(
                "workflow.progress",
                {
                    "workflow_id": workflow_id,
                    "task_completed": getattr(task, 'task_id', None),
                },
                sender_id="coordinator",
            )
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        workflows = self.workflow_engine.get_all_workflows()
        
        return {
            "total_workflows": len(workflows),
            "active_workflows": sum(1 for w in workflows if w.status == WorkflowStatus.RUNNING),
            "completed_workflows": sum(1 for w in workflows if w.status == WorkflowStatus.COMPLETED),
            "failed_workflows": sum(1 for w in workflows if w.status == WorkflowStatus.FAILED),
            "message_topics": self.message_bus.get_topics(),
            "timestamp": datetime.now().isoformat(),
        }
