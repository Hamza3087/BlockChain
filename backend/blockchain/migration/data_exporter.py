"""
Sei Data Exporter for NFT Migration

This module provides functionality to export NFT data from Sei blockchain
using the CW721 standard for migration to Solana compressed NFTs.

Production implementation that fetches data directly from Sei blockchain.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, AsyncGenerator
from decimal import Decimal
import structlog
from django.conf import settings
from django.utils import timezone

from ..config import get_migration_config
from ..clients.sei_client import SeiClient, SeiNFTInfo, SeiContractError, SeiNetworkError

logger = structlog.get_logger(__name__)


class DataExportError(Exception):
    """Exception raised for data export errors."""
    pass


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
            self.data_hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate SHA-256 hash of the NFT data for integrity verification."""
        # Create a deterministic representation for hashing
        hash_data = {
            'contract_address': self.contract_address,
            'token_id': self.token_id,
            'owner_address': self.owner_address,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'external_url': self.external_url,
            'attributes': sorted(self.attributes, key=lambda x: str(x)) if self.attributes else [],
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
    
    @classmethod
    def from_sei_nft_info(cls, sei_nft: SeiNFTInfo) -> 'SeiNFTData':
        """Create instance from SeiNFTInfo."""
        return cls(
            contract_address=sei_nft.contract_address,
            token_id=sei_nft.token_id,
            owner_address=sei_nft.owner,
            name=sei_nft.name,
            description=sei_nft.description,
            image_url=sei_nft.image,
            external_url=sei_nft.external_url,
            attributes=sei_nft.attributes or [],
            metadata=sei_nft.raw_metadata or {}
        )
    
    def validate(self) -> List[str]:
        """
        Validate the NFT data structure.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Required fields
        if not self.contract_address:
            errors.append("contract_address is required")
        if not self.token_id:
            errors.append("token_id is required")
        if not self.name:
            errors.append("name is required")
        
        # Field length validation
        if len(self.name) > 200:
            errors.append("name exceeds maximum length of 200 characters")
        if len(self.description) > 1000:
            errors.append("description exceeds maximum length of 1000 characters")
        if len(self.image_url) > 500:
            errors.append("image_url exceeds maximum length of 500 characters")
        
        # Attributes validation
        if self.attributes and len(self.attributes) > 50:
            errors.append("attributes exceed maximum count of 50")
        
        return errors

    def calculate_hash(self) -> str:
        """Calculate hash for data integrity verification."""
        return self.data_hash


class DataExporter:
    """
    Sei blockchain data exporter for NFT migration.
    
    This class handles the export of NFT data from Sei CW721 contracts
    for migration to Solana compressed NFTs using direct blockchain queries.
    """

    def __init__(self, config: Dict[str, Any] = None, sei_client: SeiClient = None):
        """
        Initialize the data exporter.

        Args:
            config: Configuration dictionary (optional, uses default if not provided)
            sei_client: Pre-configured Sei client (optional, creates new if not provided)
        """
        self.config = config or get_migration_config()
        self.logger = logger.bind(component="DataExporter")
        
        # Initialize Sei client
        self.sei_client = sei_client or SeiClient()
        
        # Export statistics
        self.export_stats = {
            'total_exported': 0,
            'successful_exports': 0,
            'failed_exports': 0,
            'contracts_processed': 0,
            'start_time': None
        }

        self.logger.info(
            "DataExporter initialized",
            config_keys=list(self.config.keys()),
            sei_rpc_url=self.sei_client.rpc_url,
            sei_chain_id=self.sei_client.chain_id
        )

    async def initialize(self) -> bool:
        """Initialize the data exporter and establish connections."""
        try:
            self.export_stats['start_time'] = time.time()
            
            # Initialize Sei client
            if not await self.sei_client.initialize():
                raise DataExportError("Failed to initialize Sei client")
            
            self.logger.info("DataExporter successfully initialized")
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize DataExporter", error=str(e))
            return False

    async def close(self):
        """Close connections and cleanup resources."""
        if self.sei_client:
            await self.sei_client.close()
        
        self.logger.info(
            "DataExporter closed",
            stats=self.get_export_stats()
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
        self.export_stats['total_exported'] += 1
        
        try:
            # Get NFT info from Sei blockchain
            sei_nft = await self.sei_client.get_nft_info(contract_address, token_id)
            
            # Convert to SeiNFTData
            nft_data = SeiNFTData.from_sei_nft_info(sei_nft)
            
            # Validate the data
            validation_errors = nft_data.validate()
            if validation_errors:
                self.logger.warning(
                    "NFT data validation warnings",
                    contract=contract_address,
                    token_id=token_id,
                    errors=validation_errors
                )
            
            self.export_stats['successful_exports'] += 1
            
            export_time = time.time() - start_time
            self.logger.info(
                "NFT data exported successfully",
                contract=contract_address,
                token_id=token_id,
                name=nft_data.name,
                export_time=f"{export_time:.3f}s"
            )
            
            return nft_data
            
        except (SeiContractError, SeiNetworkError) as e:
            self.export_stats['failed_exports'] += 1
            self.logger.error(
                "Failed to export NFT data",
                contract=contract_address,
                token_id=token_id,
                error=str(e)
            )
            return None
        except Exception as e:
            self.export_stats['failed_exports'] += 1
            self.logger.error(
                "Unexpected error during NFT export",
                contract=contract_address,
                token_id=token_id,
                error=str(e)
            )
            return None

    async def export_nft_batch(self, contract_address: str, token_ids: List[str]) -> List[SeiNFTData]:
        """
        Export multiple NFTs in batch.

        Args:
            contract_address: Sei contract address
            token_ids: List of token IDs to export

        Returns:
            List of successfully exported SeiNFTData instances
        """
        start_time = time.time()

        try:
            # Get NFT batch from Sei blockchain
            sei_nfts = await self.sei_client.get_nft_batch(contract_address, token_ids)

            # Convert to SeiNFTData
            nft_data_list = []
            for sei_nft in sei_nfts:
                try:
                    nft_data = SeiNFTData.from_sei_nft_info(sei_nft)
                    nft_data_list.append(nft_data)
                except Exception as e:
                    self.logger.error(
                        "Failed to convert NFT data",
                        contract=contract_address,
                        token_id=sei_nft.token_id,
                        error=str(e)
                    )

            batch_time = time.time() - start_time
            self.logger.info(
                "NFT batch exported",
                contract=contract_address,
                requested=len(token_ids),
                successful=len(nft_data_list),
                batch_time=f"{batch_time:.3f}s"
            )

            return nft_data_list

        except Exception as e:
            self.logger.error(
                "Failed to export NFT batch",
                contract=contract_address,
                token_count=len(token_ids),
                error=str(e)
            )
            return []

    async def export_all_nfts(self, contract_address: str, page_size: int = 100) -> AsyncGenerator[SeiNFTData, None]:
        """
        Export all NFTs from a contract with pagination.

        Args:
            contract_address: Sei contract address
            page_size: Number of NFTs to process per page

        Yields:
            SeiNFTData instances
        """
        self.export_stats['contracts_processed'] += 1

        try:
            async for sei_nft in self.sei_client.get_all_nfts_paginated(contract_address, page_size):
                try:
                    nft_data = SeiNFTData.from_sei_nft_info(sei_nft)
                    self.export_stats['successful_exports'] += 1
                    yield nft_data
                except Exception as e:
                    self.export_stats['failed_exports'] += 1
                    self.logger.error(
                        "Failed to convert NFT data",
                        contract=contract_address,
                        token_id=sei_nft.token_id,
                        error=str(e)
                    )

        except Exception as e:
            self.logger.error(
                "Failed to export all NFTs",
                contract=contract_address,
                error=str(e)
            )

    async def get_contract_info(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """
        Get contract information.

        Args:
            contract_address: Sei contract address

        Returns:
            Contract information dictionary or None if failed
        """
        try:
            contract_info = await self.sei_client.get_contract_info(contract_address)

            return {
                'address': contract_info.address,
                'name': contract_info.name,
                'symbol': contract_info.symbol,
                'total_supply': contract_info.total_supply,
                'minter': contract_info.minter
            }

        except Exception as e:
            self.logger.error(
                "Failed to get contract info",
                contract=contract_address,
                error=str(e)
            )
            return None

    def get_export_stats(self) -> Dict[str, Any]:
        """Get export statistics."""
        runtime = 0
        if self.export_stats['start_time']:
            runtime = time.time() - self.export_stats['start_time']

        return {
            'total_exported': self.export_stats['total_exported'],
            'successful_exports': self.export_stats['successful_exports'],
            'failed_exports': self.export_stats['failed_exports'],
            'contracts_processed': self.export_stats['contracts_processed'],
            'success_rate': (
                self.export_stats['successful_exports'] / max(self.export_stats['total_exported'], 1) * 100
            ),
            'runtime_seconds': runtime,
            'exports_per_second': self.export_stats['successful_exports'] / max(runtime, 1)
        }
