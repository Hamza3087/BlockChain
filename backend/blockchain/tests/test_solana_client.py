"""
Unit Tests for Solana Client

Comprehensive tests for Solana blockchain client functionality including:
- Connection management
- RPC endpoint handling
- Health checking
- Error handling and recovery
- Performance monitoring
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase
from django.conf import settings

from ..clients.solana_client import SolanaClient, EndpointConfig
from ..services import get_solana_service


class TestSolanaClient(TestCase):
    """Test cases for SolanaClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_endpoints = [
            EndpointConfig(
                name="Test Devnet",
                url="https://api.devnet.solana.com",
                priority=1,
                timeout=30
            ),
            EndpointConfig(
                name="Test Mainnet",
                url="https://api.mainnet-beta.solana.com",
                priority=2,
                timeout=30
            )
        ]
    
    def test_endpoint_config_creation(self):
        """Test EndpointConfig creation and validation."""
        config = EndpointConfig(
            name="Test Endpoint",
            url="https://test.solana.com",
            priority=1,
            timeout=30
        )
        
        self.assertEqual(config.name, "Test Endpoint")
        self.assertEqual(config.url, "https://test.solana.com")
        self.assertEqual(config.priority, 1)
        self.assertEqual(config.timeout, 30)
        self.assertEqual(config.status, "unknown")
        self.assertEqual(config.response_time, 0.0)
        self.assertEqual(config.success_rate, 0.0)
    
    @pytest.mark.asyncio
    async def test_solana_client_initialization(self):
        """Test SolanaClient initialization."""
        client = SolanaClient(endpoints=self.test_endpoints)
        
        self.assertEqual(len(client.endpoints), 2)
        self.assertIsNone(client.current_endpoint)
        self.assertIsNone(client.client)
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'result': {'value': 12345}
            }
            mock_post.return_value = mock_response
            
            client = SolanaClient(endpoints=self.test_endpoints)
            await client.initialize()
            
            # Check that health check was performed
            self.assertIsNotNone(client.current_endpoint)
            self.assertEqual(client.current_endpoint.status, "healthy")
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure handling."""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock failed response
            mock_post.side_effect = Exception("Connection failed")
            
            client = SolanaClient(endpoints=self.test_endpoints)
            
            # Health check should handle failures gracefully
            await client.initialize()
            
            # Should still have endpoints, but marked as unhealthy
            self.assertEqual(len(client.endpoints), 2)
    
    @pytest.mark.asyncio
    async def test_endpoint_failover(self):
        """Test automatic endpoint failover."""
        with patch('httpx.AsyncClient.post') as mock_post:
            # First endpoint fails, second succeeds
            responses = [
                Exception("First endpoint failed"),
                Mock(status_code=200, json=lambda: {'result': {'value': 12345}})
            ]
            mock_post.side_effect = responses
            
            client = SolanaClient(endpoints=self.test_endpoints)
            await client.initialize()
            
            # Should have failed over to second endpoint
            self.assertIsNotNone(client.current_endpoint)
    
    @pytest.mark.asyncio
    async def test_get_slot(self):
        """Test get_slot method."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'result': 12345
            }
            mock_post.return_value = mock_response
            
            client = SolanaClient(endpoints=self.test_endpoints)
            await client.initialize()
            
            slot = await client.get_slot()
            self.assertEqual(slot, 12345)
    
    @pytest.mark.asyncio
    async def test_get_balance(self):
        """Test get_balance method."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'result': {'value': 1000000000}  # 1 SOL in lamports
            }
            mock_post.return_value = mock_response
            
            client = SolanaClient(endpoints=self.test_endpoints)
            await client.initialize()
            
            balance = await client.get_balance("test_address")
            self.assertEqual(balance, 1000000000)
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in RPC calls."""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock error response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'error': {
                    'code': -32602,
                    'message': 'Invalid params'
                }
            }
            mock_post.return_value = mock_response
            
            client = SolanaClient(endpoints=self.test_endpoints)
            await client.initialize()
            
            # Should handle RPC errors gracefully
            balance = await client.get_balance("invalid_address")
            self.assertIsNone(balance)
    
    def test_endpoint_sorting(self):
        """Test endpoint sorting by priority."""
        endpoints = [
            EndpointConfig("Low Priority", "https://low.com", priority=3),
            EndpointConfig("High Priority", "https://high.com", priority=1),
            EndpointConfig("Medium Priority", "https://medium.com", priority=2),
        ]
        
        client = SolanaClient(endpoints=endpoints)
        
        # Endpoints should be sorted by priority
        self.assertEqual(client.endpoints[0].priority, 1)
        self.assertEqual(client.endpoints[1].priority, 2)
        self.assertEqual(client.endpoints[2].priority, 3)
    
    @pytest.mark.asyncio
    async def test_client_close(self):
        """Test client cleanup."""
        client = SolanaClient(endpoints=self.test_endpoints)
        await client.initialize()
        
        # Should close without errors
        await client.close()
        self.assertIsNone(client.client)


