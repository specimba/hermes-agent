"""
Test suite for Zilliz Cloud integration.

Tests cover:
- Configuration loading from environment
- Client initialization with graceful degradation
- Cluster selection logic
- Health check functionality
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nexus_os.vault.zilliz_client import (
    ZillizClient,
    _get_zilliz_config,
    is_zilliz_available,
    VectorRecord
)


class TestZillizConfiguration:
    """Test configuration loading."""
    
    def test_no_config_returns_empty_dict(self):
        """Test that missing env vars return empty config."""
        with patch.dict(os.environ, {}, clear=True):
            config = _get_zilliz_config()
            assert config == {}
    
    def test_serverless_config_detected(self):
        """Test serverless cluster configuration."""
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://test.serverless.aws.cloud.zilliz.com",
            "ZILLIZ_SERVERLESS_TOKEN": "test_token"
        }):
            config = _get_zilliz_config()
            assert config["serverless_uri"] == "https://test.serverless.aws.cloud.zilliz.com"
            assert config["serverless_token"] == "test_token"
    
    def test_town_config_detected(self):
        """Test town cluster configuration."""
        with patch.dict(os.environ, {
            "ZILLIZ_TOWN_URI": "https://test.town.aws.cloud.zilliz.com",
            "ZILLIZ_TOWN_TOKEN": "test_token"
        }):
            config = _get_zilliz_config()
            assert config["town_uri"] == "https://test.town.aws.cloud.zilliz.com"
            assert config["town_token"] == "test_token"
    
    def test_dual_cluster_config(self):
        """Test both clusters configured."""
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://serverless.test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "sl_token",
            "ZILLIZ_TOWN_URI": "https://town.test.com",
            "ZILLIZ_TOWN_TOKEN": "town_token"
        }):
            config = _get_zilliz_config()
            assert len(config) == 4
            assert config["serverless_uri"] == "https://serverless.test.com"
            assert config["town_uri"] == "https://town.test.com"


class TestZillizAvailability:
    """Test availability checks."""
    
    def test_not_available_without_config(self):
        """Test Zilliz not available without config."""
        with patch.dict(os.environ, {}, clear=True):
            assert not is_zilliz_available()
    
    def test_available_with_config(self):
        """Test Zilliz available with config."""
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token"
        }):
            assert is_zilliz_available()


class TestVectorRecord:
    """Test vector record data model."""
    
    def test_vector_record_creation(self):
        """Test creating a vector record."""
        record = VectorRecord(
            id="test_123",
            embedding=[0.1, 0.2, 0.3],
            metadata={"key": "value"}
        )
        
        assert record.id == "test_123"
        assert record.embedding == [0.1, 0.2, 0.3]
        assert record.metadata["key"] == "value"
    
    def test_vector_record_to_dict(self):
        """Test converting record to dictionary."""
        record = VectorRecord(
            id="test_456",
            embedding=[0.4, 0.5],
            metadata={"agent": "test"}
        )
        
        result = record.to_dict()
        assert result["id"] == "test_456"
        assert result["vector"] == [0.4, 0.5]
        assert result["metadata"]["agent"] == "test"


class TestZillizClientInitialization:
    """Test client initialization."""
    
    def test_client_init_without_config(self):
        """Test client initializes gracefully without config."""
        with patch.dict(os.environ, {}, clear=True):
            client = ZillizClient()
            assert not client.is_available()
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_client_init_with_serverless(self, mock_milvus):
        """Test client initializes with serverless cluster."""
        mock_client = MagicMock()
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token"
        }):
            client = ZillizClient()
            assert client.is_available()
            assert "serverless" in client._connections
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_client_init_with_dual_cluster(self, mock_milvus):
        """Test client initializes with both clusters."""
        mock_client = MagicMock()
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://serverless.test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "sl_token",
            "ZILLIZ_TOWN_URI": "https://town.test.com",
            "ZILLIZ_TOWN_TOKEN": "town_token"
        }):
            client = ZillizClient()
            assert client.is_available()
            assert "serverless" in client._connections
            assert "town" in client._connections


class TestClusterSelection:
    """Test cluster selection logic."""
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_event_track_uses_serverless(self, mock_milvus):
        """Test EVENT tracks use serverless cluster."""
        mock_client = MagicMock()
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://serverless.test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token",
            "ZILLIZ_TOWN_URI": "https://town.test.com",
            "ZILLIZ_TOWN_TOKEN": "token"
        }):
            client = ZillizClient()
            cluster = client._get_cluster_for_track("EVENT")
            assert cluster == "serverless"
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_trust_track_uses_town(self, mock_milvus):
        """Test TRUST tracks use town cluster."""
        mock_client = MagicMock()
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://serverless.test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token",
            "ZILLIZ_TOWN_URI": "https://town.test.com",
            "ZILLIZ_TOWN_TOKEN": "token"
        }):
            client = ZillizClient()
            cluster = client._get_cluster_for_track("TRUST")
            assert cluster == "town"
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_unknown_track_fallback_to_town(self, mock_milvus):
        """Test unknown track types fallback to town."""
        mock_client = MagicMock()
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_TOWN_URI": "https://town.test.com",
            "ZILLIZ_TOWN_TOKEN": "token"
        }):
            client = ZillizClient()
            cluster = client._get_cluster_for_track("UNKNOWN_TRACK")
            assert cluster == "town"


class TestHealthCheck:
    """Test health check functionality."""
    
    def test_health_check_without_config(self):
        """Test health check returns unavailable status."""
        with patch.dict(os.environ, {}, clear=True):
            client = ZillizClient()
            status = client.health_check() if hasattr(client.health_check(), '__await__') else client.health_check()
            
            # Handle async if needed
            if hasattr(status, '__await__'):
                import asyncio
                status = asyncio.run(status)
            
            assert status["available"] is False
            assert status["clusters"] == {}
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_health_check_with_clusters(self, mock_milvus):
        """Test health check reports cluster status."""
        mock_client = MagicMock()
        mock_client.list_collections.return_value = ["collection1", "collection2"]
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token"
        }):
            client = ZillizClient()
            
            import asyncio
            status = asyncio.run(client.health_check())
            
            assert status["available"] is True
            assert "serverless" in status["clusters"]
            assert status["clusters"]["serverless"]["status"] == "healthy"
            assert status["clusters"]["serverless"]["collections"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
