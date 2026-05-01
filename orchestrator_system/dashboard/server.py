#!/usr/bin/env python3
"""
Dashboard Server

HTTP server providing a web-based dashboard for monitoring and controlling
the multi-agent orchestration system.
"""

import json
import logging
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class DashboardAPI:
    """REST API for dashboard operations."""
    
    def __init__(self, orchestrator=None, governance=None, coordinator=None):
        self.orchestrator = orchestrator
        self.governance = governance
        self.coordinator = coordinator
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get overall system status."""
        overview = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "components": {},
        }
        
        if self.orchestrator:
            orch_status = self.orchestrator.get_status()
            overview["components"]["orchestrator"] = {
                "status": "running" if orch_status.get("running") else "stopped",
                "agents": orch_status.get("total_agents", 0),
                "tasks": orch_status.get("total_tasks", 0),
            }
        
        if self.governance:
            compliance = self.governance.get_compliance_report()
            overview["components"]["governance"] = {
                "status": compliance.get("compliance_status", "unknown"),
                "policies": compliance.get("active_policies", 0),
            }
        
        if self.coordinator:
            coord_status = self.coordinator.get_system_status()
            overview["components"]["coordinator"] = {
                "workflows": coord_status.get("total_workflows", 0),
                "active_workflows": coord_status.get("active_workflows", 0),
            }
        
        return overview
    
    def get_agents(self) -> Dict[str, Any]:
        """Get all agents status."""
        if not self.orchestrator:
            return {"agents": []}
        
        status = self.orchestrator.get_status()
        return {"agents": status.get("agents", [])}
    
    def get_agent_detail(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed info for a specific agent."""
        if not self.orchestrator:
            return None
        
        agent = self.orchestrator.registry.get(agent_id)
        if not agent:
            return None
        
        return agent.get_info()
    
    def get_tasks(self) -> Dict[str, Any]:
        """Get all tasks."""
        if not self.orchestrator:
            return {"tasks": []}
        
        tasks = self.orchestrator.task_manager.get_all_tasks()
        return {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "description": t.description[:100] + "..." if len(t.description) > 100 else t.description,
                    "status": t.status,
                    "priority": t.priority.name if hasattr(t.priority, 'name') else str(t.priority),
                    "assigned_agent": t.assigned_agent_id,
                    "created_at": t.created_at.isoformat(),
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                }
                for t in tasks
            ]
        }
    
    def get_workflows(self) -> Dict[str, Any]:
        """Get all workflows."""
        if not self.coordinator:
            return {"workflows": []}
        
        workflows = self.coordinator.workflow_engine.get_all_workflows()
        return {
            "workflows": [
                {
                    "workflow_id": w.workflow_id,
                    "name": w.name,
                    "status": w.status.value,
                    "task_count": len(w.tasks),
                    "created_at": w.created_at.isoformat(),
                }
                for w in workflows
            ]
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        if not self.orchestrator:
            return {}
        
        return self.orchestrator.export_metrics()
    
    def get_audit_events(self, limit: int = 100) -> Dict[str, Any]:
        """Get recent audit events."""
        if not self.governance:
            return {"events": []}
        
        events = self.governance.audit_logger.query_events(limit=limit)
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp.isoformat(),
                    "action": e.action,
                    "result": e.result,
                    "actor_id": e.actor_id,
                }
                for e in events
            ]
        }
    
    def create_agent(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new agent."""
        if not self.orchestrator:
            return {"error": "Orchestrator not available"}
        
        from orchestrator_system.orchestrator.core import AgentConfig
        
        agent_config = AgentConfig(
            agent_id=config.get("agent_id"),
            model=config.get("model", "anthropic/claude-opus-4.6"),
            toolsets=config.get("toolsets", ["terminal", "file", "web"]),
            max_iterations=config.get("max_iterations", 50),
            strictness_level=config.get("strictness_level", "medium"),
            task_type=config.get("task_type", "general"),
            groups=config.get("groups", []),
        )
        
        agent = self.orchestrator.create_agent(agent_config)
        if agent:
            return {"success": True, "agent_id": agent.config.agent_id}
        return {"success": False, "error": "Failed to create agent"}
    
    def update_agent(self, agent_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing agent's configuration."""
        if not self.orchestrator:
            return {"error": "Orchestrator not available"}
        
        agent = self.orchestrator.registry.get(agent_id)
        if not agent:
            return {"error": "Agent not found", "success": False}
        
        # Apply updates
        if "name" in updates:
            agent.config.metadata["name"] = updates["name"]
        if "task" in updates:
            agent.config.task_type = updates["task"]
        if "strictness_level" in updates:
            agent.config.strictness_level = updates["strictness_level"]
        if "model" in updates:
            agent.config.model = updates["model"]
        if "toolsets" in updates:
            agent.config.toolsets = updates["toolsets"]
        if "enabled" in updates:
            agent.config.enabled = updates["enabled"]
        if "groups" in updates:
            # Update group memberships
            for group_id in updates["groups"]:
                self.orchestrator.registry.add_agent_to_group(agent_id, group_id)
        
        logger.info(f"Agent {agent_id} updated")
        return {"success": True, "agent_id": agent_id}
    
    def get_groups(self) -> Dict[str, Any]:
        """Get all agent groups."""
        if not self.orchestrator:
            return {"groups": []}
        
        groups = self.orchestrator.registry.get_all_groups()
        return {"groups": [g.to_dict() for g in groups]}
    
    def create_group(self, name: str, description: str = "", 
                    criteria: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new agent group."""
        if not self.orchestrator:
            return {"error": "Orchestrator not available", "success": False}
        
        group = self.orchestrator.registry.create_group(name, description, criteria)
        return {"success": True, "group": group.to_dict()}
    
    def submit_feedback(self, agent_id: str, task_id: str, 
                       rating: int, comment: str = "") -> Dict[str, Any]:
        """Submit feedback on agent performance."""
        if not self.orchestrator:
            return {"error": "Orchestrator not available", "success": False}
        
        from orchestrator_system.feedback.loop import FeedbackEntry
        
        feedback = FeedbackEntry(
            agent_id=agent_id,
            task_id=task_id,
            rating=rating,
            comment=comment,
        )
        
        # Submit to feedback engine if available
        if self.orchestrator._feedback_engine:
            self.orchestrator._feedback_engine.submit_feedback(feedback)
        
        # Update agent metrics
        agent = self.orchestrator.registry.get(agent_id)
        if agent:
            if "feedback_count" not in agent.config.metadata:
                agent.config.metadata["feedback_count"] = 0
                agent.config.metadata["total_rating"] = 0
                agent.config.metadata["average_rating"] = 0.0
            
            agent.config.metadata["feedback_count"] += 1
            agent.config.metadata["total_rating"] += rating
            agent.config.metadata["average_rating"] = (
                agent.config.metadata["total_rating"] / 
                agent.config.metadata["feedback_count"]
            )
        
        logger.info(f"Feedback submitted for agent {agent_id}, task {task_id}: {rating}")
        return {"success": True, "feedback_id": feedback.feedback_id}
    
    def delegate_task_to_agent(self, agent_id: str, description: str,
                               priority: str = "normal") -> Dict[str, Any]:
        """Delegate a specific task to a specific agent."""
        if not self.orchestrator:
            return {"error": "Orchestrator not available", "success": False}
        
        from orchestrator_system.orchestrator.core import TaskPriority
        
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL,
        }
        
        task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
        
        # Check if agent exists and is available
        agent = self.orchestrator.registry.get(agent_id)
        if not agent:
            return {"error": "Agent not found", "success": False}
        
        task = self.orchestrator.delegate_task(
            description=description,
            priority=task_priority,
            preferred_agent_id=agent_id,
        )
        
        if task:
            return {
                "success": True,
                "task_id": task.task_id,
                "status": task.status,
                "assigned_agent": agent_id,
            }
        return {"success": False, "error": "Failed to create task"}
    
    def delegate_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate a new task."""
        if not self.orchestrator:
            return {"error": "Orchestrator not available"}
        
        from orchestrator_system.orchestrator.core import TaskPriority
        
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL,
        }
        
        priority = priority_map.get(task_data.get("priority", "normal"), TaskPriority.NORMAL)
        
        task = self.orchestrator.delegate_task(
            description=task_data.get("description", ""),
            priority=priority,
            required_toolsets=task_data.get("toolsets"),
            preferred_agent_id=task_data.get("agent_id"),
        )
        
        if task:
            return {
                "success": True,
                "task_id": task.task_id,
                "status": task.status,
            }
        return {"success": False, "error": "Failed to create task"}
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a task."""
        if not self.orchestrator:
            return {"error": "Orchestrator not available"}
        
        success = self.orchestrator.task_manager.cancel_task(task_id)
        return {"success": success}


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for dashboard API."""
    
    api: DashboardAPI = None
    
    def log_message(self, format, *args):
        logger.debug(f"Dashboard: {args[0]}")
    
    def send_json_response(self, data: Dict[str, Any], status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path == '/api/overview':
            self.send_json_response(self.api.get_system_overview())
        elif path == '/api/agents':
            self.send_json_response(self.api.get_agents())
        elif path.startswith('/api/agents/'):
            agent_id = path.split('/')[-1]
            result = self.api.get_agent_detail(agent_id)
            if result:
                self.send_json_response(result)
            else:
                self.send_json_response({"error": "Agent not found"}, 404)
        elif path == '/api/tasks':
            self.send_json_response(self.api.get_tasks())
        elif path == '/api/workflows':
            self.send_json_response(self.api.get_workflows())
        elif path == '/api/metrics':
            self.send_json_response(self.api.get_metrics())
        elif path == '/api/audit':
            limit = int(query.get('limit', [100])[0])
            self.send_json_response(self.api.get_audit_events(limit))
        elif path == '/api/compliance':
            if self.api.governance:
                self.send_json_response(self.api.governance.get_compliance_report())
            else:
                self.send_json_response({"error": "Governance not available"}, 404)
        elif path == '/':
            self.serve_dashboard_html()
        else:
            self.send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, 400)
            return
        
        if path == '/api/agents':
            result = self.api.create_agent(data)
            status = 200 if result.get("success") else 400
            self.send_json_response(result, status)
        elif path.startswith('/api/agents/') and not path.endswith('/cancel'):
            # Handle agent-specific operations
            parts = path.split('/')
            agent_id = parts[3]  # /api/agents/{agent_id}
            
            if len(parts) == 4:
                # GET /api/agents/{agent_id} - get agent details
                result = self.api.get_agent_detail(agent_id)
                if result:
                    self.send_json_response(result)
                else:
                    self.send_json_response({"error": "Agent not found"}, 404)
            elif len(parts) == 5 and parts[4] == 'update':
                # POST /api/agents/{agent_id}/update
                result = self.api.update_agent(agent_id, data)
                status = 200 if result.get("success") else 400
                self.send_json_response(result, status)
            elif len(parts) == 5 and parts[4] == 'delegate':
                # POST /api/agents/{agent_id}/delegate
                description = data.get("description", "")
                priority = data.get("priority", "normal")
                result = self.api.delegate_task_to_agent(agent_id, description, priority)
                status = 200 if result.get("success") else 400
                self.send_json_response(result, status)
            elif len(parts) == 5 and parts[4] == 'feedback':
                # POST /api/agents/{agent_id}/feedback
                task_id = data.get("task_id", "")
                rating = data.get("rating", 0)
                comment = data.get("comment", "")
                result = self.api.submit_feedback(agent_id, task_id, rating, comment)
                status = 200 if result.get("success") else 400
                self.send_json_response(result, status)
        elif path == '/api/groups':
            if self.command == 'GET':
                result = self.api.get_groups()
                self.send_json_response(result)
            elif self.command == 'POST':
                name = data.get("name", "")
                description = data.get("description", "")
                criteria = data.get("criteria")
                result = self.api.create_group(name, description, criteria)
                status = 200 if result.get("success") else 400
                self.send_json_response(result, status)
    
    def serve_dashboard_html(self):
        """Serve the dashboard HTML interface."""
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes Multi-Agent Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0f172a; color: #e2e8f0; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px; margin-bottom: 30px; }
        h1 { font-size: 2em; margin-bottom: 10px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; }
        .card h2 { font-size: 1.2em; margin-bottom: 16px; color: #94a3b8; }
        .stat { font-size: 2.5em; font-weight: bold; color: #667eea; }
        .stat-label { color: #64748b; font-size: 0.9em; margin-top: 8px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; }
        th { color: #94a3b8; }
        .btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; float: right; }
    </style>
</head>
<body>
    <div class="container">
        <header><h1>Hermes Multi-Agent Dashboard</h1></header>
        <div class="grid" id="overview"></div>
        <div class="card"><h2>Agents <button class="btn" onclick="loadData()">Refresh</button></h2>
        <table id="agents-table"><thead><tr><th>ID</th><th>Model</th><th>Status</th><th>Tasks</th></tr></thead><tbody></tbody></table></div>
    </div>
    <script>
        async function loadData() {
            const [overview, agents] = await Promise.all([
                fetch('/api/overview').then(r => r.json()),
                fetch('/api/agents').then(r => r.json())
            ]);
            document.getElementById('overview').innerHTML = 
                '<div class="card"><h2>Status</h2><div class="stat">' + overview.status + '</div></div>' +
                '<div class="card"><h2>Agents</h2><div class="stat">' + (overview.components.orchestrator?.agents || 0) + '</div></div>';
            document.querySelector('#agents-table tbody').innerHTML = 
                agents.agents.map(a => '<tr><td>' + a.agent_id + '</td><td>' + a.model + '</td><td>' + a.status + '</td><td>' + (a.metrics?.tasks_completed || 0) + '</td></tr>').join('');
        }
        loadData();
        setInterval(loadData, 5000);
    </script>
</body>
</html>'''
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html.encode())


class DashboardServer:
    """Dashboard HTTP server."""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8080,
                 orchestrator=None, governance=None, coordinator=None):
        self.host = host
        self.port = port
        self.orchestrator = orchestrator
        self.governance = governance
        self.coordinator = coordinator
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.api = DashboardAPI(orchestrator, governance, coordinator)
    
    def start(self):
        """Start the dashboard server."""
        if self._running:
            return
        DashboardRequestHandler.api = self.api
        self._server = HTTPServer((self.host, self.port), DashboardRequestHandler)
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        logger.info(f"Dashboard server started on http://{self.host}:{self.port}")
    
    def _serve(self):
        """Run the HTTP server."""
        while self._running:
            self._server.handle_request()
    
    def stop(self):
        """Stop the dashboard server."""
        self._running = False
        if self._server:
            self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Dashboard server stopped")
    
    def get_url(self) -> str:
        """Get the dashboard URL."""
        return f"http://localhost:{self.port}"
