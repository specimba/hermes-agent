"""
Test suite for OpenShell Gateway integration.

Tests cover:
- Executor initialization
- Health checking
- Sandbox creation and management
- Command execution
- Error handling
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtimes.openshell_executor import OpenShellExecutor, SandboxResult


class TestOpenShellExecutorInit:
    """Test executor initialization."""
    
    def test_default_init(self):
        """Test default initialization."""
        executor = OpenShellExecutor()
        assert executor.gateway_url == "http://127.0.0.1:8080"
        assert executor.timeout == 300
        assert executor.session.headers["Content-Type"] == "application/json"
    
    def test_custom_init(self):
        """Test custom initialization."""
        executor = OpenShellExecutor(
            gateway_url="http://test-host:9090",
            timeout=60
        )
        assert executor.gateway_url == "http://test-host:9090"
        assert executor.timeout == 60


class TestHealthCheck:
    """Test gateway health checking."""
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_healthy_gateway(self, mock_session):
        """Test health check returns True for healthy gateway."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.return_value.get.return_value = mock_response
        
        executor = OpenShellExecutor()
        assert executor.health_check() is True
        mock_session.return_value.get.assert_called_once_with(
            "http://127.0.0.1:8080/health",
            timeout=5
        )
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_unhealthy_gateway_status(self, mock_session):
        """Test health check returns False for non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_session.return_value.get.return_value = mock_response
        
        executor = OpenShellExecutor()
        assert executor.health_check() is False
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_health_check_exception(self, mock_session):
        """Test health check returns False on connection error."""
        mock_session.return_value.get.side_effect = Exception("Connection refused")
        
        executor = OpenShellExecutor()
        assert executor.health_check() is False


class TestSandboxCreation:
    """Test sandbox creation and management."""
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_create_sandbox_success(self, mock_session):
        """Test successful sandbox creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sandbox_id": "sb-12345"}
        mock_session.return_value.post.return_value = mock_response
        
        executor = OpenShellExecutor()
        sandbox_id = executor.create_sandbox(
            policy_profile="default",
            task_id="task-001",
            environment_vars={"ENV": "test"}
        )
        
        assert sandbox_id == "sb-12345"
        mock_session.return_value.post.assert_called_once()
        call_args = mock_session.return_value.post.call_args
        assert "sandboxes" in call_args[0][0]
        assert call_args[1]["json"]["policy"] == "default"
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_create_sandbox_failure(self, mock_session):
        """Test sandbox creation failure."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Policy not found"
        mock_session.return_value.post.return_value = mock_response
        
        executor = OpenShellExecutor()
        sandbox_id = executor.create_sandbox("invalid", "task-001")
        assert sandbox_id is None


class TestCommandExecution:
    """Test command execution in sandboxes."""
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_execute_success(self, mock_session):
        """Test successful command execution."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "stdout": "hello world",
            "stderr": "",
            "exit_code": 0,
            "policy_profile": "default"
        }
        mock_session.return_value.post.return_value = mock_response
        
        executor = OpenShellExecutor()
        result = executor.execute_in_sandbox(
            sandbox_id="sb-123",
            command="echo",
            args=["hello world"]
        )
        
        assert result.success is True
        assert result.output == "hello world"
        assert result.exit_code == 0
        assert result.sandbox_id == "sb-123"
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_execute_failure(self, mock_session):
        """Test command execution failure."""
        mock_session.return_value.post.side_effect = Exception("Execution timeout")
        
        executor = OpenShellExecutor()
        result = executor.execute_in_sandbox("sb-123", "sleep", ["10"])
        
        assert result.success is False
        assert "Execution timeout" in result.error
        assert result.exit_code == -1


class TestSandboxDestruction:
    """Test sandbox cleanup."""
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_destroy_sandbox_success(self, mock_session):
        """Test successful sandbox destruction."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_session.return_value.delete.return_value = mock_response
        
        executor = OpenShellExecutor()
        result = executor.destroy_sandbox("sb-123")
        assert result is True
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_destroy_sandbox_failure(self, mock_session):
        """Test sandbox destruction failure."""
        mock_session.return_value.delete.side_effect = Exception("Not found")
        
        executor = OpenShellExecutor()
        result = executor.destroy_sandbox("invalid-sb")
        assert result is False


class TestSandboxStatus:
    """Test sandbox status retrieval."""
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_get_status_success(self, mock_session):
        """Test successful status retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "sb-123", "status": "running"}
        mock_session.return_value.get.return_value = mock_response
        
        executor = OpenShellExecutor()
        status = executor.get_sandbox_status("sb-123")
        assert status is not None
        assert status["status"] == "running"
    
    @patch('runtimes.openshell_executor.requests.Session')
    def test_get_status_not_found(self, mock_session):
        """Test status retrieval for non-existent sandbox."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.return_value.get.return_value = mock_response
        
        executor = OpenShellExecutor()
        status = executor.get_sandbox_status("invalid")
        assert status is None


class TestTaskExecution:
    """Test TaskPacket execution flow."""
    
    @patch('runtimes.openshell_executor.OpenShellExecutor.create_sandbox')
    @patch('runtimes.openshell_executor.OpenShellExecutor.execute_in_sandbox')
    def test_execute_python_task(self, mock_execute, mock_create):
        """Test executing a Python code task."""
        mock_create.return_value = "sb-123"
        mock_execute.return_value = SandboxResult(
            success=True,
            output="42",
            error=None,
            exit_code=0,
            duration_ms=100,
            sandbox_id="sb-123",
            policy_profile="default"
        )
        
        # Mock TaskPacket import
        mock_taskpacket = MagicMock()
        mock_taskpacket.action = "execute_code"
        mock_taskpacket.payload = {"code": "print(42)", "language": "python"}
        mock_taskpacket.agent_id = "agent1"
        mock_taskpacket.sandbox_identity.sandbox_id = "sb-123"
        mock_taskpacket.sandbox_identity.policy_profile = "default"
        mock_taskpacket.sandbox_identity.trust_tier = MagicMock(value="basic")
        
        executor = OpenShellExecutor()
        result = executor.execute_task(mock_taskpacket)
        
        assert result.success is True
        assert result.output == "42"
        mock_create.assert_called_once()
        mock_execute.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
