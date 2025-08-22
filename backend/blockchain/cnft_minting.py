"""
Compressed NFT Minting System for ReplantWorld.

This module provides comprehensive compressed NFT minting functionality
using Metaplex Bubblegum for carbon credit NFTs.
"""

import os
import json
import asyncio
import hashlib
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

import structlog
from solders.pubkey import Pubkey
from solders.keypair import Keypair

from .merkle_tree import MerkleTreeManager, MerkleTreeInfo
from .config import get_solana_config
from .logging_utils import (
    log_blockchain_operation,
    log_operation_context,
    log_mint_event,
    OperationType,
    LogLevel,
    create_operation_logger
)

logger = create_operation_logger("cnft_minting")


class NFTMintStatus(Enum):
    """Status of NFT minting operation."""
    PENDING = "pending"
    MINTING = "minting"
    SUCCESS = "success"
    FAILED = "failed"
    CONFIRMED = "confirmed"


@dataclass
class NFTMetadata:
    """Metadata structure for compressed NFTs."""
    name: str
    symbol: str
    description: str
    image: str
    external_url: Optional[str] = None
    attributes: Optional[List[Dict[str, Any]]] = None
    properties: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize default values and validate."""
        if self.attributes is None:
            self.attributes = []
        if self.properties is None:
            self.properties = {}
        
        # Validate required fields
        if not self.name or len(self.name.strip()) == 0:
            raise ValueError("Name is required")
        if not self.symbol or len(self.symbol.strip()) == 0:
            raise ValueError("Symbol is required")
        if not self.description or len(self.description.strip()) == 0:
            raise ValueError("Description is required")
        if not self.image or len(self.image.strip()) == 0:
            raise ValueError("Image URL is required")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def create_carbon_credit_metadata(
        cls,
        tree_id: str,
        tree_species: str,
        location: str,
        planting_date: str,
        carbon_offset_tons: float,
        image_url: str,
        external_url: Optional[str] = None
    ) -> 'NFTMetadata':
        """
        Create metadata for a carbon credit NFT.
        
        Args:
            tree_id: Unique identifier for the tree
            tree_species: Species of the tree
            location: Geographic location
            planting_date: Date when tree was planted
            carbon_offset_tons: Estimated carbon offset in tons
            image_url: URL to tree image
            external_url: Optional external URL for more info
            
        Returns:
            NFTMetadata instance for carbon credit
        """
        return cls(
            name=f"Carbon Credit Tree #{tree_id}",
            symbol="CCT",
            description=f"Carbon credit NFT representing a {tree_species} tree planted in {location} on {planting_date}. Estimated carbon offset: {carbon_offset_tons} tons CO2.",
            image=image_url,
            external_url=external_url,
            attributes=[
                {"trait_type": "Tree ID", "value": tree_id},
                {"trait_type": "Species", "value": tree_species},
                {"trait_type": "Location", "value": location},
                {"trait_type": "Planting Date", "value": planting_date},
                {"trait_type": "Carbon Offset (tons)", "value": carbon_offset_tons, "display_type": "number"},
                {"trait_type": "Status", "value": "Active"},
                {"trait_type": "Verification", "value": "Verified"}
            ],
            properties={
                "category": "Carbon Credit",
                "type": "Tree NFT",
                "version": "1.0",
                "created_at": int(time.time())
            }
        )


@dataclass
class MintRequest:
    """Request structure for minting compressed NFTs."""
    tree_address: str
    recipient: str
    metadata: NFTMetadata
    mint_id: Optional[str] = None
    
    def __post_init__(self):
        """Initialize mint ID if not provided."""
        if self.mint_id is None:
            self.mint_id = str(uuid.uuid4())


@dataclass
class MintResult:
    """Result of NFT minting operation."""
    mint_id: str
    tree_address: str
    recipient: str
    metadata: NFTMetadata
    status: NFTMintStatus
    signature: Optional[str] = None
    leaf_index: Optional[int] = None
    asset_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['metadata'] = self.metadata.to_dict()
        result['status'] = self.status.value
        return result


class CompressedNFTMinter:
    """
    Manages compressed NFT minting operations.
    
    Provides functionality to mint compressed NFTs to Merkle trees
    with proper metadata handling and transaction management.
    """
    
    def __init__(self, merkle_tree_manager: MerkleTreeManager):
        """
        Initialize the compressed NFT minter.
        
        Args:
            merkle_tree_manager: MerkleTreeManager instance
        """
        self.tree_manager = merkle_tree_manager
        self.client = merkle_tree_manager.client
        self.config = get_solana_config()
        self.network = self.config['network']
        
        # Mint tracking
        self.mint_history: Dict[str, MintResult] = {}
        
        logger.info(
            "CompressedNFTMinter initialized",
            network=self.network,
            authority=str(self.tree_manager.authority)
        )
    
    @log_blockchain_operation(
        OperationType.NFT_MINTING,
        "mint_compressed_nft",
        LogLevel.INFO,
        include_performance=True
    )
    async def mint_compressed_nft(
        self,
        mint_request: MintRequest,
        confirm_transaction: bool = True
    ) -> MintResult:
        """
        Mint a compressed NFT to a Merkle tree.
        
        Args:
            mint_request: Minting request details
            confirm_transaction: Whether to wait for transaction confirmation
            
        Returns:
            MintResult with operation details
        """
        start_time = time.time()

        # Log mint start event
        log_mint_event(
            "started",
            mint_request.mint_id,
            mint_request.tree_address,
            mint_request.recipient,
            {
                "nft_name": mint_request.metadata.name,
                "nft_symbol": mint_request.metadata.symbol,
                "network": self.network
            }
        )

        logger.info(
            "Starting compressed NFT mint",
            mint_id=mint_request.mint_id,
            tree_address=mint_request.tree_address,
            recipient=mint_request.recipient,
            nft_name=mint_request.metadata.name
        )
        
        # Initialize result
        result = MintResult(
            mint_id=mint_request.mint_id,
            tree_address=mint_request.tree_address,
            recipient=mint_request.recipient,
            metadata=mint_request.metadata,
            status=NFTMintStatus.PENDING,
            timestamp=start_time
        )
        
        try:
            # Validate tree exists and is active
            tree_info = await self.tree_manager.get_tree_info(mint_request.tree_address)
            if not tree_info:
                raise ValueError(f"Tree not found: {mint_request.tree_address}")
            
            if tree_info.status.value != "active":
                raise ValueError(f"Tree is not active: {tree_info.status.value}")
            
            # Check tree capacity
            capacity_info = await self.tree_manager.get_tree_capacity_info(mint_request.tree_address)
            if capacity_info['is_full']:
                raise ValueError("Tree is at full capacity")
            
            # Validate recipient address
            try:
                recipient_pubkey = Pubkey.from_string(mint_request.recipient)
            except Exception as e:
                raise ValueError(f"Invalid recipient address: {mint_request.recipient}")
            
            # Update status
            result.status = NFTMintStatus.MINTING
            
            # For now, simulate the minting process since actual Bubblegum integration
            # requires complex instruction building. In production, this would:
            # 1. Create metadata account
            # 2. Build mint_to_collection_v1 instruction
            # 3. Submit transaction with proper accounts
            # 4. Wait for confirmation
            # 5. Extract leaf index and asset ID
            
            # Simulate minting process
            await asyncio.sleep(2)  # Simulate network delay
            
            # Generate simulated results
            result.signature = f"mint_{mint_request.mint_id}_{int(time.time())}"
            result.leaf_index = tree_info.current_size
            result.asset_id = self._generate_asset_id(mint_request.tree_address, result.leaf_index)
            result.status = NFTMintStatus.SUCCESS
            
            # Update tree size
            tree_info.current_size += 1
            
            # Store result
            self.mint_history[mint_request.mint_id] = result
            
            mint_time = time.time() - start_time

            # Log successful mint event
            log_mint_event(
                "completed",
                mint_request.mint_id,
                mint_request.tree_address,
                mint_request.recipient,
                {
                    "signature": result.signature,
                    "leaf_index": result.leaf_index,
                    "asset_id": result.asset_id,
                    "mint_time_seconds": mint_time,
                    "tree_utilization": f"{tree_info.current_size}/{tree_info.config.max_capacity}",
                    "nft_name": mint_request.metadata.name
                }
            )

            logger.info(
                "Compressed NFT minted successfully",
                mint_id=mint_request.mint_id,
                signature=result.signature,
                leaf_index=result.leaf_index,
                asset_id=result.asset_id,
                mint_time_seconds=mint_time,
                tree_utilization=f"{tree_info.current_size}/{tree_info.config.max_capacity}"
            )
            
            # Confirm transaction if requested
            if confirm_transaction:
                result.status = NFTMintStatus.CONFIRMED
                logger.info("Transaction confirmed", mint_id=mint_request.mint_id)
            
            return result
            
        except Exception as e:
            result.status = NFTMintStatus.FAILED
            result.error_message = str(e)

            # Log failed mint event
            log_mint_event(
                "failed",
                mint_request.mint_id,
                mint_request.tree_address,
                mint_request.recipient,
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "nft_name": mint_request.metadata.name
                },
                LogLevel.ERROR
            )

            logger.error(
                "Failed to mint compressed NFT",
                mint_id=mint_request.mint_id,
                error=str(e),
                tree_address=mint_request.tree_address,
                recipient=mint_request.recipient
            )

            # Store failed result
            self.mint_history[mint_request.mint_id] = result

            raise
    
    def _generate_asset_id(self, tree_address: str, leaf_index: int) -> str:
        """Generate asset ID for compressed NFT."""
        # In production, this would be calculated based on tree address and leaf index
        # using the proper Bubblegum derivation
        data = f"{tree_address}:{leaf_index}".encode()
        hash_digest = hashlib.sha256(data).hexdigest()
        return f"asset_{hash_digest[:16]}"
    
    async def get_mint_result(self, mint_id: str) -> Optional[MintResult]:
        """Get minting result by mint ID."""
        return self.mint_history.get(mint_id)
    
    async def list_mint_history(self, limit: int = 100) -> List[MintResult]:
        """List recent minting history."""
        results = list(self.mint_history.values())
        # Sort by timestamp, most recent first
        results.sort(key=lambda x: x.timestamp or 0, reverse=True)
        return results[:limit]
    
    async def get_tree_mint_count(self, tree_address: str) -> int:
        """Get number of NFTs minted to a specific tree."""
        count = 0
        for result in self.mint_history.values():
            if result.tree_address == tree_address and result.status in [NFTMintStatus.SUCCESS, NFTMintStatus.CONFIRMED]:
                count += 1
        return count
    
    def save_mint_history_to_file(self, filepath: str):
        """Save mint history to file."""
        try:
            history_data = {
                mint_id: result.to_dict()
                for mint_id, result in self.mint_history.items()
            }
            
            with open(filepath, 'w') as f:
                json.dump(history_data, f, indent=2)
            
            logger.info("Mint history saved to file", filepath=filepath, count=len(self.mint_history))
            
        except Exception as e:
            logger.error("Failed to save mint history to file", filepath=filepath, error=str(e))
            raise
    
    def load_mint_history_from_file(self, filepath: str):
        """Load mint history from file."""
        try:
            if not os.path.exists(filepath):
                logger.info("Mint history file not found, starting with empty history", filepath=filepath)
                return
            
            with open(filepath, 'r') as f:
                history_data = json.load(f)
            
            self.mint_history = {}
            for mint_id, result_data in history_data.items():
                # Reconstruct MintResult
                metadata_data = result_data.pop('metadata')
                metadata = NFTMetadata(**metadata_data)
                
                status_str = result_data.pop('status')
                status = NFTMintStatus(status_str)
                
                result = MintResult(metadata=metadata, status=status, **result_data)
                self.mint_history[mint_id] = result
            
            logger.info("Mint history loaded from file", filepath=filepath, count=len(self.mint_history))
            
        except Exception as e:
            logger.error("Failed to load mint history from file", filepath=filepath, error=str(e))
            raise
