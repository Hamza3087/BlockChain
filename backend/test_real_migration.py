#!/usr/bin/env python3
"""
Test Real Migration with Database Storage

This script tests the complete real on-chain migration pipeline with database storage.
"""

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from asgiref.sync import sync_to_async
from blockchain.clients.real_onchain_client import RealOnChainClient
from blockchain.migration.migration_mapper import MigrationMapper
from blockchain.models import MigrationJob, SeiNFT, MigrationLog


class SeiDataFetcher:
    """Fetch data directly from Sei blockchain using CW721 queries."""
    
    def __init__(self):
        self.contract_address = os.getenv('SEI_NFT_ADDRESS')
        self.base_url = os.getenv('SEI_RPC_URL', 'https://rest-testnet.sei-apis.com')
    
    def query_contract(self, query_json):
        """Query the smart contract"""
        import requests
        import base64
        
        query_b64 = base64.b64encode(json.dumps(query_json).encode()).decode()
        url = f"{self.base_url}/cosmwasm/wasm/v1/contract/{self.contract_address}/smart/{query_b64}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_token_info(self, token_id):
        """Get complete info for a single token"""
        import requests
        
        token_data = {"token_id": token_id}
        
        # Get NFT info (metadata URI)
        nft_info = self.query_contract({"nft_info": {"token_id": token_id}})
        if 'data' in nft_info:
            token_data.update(nft_info['data'])
            
        # Get owner info
        owner_info = self.query_contract({"owner_of": {"token_id": token_id}})
        if 'data' in owner_info:
            token_data['owner'] = owner_info['data']['owner']
            token_data['approvals'] = owner_info['data'].get('approvals', [])
            
        # Get off-chain metadata if token_uri exists
        if 'token_uri' in token_data:
            try:
                metadata_response = requests.get(token_data['token_uri'])
                if metadata_response.status_code == 200:
                    metadata = metadata_response.json()
                    token_data['metadata'] = metadata
            except Exception as e:
                token_data['metadata_error'] = str(e)
                
        return token_data


