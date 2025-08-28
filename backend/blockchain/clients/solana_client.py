"""
Solana RPC Client with failover and retry mechanisms for ReplantWorld.

This module provides a robust Solana client that can handle multiple RPC endpoints,
automatic failover, retry logic, and comprehensive health monitoring.
"""

import asyncio
import random
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

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

        # Initialize logger
        self.logger = logger.bind(component="SolanaClient")

        self.logger.info(
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

    # Merkle Tree specific methods for compressed NFTs

    async def get_account_info_with_commitment(self, pubkey: Pubkey, commitment: str = "confirmed") -> RPCResponse:
        """Get account info with specific commitment level."""
        return await self._make_rpc_call_with_retry("get_account_info", pubkey, {"commitment": commitment})

    async def get_multiple_accounts(self, pubkeys: List[Pubkey], encoding: str = "base64") -> RPCResponse:
        """Get multiple account information in a single call."""
        return await self._make_rpc_call_with_retry("get_multiple_accounts", pubkeys, {"encoding": encoding})

    async def simulate_transaction(self, transaction, commitment: str = "confirmed") -> RPCResponse:
        """Simulate a transaction before sending."""
        return await self._make_rpc_call_with_retry("simulate_transaction", transaction, {"commitment": commitment})

    async def get_recent_blockhash(self, commitment: str = "confirmed") -> RPCResponse:
        """Get recent blockhash for transaction building."""
        return await self._make_rpc_call_with_retry("get_recent_blockhash", {"commitment": commitment})

    async def get_minimum_balance_for_rent_exemption(self, data_length: int) -> RPCResponse:
        """Get minimum balance required for rent exemption."""
        return await self._make_rpc_call_with_retry("get_minimum_balance_for_rent_exemption", data_length)

    async def send_transaction_with_opts(self, transaction, opts: Dict[str, Any]) -> RPCResponse:
        """Send transaction with custom options."""
        return await self._make_rpc_call_with_retry("send_transaction", transaction, opts)

    async def get_signature_statuses(self, signatures: List[str]) -> RPCResponse:
        """Get status of multiple transaction signatures."""
        return await self._make_rpc_call_with_retry("get_signature_statuses", signatures)

    async def mint_compressed_nft(self, metadata: Dict[str, Any], recipient: str = None) -> Dict[str, Any]:
        """
        Mint a real compressed NFT on Solana devnet with actual on-chain transactions.

        Args:
            metadata: NFT metadata
            recipient: Recipient address (optional, uses funded account if not provided)

        Returns:
            Real minting result with actual transaction signature and addresses
        """
        try:
            # Import the real on-chain client
            from .real_onchain_client import RealOnChainClient

            # Use UMI/Metaplex JS to create tree and mint reliably
            import subprocess, json, os
            env = os.environ.copy()
            env.setdefault('SOLANA_KEYPAIR', '/home/hamza/my_devnet_wallet.json')
            env.setdefault('SOLANA_RPC_URL', 'https://api.devnet.solana.com')

            # 1) Choose tree: reuse persistent tree if provided, else create one (finalized)
            tree_address = env.get('SOLANA_TREE_ADDRESS')
            if not tree_address:
                create_proc = subprocess.run(
                    ["node", "scripts/create_tree_onchain.js"],
                    cwd=str(Path(__file__).resolve().parents[2]),
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                try:
                    create_out = json.loads(create_proc.stdout.strip().splitlines()[-1])
                except Exception:
                    raise Exception(f"Tree creation failed: {create_proc.stdout}\n{create_proc.stderr}")
                if create_out.get('status') != 'success':
                    raise Exception(f"Tree creation error: {create_out}")
                tree_address = create_out['tree_address']

            # 2) Mint on that (finalized) tree
            env['SOLANA_TREE_ADDRESS'] = tree_address
            env['MINT_METADATA_JSON'] = json.dumps(metadata)
            mint_proc = subprocess.run(
                ["node", "scripts/mint_cnft_onchain.js"],
                cwd=str(Path(__file__).resolve().parents[2]),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            try:
                mint_out = json.loads(mint_proc.stdout.strip().splitlines()[-1])
            except Exception:
                raise Exception(f"Mint failed: {mint_proc.stdout}\n{mint_proc.stderr}")
            if mint_out.get('status') != 'success':
                raise Exception(f"Mint error: {mint_out}")

            self.logger.info(
                "Real compressed NFT minted on-chain",
                tree_address=tree_address,
                tx_signature=mint_out["transaction_signature"],
            )

            asset_id = mint_out.get("asset_id")
            leaf_index = mint_out.get("leaf_index")

            return {
                'status': 'success',
                'mint_address': asset_id or None,  # For cNFTs, use asset_id as mint identifier
                'asset_id': asset_id,
                'leaf_index': leaf_index,
                'tree_address': tree_address,
                'transaction_signature': mint_out["transaction_signature"],
                'recipient': recipient or env['SOLANA_KEYPAIR'],
                'metadata': metadata,
                'metadata_uri': mint_out.get("metadata_uri"),
                'timestamp': datetime.now().isoformat(),
                'network': 'devnet',
                'type': 'real_onchain_compressed_nft',
                'program_id': 'BGUMAp9Gq7iTEuizy4pqaxsTyUCBK68MDfK752saRPUY',
                'payer': None,
                'is_real_onchain': True,
                'verification_url': f"https://explorer.solana.com/tx/{mint_out['transaction_signature']}?cluster=devnet"
            }

        except Exception as e:
            self.logger.error(
                "Failed to mint real compressed NFT on-chain",
                error=str(e),
                metadata_name=metadata.get('name', 'unknown')
            )

            # Return error - no fallback to simulation as per requirements
            return {
                'status': 'error',
                'error': str(e),
                'metadata': metadata,
                'timestamp': datetime.now().isoformat(),
                'network': 'devnet',
                'type': 'failed_real_onchain_mint'
            }



    async def _mint_testnet_simulation(self, metadata: Dict[str, Any], recipient: str = None) -> Dict[str, Any]:
        """
        Create a realistic testnet simulation with proper Solana address formats.
        """
        import base58
        import secrets
        from datetime import datetime

        # Generate realistic Solana addresses (44 characters, base58 encoded)
        mint_keypair_bytes = secrets.token_bytes(32)
        tree_keypair_bytes = secrets.token_bytes(32)

        mint_address = base58.b58encode(mint_keypair_bytes).decode('utf-8')
        tree_address = base58.b58encode(tree_keypair_bytes).decode('utf-8')

        # Generate realistic transaction signature (88 characters, base58)
        tx_bytes = secrets.token_bytes(64)
        tx_signature = base58.b58encode(tx_bytes).decode('utf-8')

        # Upload metadata to storage
        metadata_uri = await self._upload_metadata_to_storage(metadata)

        self.logger.info(
            "Testnet compressed NFT simulation created",
            mint_address=mint_address,
            tree_address=tree_address,
            tx_signature=tx_signature
        )

        return {
            'status': 'success',
            'mint_address': mint_address,
            'tree_address': tree_address,
            'transaction_signature': tx_signature,
            'recipient': recipient or mint_address,
            'metadata': metadata,
            'metadata_uri': metadata_uri,
            'timestamp': datetime.now().isoformat(),
            'network': 'devnet',
            'type': 'compressed_nft_simulation'
        }

    async def _upload_metadata_to_storage(self, metadata: Dict[str, Any]) -> str:
        """
        Upload metadata to decentralized storage (IPFS/Arweave).
        For now, simulate with a realistic URI.
        """
        import hashlib
        import json

        # Create a deterministic hash for the metadata
        metadata_str = json.dumps(metadata, sort_keys=True)
        metadata_hash = hashlib.sha256(metadata_str.encode()).hexdigest()

        # Return a realistic IPFS URI
        return f"https://ipfs.io/ipfs/Qm{metadata_hash[:44]}"

    async def _create_compressed_nft_transaction(self, mint_address: str, tree_address: str,
                                               recipient: str, metadata_uri: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a compressed NFT transaction using Bubblegum program.
        """
        # This would contain the actual Solana transaction creation logic
        # For now, return transaction data structure
        return {
            "mint_address": mint_address,
            "tree_address": tree_address,
            "recipient": recipient,
            "metadata_uri": metadata_uri,
            "program_id": "BGUMAp9Gq7iTEuizy4pqaxsTyUCBK68MDfK752saRPUY",  # Bubblegum program
            "instructions": []
        }

    async def _send_compressed_nft_transaction(self, transaction_data: Dict[str, Any]) -> str:
        """
        Send the compressed NFT transaction to Solana.
        """
        # This would send the actual transaction
        # For now, simulate a transaction signature
        import base58
        import secrets

        tx_bytes = secrets.token_bytes(64)
        return base58.b58encode(tx_bytes).decode('utf-8')

    async def _confirm_transaction(self, tx_signature: str, max_retries: int = 30) -> bool:
        """
        Confirm a transaction on Solana.
        """
        for attempt in range(max_retries):
            try:
                # Check transaction status
                response = await self._make_rpc_request(
                    "getSignatureStatuses",
                    [[tx_signature], {"searchTransactionHistory": True}]
                )

                if response and "result" in response:
                    statuses = response["result"]["value"]
                    if statuses and statuses[0]:
                        status = statuses[0]
                        if status.get("confirmationStatus") in ["confirmed", "finalized"]:
                            return True
                        elif status.get("err"):
                            raise Exception(f"Transaction failed: {status['err']}")

                # Wait before next attempt
                await asyncio.sleep(2)

            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(2)

        raise Exception("Transaction confirmation timeout")

    async def get_confirmed_transaction(self, signature: str, encoding: str = "json") -> RPCResponse:
        """Get confirmed transaction details."""
        return await self._make_rpc_call_with_retry("get_confirmed_transaction", signature, encoding)

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
