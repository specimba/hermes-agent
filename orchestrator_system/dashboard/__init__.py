"""
Dashboard Module

Web-based monitoring and control interface for the multi-agent system.
"""

from .server import DashboardServer
from .api import DashboardAPI

__all__ = [
    "DashboardServer",
    "DashboardAPI",
]
