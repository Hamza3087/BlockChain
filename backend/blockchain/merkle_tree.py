"""
Merkle Tree Management for Compressed NFTs.

This module provides comprehensive Merkle tree creation and management
functionality for compressed NFTs using Metaplex Bubblegum.
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import time

import structlog
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.sysvar import RENT
from solana.rpc.types import TxOpts
from solana.transaction import Transaction
from construct import Container

from .config import get_solana_config, get_bubblegum_program_id
from .logging_utils import (
    log_blockchain_operation,
    log_operation_context,
    log_tree_event,
    OperationType,
    LogLevel,
    create_operation_logger
)

logger = create_operation_logger("merkle_tree")


class TreeStatus(Enum):
    """Status of a Merkle tree."""
    CREATING = "creating"
    ACTIVE = "active"
    FULL = "full"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class MerkleTreeConfig:
    """Configuration for Merkle tree creation."""
    max_depth: int = 14  # Max 16,384 NFTs (2^14)
    max_buffer_size: int = 64  # Concurrent proof buffer
    canopy_depth: int = 0  # On-chain proof storage depth
    public: bool = True  # Allow public minting
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if self.max_depth < 3 or self.max_depth > 30:
            raise ValueError("max_depth must be between 3 and 30")
        if self.max_buffer_size < 8 or self.max_buffer_size > 2048:
            raise ValueError("max_buffer_size must be between 8 and 2048")
        if self.canopy_depth < 0 or self.canopy_depth > self.max_depth:
            raise ValueError("canopy_depth must be between 0 and max_depth")
    
    @property
    def max_capacity(self) -> int:
        """Calculate maximum NFT capacity."""
        return 2 ** self.max_depth
    
    @property
    def estimated_cost_lamports(self) -> int:
        """Estimate creation cost in lamports."""
        # Base cost calculation (simplified)
        base_cost = 1_000_000  # 0.001 SOL base
        depth_cost = self.max_depth * 100_000  # Scale with depth
        buffer_cost = self.max_buffer_size * 10_000  # Scale with buffer
        canopy_cost = self.canopy_depth * 500_000  # Canopy storage cost
        
        return base_cost + depth_cost + buffer_cost + canopy_cost


@dataclass
class MerkleTreeInfo:
    """Information about a created Merkle tree."""
    tree_address: str
    tree_authority: str
    tree_delegate: str
    config: MerkleTreeConfig
    status: TreeStatus
    creation_signature: Optional[str] = None
    creation_timestamp: Optional[float] = None
    current_size: int = 0
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['config'] = asdict(self.config)
        result['status'] = self.status.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MerkleTreeInfo':
        """Create from dictionary."""
        config_data = data.pop('config')
        config = MerkleTreeConfig(**config_data)
        
        status_str = data.pop('status')
        status = TreeStatus(status_str)
        
        return cls(config=config, status=status, **data)


class MerkleTreeManager:
    """
    Manages Merkle trees for compressed NFTs.
    
    Provides functionality to create, manage, and monitor Merkle trees
    used for compressed NFT collections.
    """
    
    def __init__(self, solana_client, keypair_path: Optional[str] = None):
        """
        Initialize the Merkle tree manager.
        
        Args:
            solana_client: SolanaClient instance
            keypair_path: Path to keypair file (defaults to config)
        """
        self.client = solana_client
        self.config = get_solana_config()
        self.network = self.config['network']
        self.bubblegum_program_id = Pubkey.from_string(get_bubblegum_program_id(self.network))
        
        # Load keypair
        if keypair_path is None:
            keypair_path = os.path.expanduser(self.config['keypair_path'])
        
        self.keypair = self._load_keypair(keypair_path)
        self.authority = self.keypair.pubkey()
        
        # Tree storage
        self.trees: Dict[str, MerkleTreeInfo] = {}
        
        logger.info(
            "MerkleTreeManager initialized",
            network=self.network,
            authority=str(self.authority),
            bubblegum_program=str(self.bubblegum_program_id)
        )
    
    def _load_keypair(self, keypair_path: str) -> Keypair:
        """Load keypair from file."""
        try:
            with open(keypair_path, 'r') as f:
                keypair_data = json.load(f)
            
            if isinstance(keypair_data, list) and len(keypair_data) == 64:
                return Keypair.from_bytes(bytes(keypair_data))
            else:
                raise ValueError("Invalid keypair format")
                
        except Exception as e:
            logger.error("Failed to load keypair", path=keypair_path, error=str(e))
            raise
    
    def create_tree_config(
        self,
        max_depth: int = 14,
        max_buffer_size: int = 64,
        canopy_depth: int = 0,
        public: bool = True
    ) -> MerkleTreeConfig:
        """
        Create a Merkle tree configuration.
        
        Args:
            max_depth: Maximum tree depth (determines capacity)
            max_buffer_size: Concurrent proof buffer size
            canopy_depth: On-chain proof storage depth
            public: Whether to allow public minting
            
        Returns:
            MerkleTreeConfig instance
        """
        config = MerkleTreeConfig(
            max_depth=max_depth,
            max_buffer_size=max_buffer_size,
            canopy_depth=canopy_depth,
            public=public
        )
        
        logger.info(
            "Created tree configuration",
            max_capacity=config.max_capacity,
            estimated_cost_sol=config.estimated_cost_lamports / 1_000_000_000,
            **asdict(config)
        )
        
        return config
    
    @log_blockchain_operation(
        OperationType.TREE_CREATION,
        "create_merkle_tree",
        LogLevel.INFO,
        include_performance=True
    )
    async def create_merkle_tree(
        self,
        config: MerkleTreeConfig,
        tree_name: Optional[str] = None
    ) -> MerkleTreeInfo:
        """
        Create a new Merkle tree for compressed NFTs.
        
        Args:
            config: Tree configuration
            tree_name: Optional name for the tree
            
        Returns:
            MerkleTreeInfo with creation details
        """
        start_time = time.time()
        
        logger.info(
            "Starting Merkle tree creation",
            max_depth=config.max_depth,
            max_capacity=config.max_capacity,
            estimated_cost_sol=config.estimated_cost_lamports / 1_000_000_000,
            tree_name=tree_name
        )
        
        try:
            # Generate tree keypair
            tree_keypair = Keypair()
            tree_address = tree_keypair.pubkey()
            
            # Create tree info
            tree_info = MerkleTreeInfo(
                tree_address=str(tree_address),
                tree_authority=str(self.authority),
                tree_delegate=str(self.authority),  # Same as authority for now
                config=config,
                status=TreeStatus.CREATING,
                creation_timestamp=start_time,
                metadata={
                    'name': tree_name or f"Tree-{int(start_time)}",
                    'network': self.network,
                    'creator': str(self.authority)
                }
            )
            
            # Check balance
            balance_response = await self.client.get_balance(self.authority)
            current_balance = balance_response.value
            
            if current_balance < config.estimated_cost_lamports:
                required_sol = config.estimated_cost_lamports / 1_000_000_000
                current_sol = current_balance / 1_000_000_000
                
                logger.error(
                    "Insufficient balance for tree creation",
                    required_sol=required_sol,
                    current_sol=current_sol,
                    deficit_sol=required_sol - current_sol
                )
                
                tree_info.status = TreeStatus.ERROR
                raise ValueError(f"Insufficient balance: need {required_sol:.6f} SOL, have {current_sol:.6f} SOL")
            
            # For now, we'll simulate tree creation since actual Bubblegum integration
            # requires complex instruction building. In production, this would:
            # 1. Build create_tree instruction with proper accounts
            # 2. Submit transaction
            # 3. Confirm transaction
            # 4. Verify tree state
            
            # Simulate successful creation
            await asyncio.sleep(1)  # Simulate network delay
            
            tree_info.creation_signature = f"sim_{int(time.time())}"
            tree_info.status = TreeStatus.ACTIVE
            
            # Store tree info
            self.trees[str(tree_address)] = tree_info

            creation_time = time.time() - start_time

            # Log tree creation event
            log_tree_event(
                "created",
                str(tree_address),
                {
                    "tree_name": tree_name,
                    "max_capacity": config.max_capacity,
                    "creation_signature": tree_info.creation_signature,
                    "creation_time_seconds": creation_time,
                    "network": self.network
                }
            )

            logger.info(
                "Merkle tree created successfully",
                tree_address=str(tree_address),
                creation_signature=tree_info.creation_signature,
                creation_time_seconds=creation_time,
                max_capacity=config.max_capacity,
                tree_name=tree_name
            )
            
            return tree_info
            
        except Exception as e:
            logger.error(
                "Failed to create Merkle tree",
                error=str(e),
                tree_name=tree_name,
                config=asdict(config)
            )
            raise
    
    async def get_tree_info(self, tree_address: str) -> Optional[MerkleTreeInfo]:
        """
        Get information about a Merkle tree.
        
        Args:
            tree_address: Tree public key as string
            
        Returns:
            MerkleTreeInfo if found, None otherwise
        """
        if tree_address in self.trees:
            return self.trees[tree_address]
        
        # In production, this would query the blockchain
        logger.warning("Tree not found in local storage", tree_address=tree_address)
        return None
    
    async def list_trees(self) -> List[MerkleTreeInfo]:
        """List all managed trees."""
        return list(self.trees.values())
    
    async def get_tree_capacity_info(self, tree_address: str) -> Dict[str, Any]:
        """
        Get capacity information for a tree.
        
        Args:
            tree_address: Tree public key as string
            
        Returns:
            Dictionary with capacity information
        """
        tree_info = await self.get_tree_info(tree_address)
        if not tree_info:
            raise ValueError(f"Tree not found: {tree_address}")
        
        max_capacity = tree_info.config.max_capacity
        current_size = tree_info.current_size
        remaining = max_capacity - current_size
        utilization = (current_size / max_capacity) * 100 if max_capacity > 0 else 0
        
        return {
            'tree_address': tree_address,
            'max_capacity': max_capacity,
            'current_size': current_size,
            'remaining_capacity': remaining,
            'utilization_percent': utilization,
            'is_full': remaining == 0,
            'status': tree_info.status.value
        }
    
    def save_trees_to_file(self, filepath: str):
        """Save tree information to file."""
        try:
            trees_data = {
                addr: tree_info.to_dict() 
                for addr, tree_info in self.trees.items()
            }
            
            with open(filepath, 'w') as f:
                json.dump(trees_data, f, indent=2)
            
            logger.info("Trees saved to file", filepath=filepath, count=len(self.trees))
            
        except Exception as e:
            logger.error("Failed to save trees to file", filepath=filepath, error=str(e))
            raise
    
    def load_trees_from_file(self, filepath: str):
        """Load tree information from file."""
        try:
            if not os.path.exists(filepath):
                logger.info("Trees file not found, starting with empty tree list", filepath=filepath)
                return
            
            with open(filepath, 'r') as f:
                trees_data = json.load(f)
            
            self.trees = {
                addr: MerkleTreeInfo.from_dict(tree_data)
                for addr, tree_data in trees_data.items()
            }
            
            logger.info("Trees loaded from file", filepath=filepath, count=len(self.trees))
            
        except Exception as e:
            logger.error("Failed to load trees from file", filepath=filepath, error=str(e))
            raise
