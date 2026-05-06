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


class TestCollectionName:
    """Test collection name generation."""
    
    def test_event_collection_name(self):
        """Test EVENT track collection name."""
        client = ZillizClient()
        name = client._get_collection_name("EVENT")
        assert name == "nexus_event"
    
    def test_trust_collection_name(self):
        """Test TRUST track collection name."""
        client = ZillizClient()
        name = client._get_collection_name("TRUST")
        assert name == "nexus_trust"
    
    def test_governance_collection_name(self):
        """Test GOVERNANCE track collection name."""
        client = ZillizClient()
        name = client._get_collection_name("GOVERNANCE")
        assert name == "nexus_governance"


class TestEnsureCollection:
    """Test collection creation and management."""
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_skip_when_unavailable(self, mock_milvus):
        """Test ensure_collection does nothing when client unavailable."""
        with patch.dict(os.environ, {}, clear=True):
            client = ZillizClient()
            asyncio.run(client.ensure_collection("EVENT"))
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_existing_collection(self, mock_milvus):
        """Test ensure_collection skips if collection already exists."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token"
        }):
            client = ZillizClient()
            asyncio.run(client.ensure_collection("EVENT"))
            mock_client.create_collection.assert_not_called()
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_create_new_collection(self, mock_milvus):
        """Test ensure_collection creates collection if not exists."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token"
        }):
            client = ZillizClient()
            asyncio.run(client.ensure_collection("EVENT", dimension=512))
            mock_client.create_collection.assert_called_once()


class TestStoreEmbedding:
    """Test embedding storage functionality."""
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_skip_when_unavailable(self, mock_milvus):
        """Test store_embedding skips when client unavailable."""
        with patch.dict(os.environ, {}, clear=True):
            client = ZillizClient()
            asyncio.run(client.store_embedding(
                "agent1", "lane1", "EVENT", "key1", "val1", [0.1]
            ))
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_store_success(self, mock_milvus):
        """Test successful embedding storage."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token"
        }):
            client = ZillizClient()
            asyncio.run(client.store_embedding(
                agent_id="agent1",
                lane="impl",
                track_type="EVENT",
                key="test_key",
                value="test_value",
                embedding=[0.1, 0.2, 0.3],
                metadata={"foo": "bar"}
            ))
            mock_client.insert.assert_called_once()
            call_args = mock_client.insert.call_args
            assert call_args[1]["collection_name"] == "nexus_event"
            assert len(call_args[1]["data"]) == 1


class TestSimilarSearch:
    """Test similarity search functionality."""
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_return_empty_when_unavailable(self, mock_milvus):
        """Test similar_search returns empty list when unavailable."""
        with patch.dict(os.environ, {}, clear=True):
            client = ZillizClient()
            results = asyncio.run(client.similar_search([0.1, 0.2]))
            assert results == []
    
    @patch('src.nexus_os.vault.zilliz_client.MilvusClient')
    def test_search_with_track_type(self, mock_milvus):
        """Test search filtered by track type."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_hit = MagicMock()
        mock_hit.entity.get.return_value = {"agent_id": "agent1"}
        mock_hit.entity.id = "hit1"
        mock_hit.distance = 0.5
        mock_client.search.return_value = [[mock_hit]]
        mock_milvus.return_value = mock_client
        
        with patch.dict(os.environ, {
            "ZILLIZ_SERVERLESS_URI": "https://test.com",
            "ZILLIZ_SERVERLESS_TOKEN": "token"
        }):
            client = ZillizClient()
            results = asyncio.run(client.similar_search(
                query_embedding=[0.1],
                track_type="EVENT",
                top_k=3
            ))
            assert len(results) == 1
            assert results[0]["id"] == "hit1"
            mock_client.search.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