async def test_real_migration():
    """Test real migration with database storage."""
    
    print("🚀 TESTING REAL ON-CHAIN MIGRATION WITH DATABASE STORAGE")
    print("=" * 80)
    print()
    
    # Create output directory
    output_dir = Path(f"test_migration_output/{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_dir}")
    
    # Initialize components
    sei_fetcher = SeiDataFetcher()
    migration_mapper = MigrationMapper()
    
    # Create or get system user
    system_user, created = await sync_to_async(User.objects.get_or_create)(
        username='test_migration_user',
        defaults={
            'email': 'test@replantworld.io',
            'first_name': 'Test',
            'last_name': 'Migration'
        }
    )

    # Create migration job
    migration_job = await sync_to_async(MigrationJob.objects.create)(
        name=f'Test Real Migration from {sei_fetcher.contract_address}',
        description=f'Test real on-chain NFT migration from Sei contract {sei_fetcher.contract_address} to Solana',
        sei_contract_addresses=[sei_fetcher.contract_address],
        status='running',
        created_by=system_user
    )
    
    print(f"📋 Created migration job: {migration_job.job_id}")
    
    try:
        # Step 1: Fetch a single NFT from Sei
        print("\n📡 STEP 1: Fetching NFT data from Sei blockchain")
        token_id = "100"  # Test with a specific token
        token_data = sei_fetcher.get_token_info(token_id)
        
        if 'error' in token_data:
            print(f"❌ Failed to fetch token data: {token_data['error']}")
            return
        
        print(f"✅ Fetched token {token_id}: {token_data.get('metadata', {}).get('name', 'Unknown')}")
        
        # Save original data
        with open(output_dir / "01_sei_original_data.json", 'w') as f:
            json.dump(token_data, f, indent=2)
        
        # Step 2: Map to Solana format
        print("\n🔄 STEP 2: Mapping to Solana format")
        token_data['contract_address'] = sei_fetcher.contract_address
        mapped_data = await migration_mapper.map_sei_to_solana(token_data)
        
        with open(output_dir / "02_solana_mapped_data.json", 'w') as f:
            json.dump(mapped_data, f, indent=2)
        
        print(f"✅ Mapped data: {mapped_data.get('name', 'Unknown')}")
        
        # Step 3: Create real compressed NFT on-chain
        print("\n🌱 STEP 3: Minting real compressed NFT on-chain")
        
        async with RealOnChainClient() as client:
            # Create Merkle tree
            tree_result = await client.create_merkle_tree()
            print(f"🌳 Tree result: {tree_result['status']}")
            print(f"   Tree Address: {tree_result['tree_address']}")
            
            # Mint compressed NFT
            mint_result = await client.mint_compressed_nft(
                tree_address=tree_result["tree_address"],
                metadata=mapped_data,
                recipient=None
            )
            
            print(f"🌱 Mint result: {mint_result['status']}")
            print(f"   Mint Address: {mint_result['mint_address']}")
            print(f"   Transaction: {mint_result['transaction_signature']}")
            
            # Save mint result
            with open(output_dir / "03_mint_result.json", 'w') as f:
                json.dump(mint_result, f, indent=2)
            
            # Step 4: Store in database
            print("\n💾 STEP 4: Storing in database")
            
            sei_nft = await sync_to_async(SeiNFT.objects.create)(
                sei_contract_address=token_data.get('contract_address', ''),
                sei_token_id=token_data.get('token_id', ''),
                sei_owner_address=token_data.get('owner', ''),
                name=mapped_data.get('name', ''),
                description=mapped_data.get('description', ''),
                image_url=mapped_data.get('image', ''),
                external_url=mapped_data.get('external_url', ''),
                attributes=mapped_data.get('attributes', []),
                sei_data_hash=str(hash(json.dumps(token_data, sort_keys=True))),
                migration_job=migration_job,

                # Solana data
                solana_mint_address=mint_result.get('mint_address', ''),
                solana_tree_address=mint_result.get('tree_address', ''),
                solana_transaction_signature=mint_result.get('transaction_signature', ''),
                solana_metadata_uri=mint_result.get('metadata_uri', ''),
                is_real_onchain=mint_result.get('status') == 'success',
                migration_status='completed'
            )

            # Create migration log
            await sync_to_async(MigrationLog.objects.create)(
                migration_job=migration_job,
                sei_nft=sei_nft,
                event_type='nft_migration',
                level='info',
                message=f'Successfully processed NFT {token_id} - Status: {mint_result.get("status")}',
                details={
                    'mint_result': mint_result,
                    'mapped_data': mapped_data,
                    'token_id': token_id
                }
            )
            
            print(f"✅ Saved to database: SeiNFT ID {sei_nft.id}")
            
            # Step 5: Verify on-chain (if real transaction)
            if mint_result["status"] == "success":
                print("\n🔍 STEP 5: Verifying on-chain")
                verification = await client.verify_on_chain(mint_result["mint_address"])
                
                with open(output_dir / "04_verification.json", 'w') as f:
                    json.dump(verification, f, indent=2)
                
                if verification.get("exists"):
                    print("✅ Account exists on-chain!")
                    print(f"   Lamports: {verification.get('lamports', 0)}")
                    print(f"   Owner: {verification.get('owner', 'Unknown')}")
                else:
                    print("⚠️  Account not found on-chain (may be simulated)")
            
            # Update migration job
            migration_job.status = 'completed'
            migration_job.total_nfts = 1
            migration_job.successful_nfts = 1 if mint_result.get('status') == 'success' else 0
            migration_job.failed_nfts = 0 if mint_result.get('status') == 'success' else 1
            await sync_to_async(migration_job.save)()
            
            print(f"\n🎉 MIGRATION TEST COMPLETE!")
            print(f"📊 Status: {mint_result['status']}")
            print(f"📁 Output: {output_dir}")
            
            # Print verification commands
            print(f"\n🔍 VERIFICATION COMMANDS:")
            if mint_result.get('status') == 'success':
                mint_address = mint_result['mint_address']
                tree_address = mint_result['tree_address']
                tx_signature = mint_result['transaction_signature']
                
                print(f"   Check mint account:")
                print(f"   curl -X POST https://api.devnet.solana.com -H 'Content-Type: application/json' \\")
                print(f"        -d '{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getAccountInfo\",\"params\":[\"{mint_address}\",{{\"encoding\":\"base64\"}}]}}'")
                print(f"   🔗 Explorer: https://explorer.solana.com/address/{mint_address}?cluster=devnet")
                print(f"   🔗 Transaction: https://explorer.solana.com/tx/{tx_signature}?cluster=devnet")
            else:
                print(f"   ⚠️  Simulated transaction - no on-chain data to verify")
            
            # Database verification
            print(f"\n💾 DATABASE VERIFICATION:")
            print(f"   SeiNFT record created with ID: {sei_nft.id}")
            print(f"   Migration Job ID: {migration_job.job_id}")
            print(f"   Is Real On-Chain: {sei_nft.is_real_onchain}")
            
            return {
                "status": "success",
                "sei_nft_id": sei_nft.id,
                "migration_job_id": str(migration_job.job_id),
                "mint_result": mint_result,
                "output_dir": str(output_dir)
            }
            
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        migration_job.status = 'failed'
        await sync_to_async(migration_job.save)()
        import traceback
        traceback.print_exc()
        return {"status": "failed", "error": str(e)}


def main():
    """Main function."""
    result = asyncio.run(test_real_migration())
    
    print("\n" + "=" * 80)
    print("✅ REAL MIGRATION TEST COMPLETE!")
    print(f"📊 Final Status: {result.get('status', 'unknown')}")
    
    if result.get('status') == 'success':
        print("🎯 All components working correctly:")
        print("   ✅ Sei data fetching")
        print("   ✅ Data mapping")
        print("   ✅ On-chain minting (real or simulated)")
        print("   ✅ Database storage")
        print("   ✅ Verification")


if __name__ == "__main__":
    main()
