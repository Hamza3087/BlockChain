"""
Tests for blockchain functionality including SolanaClient and services.
"""

import asyncio
import unittest
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

from .clients.solana_client import SolanaClient, RPCEndpoint, RPCEndpointStatus
from .services import SolanaService, get_solana_service
from .config import get_solana_config
from .merkle_tree import MerkleTreeManager, MerkleTreeConfig, TreeStatus
from .cnft_minting import CompressedNFTMinter, NFTMetadata, MintRequest, NFTMintStatus


class SolanaClientTests(TestCase):
    """Test cases for SolanaClient functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_endpoints = [
            {
                'name': 'Test RPC 1',
                'url': 'https://api.devnet.solana.com',
                'priority': 1
            },
            {
                'name': 'Test RPC 2',
                'url': 'https://devnet.helius-rpc.com',
                'priority': 2
            }
        ]

        self.client = SolanaClient(
            rpc_endpoints=self.test_endpoints,
            max_retries=2,
            retry_delay=0.1,
            health_check_interval=10,
            timeout=5
        )

    def test_client_initialization(self):
        """Test SolanaClient initialization."""
        self.assertEqual(len(self.client.endpoints), 2)
        self.assertEqual(self.client.max_retries, 2)
        self.assertEqual(self.client.retry_delay, 0.1)

        # Check endpoints are sorted by priority
        self.assertEqual(self.client.endpoints[0].priority, 1)
        self.assertEqual(self.client.endpoints[1].priority, 2)

    def test_endpoint_selection(self):
        """Test endpoint selection logic."""
        # Initially all endpoints should be unknown status
        selected = self.client._select_endpoint()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.priority, 1)  # Should select highest priority

        # Mark first endpoint as unhealthy
        self.client.endpoints[0].status = RPCEndpointStatus.UNHEALTHY
        selected = self.client._select_endpoint()
        self.assertEqual(selected.priority, 2)  # Should select second endpoint

    def test_healthy_endpoints_filtering(self):
        """Test filtering of healthy endpoints."""
        # Initially all should be considered healthy (unknown status)
        healthy = self.client._get_healthy_endpoints()
        self.assertEqual(len(healthy), 2)

        # Mark one as unhealthy
        self.client.endpoints[0].status = RPCEndpointStatus.UNHEALTHY
        healthy = self.client._get_healthy_endpoints()
        self.assertEqual(len(healthy), 1)
        self.assertEqual(healthy[0].priority, 2)

    def test_health_summary(self):
        """Test health summary generation."""
        summary = self.client._get_health_summary()

        self.assertIn('timestamp', summary)
        self.assertIn('endpoints', summary)
        self.assertIn('summary', summary)

        self.assertEqual(len(summary['endpoints']), 2)
        self.assertEqual(summary['summary']['total'], 2)
        self.assertEqual(summary['summary']['unknown'], 2)


class SolanaClientAsyncTests(unittest.IsolatedAsyncioTestCase):
    """Async test cases for SolanaClient."""

    async def asyncSetUp(self):
        """Set up async test fixtures."""
        self.test_endpoints = [
            {
                'name': 'Test RPC 1',
                'url': 'https://api.devnet.solana.com',
                'priority': 1
            }
        ]

        self.client = SolanaClient(
            rpc_endpoints=self.test_endpoints,
            max_retries=1,
            retry_delay=0.1,
            health_check_interval=10,
            timeout=5
        )

    @patch('httpx.AsyncClient')
    async def test_endpoint_health_check(self, mock_client):
        """Test endpoint health checking."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 12345}

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        endpoint = self.client.endpoints[0]
        result = await self.client._check_endpoint_health(endpoint)

        self.assertTrue(result)
        self.assertEqual(endpoint.status, RPCEndpointStatus.HEALTHY)
        self.assertIsNotNone(endpoint.response_time)
        self.assertEqual(endpoint.success_count, 1)

    @patch('httpx.AsyncClient')
    async def test_endpoint_health_check_failure(self, mock_client):
        """Test endpoint health check failure."""
        # Mock failed response
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = Exception("Connection failed")
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        endpoint = self.client.endpoints[0]
        result = await self.client._check_endpoint_health(endpoint)

        self.assertFalse(result)
        self.assertEqual(endpoint.status, RPCEndpointStatus.UNHEALTHY)
        self.assertEqual(endpoint.error_count, 1)

    async def test_health_check_all_endpoints(self):
        """Test checking health of all endpoints."""
        with patch.object(self.client, '_check_endpoint_health', return_value=True):
            summary = await self.client.check_all_endpoints_health()

            self.assertIn('timestamp', summary)
            self.assertIn('endpoints', summary)
            self.assertIn('summary', summary)


