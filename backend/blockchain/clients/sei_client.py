"""
Sei Blockchain Client for CW721 NFT Contract Interactions

This module provides a robust client for interacting with Sei blockchain
CW721 smart contracts to fetch NFT data for migration to Solana.
"""

import asyncio
import base64
import json
import time
from typing import List, Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass
from enum import Enum
import aiohttp
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)


class SeiNetworkError(Exception):
    """Exception raised for Sei network-related errors."""
    pass


class SeiContractError(Exception):
    """Exception raised for Sei contract-related errors."""
    pass


@dataclass
class SeiNFTInfo:
    """Data structure for Sei NFT information from CW721 contract."""
    contract_address: str
    token_id: str
    owner: str
    name: str
    description: str
    image: str
    external_url: str = ""
    attributes: List[Dict[str, Any]] = None
    metadata_uri: str = ""
    raw_metadata: Dict[str, Any] = None


@dataclass
class SeiContractInfo:
    """Information about a Sei CW721 contract."""
    address: str
    name: str
    symbol: str
    total_supply: int
    minter: str


class SeiClient:
    """
    Client for interacting with Sei blockchain CW721 contracts.
    
    Features:
    - CW721 contract queries (token info, metadata, ownership)
    - Batch NFT data retrieval
    - Automatic retry logic with exponential backoff
    - Rate limiting and connection pooling
    - Comprehensive error handling and logging
    """
    
    def __init__(
        self,
        rpc_url: str = None,
        chain_id: str = None,
        max_retries: int = None,
        retry_delay: float = None,
        timeout: int = None,
        batch_size: int = None
    ):
        """
        Initialize Sei client.
        
        Args:
            rpc_url: Sei RPC endpoint URL
            chain_id: Sei chain ID
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            timeout: Request timeout in seconds
            batch_size: Batch size for bulk operations
        """
        self.rpc_url = rpc_url or settings.SEI_RPC_URL
        self.chain_id = chain_id or settings.SEI_CHAIN_ID
        self.max_retries = max_retries or settings.SEI_MAX_RETRIES
        self.retry_delay = retry_delay or settings.SEI_RETRY_DELAY
        self.timeout = timeout or settings.SEI_TIMEOUT
        self.batch_size = batch_size or settings.SEI_BATCH_SIZE
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger.bind(component="SeiClient")
        
        # Request statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retry_count': 0,
            'start_time': time.time()
        }
        
        self.logger.info(
            "SeiClient initialized",
            rpc_url=self.rpc_url,
            chain_id=self.chain_id,
            batch_size=self.batch_size
        )
    
    async def initialize(self) -> bool:
        """Initialize the HTTP session and test connectivity."""
        try:
            connector = aiohttp.TCPConnector(
                limit=100,  # Connection pool limit
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'ReplantWorld-SeiClient/1.0'
                }
            )
            
            # Test connectivity
            await self._test_connectivity()
            
            self.logger.info("SeiClient successfully initialized and connected")
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize SeiClient", error=str(e))
            if self.session:
                await self.session.close()
                self.session = None
            return False
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
            self.logger.info("SeiClient session closed")
    
    async def _test_connectivity(self):
        """Test connectivity to Sei RPC endpoint."""
        try:
            # Query chain info to test connectivity
            url = f"{self.rpc_url}/cosmos/base/tendermint/v1beta1/node_info"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    node_info = data.get('default_node_info', {})
                    network = node_info.get('network', 'unknown')
                    
                    self.logger.info(
                        "Sei connectivity test successful",
                        network=network,
                        status_code=response.status
                    )
                else:
                    raise SeiNetworkError(f"Connectivity test failed: HTTP {response.status}")
                    
        except Exception as e:
            raise SeiNetworkError(f"Failed to connect to Sei RPC: {str(e)}")
    
    async def _make_request(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        if not self.session:
            raise SeiNetworkError("SeiClient not initialized. Call initialize() first.")
        
        self.stats['total_requests'] += 1
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.stats['successful_requests'] += 1
                        return data
                    elif response.status == 429:  # Rate limited
                        if attempt < self.max_retries:
                            wait_time = self.retry_delay * (2 ** attempt)
                            self.logger.warning(
                                "Rate limited, retrying",
                                attempt=attempt + 1,
                                wait_time=wait_time
                            )
                            await asyncio.sleep(wait_time)
                            continue
                    else:
                        error_text = await response.text()
                        raise SeiNetworkError(f"HTTP {response.status}: {error_text}")
                        
            except asyncio.TimeoutError as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    self.stats['retry_count'] += 1
                    self.logger.warning(
                        "Request timeout, retrying",
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        url=url
                    )
                    await asyncio.sleep(wait_time)
                    continue
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    self.stats['retry_count'] += 1
                    self.logger.warning(
                        "Request failed, retrying",
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    await asyncio.sleep(wait_time)
                    continue
        
        # All retries exhausted
        self.stats['failed_requests'] += 1
        raise SeiNetworkError(f"Request failed after {self.max_retries + 1} attempts: {str(last_exception)}")
    
    async def get_contract_info(self, contract_address: str) -> SeiContractInfo:
        """Get information about a CW721 contract."""
        try:
            # Query contract info
            query = {"contract_info": {}}
            query_b64 = base64.b64encode(json.dumps(query).encode()).decode()
            
            url = f"{self.rpc_url}/cosmwasm/wasm/v1/contract/{contract_address}/smart/{query_b64}"
            
            response = await self._make_request(url)
            data = response.get('data', {})
            
            return SeiContractInfo(
                address=contract_address,
                name=data.get('name', ''),
                symbol=data.get('symbol', ''),
                total_supply=0,  # Will be queried separately if needed
                minter=data.get('minter', '')
            )
            
        except Exception as e:
            raise SeiContractError(f"Failed to get contract info for {contract_address}: {str(e)}")
    
    async def get_nft_info(self, contract_address: str, token_id: str) -> SeiNFTInfo:
        """Get NFT information from CW721 contract."""
        try:
            # Query NFT info
            query = {"nft_info": {"token_id": token_id}}
            query_b64 = base64.b64encode(json.dumps(query).encode()).decode()
            
            url = f"{self.rpc_url}/cosmwasm/wasm/v1/contract/{contract_address}/smart/{query_b64}"
            
            response = await self._make_request(url)
            nft_data = response.get('data', {})
            
            # Query owner info
            owner_query = {"owner_of": {"token_id": token_id}}
            owner_query_b64 = base64.b64encode(json.dumps(owner_query).encode()).decode()
            
            owner_url = f"{self.rpc_url}/cosmwasm/wasm/v1/contract/{contract_address}/smart/{owner_query_b64}"
            owner_response = await self._make_request(owner_url)
            owner_data = owner_response.get('data', {})
            
            # Extract metadata
            extension = nft_data.get('extension', {})
            
            return SeiNFTInfo(
                contract_address=contract_address,
                token_id=token_id,
                owner=owner_data.get('owner', ''),
                name=extension.get('name', ''),
                description=extension.get('description', ''),
                image=extension.get('image', ''),
                external_url=extension.get('external_url', ''),
                attributes=extension.get('attributes', []),
                metadata_uri=nft_data.get('token_uri', ''),
                raw_metadata=nft_data
            )
            
        except Exception as e:
            raise SeiContractError(f"Failed to get NFT info for {contract_address}:{token_id}: {str(e)}")

    async def get_all_tokens(self, contract_address: str, start_after: str = None, limit: int = None) -> List[str]:
        """Get all token IDs from a CW721 contract."""
        try:
            query = {"all_tokens": {}}
            if start_after:
                query["all_tokens"]["start_after"] = start_after
            if limit:
                query["all_tokens"]["limit"] = limit

            query_b64 = base64.b64encode(json.dumps(query).encode()).decode()
            url = f"{self.rpc_url}/cosmwasm/wasm/v1/contract/{contract_address}/smart/{query_b64}"

            response = await self._make_request(url)
            data = response.get('data', {})

            return data.get('tokens', [])

        except Exception as e:
            raise SeiContractError(f"Failed to get all tokens for {contract_address}: {str(e)}")

    async def get_tokens_by_owner(self, contract_address: str, owner: str, start_after: str = None, limit: int = None) -> List[str]:
        """Get token IDs owned by a specific address."""
        try:
            query = {"tokens": {"owner": owner}}
            if start_after:
                query["tokens"]["start_after"] = start_after
            if limit:
                query["tokens"]["limit"] = limit

            query_b64 = base64.b64encode(json.dumps(query).encode()).decode()
            url = f"{self.rpc_url}/cosmwasm/wasm/v1/contract/{contract_address}/smart/{query_b64}"

            response = await self._make_request(url)
            data = response.get('data', {})

            return data.get('tokens', [])

        except Exception as e:
            raise SeiContractError(f"Failed to get tokens by owner for {contract_address}: {str(e)}")

    async def get_nft_batch(self, contract_address: str, token_ids: List[str]) -> List[SeiNFTInfo]:
        """Get multiple NFTs in batch with rate limiting."""
        results = []

        # Process in batches to avoid overwhelming the RPC
        for i in range(0, len(token_ids), self.batch_size):
            batch = token_ids[i:i + self.batch_size]

            # Create tasks for concurrent requests
            tasks = []
            for token_id in batch:
                task = self.get_nft_info(contract_address, token_id)
                tasks.append(task)

            # Execute batch with some delay between batches
            try:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in batch_results:
                    if isinstance(result, Exception):
                        self.logger.error(
                            "Failed to fetch NFT in batch",
                            error=str(result),
                            contract=contract_address
                        )
                    else:
                        results.append(result)

                # Small delay between batches to be respectful to the RPC
                if i + self.batch_size < len(token_ids):
                    await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(
                    "Batch processing failed",
                    error=str(e),
                    batch_start=i,
                    batch_size=len(batch)
                )

        self.logger.info(
            "Batch NFT retrieval completed",
            requested=len(token_ids),
            successful=len(results),
            contract=contract_address
        )

        return results

    async def get_all_nfts_paginated(self, contract_address: str, page_size: int = 100) -> AsyncGenerator[SeiNFTInfo, None]:
        """Get all NFTs from a contract with pagination."""
        start_after = None

        while True:
            try:
                # Get token IDs for this page
                token_ids = await self.get_all_tokens(
                    contract_address,
                    start_after=start_after,
                    limit=page_size
                )

                if not token_ids:
                    break

                # Get NFT info for all tokens in this page
                nfts = await self.get_nft_batch(contract_address, token_ids)

                for nft in nfts:
                    yield nft

                # Set up for next page
                if len(token_ids) < page_size:
                    # Last page
                    break
                else:
                    start_after = token_ids[-1]

            except Exception as e:
                self.logger.error(
                    "Pagination failed",
                    error=str(e),
                    contract=contract_address,
                    start_after=start_after
                )
                break

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        runtime = time.time() - self.stats['start_time']

        return {
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'failed_requests': self.stats['failed_requests'],
            'retry_count': self.stats['retry_count'],
            'success_rate': (
                self.stats['successful_requests'] / max(self.stats['total_requests'], 1) * 100
            ),
            'runtime_seconds': runtime,
            'requests_per_second': self.stats['total_requests'] / max(runtime, 1)
        }
