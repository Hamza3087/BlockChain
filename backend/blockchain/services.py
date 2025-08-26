"""
Blockchain services for ReplantWorld.

This module provides high-level services for interacting with the Solana blockchain,
including connection management, health monitoring, and Metaplex Bubblegum operations.
"""

import asyncio
from typing import Optional, Dict, Any
from django.conf import settings
import structlog

from .clients.solana_client import SolanaClient
from .config import get_solana_config

logger = structlog.get_logger(__name__)


class SolanaService:
    """
    High-level service for Solana blockchain operations.
    
    This service manages the SolanaClient instance and provides
    convenient methods for blockchain operations.
    """
    
    _instance: Optional['SolanaService'] = None
    _client: Optional[SolanaClient] = None
    
    def __new__(cls) -> 'SolanaService':
        """Singleton pattern to ensure only one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the Solana service."""
        if not hasattr(self, '_initialized'):
            self.config = get_solana_config()
            self._initialized = True
            logger.info(
                "SolanaService initialized",
                network=self.config['network'],
                endpoint_count=len(self.config['rpc_endpoints'])
            )
    
    @property
    def client(self) -> Optional[SolanaClient]:
        """Get the SolanaClient instance."""
        return self._client
    
    async def initialize(self) -> bool:
        """Initialize the Solana client and establish connection."""
        try:
            if self._client is None:
                self._client = SolanaClient(
                    rpc_endpoints=self.config['rpc_endpoints'],
                    max_retries=self.config['max_retries'],
                    retry_delay=self.config['retry_delay'],
                    health_check_interval=self.config['health_check_interval'],
                    timeout=self.config['timeout']
                )
            
            # Establish connection
            connected = await self._client.connect()
            if connected:
                logger.info("SolanaService successfully initialized and connected")
                return True
            else:
                logger.error("Failed to establish connection to Solana RPC")
                return False
                
        except Exception as e:
            logger.error("Failed to initialize SolanaService", error=str(e))
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of Solana connections."""
        if not self._client:
            return {
                "status": "not_initialized",
                "message": "SolanaService not initialized"
            }
        
        try:
            # Get endpoint health status
            health_summary = await self._client.check_all_endpoints_health()
            
            # Get current endpoint info
            current_endpoint = self._client.get_current_endpoint_info()
            
            # Test basic connectivity
            try:
                slot_response = await self._client.get_slot()
                current_slot = slot_response.value if slot_response.value is not None else "unknown"
                connectivity_status = "connected"
            except Exception as e:
                current_slot = "unknown"
                connectivity_status = "disconnected"
                logger.warning("Connectivity test failed", error=str(e))
            
            return {
                "status": "initialized",
                "connectivity": connectivity_status,
                "current_slot": current_slot,
                "current_endpoint": current_endpoint,
                "network": self.config['network'],
                "health_summary": health_summary,
                "config": {
                    "max_retries": self.config['max_retries'],
                    "retry_delay": self.config['retry_delay'],
                    "health_check_interval": self.config['health_check_interval'],
                    "timeout": self.config['timeout']
                }
            }
            
        except Exception as e:
            logger.error("Failed to get health status", error=str(e))
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}"
            }
    
    async def get_network_info(self) -> Dict[str, Any]:
        """Get current network information."""
        if not self._client:
            raise RuntimeError("SolanaService not initialized")
        
        try:
            # Get basic network info
            slot_response = await self._client.get_slot()
            block_height_response = await self._client.get_block_height()
            
            return {
                "network": self.config['network'],
                "current_slot": slot_response.value,
                "block_height": block_height_response.value,
                "bubblegum_program_id": self.config['bubblegum_program_id'],
                "endpoint": self._client.get_current_endpoint_info()
            }
            
        except Exception as e:
            logger.error("Failed to get network info", error=str(e))
            raise
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection to Solana RPC."""
        if not self._client:
            return {"status": "error", "message": "Client not initialized"}
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Test basic RPC calls
            slot_response = await self._client.get_slot()
            block_height_response = await self._client.get_block_height()
            
            end_time = asyncio.get_event_loop().time()
            response_time = end_time - start_time
            
            return {
                "status": "success",
                "response_time": response_time,
                "current_slot": slot_response.value,
                "block_height": block_height_response.value,
                "endpoint": self._client.get_current_endpoint_info()
            }
            
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            return {
                "status": "error",
                "message": str(e),
                "endpoint": self._client.get_current_endpoint_info() if self._client else None
            }
    
    async def close(self):
        """Close the Solana service and cleanup resources."""
        if self._client:
            await self._client.close()
            self._client = None
        
        logger.info("SolanaService closed")


# Global service instance
solana_service = SolanaService()


async def get_solana_service() -> SolanaService:
    """Get the global SolanaService instance, initializing if necessary."""
    if not solana_service.client:
        await solana_service.initialize()
    return solana_service
