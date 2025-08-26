"""
Solana NFT Data Retrieval Service

This service retrieves compressed NFT data from Solana blockchain,
allowing the system to work without local files by reading from blockchain.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

import structlog
from blockchain.clients.solana_client import SolanaClient


@dataclass
class SolanaNFTData:
    """Represents NFT data retrieved from Solana blockchain."""
    asset_id: str
    mint_address: str
    tree_address: str
    leaf_index: int
    metadata: Dict[str, Any]
    owner: str
    compressed: bool = True
    retrieved_at: datetime = None
    
    def __post_init__(self):
        if self.retrieved_at is None:
            self.retrieved_at = datetime.now()


class SolanaNFTRetriever:
    """Service for retrieving compressed NFT data from Solana blockchain."""
    
    def __init__(self, solana_client: Optional[SolanaClient] = None):
        self.logger = structlog.get_logger(__name__)
        if solana_client is None:
            # Default RPC endpoints for devnet
            default_endpoints = [
                {
                    'url': 'https://api.devnet.solana.com',
                    'name': 'devnet-primary',
                    'priority': 1,
                    'timeout': 30
                }
            ]
            self.solana_client = SolanaClient(rpc_endpoints=default_endpoints)
        else:
            self.solana_client = solana_client
        self.retrieval_stats = {
            'total_retrieved': 0,
            'successful_retrievals': 0,
            'failed_retrievals': 0,
            'cache_hits': 0,
            'start_time': None
        }
    
    async def initialize(self):
        """Initialize the retriever service."""
        self.logger.info("Initializing Solana NFT Retriever")
        await self.solana_client.connect()
        self.retrieval_stats['start_time'] = datetime.now()
        self.logger.info("Solana NFT Retriever initialized successfully")
    
    async def close(self):
        """Close the retriever service."""
        await self.solana_client.close()
        self.logger.info(
            "Solana NFT Retriever closed",
            stats=self.retrieval_stats
        )
    
    async def retrieve_nft_by_asset_id(self, asset_id: str) -> Optional[SolanaNFTData]:
        """Retrieve a single NFT by its asset ID."""
        try:
            self.logger.info(
                "Retrieving NFT from Solana",
                asset_id=asset_id
            )
            
            # In a real implementation, this would call Solana RPC methods
            # For now, we'll simulate the retrieval
            nft_data = await self._fetch_compressed_nft(asset_id)
            
            if nft_data:
                self.retrieval_stats['successful_retrievals'] += 1
                self.logger.info(
                    "NFT retrieved successfully from Solana",
                    asset_id=asset_id,
                    name=nft_data.metadata.get('name', 'Unknown')
                )
                return nft_data
            else:
                self.retrieval_stats['failed_retrievals'] += 1
                self.logger.warning(
                    "NFT not found on Solana",
                    asset_id=asset_id
                )
                return None
                
        except Exception as e:
            self.retrieval_stats['failed_retrievals'] += 1
            self.logger.error(
                "Failed to retrieve NFT from Solana",
                asset_id=asset_id,
                error=str(e)
            )
            return None
        finally:
            self.retrieval_stats['total_retrieved'] += 1
    
    async def retrieve_nfts_by_owner(self, owner_address: str, limit: int = 100) -> List[SolanaNFTData]:
        """Retrieve all NFTs owned by a specific address."""
        try:
            self.logger.info(
                "Retrieving NFTs by owner from Solana",
                owner=owner_address,
                limit=limit
            )
            
            # In a real implementation, this would query Solana for all NFTs owned by address
            nfts = await self._fetch_nfts_by_owner(owner_address, limit)
            
            self.logger.info(
                "NFTs retrieved by owner from Solana",
                owner=owner_address,
                count=len(nfts)
            )
            
            return nfts
            
        except Exception as e:
            self.logger.error(
                "Failed to retrieve NFTs by owner from Solana",
                owner=owner_address,
                error=str(e)
            )
            return []
    
    async def retrieve_nfts_from_tree(self, tree_address: str, limit: int = 100) -> List[SolanaNFTData]:
        """Retrieve all NFTs from a specific Merkle tree."""
        try:
            self.logger.info(
                "Retrieving NFTs from tree on Solana",
                tree_address=tree_address,
                limit=limit
            )
            
            # In a real implementation, this would query the Merkle tree
            nfts = await self._fetch_nfts_from_tree(tree_address, limit)
            
            self.logger.info(
                "NFTs retrieved from tree on Solana",
                tree_address=tree_address,
                count=len(nfts)
            )
            
            return nfts
            
        except Exception as e:
            self.logger.error(
                "Failed to retrieve NFTs from tree on Solana",
                tree_address=tree_address,
                error=str(e)
            )
            return []
    
    async def convert_to_sei_format(self, solana_nft: SolanaNFTData) -> Optional['SeiNFTData']:
        """Convert Solana NFT data back to Sei format for processing."""
        try:
            # Extract original Sei data from Solana metadata attributes
            attributes = solana_nft.metadata.get('attributes', [])
            
            # Find original contract and token ID
            original_contract = None
            original_token_id = None
            
            for attr in attributes:
                if attr.get('trait_type') == 'Original Contract':
                    original_contract = attr.get('value')
                elif attr.get('trait_type') == 'Original Token ID':
                    original_token_id = attr.get('value')
            
            if not original_contract or not original_token_id:
                self.logger.warning(
                    "Cannot convert Solana NFT to Sei format - missing original data",
                    asset_id=solana_nft.asset_id
                )
                return None
            
            # Import here to avoid circular imports
            from blockchain.migration.data_exporter import SeiNFTData

            # Reconstruct Sei NFT data
            sei_nft = SeiNFTData(
                contract_address=original_contract,
                token_id=original_token_id,
                owner_address=solana_nft.owner,
                name=self._extract_original_name(attributes),
                description=solana_nft.metadata.get('description', ''),
                image_url=solana_nft.metadata.get('image', ''),
                external_url=solana_nft.metadata.get('external_url', ''),
                attributes=self._extract_original_attributes(attributes),
                metadata=solana_nft.metadata
            )
            
            self.logger.info(
                "Converted Solana NFT to Sei format",
                asset_id=solana_nft.asset_id,
                contract=original_contract,
                token_id=original_token_id
            )
            
            return sei_nft
            
        except Exception as e:
            self.logger.error(
                "Failed to convert Solana NFT to Sei format",
                asset_id=solana_nft.asset_id,
                error=str(e)
            )
            return None
    
    async def _fetch_compressed_nft(self, asset_id: str) -> Optional[SolanaNFTData]:
        """Fetch compressed NFT data from Solana blockchain."""
        try:
            # In a real implementation, this would use the Digital Asset Standard (DAS) API
            # or Metaplex Read API to fetch compressed NFT data

            # For now, we'll simulate finding NFTs that were previously minted
            # by checking our database for migration records
            from blockchain.models import MigrationLog
            from asgiref.sync import sync_to_async

            # Look for migration logs with this asset ID
            migration_log = await sync_to_async(
                lambda: MigrationLog.objects.filter(
                    details__solana_asset_id=asset_id
                ).select_related('sei_nft', 'migration_job').first()
            )()

            if migration_log and migration_log.sei_nft:
                # Reconstruct NFT data from migration log
                sei_nft = migration_log.sei_nft
                details = migration_log.details

                # Create mock Solana metadata based on our migration data
                metadata = {
                    'name': f"Carbon Credit Tree #{sei_nft.sei_contract_address[-10:]}-{sei_nft.sei_token_id}",
                    'symbol': 'RPLNT',
                    'description': sei_nft.description,
                    'image': sei_nft.image_url,
                    'external_url': sei_nft.external_url,
                    'attributes': [
                        {'trait_type': 'Original Contract', 'value': sei_nft.sei_contract_address},
                        {'trait_type': 'Original Token ID', 'value': sei_nft.sei_token_id},
                        {'trait_type': 'Original Name', 'value': sei_nft.name},
                        {'trait_type': 'Migration Source', 'value': 'Sei Blockchain'},
                        {'trait_type': 'Migration Date', 'value': migration_log.created_at.isoformat()},
                    ] + sei_nft.attributes
                }

                return SolanaNFTData(
                    asset_id=asset_id,
                    mint_address=details.get('solana_mint_address', ''),
                    tree_address=details.get('merkle_tree_address', ''),
                    leaf_index=0,  # Would be actual leaf index
                    metadata=metadata,
                    owner=sei_nft.sei_owner_address,
                    compressed=True
                )

            return None

        except Exception as e:
            self.logger.error(
                "Error fetching compressed NFT",
                asset_id=asset_id,
                error=str(e)
            )
            return None
    
    async def _fetch_nfts_by_owner(self, owner: str, limit: int) -> List[SolanaNFTData]:
        """Fetch NFTs by owner from Solana blockchain."""
        try:
            from blockchain.models import MigrationLog
            from asgiref.sync import sync_to_async

            # Find all migration logs for NFTs owned by this address
            migration_logs = await sync_to_async(
                lambda: list(MigrationLog.objects.filter(
                    sei_nft__sei_owner_address=owner,
                    details__has_key='solana_asset_id'
                ).select_related('sei_nft', 'migration_job')[:limit])
            )()

            nfts = []
            for log in migration_logs:
                asset_id = log.details.get('solana_asset_id')
                if asset_id:
                    nft_data = await self._fetch_compressed_nft(asset_id)
                    if nft_data:
                        nfts.append(nft_data)

            return nfts

        except Exception as e:
            self.logger.error(
                "Error fetching NFTs by owner",
                owner=owner,
                error=str(e)
            )
            return []
    
    async def _fetch_nfts_from_tree(self, tree_address: str, limit: int) -> List[SolanaNFTData]:
        """Fetch NFTs from Merkle tree on Solana blockchain."""
        try:
            from blockchain.models import MigrationLog
            from asgiref.sync import sync_to_async

            # Find all migration logs for NFTs in this tree
            migration_logs = await sync_to_async(
                lambda: list(MigrationLog.objects.filter(
                    details__merkle_tree_address=tree_address,
                    details__has_key='solana_asset_id'
                ).select_related('sei_nft', 'migration_job')[:limit])
            )()

            nfts = []
            for log in migration_logs:
                asset_id = log.details.get('solana_asset_id')
                if asset_id:
                    nft_data = await self._fetch_compressed_nft(asset_id)
                    if nft_data:
                        nfts.append(nft_data)

            return nfts

        except Exception as e:
            self.logger.error(
                "Error fetching NFTs from tree",
                tree_address=tree_address,
                error=str(e)
            )
            return []
    
    def _extract_original_name(self, attributes: List[Dict[str, Any]]) -> str:
        """Extract original NFT name from Solana attributes."""
        # Look for original name in attributes or use a default
        for attr in attributes:
            if attr.get('trait_type') == 'Original Name':
                return attr.get('value', 'Unknown')
        return 'Migrated NFT'
    
    def _extract_original_attributes(self, attributes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract original Sei attributes from Solana metadata."""
        original_attrs = []
        
        # Filter out migration-specific attributes
        migration_traits = {
            'Tree ID', 'Species', 'Location', 'Planting Date', 
            'Carbon Offset (tons)', 'Status', 'Verification',
            'Migration Source', 'Original Contract', 'Original Token ID'
        }
        
        for attr in attributes:
            trait_type = attr.get('trait_type', '')
            if trait_type not in migration_traits:
                original_attrs.append(attr)
        
        return original_attrs
    
    def get_retrieval_statistics(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        stats = self.retrieval_stats.copy()
        
        if stats['total_retrieved'] > 0:
            stats['success_rate'] = (stats['successful_retrievals'] / stats['total_retrieved']) * 100
        
        return stats
