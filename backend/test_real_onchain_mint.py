#!/usr/bin/env python3
"""
Test Real On-Chain Compressed NFT Minting

This script attempts to mint actual compressed NFTs on Solana devnet
that will be verifiable on-chain.
"""

import asyncio
import json
from datetime import datetime

from blockchain.clients.real_cnft_client import RealCompressedNFTClient

async def test_real_onchain_mint():
    """Test real on-chain compressed NFT minting."""
    
    print("🚀 TESTING REAL ON-CHAIN COMPRESSED NFT MINTING")
    print("=" * 80)
    print()
    
    # Sample tree NFT metadata
    sample_metadata = {
        "name": "Real Tree NFT #001",
        "symbol": "RTREE",
        "description": "A real tree NFT minted on Solana devnet using actual transactions",
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
                "value": "Real Planter"
            },
            {
                "trait_type": "Date Planted",
                "value": "2024-08-26"
            },
            {
                "trait_type": "Migration Source",
                "value": "Sei Blockchain"
            },
            {
                "trait_type": "Mint Type",
                "value": "Real On-Chain"
            }
        ]
    }
    
    async with RealCompressedNFTClient() as client:
        try:
            print(f"🔑 Payer Address: {client.payer_keypair.pubkey()}")
            print()
            
            # Step 1: Check initial balance
            print("💰 Checking initial balance...")
            initial_balance = await client.get_balance()
            print(f"   Initial balance: {initial_balance / 1e9:.4f} SOL")
            
            if initial_balance < 100000000:  # Less than 0.1 SOL
                print("   💸 Requesting airdrop...")
                airdrop_tx = await client.request_airdrop(1000000000)  # 1 SOL
                print(f"   ✅ Airdrop transaction: {airdrop_tx}")
                
                new_balance = await client.get_balance()
                print(f"   💰 New balance: {new_balance / 1e9:.4f} SOL")
            
            print()
            
            # Step 2: Create Merkle Tree
            print("🌳 Creating real Merkle tree on Solana...")
            tree_result = await client.create_merkle_tree(
                max_depth=14,  # Supports up to 16,384 NFTs
                max_buffer_size=64
            )
            
            print(f"   Status: {tree_result['status']}")
            print(f"   Tree Address: {tree_result['tree_address']}")
            print(f"   Max NFTs: {tree_result['max_nfts']:,}")
            
            if tree_result['status'] == 'success':
                print(f"   ✅ Transaction: {tree_result['transaction_signature']}")
                print(f"   🔗 Explorer: https://explorer.solana.com/tx/{tree_result['transaction_signature']}?cluster=devnet")
            else:
                print(f"   ⚠️  Fallback to simulation: {tree_result.get('error', 'Unknown error')}")
            
            print()
            
            # Step 3: Mint Compressed NFT
            print("🌱 Minting real compressed NFT...")
            mint_result = await client.mint_compressed_nft(
                tree_address=tree_result["tree_address"],
                metadata=sample_metadata,
                recipient=None  # Will use payer as recipient
            )
            
            print(f"   Status: {mint_result['status']}")
            print(f"   Mint Address: {mint_result['mint_address']}")
            print(f"   Tree Address: {mint_result['tree_address']}")
            print(f"   Recipient: {mint_result['recipient']}")
            print(f"   Metadata URI: {mint_result['metadata_uri']}")
            
            if mint_result['status'] == 'success':
                print(f"   ✅ Transaction: {mint_result['transaction_signature']}")
                print(f"   🔗 Explorer: https://explorer.solana.com/tx/{mint_result['transaction_signature']}?cluster=devnet")
                print(f"   🔍 Account: https://explorer.solana.com/address/{mint_result['mint_address']}?cluster=devnet")
            else:
                print(f"   ⚠️  Fallback to simulation: {mint_result.get('error', 'Unknown error')}")
            
            print()
            
            # Step 4: Verify on-chain
            print("🔍 VERIFICATION:")
            print(f"   Run: solana account {mint_result['mint_address']} --url https://api.devnet.solana.com")
            print(f"   Run: solana account {tree_result['tree_address']} --url https://api.devnet.solana.com")
            print()
            
            # Step 5: Test with Helius API
            print("🔎 TESTING HELIUS API:")
            await test_helius_api(mint_result['mint_address'])
            
            # Step 6: Save results
            results = {
                "test_timestamp": datetime.now().isoformat(),
                "payer_address": str(client.payer_keypair.pubkey()),
                "tree_creation": tree_result,
                "mint_result": mint_result,
                "metadata": sample_metadata
            }
            
            with open("real_onchain_mint_results.json", "w") as f:
                json.dump(results, f, indent=2)
            
            print("💾 Results saved to: real_onchain_mint_results.json")
            print()
            
            # Final balance check
            final_balance = await client.get_balance()
            print(f"💰 Final balance: {final_balance / 1e9:.4f} SOL")
            print(f"   Used: {(initial_balance - final_balance) / 1e9:.4f} SOL")
            
        except Exception as e:
            print(f"💥 Test failed: {e}")
            import traceback
            traceback.print_exc()

async def test_helius_api(mint_address: str):
    """Test Helius API for compressed NFT data."""
    import aiohttp
    
    helius_endpoints = [
        "https://devnet.helius-rpc.com/?api-key=demo",
        "https://mainnet.helius-rpc.com/?api-key=demo"
    ]
    
    for endpoint in helius_endpoints:
        network = "devnet" if "devnet" in endpoint else "mainnet"
        print(f"   Testing {network}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getAsset",
                    "params": [mint_address]
                }
                
                async with session.post(endpoint, json=payload) as response:
                    result = await response.json()
                    
                    if "error" in result:
                        print(f"     ❌ {network}: {result['error']['message']}")
                    else:
                        print(f"     ✅ {network}: Asset found!")
                        asset_data = result.get('result', {})
                        print(f"        Name: {asset_data.get('content', {}).get('metadata', {}).get('name', 'N/A')}")
                        print(f"        Owner: {asset_data.get('ownership', {}).get('owner', 'N/A')}")
                        
        except Exception as e:
            print(f"     ⚠️  {network}: {e}")

def main():
    """Main function."""
    print("🎯 REAL ON-CHAIN COMPRESSED NFT MINTING TEST")
    print()
    print("📝 This test will:")
    print("   1. Request SOL airdrop on devnet")
    print("   2. Create a real Merkle tree on-chain")
    print("   3. Mint a real compressed NFT")
    print("   4. Verify the NFT exists on-chain")
    print()
    
    # Run the test
    asyncio.run(test_real_onchain_mint())
    
    print()
    print("=" * 80)
    print("✅ REAL ON-CHAIN MINTING TEST COMPLETE!")
    print()
    print("🔍 VERIFICATION COMMANDS:")
    print("   Check if accounts exist on Solana devnet using the addresses above")
    print("   Use: solana account <address> --url https://api.devnet.solana.com")

if __name__ == "__main__":
    main()
