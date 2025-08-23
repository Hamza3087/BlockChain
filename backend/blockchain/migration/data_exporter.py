"""
Sei Data Exporter for NFT Migration

This module provides functionality to export NFT data from Sei blockchain
using the CW721 standard for migration to Solana compressed NFTs.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, AsyncGenerator
from decimal import Decimal
import aiohttp
import structlog
from django.conf import settings
from django.utils import timezone

from ..config import get_migration_config

logger = structlog.get_logger(__name__)


@dataclass
class SeiNFTData:
    """
    Data structure for Sei NFT information.
    
    This represents the complete NFT data structure from Sei blockchain
    following the CW721 standard.
    """
    
    # Blockchain identifiers
    contract_address: str
    token_id: str
    owner_address: str
    
    # NFT metadata
    name: str
    description: str
    image_url: str
    external_url: str = ""
    
    # Attributes and traits
    attributes: List[Dict[str, Any]] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = None
    
    # Export metadata
    export_timestamp: float = None
    data_hash: str = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.attributes is None:
            self.attributes = []
        if self.metadata is None:
            self.metadata = {}
        if self.export_timestamp is None:
            self.export_timestamp = time.time()
        if self.data_hash is None:
            self.data_hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of the NFT data for integrity verification."""
        # Create a consistent representation for hashing
        hash_data = {
            'contract_address': self.contract_address,
            'token_id': self.token_id,
            'owner_address': self.owner_address,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'external_url': self.external_url,
            'attributes': sorted(self.attributes, key=lambda x: str(x)) if self.attributes else [],
            'metadata': dict(sorted(self.metadata.items())) if self.metadata else {}
        }
        
        # Convert to JSON string and hash
        json_str = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SeiNFTData':
        """Create instance from dictionary."""
        return cls(**data)


