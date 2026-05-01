# Hermes Multi-Agent Orchestration System

A comprehensive system for managing and orchestrating multiple AI agents, with robust governance, coordination, monitoring, and continuous improvement features.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    HERMES ORCHESTRATION SYSTEM                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Orchestrator │  │  Governance  │  │ Coordinator  │          │
│  │   (Core)     │  │   Engine     │  │  (Workflow)  │          │
│  │              │  │              │  │              │          │
│  │ - Agent Mgmt │  │ - Policies   │  │ - DAG Flow   │          │
│  │ - Task Queue │  │ - Security   │  │ - Messaging  │          │
│  │ - Load Bal.  │  │ - Audit Log  │  │ - Events     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           │                                     │
│                  ┌────────▼────────┐                            │
│                  │ Feedback Engine │                            │
│                  │                 │                            │
│                  │ - Analytics     │                            │
│                  │ - Insights      │                            │
│                  │ - Optimization  │                            │
│                  └────────┬────────┘                            │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                   │
│         │                 │                 │                   │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐          │
│  │   Agent 1    │  │   Agent 2    │  │   Agent N    │          │
│  │  (AI Model)  │  │  (AI Model)  │  │  (AI Model)  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                     ┌────────▼────────┐
                     │   Dashboard     │
                     │   (Web UI)      │
                     │  Port: 8080     │
                     └─────────────────┘
```

## Components

### 1. Agent Orchestrator (`orchestrator_system/orchestrator/`)
- **AgentOrchestrator**: Central coordinator for agent lifecycle and task delegation
- **AgentRegistry**: Manages registered agent instances
- **TaskManager**: Handles task queue, priorities, and execution tracking
- **ResourceAllocator**: Allocates resources to agents and tasks

**Features:**
- Dynamic agent creation and destruction
- Intelligent task delegation with load balancing
- Auto-scaling based on demand
- Real-time performance monitoring

### 2. Governance Engine (`orchestrator_system/governance/`)
- **GovernanceEngine**: Central policy enforcement and compliance
- **PolicyEngine**: Evaluates policies against requests
- **SecurityManager**: Authentication, authorization, threat detection
- **AuditLogger**: Comprehensive audit trail logging

**Features:**
- Policy-based access control
- Rate limiting and throttling
- Sensitive data protection
- Complete audit trail for compliance

### 3. Workflow Coordinator (`orchestrator_system/coordinator/`)
- **WorkflowCoordinator**: Manages complex multi-agent workflows
- **WorkflowEngine**: Executes workflow tasks with dependency resolution
- **MessageBus**: Pub/sub communication between agents

**Features:**
- Sequential, parallel, and DAG workflows
- Inter-agent messaging
- Task dependency management
- Workflow pause/resume/cancel

### 4. Feedback Engine (`orchestrator_system/feedback/`)
- **FeedbackEngine**: Continuous improvement through analytics
- **PerformanceAnalyzer**: Analyzes agent performance patterns
- **AgentLearner**: Generates insights and optimization suggestions

**Features:**
- Real-time performance tracking
- Pattern recognition and anomaly detection
- Automated improvement suggestions
- Historical trend analysis

### 5. Dashboard (`orchestrator_system/dashboard/`)
- **DashboardServer**: Web-based monitoring interface
- **DashboardAPI**: REST API for programmatic access

**Features:**
- Real-time system overview
- Agent status and metrics
- Task monitoring
- Audit log viewer
- Compliance reports

## Quick Start

### Installation

```bash
cd /workspace
pip install -r requirements.txt  # If you have dependencies
```

### Running the System

```bash
# Start the full orchestration system
python run_orchestrator.py --port 8080

# Or start without dashboard
python run_orchestrator.py --no-dashboard
```

### Access Dashboard

Open your browser to: `http://localhost:8080`

### Programmatic Usage

```python
from orchestrator_system import (
    AgentOrchestrator,
    GovernanceEngine, 
    WorkflowCoordinator,
    FeedbackEngine,
    DashboardServer
)

# Initialize components
orchestrator = AgentOrchestrator()
governance = GovernanceEngine()
coordinator = WorkflowCoordinator(orchestrator)
feedback = FeedbackEngine()

# Connect components
orchestrator.set_governance_engine(governance)
orchestrator.set_workflow_coordinator(coordinator)
orchestrator.set_feedback_engine(feedback)

# Start services
orchestrator.start()
feedback.start()

# Create agents
agent1 = orchestrator.create_agent()
agent2 = orchestrator.create_agent()

# Delegate tasks
task = orchestrator.delegate_task(
    description="Analyze project structure",
    priority="high"
)

# Start dashboard
dashboard = DashboardServer(
    port=8080,
    orchestrator=orchestrator,
    governance=governance,
    coordinator=coordinator
)
dashboard.start()

print(f"Dashboard available at {dashboard.get_url()}")
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/overview` | GET | System overview |
| `/api/agents` | GET | List all agents |
| `/api/agents/{id}` | GET | Agent details |
| `/api/agents` | POST | Create agent |
| `/api/tasks` | GET | List all tasks |
| `/api/tasks` | POST | Create task |
| `/api/tasks/{id}/cancel` | POST | Cancel task |
| `/api/workflows` | GET | List workflows |
| `/api/metrics` | GET | System metrics |
| `/api/audit` | GET | Audit events |
| `/api/compliance` | GET | Compliance report |

## Configuration

Create a `config.json` file:

```json
{
  "max_agents": 10,
  "default_model": "anthropic/claude-opus-4.6",
  "default_toolsets": ["terminal", "file", "web"],
  "enable_auto_scaling": true,
  "min_idle_agents": 2,
  "max_idle_agents": 5,
  "enable_policy_enforcement": true,
  "enable_audit_logging": true,
  "max_api_calls_per_minute": 60
}
```

Run with config:
```bash
python run_orchestrator.py --config config.json
```

## File Structure

```
/workspace/
├── orchestrator_system/
│   ├── __init__.py
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── core.py
│   ├── governance/
│   │   ├── __init__.py
│   │   └── core.py
│   ├── coordinator/
│   │   ├── __init__.py
│   │   └── core.py
│   ├── feedback/
│   │   ├── __init__.py
│   │   └── loop.py
│   └── dashboard/
│       ├── __init__.py
│       └── server.py
├── run_orchestrator.py
├── README.md
└── requirements.txt
```

## License

MIT License
