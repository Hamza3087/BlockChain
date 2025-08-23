"""
Solana blockchain configuration for ReplantWorld.
"""

import os
from typing import List, Dict, Any

# Default Solana RPC endpoints for different networks
SOLANA_RPC_ENDPOINTS = {
    'devnet': [
        {
            'name': 'Solana Devnet (Official)',
            'url': 'https://api.devnet.solana.com',
            'priority': 1
        },
        {
            'name': 'Helius Devnet',
            'url': 'https://devnet.helius-rpc.com/?api-key=demo',
            'priority': 2
        },
        {
            'name': 'QuickNode Devnet',
            'url': 'https://api.devnet.solana.com',
            'priority': 3
        }
    ],
    'mainnet': [
        {
            'name': 'Solana Mainnet (Official)',
            'url': 'https://api.mainnet-beta.solana.com',
            'priority': 1
        },
        {
            'name': 'Helius Mainnet',
            'url': 'https://mainnet.helius-rpc.com/?api-key=demo',
            'priority': 2
        },
        {
            'name': 'QuickNode Mainnet',
            'url': 'https://api.mainnet-beta.solana.com',
            'priority': 3
        }
    ],
    'testnet': [
        {
            'name': 'Solana Testnet (Official)',
            'url': 'https://api.testnet.solana.com',
            'priority': 1
        }
    ]
}

# Metaplex Bubblegum Program IDs
BUBBLEGUM_PROGRAM_IDS = {
    'devnet': 'BGUMAp9Gq7iTEuizy4pqaxsTyUCBK68MDfK752saRPUY',
    'mainnet': 'BGUMAp9Gq7iTEuizy4pqaxsTyUCBK68MDfK752saRPUY',
    'testnet': 'BGUMAp9Gq7iTEuizy4pqaxsTyUCBK68MDfK752saRPUY'
}

# SPL Token Program IDs
SPL_TOKEN_PROGRAM_ID = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
SPL_ASSOCIATED_TOKEN_PROGRAM_ID = 'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL'

# Metaplex Program IDs
METAPLEX_PROGRAM_IDS = {
    'token_metadata': 'metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s',
    'candy_machine': 'cndy3Z4yapfJBmL3ShUp5exZKqR3z33thTzeNMm2gRZ',
    'auction_house': 'hausS13jsjafwWwGqZTUQRmWyvyxn9EQpqMwV1PBBmk'
}


def get_solana_config() -> Dict[str, Any]:
    """Get Solana configuration from environment variables."""
    network = os.getenv('SOLANA_NETWORK', 'devnet').lower()
    
    # Get RPC endpoints for the network
    rpc_endpoints = SOLANA_RPC_ENDPOINTS.get(network, SOLANA_RPC_ENDPOINTS['devnet'])
    
    # Allow custom RPC endpoint override
    custom_rpc = os.getenv('SOLANA_RPC_URL')
    if custom_rpc:
        rpc_endpoints = [
            {
                'name': 'Custom RPC',
                'url': custom_rpc,
                'priority': 0  # Highest priority
            }
        ] + rpc_endpoints
    
    return {
        'network': network,
        'rpc_endpoints': rpc_endpoints,
        'bubblegum_program_id': BUBBLEGUM_PROGRAM_IDS.get(network),
        'max_retries': int(os.getenv('SOLANA_MAX_RETRIES', '3')),
        'retry_delay': float(os.getenv('SOLANA_RETRY_DELAY', '1.0')),
        'health_check_interval': int(os.getenv('SOLANA_HEALTH_CHECK_INTERVAL', '60')),
        'timeout': int(os.getenv('SOLANA_TIMEOUT', '30')),
        'keypair_path': os.getenv('SOLANA_KEYPAIR_PATH', '~/.config/solana/id.json')
    }


def get_bubblegum_program_id(network: str = None) -> str:
    """Get Bubblegum program ID for the specified network."""
    if network is None:
        network = os.getenv('SOLANA_NETWORK', 'devnet').lower()
    
    return BUBBLEGUM_PROGRAM_IDS.get(network, BUBBLEGUM_PROGRAM_IDS['devnet'])


def get_rpc_endpoints(network: str = None) -> List[Dict[str, Any]]:
    """Get RPC endpoints for the specified network."""
    if network is None:
        network = os.getenv('SOLANA_NETWORK', 'devnet').lower()

    return SOLANA_RPC_ENDPOINTS.get(network, SOLANA_RPC_ENDPOINTS['devnet'])