class DataExporter:
    """
    Sei blockchain data exporter for CW721 NFTs.
    
    This class handles the extraction of NFT data from Sei blockchain
    contracts following the CW721 standard.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the data exporter.
        
        Args:
            config: Configuration dictionary (optional, uses default if not provided)
        """
        self.config = config or get_migration_config()
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logger.bind(component="DataExporter")
        
        # Performance tracking
        self.export_stats = {
            'total_exported': 0,
            'successful_exports': 0,
            'failed_exports': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def initialize(self):
        """Initialize the HTTP session and connections."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(
                total=self.config.get('request_timeout', 30),
                connect=self.config.get('connect_timeout', 10)
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'ReplantWorld-Migration/1.0',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            )
            
            self.logger.info(
                "DataExporter initialized",
                sei_rpc_url=self.config.get('sei_rpc_url'),
                timeout=self.config.get('request_timeout')
            )
    
    async def close(self):
        """Close HTTP session and cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
            
        self.logger.info(
            "DataExporter closed",
            stats=self.export_stats
        )
    
    async def export_nft_data(self, contract_address: str, token_id: str) -> Optional[SeiNFTData]:
        """
        Export single NFT data from Sei blockchain.
        
        Args:
            contract_address: Sei contract address
            token_id: Token ID to export
            
        Returns:
            SeiNFTData instance or None if export fails
        """
        start_time = time.time()
        
        try:
            self.logger.info(
                "Exporting NFT data",
                contract_address=contract_address,
                token_id=token_id
            )
            
            # Query NFT info from contract
            nft_info = await self._query_nft_info(contract_address, token_id)
            if not nft_info:
                self.logger.error(
                    "Failed to query NFT info",
                    contract_address=contract_address,
                    token_id=token_id
                )
                self.export_stats['failed_exports'] += 1
                return None
            
            # Query owner info
            owner_info = await self._query_owner_of(contract_address, token_id)
            if not owner_info:
                self.logger.error(
                    "Failed to query NFT owner",
                    contract_address=contract_address,
                    token_id=token_id
                )
                self.export_stats['failed_exports'] += 1
                return None
            
            # Extract metadata
            metadata = await self._extract_metadata(nft_info)
            
            # Create SeiNFTData instance
            nft_data = SeiNFTData(
                contract_address=contract_address,
                token_id=token_id,
                owner_address=owner_info.get('owner', ''),
                name=metadata.get('name', ''),
                description=metadata.get('description', ''),
                image_url=metadata.get('image', ''),
                external_url=metadata.get('external_url', ''),
                attributes=metadata.get('attributes', []),
                metadata=metadata
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            self.logger.info(
                "NFT data exported successfully",
                contract_address=contract_address,
                token_id=token_id,
                execution_time_ms=execution_time,
                data_hash=nft_data.data_hash
            )
            
            self.export_stats['successful_exports'] += 1
            return nft_data
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            self.logger.error(
                "Failed to export NFT data",
                contract_address=contract_address,
                token_id=token_id,
                error=str(e),
                execution_time_ms=execution_time
            )
            
            self.export_stats['failed_exports'] += 1
            return None
        
        finally:
            self.export_stats['total_exported'] += 1
    
    async def export_collection_data(
        self, 
        contract_address: str, 
        start_token_id: int = 1,
        max_tokens: Optional[int] = None,
        batch_size: int = 10
    ) -> AsyncGenerator[SeiNFTData, None]:
        """
        Export NFT data for an entire collection.
        
        Args:
            contract_address: Sei contract address
            start_token_id: Starting token ID (default: 1)
            max_tokens: Maximum number of tokens to export (optional)
            batch_size: Number of concurrent requests (default: 10)
            
        Yields:
            SeiNFTData instances for each successfully exported NFT
        """
        self.export_stats['start_time'] = time.time()
        
        self.logger.info(
            "Starting collection export",
            contract_address=contract_address,
            start_token_id=start_token_id,
            max_tokens=max_tokens,
            batch_size=batch_size
        )
        
        try:
            # Get collection info to determine total supply
            collection_info = await self._query_collection_info(contract_address)
            total_supply = collection_info.get('num_tokens', max_tokens or 10000)
            
            if max_tokens:
                total_supply = min(total_supply, max_tokens)
            
            self.logger.info(
                "Collection info retrieved",
                contract_address=contract_address,
                total_supply=total_supply
            )
            
            # Process tokens in batches
            current_token_id = start_token_id
            
            while current_token_id <= total_supply:
                # Create batch of token IDs
                batch_end = min(current_token_id + batch_size - 1, total_supply)
                token_ids = list(range(current_token_id, batch_end + 1))
                
                self.logger.debug(
                    "Processing batch",
                    contract_address=contract_address,
                    token_ids=token_ids
                )
                
                # Process batch concurrently
                tasks = [
                    self.export_nft_data(contract_address, str(token_id))
                    for token_id in token_ids
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Yield successful results
                for result in results:
                    if isinstance(result, SeiNFTData):
                        yield result
                    elif isinstance(result, Exception):
                        self.logger.error(
                            "Batch export error",
                            contract_address=contract_address,
                            error=str(result)
                        )
                
                current_token_id = batch_end + 1
                
                # Rate limiting
                if batch_size > 1:
                    await asyncio.sleep(self.config.get('batch_delay', 0.1))
        
        finally:
            self.export_stats['end_time'] = time.time()
            
            self.logger.info(
                "Collection export completed",
                contract_address=contract_address,
                stats=self.export_stats
            )

    async def _query_nft_info(self, contract_address: str, token_id: str) -> Optional[Dict[str, Any]]:
        """Query NFT info from Sei contract."""
        query = {
            "nft_info": {
                "token_id": token_id
            }
        }

        return await self._query_contract(contract_address, query)

    async def _query_owner_of(self, contract_address: str, token_id: str) -> Optional[Dict[str, Any]]:
        """Query NFT owner from Sei contract."""
        query = {
            "owner_of": {
                "token_id": token_id
            }
        }

        return await self._query_contract(contract_address, query)

    async def _query_collection_info(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Query collection info from Sei contract."""
        query = {
            "contract_info": {}
        }

        result = await self._query_contract(contract_address, query)
        if not result:
            # Fallback to num_tokens query
            query = {"num_tokens": {}}
            result = await self._query_contract(contract_address, query)

        return result or {}

    async def _query_contract(self, contract_address: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute smart contract query on Sei blockchain."""
        if not self.session:
            await self.initialize()

        try:
            # Prepare RPC request
            rpc_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "abci_query",
                "params": {
                    "path": f"/cosmwasm.wasm.v1.Query/SmartContractState",
                    "data": self._encode_query(contract_address, query),
                    "prove": False
                }
            }

            # Make request to Sei RPC
            async with self.session.post(
                self.config['sei_rpc_url'],
                json=rpc_request
            ) as response:
                if response.status != 200:
                    self.logger.error(
                        "RPC request failed",
                        status=response.status,
                        contract_address=contract_address,
                        query=query
                    )
                    return None

                result = await response.json()

                if 'error' in result:
                    self.logger.error(
                        "RPC error",
                        error=result['error'],
                        contract_address=contract_address,
                        query=query
                    )
                    return None

                # Decode response
                return self._decode_response(result.get('result', {}).get('response', {}))

        except Exception as e:
            self.logger.error(
                "Contract query failed",
                error=str(e),
                contract_address=contract_address,
                query=query
            )
            return None

    def _encode_query(self, contract_address: str, query: Dict[str, Any]) -> str:
        """Encode contract query for Sei RPC."""
        import base64

        # Create the query message
        query_msg = {
            "contract_addr": contract_address,
            "msg": base64.b64encode(json.dumps(query).encode()).decode()
        }

        # Encode as base64
        return base64.b64encode(json.dumps(query_msg).encode()).decode()

    def _decode_response(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Decode Sei RPC response."""
        import base64

        try:
            if 'value' in response:
                decoded_data = base64.b64decode(response['value']).decode()
                return json.loads(decoded_data)
            return None
        except Exception as e:
            self.logger.error("Failed to decode response", error=str(e))
            return None

    async def _extract_metadata(self, nft_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize metadata from NFT info."""
        metadata = {}

        # Extract basic info
        if 'token_uri' in nft_info:
            # Fetch metadata from URI
            metadata = await self._fetch_metadata_from_uri(nft_info['token_uri'])

        # Merge with extension data
        if 'extension' in nft_info:
            extension = nft_info['extension']
            metadata.update({
                'name': extension.get('name', ''),
                'description': extension.get('description', ''),
                'image': extension.get('image', ''),
                'external_url': extension.get('external_url', ''),
                'attributes': extension.get('attributes', [])
            })

        return metadata

    async def _fetch_metadata_from_uri(self, uri: str) -> Dict[str, Any]:
        """Fetch metadata from URI (IPFS, HTTP, etc.)."""
        if not uri:
            return {}

        try:
            # Handle IPFS URIs
            if uri.startswith('ipfs://'):
                uri = uri.replace('ipfs://', self.config.get('ipfs_gateway', 'https://ipfs.io/ipfs/'))

            # Fetch metadata
            async with self.session.get(uri) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.warning(
                        "Failed to fetch metadata from URI",
                        uri=uri,
                        status=response.status
                    )
                    return {}

        except Exception as e:
            self.logger.error(
                "Error fetching metadata from URI",
                uri=uri,
                error=str(e)
            )
            return {}

    def get_export_statistics(self) -> Dict[str, Any]:
        """Get export statistics."""
        stats = self.export_stats.copy()

        if stats['start_time'] and stats['end_time']:
            stats['duration_seconds'] = stats['end_time'] - stats['start_time']

            if stats['duration_seconds'] > 0:
                stats['exports_per_second'] = stats['total_exported'] / stats['duration_seconds']

        if stats['total_exported'] > 0:
            stats['success_rate'] = (stats['successful_exports'] / stats['total_exported']) * 100

        return stats
