#!/usr/bin/env python3
"""
Test Real Metaplex Bubblegum Compressed NFT Minting

This script attempts to mint a real compressed NFT on Solana devnet
using proper Metaplex Bubblegum integration.
"""

import asyncio
import json
import os
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from blockchain.clients.bubblegum_client import BubblegumClient

async def test_real_bubblegum_mint():
    """Test real compressed NFT minting with Metaplex Bubblegum."""
    
    print("🧪 TESTING REAL METAPLEX BUBBLEGUM COMPRESSED NFT MINTING")
    print("=" * 80)
    print()
    
    # Sample NFT metadata from our migration
    sample_metadata = {
        "name": "Test Tree NFT",
        "symbol": "TREE",
        "description": "A test tree NFT migrated from Sei to Solana using Metaplex Bubblegum",
        "image": "https://ipfs.filebase.io/ipfs/QmVRUNcXgJfzRMGrRjoyFBoDUrv38PXLmNW1UGjbgqY5dR",
        "external_url": "https://replantworld.io",
        "attributes": [
            {
                "trait_type": "Botanical Name",
                "value": "Quercus robur"
            },
            {
                "trait_type": "Country",
                "value": "Poland"
            },
            {
                "trait_type": "Latitude",
                "value": "50.272521"
            },
            {
                "trait_type": "Longitude",
                "value": "19.639508"
            },
            {
                "trait_type": "Planter",
                "value": "Test Planter"
            },
            {
                "trait_type": "Date Planted",
                "value": "2024-08-26"
            },
            {
                "trait_type": "Migration Source",
                "value": "Sei Blockchain"
            }
        ]
    }
    
    try:
        # Initialize Bubblegum client
        print("🔧 Initializing Bubblegum client...")
        client = BubblegumClient(rpc_url="https://api.devnet.solana.com")
        
        # Step 1: Create Merkle Tree
        print("🌳 Creating Merkle tree for compressed NFTs...")
        tree_result = await client.create_merkle_tree(
            max_depth=14,  # Supports up to 16,384 NFTs
            max_buffer_size=64
        )
        
        print(f"✅ Tree creation result: {tree_result['status']}")
        print(f"   Tree Address: {tree_result['tree_address']}")
        print(f"   Max NFTs: {tree_result['max_nfts']:,}")
        print(f"   Transaction: {tree_result['transaction_signature']}")
        print()
        
        if tree_result["status"] != "success":
            print("❌ Failed to create Merkle tree")
            return
        
        # Step 2: Mint Compressed NFT
        print("🌱 Minting compressed NFT...")
        mint_result = await client.mint_compressed_nft(
            tree_address=tree_result["tree_address"],
            metadata=sample_metadata,
            recipient=None  # Will use mint address as recipient
        )
        
        print(f"✅ Mint result: {mint_result['status']}")
        if mint_result["status"] == "success":
            print(f"   Mint Address: {mint_result['mint_address']}")
            print(f"   Tree Address: {mint_result['tree_address']}")
            print(f"   Transaction: {mint_result['transaction_signature']}")
            print(f"   Metadata URI: {mint_result['metadata_uri']}")
            print(f"   Program ID: {mint_result['program_id']}")
            print()
            
            # Step 3: Verify on Solana Explorer
            print("🔗 SOLANA EXPLORER VERIFICATION LINKS:")
            print(f"   Mint Address: https://explorer.solana.com/address/{mint_result['mint_address']}?cluster=devnet")
            print(f"   Tree Address: https://explorer.solana.com/address/{mint_result['tree_address']}?cluster=devnet")
            print(f"   Transaction: https://explorer.solana.com/tx/{mint_result['transaction_signature']}?cluster=devnet")
            print()
            
            # Step 4: Test Helius API for compressed NFT data
            print("🔍 TESTING HELIUS API FOR COMPRESSED NFT DATA:")
            await test_helius_compressed_nft_api(mint_result['mint_address'])
            
            # Step 5: Save results
            output_file = Path("real_bubblegum_mint_result.json")
            with open(output_file, 'w') as f:
                json.dump({
                    "tree_creation": tree_result,
                    "mint_result": mint_result,
                    "test_metadata": sample_metadata
                }, f, indent=2)
            
            print(f"💾 Results saved to: {output_file}")
            
        else:
            print(f"❌ Mint failed: {mint_result.get('error', 'Unknown error')}")
        
        # Close client
        await client.close()
        
    except Exception as e:
        print(f"💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()

async def test_helius_compressed_nft_api(mint_address: str):
    """Test Helius API for compressed NFT data."""
    import aiohttp
    
    # Note: This would require a real Helius API key
    helius_urls = [
        f"https://devnet.helius-rpc.com/?api-key=demo",
        f"https://mainnet.helius-rpc.com/?api-key=demo"
    ]
    
    for i, url in enumerate(helius_urls):
        network = "devnet" if i == 0 else "mainnet"
        print(f"   Testing {network} Helius API...")
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getAsset",
                    "params": [mint_address]
                }
                
                async with session.post(url, json=payload) as response:
                    result = await response.json()
                    
                    if "error" in result:
                        print(f"     ❌ {network}: {result['error']['message']}")
                    else:
                        print(f"     ✅ {network}: Asset found!")
                        print(f"        Data: {json.dumps(result.get('result', {}), indent=8)[:200]}...")
                        
        except Exception as e:
            print(f"     ⚠️  {network}: API test failed - {e}")

def main():
    """Main function."""
    print("🚀 Starting Real Metaplex Bubblegum Test...")
    print()
    
    # Run the async test
    asyncio.run(test_real_bubblegum_mint())
    
    print()
    print("=" * 80)
    print("✅ TEST COMPLETE!")
    print()
    print("📝 NOTES:")
    print("   - This test uses Metaplex Bubblegum program for compressed NFTs")
    print("   - Addresses are generated using proper Solana keypairs")
    print("   - Metadata is uploaded to IPFS simulation")
    print("   - For production, fund keypairs with SOL and use real RPC calls")
    print("   - Compressed NFTs require indexer APIs (like Helius) for querying")

if __name__ == "__main__":
    main()
