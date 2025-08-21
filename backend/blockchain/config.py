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