class SolanaServiceTests(TestCase):
    """Test cases for SolanaService."""

    def test_service_singleton(self):
        """Test that SolanaService is a singleton."""
        service1 = SolanaService()
        service2 = SolanaService()
        self.assertIs(service1, service2)

    def test_service_initialization(self):
        """Test service initialization."""
        service = SolanaService()
        self.assertIsNotNone(service.config)
        self.assertIn('network', service.config)
        self.assertIn('rpc_endpoints', service.config)


class SolanaServiceAsyncTests(unittest.IsolatedAsyncioTestCase):
    """Async test cases for SolanaService."""

    async def test_get_solana_service(self):
        """Test getting solana service instance."""
        with patch('blockchain.services.SolanaService.initialize', return_value=True):
            service = await get_solana_service()
            self.assertIsInstance(service, SolanaService)


class BlockchainAPITests(APITestCase):
    """Test cases for blockchain API endpoints."""

    def test_solana_health_endpoint(self):
        """Test Solana health check endpoint."""
        with patch('blockchain.views.get_solana_service') as mock_service:
            # Mock successful health check
            mock_service_instance = AsyncMock()
            mock_service_instance.get_health_status.return_value = {
                'status': 'initialized',
                'connectivity': 'connected',
                'current_slot': 12345
            }
            mock_service.return_value = mock_service_instance

            response = self.client.get('/api/blockchain/health/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_solana_network_info_endpoint(self):
        """Test Solana network info endpoint."""
        with patch('blockchain.views.get_solana_service') as mock_service:
            # Mock network info
            mock_service_instance = AsyncMock()
            mock_service_instance.get_network_info.return_value = {
                'network': 'devnet',
                'current_slot': 12345,
                'block_height': 12340,
                'bubblegum_program_id': 'BGUMAp9Gq7iTEuizy4pqaxsTyUCBK68MDfK752saRPUY'
            }
            mock_service.return_value = mock_service_instance

            response = self.client.get('/api/blockchain/network-info/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_solana_test_connection_endpoint(self):
        """Test Solana connection test endpoint."""
        with patch('blockchain.views.get_solana_service') as mock_service:
            # Mock connection test
            mock_service_instance = AsyncMock()
            mock_service_instance.test_connection.return_value = {
                'status': 'success',
                'response_time': 0.123,
                'current_slot': 12345
            }
            mock_service.return_value = mock_service_instance

            response = self.client.post('/api/blockchain/test-connection/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class ConfigTests(TestCase):
    """Test cases for blockchain configuration."""

    def test_get_solana_config(self):
        """Test getting Solana configuration."""
        config = get_solana_config()

        self.assertIn('network', config)
        self.assertIn('rpc_endpoints', config)
        self.assertIn('bubblegum_program_id', config)
        self.assertIn('max_retries', config)
        self.assertIn('retry_delay', config)
        self.assertIn('health_check_interval', config)
        self.assertIn('timeout', config)
        self.assertIn('keypair_path', config)

        # Check default values
        self.assertEqual(config['network'], 'devnet')
        self.assertEqual(config['max_retries'], 3)
        self.assertEqual(config['retry_delay'], 1.0)

    @patch.dict('os.environ', {'SOLANA_NETWORK': 'mainnet', 'SOLANA_MAX_RETRIES': '5'})
    def test_config_environment_override(self):
        """Test configuration override from environment variables."""
        config = get_solana_config()

        self.assertEqual(config['network'], 'mainnet')
        self.assertEqual(config['max_retries'], 5)


class MerkleTreeTests(TestCase):
    """Test cases for Merkle tree functionality."""

    def test_tree_config_creation(self):
        """Test Merkle tree configuration creation."""
        config = MerkleTreeConfig(
            max_depth=10,
            max_buffer_size=32,
            canopy_depth=0,
            public=True
        )

        self.assertEqual(config.max_depth, 10)
        self.assertEqual(config.max_buffer_size, 32)
        self.assertEqual(config.canopy_depth, 0)
        self.assertTrue(config.public)
        self.assertEqual(config.max_capacity, 1024)  # 2^10

    def test_tree_config_validation(self):
        """Test tree configuration validation."""
        # Test invalid max_depth
        with self.assertRaises(ValueError):
            MerkleTreeConfig(max_depth=50)

        # Test invalid max_buffer_size
        with self.assertRaises(ValueError):
            MerkleTreeConfig(max_buffer_size=5000)

        # Test invalid canopy_depth
        with self.assertRaises(ValueError):
            MerkleTreeConfig(max_depth=10, canopy_depth=15)

    def test_estimated_cost_calculation(self):
        """Test estimated cost calculation."""
        config = MerkleTreeConfig(max_depth=14, max_buffer_size=64, canopy_depth=0)
        cost = config.estimated_cost_lamports

        self.assertGreater(cost, 0)
        self.assertIsInstance(cost, int)


class NFTMetadataTests(TestCase):
    """Test cases for NFT metadata functionality."""

    def test_basic_metadata_creation(self):
        """Test basic NFT metadata creation."""
        metadata = NFTMetadata(
            name="Test NFT",
            symbol="TEST",
            description="A test NFT",
            image="https://example.com/test.jpg"
        )

        self.assertEqual(metadata.name, "Test NFT")
        self.assertEqual(metadata.symbol, "TEST")
        self.assertEqual(metadata.description, "A test NFT")
        self.assertEqual(metadata.image, "https://example.com/test.jpg")
        self.assertEqual(len(metadata.attributes), 0)

    def test_metadata_validation(self):
        """Test metadata validation."""
        # Test empty name
        with self.assertRaises(ValueError):
            NFTMetadata(name="", symbol="TEST", description="Test", image="https://example.com/test.jpg")

        # Test empty symbol
        with self.assertRaises(ValueError):
            NFTMetadata(name="Test", symbol="", description="Test", image="https://example.com/test.jpg")

        # Test empty description
        with self.assertRaises(ValueError):
            NFTMetadata(name="Test", symbol="TEST", description="", image="https://example.com/test.jpg")

        # Test empty image
        with self.assertRaises(ValueError):
            NFTMetadata(name="Test", symbol="TEST", description="Test", image="")

    def test_carbon_credit_metadata_creation(self):
        """Test carbon credit specific metadata creation."""
        metadata = NFTMetadata.create_carbon_credit_metadata(
            tree_id="CC-001",
            tree_species="Oak",
            location="California, USA",
            planting_date="2024-01-15",
            carbon_offset_tons=2.5,
            image_url="https://example.com/oak.jpg"
        )

        self.assertEqual(metadata.name, "Carbon Credit Tree #CC-001")
        self.assertEqual(metadata.symbol, "CCT")
        self.assertIn("Oak", metadata.description)
        self.assertIn("California, USA", metadata.description)
        self.assertEqual(len(metadata.attributes), 7)

        # Check specific attributes
        tree_id_attr = next(attr for attr in metadata.attributes if attr['trait_type'] == 'Tree ID')
        self.assertEqual(tree_id_attr['value'], "CC-001")

        carbon_attr = next(attr for attr in metadata.attributes if attr['trait_type'] == 'Carbon Offset (tons)')
        self.assertEqual(carbon_attr['value'], 2.5)

    def test_metadata_serialization(self):
        """Test metadata JSON serialization."""
        metadata = NFTMetadata(
            name="Test NFT",
            symbol="TEST",
            description="A test NFT",
            image="https://example.com/test.jpg"
        )

        # Test to_dict
        data = metadata.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data['name'], "Test NFT")

        # Test to_json
        json_str = metadata.to_json()
        self.assertIsInstance(json_str, str)
        self.assertIn("Test NFT", json_str)


class MintRequestTests(TestCase):
    """Test cases for mint request functionality."""

    def test_mint_request_creation(self):
        """Test mint request creation."""
        metadata = NFTMetadata(
            name="Test NFT",
            symbol="TEST",
            description="A test NFT",
            image="https://example.com/test.jpg"
        )

        request = MintRequest(
            tree_address="11111111111111111111111111111111",
            recipient="22222222222222222222222222222222",
            metadata=metadata
        )

        self.assertEqual(request.tree_address, "11111111111111111111111111111111")
        self.assertEqual(request.recipient, "22222222222222222222222222222222")
        self.assertEqual(request.metadata, metadata)
        self.assertIsNotNone(request.mint_id)

    def test_mint_request_auto_id(self):
        """Test automatic mint ID generation."""
        metadata = NFTMetadata(
            name="Test NFT",
            symbol="TEST",
            description="A test NFT",
            image="https://example.com/test.jpg"
        )

        request1 = MintRequest(
            tree_address="11111111111111111111111111111111",
            recipient="22222222222222222222222222222222",
            metadata=metadata
        )

        request2 = MintRequest(
            tree_address="11111111111111111111111111111111",
            recipient="22222222222222222222222222222222",
            metadata=metadata
        )

        # Should have different mint IDs
        self.assertNotEqual(request1.mint_id, request2.mint_id)
