#!/usr/bin/env python3
"""
Hermes Multi-Agent Orchestration System - Main Entry Point

This script initializes and runs the complete multi-agent orchestration system
with orchestrator, governance, coordinator, dashboard, and feedback components.

Usage:
    python run_orchestrator.py [--port 8080] [--config config.json]
"""

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path.home() / '.hermes' / 'orchestrator.log')
    ]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Hermes Multi-Agent Orchestrator')
    parser.add_argument('--port', type=int, default=8080, help='Dashboard port (default: 8080)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Dashboard host (default: 0.0.0.0)')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--no-dashboard', action='store_true', help='Disable dashboard')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Hermes Multi-Agent Orchestration System Starting...")
    logger.info("=" * 60)
    
    # Import components
    from orchestrator_system.orchestrator.core import AgentOrchestrator
    from orchestrator_system.governance.core import GovernanceEngine
    from orchestrator_system.coordinator.core import WorkflowCoordinator
    from orchestrator_system.dashboard.server import DashboardServer
    from orchestrator_system.feedback.loop import FeedbackEngine
    
    # Initialize components
    logger.info("Initializing components...")
    
    # 1. Initialize Orchestrator
    orchestrator = AgentOrchestrator(config_path=args.config)
    logger.info("✓ AgentOrchestrator initialized")
    
    # 2. Initialize Governance
    governance = GovernanceEngine(config_path=args.config)
    logger.info("✓ GovernanceEngine initialized")
    
    # 3. Initialize Coordinator
    coordinator = WorkflowCoordinator(orchestrator)
    logger.info("✓ WorkflowCoordinator initialized")
    
    # 4. Initialize Feedback Engine
    feedback = FeedbackEngine(config_path=args.config)
    logger.info("✓ FeedbackEngine initialized")
    
    # Connect components
    orchestrator.set_governance_engine(governance)
    orchestrator.set_workflow_coordinator(coordinator)
    orchestrator.set_feedback_engine(feedback)
    logger.info("✓ Components connected")
    
    # Start background services
    orchestrator.start()
    feedback.start()
    coordinator.message_bus.start()
    logger.info("✓ Background services started")
    
    # Start dashboard (optional)
    dashboard = None
    if not args.no_dashboard:
        dashboard = DashboardServer(
            host=args.host,
            port=args.port,
            orchestrator=orchestrator,
            governance=governance,
            coordinator=coordinator,
        )
        dashboard.start()
        logger.info(f"✓ Dashboard available at http://localhost:{args.port}")
    
    # Create some initial agents for demonstration
    logger.info("Creating initial agents...")
    for i in range(2):
        agent = orchestrator.create_agent()
        if agent:
            logger.info(f"  Created agent: {agent.config.agent_id}")
    
    # Demo task delegation
    logger.info("\nSystem ready! Delegating demo tasks...")
    
    def on_complete(task, result, agent):
        logger.info(f"Task {task.task_id} completed by {agent.config.agent_id}")
    
    orchestrator.on_task_complete(on_complete)
    
    # Delegate some demo tasks
    demo_tasks = [
        "Analyze the current directory structure and report findings",
        "Review Python files for potential improvements",
    ]
    
    for task_desc in demo_tasks:
        task = orchestrator.delegate_task(
            description=task_desc,
            metadata={"source": "demo"},
        )
        if task:
            logger.info(f"  Queued task: {task.task_id}")
    
    # Handle shutdown
    running = True
    
    def signal_handler(sig, frame):
        nonlocal running
        logger.info("\nShutdown signal received...")
        running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("\n" + "=" * 60)
    logger.info("System is running. Press Ctrl+C to stop.")
    logger.info("=" * 60 + "\n")
    
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup
        logger.info("Shutting down...")
        
        if dashboard:
            dashboard.stop()
        
        feedback.stop()
        coordinator.message_bus.stop()
        orchestrator.stop()
        
        # Export final metrics
        metrics_path = Path.home() / '.hermes' / 'final_metrics.json'
        with open(metrics_path, 'w') as f:
            json.dump(orchestrator.export_metrics(), f, indent=2)
        logger.info(f"Final metrics saved to {metrics_path}")
        
        logger.info("System shutdown complete.")


if __name__ == '__main__':
    main()