def get_migration_config() -> Dict[str, Any]:
    """Get migration configuration from environment variables."""
    return {
        # Sei blockchain configuration
        'sei_rpc_url': os.getenv('SEI_RPC_URL', 'https://rpc.sei-apis.com'),
        'sei_network': os.getenv('SEI_NETWORK', 'pacific-1'),
        'ipfs_gateway': os.getenv('IPFS_GATEWAY', 'https://ipfs.io/ipfs/'),

        # Request configuration
        'request_timeout': int(os.getenv('MIGRATION_REQUEST_TIMEOUT', '30')),
        'connect_timeout': int(os.getenv('MIGRATION_CONNECT_TIMEOUT', '10')),
        'batch_delay': float(os.getenv('MIGRATION_BATCH_DELAY', '0.1')),
        'max_migration_duration_hours': int(os.getenv('MAX_MIGRATION_DURATION_HOURS', '24')),

        # Mapping rules
        'mapping_rules': {
            'max_name_length': int(os.getenv('MIGRATION_MAX_NAME_LENGTH', '32')),
            'max_description_length': int(os.getenv('MIGRATION_MAX_DESCRIPTION_LENGTH', '200')),
            'max_symbol_length': int(os.getenv('MIGRATION_MAX_SYMBOL_LENGTH', '10')),
            'default_symbol': os.getenv('MIGRATION_DEFAULT_SYMBOL', 'TREE'),
            'image_url_transformations': {
                'ipfs_gateway': os.getenv('IPFS_GATEWAY', 'https://ipfs.io/ipfs/'),
                'supported_formats': ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']
            },
            'attribute_mappings': {
                'trait_type': 'trait_type',
                'value': 'value',
                'display_type': 'display_type'
            },
            'required_fields': ['name', 'image'],
            'carbon_credit_detection': {
                'keywords': ['carbon', 'offset', 'credit', 'tree', 'forest', 'environmental'],
                'attribute_names': ['carbon_offset', 'co2_offset', 'environmental_impact']
            }
        },

        # Validation rules
        'validation_rules': {
            'data_integrity': {
                'hash_validation': os.getenv('MIGRATION_HASH_VALIDATION', 'true').lower() == 'true',
                'required_fields': ['contract_address', 'token_id', 'name'],
                'max_field_lengths': {
                    'name': int(os.getenv('MIGRATION_MAX_NAME_LENGTH', '200')),
                    'description': int(os.getenv('MIGRATION_MAX_DESCRIPTION_LENGTH', '1000')),
                    'image_url': int(os.getenv('MIGRATION_MAX_IMAGE_URL_LENGTH', '500'))
                }
            },
            'metadata_integrity': {
                'validate_json_structure': os.getenv('MIGRATION_VALIDATE_JSON', 'true').lower() == 'true',
                'validate_attributes': os.getenv('MIGRATION_VALIDATE_ATTRIBUTES', 'true').lower() == 'true',
                'max_attributes': int(os.getenv('MIGRATION_MAX_ATTRIBUTES', '50')),
                'required_metadata_fields': ['name']
            },
            'blockchain_integrity': {
                'validate_addresses': os.getenv('MIGRATION_VALIDATE_ADDRESSES', 'true').lower() == 'true',
                'validate_token_ids': os.getenv('MIGRATION_VALIDATE_TOKEN_IDS', 'true').lower() == 'true',
                'check_duplicates': os.getenv('MIGRATION_CHECK_DUPLICATES', 'true').lower() == 'true'
            },
            'progress_tracking': {
                'checkpoint_interval': int(os.getenv('MIGRATION_CHECKPOINT_INTERVAL', '100')),
                'progress_report_interval': int(os.getenv('MIGRATION_PROGRESS_INTERVAL', '10'))
            },
            'rollback': {
                'max_rollback_depth': int(os.getenv('MIGRATION_MAX_ROLLBACK_DEPTH', '1000')),
                'rollback_timeout_seconds': int(os.getenv('MIGRATION_ROLLBACK_TIMEOUT', '300')),
                'preserve_logs': os.getenv('MIGRATION_PRESERVE_LOGS', 'true').lower() == 'true'
            }
        }
    }