class TestSolanaService(TestCase):
    """Test cases for SolanaService."""
    
    @pytest.mark.asyncio
    async def test_get_solana_service(self):
        """Test get_solana_service function."""
        service = await get_solana_service()
        
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.client)
    
    @pytest.mark.asyncio
    async def test_service_singleton(self):
        """Test that service returns same instance."""
        service1 = await get_solana_service()
        service2 = await get_solana_service()
        
        # Should return the same instance
        self.assertIs(service1, service2)
    
    @pytest.mark.asyncio
    async def test_service_health_check(self):
        """Test service health check."""
        service = await get_solana_service()
        
        # Should have a health check method
        self.assertTrue(hasattr(service, 'health_check'))
        
        # Health check should return status
        health_status = await service.health_check()
        self.assertIsInstance(health_status, dict)
        self.assertIn('status', health_status)


@pytest.mark.asyncio
class TestSolanaClientIntegration:
    """Integration tests for SolanaClient with real endpoints."""
    
    async def test_real_devnet_connection(self):
        """Test connection to real Solana devnet (if available)."""
        # Skip if not in integration test mode
        if not getattr(settings, 'RUN_INTEGRATION_TESTS', False):
            pytest.skip("Integration tests disabled")
        
        endpoints = [
            EndpointConfig(
                name="Solana Devnet",
                url="https://api.devnet.solana.com",
                priority=1
            )
        ]
        
        client = SolanaClient(endpoints=endpoints)
        
        try:
            await client.initialize()
            
            # Should be able to get current slot
            slot = await client.get_slot()
            assert isinstance(slot, int)
            assert slot > 0
            
        finally:
            await client.close()
    
    async def test_performance_monitoring(self):
        """Test performance monitoring functionality."""
        client = SolanaClient(endpoints=self.test_endpoints)
        
        # Enable performance monitoring
        client.enable_monitoring = True
        
        await client.initialize()
        
        # Performance metrics should be tracked
        stats = client.get_performance_stats()
        assert isinstance(stats, dict)
        assert 'total_requests' in stats
        
        await client.close()


# Test fixtures and factories
class SolanaClientFactory:
    """Factory for creating test SolanaClient instances."""
    
    @staticmethod
    def create_test_client(endpoint_count=2):
        """Create a test client with mock endpoints."""
        endpoints = []
        for i in range(endpoint_count):
            endpoints.append(
                EndpointConfig(
                    name=f"Test Endpoint {i+1}",
                    url=f"https://test{i+1}.solana.com",
                    priority=i+1
                )
            )
        
        return SolanaClient(endpoints=endpoints)
    
    @staticmethod
    def create_mock_response(result=None, error=None):
        """Create a mock HTTP response."""
        mock_response = Mock()
        mock_response.status_code = 200
        
        if error:
            mock_response.json.return_value = {'error': error}
        else:
            mock_response.json.return_value = {'result': result}
        
        return mock_response


# Performance benchmarks
class TestSolanaClientPerformance(TestCase):
    """Performance tests for SolanaClient."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        client = SolanaClientFactory.create_test_client()
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = SolanaClientFactory.create_mock_response(12345)
            
            await client.initialize()
            
            # Make multiple concurrent requests
            tasks = [client.get_slot() for _ in range(10)]
            results = await asyncio.gather(*tasks)
            
            # All requests should succeed
            self.assertEqual(len(results), 10)
            self.assertTrue(all(r == 12345 for r in results))
    
    @pytest.mark.asyncio
    async def test_request_timeout(self):
        """Test request timeout handling."""
        client = SolanaClientFactory.create_test_client()
        
        with patch('httpx.AsyncClient.post') as mock_post:
            # Simulate timeout
            mock_post.side_effect = asyncio.TimeoutError("Request timeout")
            
            await client.initialize()
            
            # Request should handle timeout gracefully
            result = await client.get_slot()
            self.assertIsNone(result)
