"""
Solana RPC Client with failover and retry mechanisms for ReplantWorld.

This module provides a robust Solana client that can handle multiple RPC endpoints,
automatic failover, retry logic, and comprehensive health monitoring.
"""

import asyncio
import random
import time
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum

import structlog
from solana.rpc.async_api import AsyncClient
from solana.rpc.api import Client
from solana.rpc.core import RPCException
from typing import Any, Dict
RPCResponse = Dict[str, Any]  # backward compatibility shim
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import httpx

logger = structlog.get_logger(__name__)


class RPCEndpointStatus(Enum):
    """Status of an RPC endpoint."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class RPCEndpoint:
    """Represents a Solana RPC endpoint with health metrics."""
    url: str
    name: str
    priority: int = 1  # Lower number = higher priority
    status: RPCEndpointStatus = RPCEndpointStatus.UNKNOWN
    last_check: Optional[float] = None
    response_time: Optional[float] = None
    error_count: int = 0
    success_count: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        total = self.success_count + self.error_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100


class SolanaClient:
    """
    Robust Solana RPC client with failover and retry mechanisms.
    
    Features:
    - Multiple RPC endpoint support with automatic failover
    - Exponential backoff retry logic
    - Health monitoring and endpoint status tracking
    - Connection pooling and async support
    - Comprehensive logging
    """
    
    def __init__(
        self,
        rpc_endpoints: List[Dict[str, Any]],
        max_retries: int = 3,
        retry_delay: float = 1.0,
        health_check_interval: int = 60,
        timeout: int = 30
    ):
        """
        Initialize the Solana client.
        
        Args:
            rpc_endpoints: List of RPC endpoint configurations
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff)
            health_check_interval: Seconds between health checks
            timeout: Request timeout in seconds
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.health_check_interval = health_check_interval
        self.timeout = timeout
        
        # Initialize RPC endpoints
        self.endpoints: List[RPCEndpoint] = []
        for endpoint_config in rpc_endpoints:
            endpoint = RPCEndpoint(
                url=endpoint_config['url'],
                name=endpoint_config.get('name', endpoint_config['url']),
                priority=endpoint_config.get('priority', 1)
            )
            self.endpoints.append(endpoint)
        
        # Sort endpoints by priority
        self.endpoints.sort(key=lambda x: x.priority)
        
        # Current active endpoint
        self.current_endpoint: Optional[RPCEndpoint] = None
        self.client: Optional[Union[Client, AsyncClient]] = None
        self.async_client: Optional[AsyncClient] = None
        
        # Health monitoring
        self.last_health_check = 0
        
        logger.info(
            "SolanaClient initialized",
            endpoint_count=len(self.endpoints),
            endpoints=[ep.name for ep in self.endpoints]
        )
    
    def _get_healthy_endpoints(self) -> List[RPCEndpoint]:
        """Get list of healthy endpoints sorted by priority."""
        healthy = [
            ep for ep in self.endpoints 
            if ep.status in [RPCEndpointStatus.HEALTHY, RPCEndpointStatus.UNKNOWN]
        ]
        return sorted(healthy, key=lambda x: (x.priority, -x.success_rate))
    
    def _select_endpoint(self) -> Optional[RPCEndpoint]:
        """Select the best available endpoint."""
        healthy_endpoints = self._get_healthy_endpoints()
        
        if not healthy_endpoints:
            logger.warning("No healthy endpoints available, trying degraded ones")
            degraded = [ep for ep in self.endpoints if ep.status == RPCEndpointStatus.DEGRADED]
            if degraded:
                return sorted(degraded, key=lambda x: (x.priority, -x.success_rate))[0]
            return None
        
        return healthy_endpoints[0]
    
    async def _check_endpoint_health(self, endpoint: RPCEndpoint) -> bool:
        """Check the health of a specific endpoint."""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Simple health check - get slot
                response = await client.post(
                    endpoint.url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getSlot"
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                response_time = time.time() - start_time
                endpoint.response_time = response_time
                endpoint.last_check = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        endpoint.success_count += 1
                        endpoint.status = RPCEndpointStatus.HEALTHY
                        
                        logger.debug(
                            "Endpoint health check passed",
                            endpoint=endpoint.name,
                            response_time=response_time,
                            slot=data.get("result")
                        )
                        return True
                
                endpoint.error_count += 1
                endpoint.status = RPCEndpointStatus.DEGRADED
                return False
                
        except Exception as e:
            endpoint.error_count += 1
            endpoint.status = RPCEndpointStatus.UNHEALTHY
            endpoint.last_check = time.time()
            
            logger.warning(
                "Endpoint health check failed",
                endpoint=endpoint.name,
                error=str(e),
                response_time=time.time() - start_time
            )
            return False
    
    async def check_all_endpoints_health(self) -> Dict[str, Any]:
        """Check health of all endpoints and return status summary."""
        if time.time() - self.last_health_check < self.health_check_interval:
            return self._get_health_summary()
        
        logger.info("Starting health check for all endpoints")
        
        # Check all endpoints concurrently
        tasks = [self._check_endpoint_health(ep) for ep in self.endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        self.last_health_check = time.time()
        
        # Log summary
        healthy_count = sum(1 for ep in self.endpoints if ep.status == RPCEndpointStatus.HEALTHY)
        degraded_count = sum(1 for ep in self.endpoints if ep.status == RPCEndpointStatus.DEGRADED)
        unhealthy_count = sum(1 for ep in self.endpoints if ep.status == RPCEndpointStatus.UNHEALTHY)
        
        logger.info(
            "Health check completed",
            healthy=healthy_count,
            degraded=degraded_count,
            unhealthy=unhealthy_count,
            total=len(self.endpoints)
        )
        
        return self._get_health_summary()
    
    def _get_health_summary(self) -> Dict[str, Any]:
        """Get current health summary of all endpoints."""
        return {
            "timestamp": time.time(),
            "endpoints": [
                {
                    "name": ep.name,
                    "url": ep.url,
                    "status": ep.status.value,
                    "priority": ep.priority,
                    "response_time": ep.response_time,
                    "success_rate": ep.success_rate,
                    "last_check": ep.last_check
                }
                for ep in self.endpoints
            ],
            "summary": {
                "healthy": sum(1 for ep in self.endpoints if ep.status == RPCEndpointStatus.HEALTHY),
                "degraded": sum(1 for ep in self.endpoints if ep.status == RPCEndpointStatus.DEGRADED),
                "unhealthy": sum(1 for ep in self.endpoints if ep.status == RPCEndpointStatus.UNHEALTHY),
                "unknown": sum(1 for ep in self.endpoints if ep.status == RPCEndpointStatus.UNKNOWN),
                "total": len(self.endpoints)
            }
        }

    async def _switch_endpoint(self) -> bool:
        """Switch to a different healthy endpoint."""
        new_endpoint = self._select_endpoint()

        if not new_endpoint:
            logger.error("No healthy endpoints available for failover")
            return False

        if new_endpoint == self.current_endpoint:
            logger.warning("Already using the best available endpoint")
            return False

        old_endpoint_name = self.current_endpoint.name if self.current_endpoint else "None"
        self.current_endpoint = new_endpoint

        # Close existing clients
        if self.client:
            try:
                self.client.close()
            except:
                pass

        if self.async_client:
            try:
                await self.async_client.close()
            except:
                pass

        # Create new clients
        self.client = Client(self.current_endpoint.url)
        self.async_client = AsyncClient(self.current_endpoint.url)

        logger.info(
            "Switched RPC endpoint",
            old_endpoint=old_endpoint_name,
            new_endpoint=self.current_endpoint.name,
            new_url=self.current_endpoint.url
        )

        return True

    async def connect(self) -> bool:
        """Establish connection to the best available RPC endpoint."""
        try:
            # Run health check first
            await self.check_all_endpoints_health()

            # Select and connect to best endpoint
            endpoint = self._select_endpoint()
            if not endpoint:
                logger.error("No healthy endpoints available for connection")
                return False

            self.current_endpoint = endpoint
            self.client = Client(endpoint.url)
            self.async_client = AsyncClient(endpoint.url)

            # Test the connection
            try:
                slot = await self.async_client.get_slot()
                if slot.value is not None:
                    logger.info(
                        "Successfully connected to Solana RPC",
                        endpoint=endpoint.name,
                        url=endpoint.url,
                        current_slot=slot.value
                    )
                    return True
            except Exception as e:
                logger.error(
                    "Failed to test connection",
                    endpoint=endpoint.name,
                    error=str(e)
                )
                endpoint.status = RPCEndpointStatus.UNHEALTHY
                return await self.connect()  # Try next endpoint

        except Exception as e:
            logger.error("Failed to establish connection", error=str(e))
            return False

        return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RPCException, httpx.RequestError, asyncio.TimeoutError)),
        before_sleep=before_sleep_log(logger, "warning")
    )
    async def _make_rpc_call_with_retry(self, method_name: str, *args, **kwargs):
        """Make an RPC call with retry logic and automatic failover."""
        if not self.async_client or not self.current_endpoint:
            if not await self.connect():
                raise RPCException("No healthy RPC endpoints available")

        try:
            # Get the method from the async client
            method = getattr(self.async_client, method_name)
            result = await method(*args, **kwargs)

            # Update success metrics
            self.current_endpoint.success_count += 1
            if self.current_endpoint.status == RPCEndpointStatus.DEGRADED:
                self.current_endpoint.status = RPCEndpointStatus.HEALTHY

            return result

        except Exception as e:
            # Update error metrics
            self.current_endpoint.error_count += 1

            # Check if we should mark endpoint as unhealthy
            if self.current_endpoint.error_count > 5:
                self.current_endpoint.status = RPCEndpointStatus.UNHEALTHY
                logger.warning(
                    "Marking endpoint as unhealthy due to repeated failures",
                    endpoint=self.current_endpoint.name,
                    error_count=self.current_endpoint.error_count
                )

            # Try to switch to a different endpoint
            if await self._switch_endpoint():
                logger.info("Retrying with different endpoint after failure")
                # Retry with new endpoint
                method = getattr(self.async_client, method_name)
                return await method(*args, **kwargs)

            # Re-raise the exception if no failover possible
            logger.error(
                "RPC call failed and no failover available",
                method=method_name,
                endpoint=self.current_endpoint.name if self.current_endpoint else "None",
                error=str(e)
            )
            raise

    # Public API methods with automatic retry and failover

    async def get_slot(self) -> RPCResponse:
        """Get the current slot."""
        return await self._make_rpc_call_with_retry("get_slot")

    async def get_block_height(self) -> RPCResponse:
        """Get the current block height."""
        return await self._make_rpc_call_with_retry("get_block_height")

    async def get_balance(self, pubkey: Pubkey) -> RPCResponse:
        """Get account balance."""
        return await self._make_rpc_call_with_retry("get_balance", pubkey)

    async def get_account_info(self, pubkey: Pubkey) -> RPCResponse:
        """Get account information."""
        return await self._make_rpc_call_with_retry("get_account_info", pubkey)

    async def send_transaction(self, transaction, opts=None) -> RPCResponse:
        """Send a transaction."""
        return await self._make_rpc_call_with_retry("send_transaction", transaction, opts)

    async def confirm_transaction(self, signature: str) -> RPCResponse:
        """Confirm a transaction."""
        return await self._make_rpc_call_with_retry("confirm_transaction", signature)

    async def get_transaction(self, signature: str, encoding: str = "json") -> RPCResponse:
        """Get transaction details."""
        return await self._make_rpc_call_with_retry("get_transaction", signature, encoding)

    async def get_program_accounts(self, pubkey: Pubkey, encoding: str = "base64") -> RPCResponse:
        """Get accounts owned by a program."""
        return await self._make_rpc_call_with_retry("get_program_accounts", pubkey, encoding)

    def get_sync_client(self) -> Optional[Client]:
        """Get synchronous client for blocking operations."""
        if not self.current_endpoint:
            return None
        return self.client

    async def close(self):
        """Close all client connections."""
        if self.client:
            try:
                self.client.close()
            except:
                pass

        if self.async_client:
            try:
                await self.async_client.close()
            except:
                pass

        logger.info("SolanaClient connections closed")

    def get_current_endpoint_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently active endpoint."""
        if not self.current_endpoint:
            return None

        return {
            "name": self.current_endpoint.name,
            "url": self.current_endpoint.url,
            "status": self.current_endpoint.status.value,
            "priority": self.current_endpoint.priority,
            "response_time": self.current_endpoint.response_time,
            "success_rate": self.current_endpoint.success_rate,
            "success_count": self.current_endpoint.success_count,
            "error_count": self.current_endpoint.error_count,
            "last_check": self.current_endpoint.last_check
        }
