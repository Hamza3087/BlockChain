#!/usr/bin/env python3
"""
Metadata Storage Service

This service handles storing and retrieving NFT metadata both on-chain and off-chain,
ensuring proper format for Solana NFT standards.
"""

import json
import hashlib
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from django.conf import settings

import structlog

logger = structlog.get_logger(__name__)


class MetadataStorageService:
    """Service for storing and managing NFT metadata."""
    
    def __init__(self, storage_dir: str = None):
        """Initialize the metadata storage service."""
        self.storage_dir = Path(storage_dir or getattr(settings, 'METADATA_STORAGE_DIR', 'metadata_storage'))
        self.storage_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.storage_dir / 'onchain').mkdir(exist_ok=True)
        (self.storage_dir / 'offchain').mkdir(exist_ok=True)
        (self.storage_dir / 'original').mkdir(exist_ok=True)
    
    def create_solana_metadata(self, sei_metadata: Dict[str, Any], token_id: str) -> Dict[str, Any]:
        """
        Create Solana-compatible metadata from Sei NFT data.
        
        Args:
            sei_metadata: Original Sei NFT metadata
            token_id: Token ID
            
        Returns:
            Solana-compatible metadata dictionary
        """
        # Extract basic metadata
        name = sei_metadata.get('name', f'Tree #{token_id}')
        description = sei_metadata.get('description', '')
        image = sei_metadata.get('image', '')
        external_url = sei_metadata.get('external_url', '')
        
        # Process attributes
        attributes = []
        for attr in sei_metadata.get('attributes', []):
            if isinstance(attr, dict) and 'trait_type' in attr and 'value' in attr:
                attributes.append({
                    'trait_type': attr['trait_type'],
                    'value': str(attr['value'])
                })
        
        # Create Solana-compatible metadata
        solana_metadata = {
            'name': name,
            'symbol': 'RPLNT',  # ReplantWorld symbol
            'description': description,
            'image': image,
            'external_url': external_url,
            'attributes': attributes,
            'properties': {
                'files': [
                    {
                        'uri': image,
                        'type': 'image/png'
                    }
                ] if image else [],
                'category': 'image',
                'creators': [
                    {
                        'address': 'ReplantWorldCreatorAddress',  # Replace with actual creator address
                        'share': 100
                    }
                ]
            },
            'collection': {
                'name': 'ReplantWorld Trees',
                'family': 'ReplantWorld'
            }
        }
        
        return solana_metadata
    
    async def store_metadata(
        self,
        original_metadata: Dict[str, Any],
        solana_metadata: Dict[str, Any],
        token_id: str,
        contract_address: str
    ) -> Dict[str, str]:
        """
        Store metadata in multiple formats.
        
        Args:
            original_metadata: Original Sei metadata
            solana_metadata: Solana-compatible metadata
            token_id: Token ID
            contract_address: Contract address
            
        Returns:
            Dictionary with file paths and URIs
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create unique filename
        filename_base = f"{contract_address}_{token_id}_{timestamp}"
        
        # Store original metadata
        original_path = self.storage_dir / 'original' / f"{filename_base}_original.json"
        async with aiofiles.open(original_path, 'w') as f:
            await f.write(json.dumps(original_metadata, indent=2))
        
        # Store Solana metadata
        solana_path = self.storage_dir / 'onchain' / f"{filename_base}_solana.json"
        async with aiofiles.open(solana_path, 'w') as f:
            await f.write(json.dumps(solana_metadata, indent=2))
        
        # Create off-chain metadata with additional data
        offchain_metadata = {
            **solana_metadata,
            'migration_data': {
                'original_contract': contract_address,
                'original_token_id': token_id,
                'migration_timestamp': datetime.now().isoformat(),
                'source_blockchain': 'sei',
                'target_blockchain': 'solana',
                'migration_version': '1.0'
            },
            'verification': {
                'original_hash': hashlib.sha256(
                    json.dumps(original_metadata, sort_keys=True).encode()
                ).hexdigest(),
                'solana_hash': hashlib.sha256(
                    json.dumps(solana_metadata, sort_keys=True).encode()
                ).hexdigest()
            }
        }
        
        # Store off-chain metadata
        offchain_path = self.storage_dir / 'offchain' / f"{filename_base}_offchain.json"
        async with aiofiles.open(offchain_path, 'w') as f:
            await f.write(json.dumps(offchain_metadata, indent=2))
        
        # Generate URIs (in production, these would be IPFS or Arweave URIs)
        base_url = getattr(settings, 'METADATA_BASE_URL', 'https://metadata.replantworld.io')
        
        result = {
            'original_path': str(original_path),
            'solana_path': str(solana_path),
            'offchain_path': str(offchain_path),
            'solana_uri': f"{base_url}/onchain/{filename_base}_solana.json",
            'offchain_uri': f"{base_url}/offchain/{filename_base}_offchain.json",
            'original_uri': f"{base_url}/original/{filename_base}_original.json"
        }
        
        logger.info(
            "Metadata stored successfully",
            token_id=token_id,
            contract_address=contract_address,
            paths=result
        )
        
        return result
    
    async def get_metadata(self, token_id: str, contract_address: str, metadata_type: str = 'solana') -> Optional[Dict[str, Any]]:
        """
        Retrieve stored metadata.
        
        Args:
            token_id: Token ID
            contract_address: Contract address
            metadata_type: Type of metadata ('original', 'solana', 'offchain')
            
        Returns:
            Metadata dictionary or None if not found
        """
        # Find the most recent metadata file for this token
        search_pattern = f"{contract_address}_{token_id}_*_{metadata_type}.json"
        metadata_dir = self.storage_dir / metadata_type
        
        matching_files = list(metadata_dir.glob(search_pattern))
        if not matching_files:
            return None
        
        # Get the most recent file
        latest_file = max(matching_files, key=lambda p: p.stat().st_mtime)
        
        try:
            async with aiofiles.open(latest_file, 'r') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to read metadata file {latest_file}: {e}")
            return None
    
    def create_verification_command(self, transaction_signature: str) -> str:
        """
        Create a curl command to verify on-chain data.
        
        Args:
            transaction_signature: Solana transaction signature
            
        Returns:
            Curl command string
        """
        return f"""
# Verify transaction on Solana devnet
curl -X POST -H "Content-Type: application/json" -d '{{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getTransaction",
    "params": [
        "{transaction_signature}",
        {{
            "encoding": "json",
            "commitment": "confirmed",
            "maxSupportedTransactionVersion": 0
        }}
    ]
}}' https://api.devnet.solana.com

# Check transaction status
curl -X POST -H "Content-Type: application/json" -d '{{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getSignatureStatuses",
    "params": [
        ["{transaction_signature}"]
    ]
}}' https://api.devnet.solana.com

# View on Solana Explorer
echo "View on Solana Explorer: https://explorer.solana.com/tx/{transaction_signature}?cluster=devnet"
"""
