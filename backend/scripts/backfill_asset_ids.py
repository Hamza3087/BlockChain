#!/usr/bin/env python3
"""
Backfill asset IDs for the 10 minted cNFTs from the last migration run.
Updates both JSON files and database records.
"""

import json
import os
import sys
from pathlib import Path

# Add Django setup
sys.path.append(str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from blockchain.models import SeiNFT

# Asset IDs computed from tree + leaf index for the 10 minted cNFTs
ASSET_MAPPINGS = {
    '105': {
        'asset_id': 'HHqUQQYPvbdzSYNGkLh1PUZ6m7oSeJUyxuLrtPFuJhef',
        'leaf_index': 0,
        'tx': '5U2DPKGpfdShn9rHgUsTk69XCUeq9WqcjYLViEmfcpp8S5pxRy4YyNtuup2NFbubvk9NqC634fq5g1g5XKdLb7jp'
    },
    '106': {
        'asset_id': '4Uqcpk79iHMxxHD24DTaYtsYxixaJ357TzGv56V48jNy',
        'leaf_index': 1,
        'tx': '3ds8roYVoaXJH9XCaEQEQii3kRvnMA5e2BHopLXNVuU9yHRhVSuQWWKJpQgtzvUkfgDtA6YC8k1rtbgf1xMCpt83'
    },
    '101': {
        'asset_id': 'BKYzsW4XJzpGyNveaa4jWj5UzaXNPBwCDzFYsVidUyEi',
        'leaf_index': 2,
        'tx': '2jpSLSqNqyAsBWJKz1fV4La43jgqij9iLukfk7Ugx91EbL4rHSG4EeTk1Zx3TEgHduYsbMzFKFb74nVoCEqwEXCh'
    },
    '102': {
        'asset_id': '8PThSdJXNERU4TfoW1EphZWkZEFXB73txKUXwcZCC7kx',
        'leaf_index': 3,
        'tx': '3auvqB7pztFsYwn7Jp11mUybCzuJviw8nEjoBNyS2Vfq8EPo59EXonJtFTxqc4dpakrK55SsQzq4uuatJrHhyq2M'
    },
    '100': {
        'asset_id': '5H3VXmpvVXUtLeMBybwSWPcSoWruc7BsJeLES5TifoaF',
        'leaf_index': 4,
        'tx': '4u9t9xsmd2tN2E8T735wto1E2NUXBK859hyoLtzuMwByr1esr6y6gHWSie3aXrCX9Wu71eBuVp85YyPNUHM8QqUW'
    },
    '107': {
        'asset_id': '2KdmoKKZnXrjD1ZCipuujZkxfR8RgvPmWAHdufTkHqK4',
        'leaf_index': 5,
        'tx': '28cJVVNbkxzum9zYdk3KfKs8ZSkiBmZvhQ4yEZpDDuYWGCS7wLC3wA82Lk2JQow4ZrH3GxYhHiQZ9EFko1y1GMT4'
    },
    '103': {
        'asset_id': 'CYwxB8vCYGWuskuNsUZzCqp616GDXWzpcKmP9mbzMkMd',
        'leaf_index': 6,
        'tx': '3iBKuH1KnKviA2Q5WLdWax8YrFkp1aERmMPitBXmzSB5ukiXwcC8Vs75BJ6SiNR3a8Hnob9Xcy6WRsJxUQ98KwXY'
    },
    '104': {
        'asset_id': '4Y5Q9XAiYVgpza2Pt3yRMzft7CfyQBecimdw436dHZgd',
        'leaf_index': 7,
        'tx': '2oiyW8gvZ3z54hrnNY4ZpCm9p2rtWhPt9REsdqU4SYB3C1Y7MKZHo6KQDvqmT1c3Y48pESzUbGaUrwjMZdSVxsPE'
    },
    '1': {
        'asset_id': 'AQSYh4Wgbi2PhDSrVxUFuzVdLhZQQV4iadzvZQPwnjE6',
        'leaf_index': 8,
        'tx': '4SyCQ6Woa1tMPinWzkXJ3vcoVM2GFNVMm7mbfQpH4GoKVKm7iB7bbnnH7qQAJc2LF1YVNEeMKgTSFvricZPc4o3x'
    },
    '10': {
        'asset_id': 'Aeb4B7KFQMWRXR3CgBfc4XCygyyy1btFuTpVaLpyiyKJ',
        'leaf_index': 9,
        'tx': '31T8uPEwa5Wdsdjxj2yh69gRXaTgh7JaY5HesSPZ4xcgsYrTJeraTs9bekuSTLC8DEjFv5pRACkgrMXBAuDCrAVR'
    }
}

TREE_ADDRESS = 'erY15sCGJmk3H7y9BLZRLmmLgY8P4We1nGUsgBL5kJM'
MIGRATION_OUTPUT_DIR = Path('migration_output/20250828_123247')

def main():
    print("🔄 Backfilling asset IDs for 10 minted cNFTs...")
    
    updated_files = 0
    updated_db_records = 0
    
    # Update JSON files
    for token_id, data in ASSET_MAPPINGS.items():
        nft_folder = MIGRATION_OUTPUT_DIR / f'nft_{token_id}'
        mint_result_file = nft_folder / '05_solana_mint_result.json'
        
        if mint_result_file.exists():
            with open(mint_result_file, 'r') as f:
                mint_result = json.load(f)
            
            # Update with asset_id and leaf_index
            mint_result['mint_address'] = data['asset_id']
            mint_result['asset_id'] = data['asset_id']
            mint_result['leaf_index'] = data['leaf_index']
            
            # Write back
            with open(mint_result_file, 'w') as f:
                json.dump(mint_result, f, indent=2)
            
            print(f"✅ Updated {mint_result_file}")
            updated_files += 1
        else:
            print(f"⚠️  File not found: {mint_result_file}")
    
    # Update database records
    for token_id, data in ASSET_MAPPINGS.items():
        try:
            nft = SeiNFT.objects.get(
                sei_contract_address='sei1lxsu3g5zsgrrgwgd2d7qplscye2ngyfpq2nm9hmh2h8rjrt8yj9qtdv2vc',
                sei_token_id=token_id
            )
            
            nft.solana_mint_address = data['asset_id']
            nft.solana_asset_id = data['asset_id']
            nft.save()
            
            print(f"✅ Updated DB record for token {token_id}")
            updated_db_records += 1
            
        except SeiNFT.DoesNotExist:
            print(f"⚠️  DB record not found for token {token_id}")
        except Exception as e:
            print(f"❌ Error updating DB record for token {token_id}: {e}")
    
    print(f"\n📊 Summary:")
    print(f"   Updated JSON files: {updated_files}")
    print(f"   Updated DB records: {updated_db_records}")
    print(f"   Tree address: {TREE_ADDRESS}")
    
    # Create verification file
    verification_data = {
        'tree_address': TREE_ADDRESS,
        'network': 'devnet',
        'helius_endpoint': 'https://devnet.helius-rpc.com/?api-key=4cd90c8d-a05e-4c44-bf4c-d4d41889d31e',
        'assets': ASSET_MAPPINGS
    }
    
    verification_file = MIGRATION_OUTPUT_DIR / 'asset_ids_verification.json'
    with open(verification_file, 'w') as f:
        json.dump(verification_data, f, indent=2)
    
    print(f"📋 Verification data saved to: {verification_file}")

if __name__ == '__main__':
    main()
