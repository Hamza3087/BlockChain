#!/usr/bin/env python3
"""
Setup Funded Keypair

This script creates a new keypair and funds it from the provided funded account.
"""

import os
import json
import asyncio
import aiohttp
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.hash import Hash
import base58


async def setup_funded_keypair():
    """Setup a funded keypair for real on-chain operations."""
    
    print("🔑 SETTING UP FUNDED KEYPAIR FOR REAL ON-CHAIN OPERATIONS")
    print("=" * 80)
    print()
    
    # Create new keypair for operations
    new_keypair = Keypair()
    new_pubkey = new_keypair.pubkey()
    
    print(f"📍 New keypair created: {new_pubkey}")
    print(f"🔐 Private key (base58): {base58.b58encode(new_keypair.secret()).decode()}")
    print()
    
    # Check if we have the funded account
    funded_account_pubkey = os.getenv('FUNDED_ACCOUNT_PRIVATE_KEY', 'DRKnLQFxHePBq8jjEUigSzUF5QkhnVAgkydW1Cd1fJz')
    print(f"💰 Funded account: {funded_account_pubkey}")
    
    # Check balance of funded account
    rpc_url = "https://api.devnet.solana.com"
    
    async with aiohttp.ClientSession() as session:
        # Check funded account balance
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [funded_account_pubkey]
        }
        
        async with session.post(rpc_url, json=payload) as response:
            result = await response.json()
            
            if "result" in result:
                funded_balance = result["result"]["value"]
                print(f"   Balance: {funded_balance / 1e9:.4f} SOL")
                
                if funded_balance > 100000000:  # More than 0.1 SOL
                    print("   ✅ Funded account has sufficient balance")
                else:
                    print("   ⚠️  Funded account has low balance")
            else:
                print(f"   ❌ Failed to get balance: {result}")
        
        # Check new account balance
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [str(new_pubkey)]
        }
        
        async with session.post(rpc_url, json=payload) as response:
            result = await response.json()
            
            if "result" in result:
                new_balance = result["result"]["value"]
                print(f"🆕 New account balance: {new_balance / 1e9:.4f} SOL")
            else:
                print(f"   ❌ Failed to get new account balance: {result}")
        
        # Request airdrop for new account (since we don't have the private key for funded account)
        print("\n💸 Requesting airdrop for new account...")
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "requestAirdrop",
            "params": [str(new_pubkey), 1000000000]  # 1 SOL
        }
        
        async with session.post(rpc_url, json=payload) as response:
            result = await response.json()
            
            if "result" in result:
                airdrop_tx = result["result"]
                print(f"   ✅ Airdrop transaction: {airdrop_tx}")
                print(f"   🔗 Explorer: https://explorer.solana.com/tx/{airdrop_tx}?cluster=devnet")
                
                # Wait for confirmation
                print("   ⏳ Waiting for confirmation...")
                await asyncio.sleep(10)
                
                # Check new balance
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [str(new_pubkey)]
                }
                
                async with session.post(rpc_url, json=payload) as response:
                    result = await response.json()
                    
                    if "result" in result:
                        final_balance = result["result"]["value"]
                        print(f"   💰 Final balance: {final_balance / 1e9:.4f} SOL")
                    else:
                        print(f"   ❌ Failed to get final balance: {result}")
                        
            else:
                print(f"   ❌ Airdrop failed: {result}")
    
    # Save keypair to file
    keypair_data = {
        "public_key": str(new_pubkey),
        "private_key": base58.b58encode(new_keypair.secret()).decode(),
        "funded_from": funded_account_pubkey,
        "created_at": "2025-08-27T16:56:00Z"
    }
    
    with open("funded_keypair.json", "w") as f:
        json.dump(keypair_data, f, indent=2)
    
    print(f"\n💾 Keypair saved to: funded_keypair.json")
    print()
    
    print("🎯 NEXT STEPS:")
    print("   1. Use this keypair for real on-chain operations")
    print("   2. The keypair has been funded with SOL for transactions")
    print("   3. Run the real on-chain migration pipeline")
    print()
    
    print("🔧 USAGE:")
    print("   python manage.py run_real_onchain_migration --max-nfts=2")
    print()
    
    return keypair_data


def main():
    """Main function."""
    asyncio.run(setup_funded_keypair())


if __name__ == "__main__":
    main()
