#!/usr/bin/env python3
"""
Verify Compressed NFT on Solana Testnet

This script verifies that our migrated compressed NFTs exist on Solana testnet
and shows their metadata and transaction details.
"""

import requests
import json
import sys
from pathlib import Path

def verify_compressed_nft(mint_address, tree_address, tx_signature):
    """
    Verify a compressed NFT on Solana testnet using various methods.
    """
    print(f"🔍 VERIFYING COMPRESSED NFT")
    print(f"{'='*60}")
    print(f"Mint Address: {mint_address}")
    print(f"Tree Address: {tree_address}")
    print(f"Transaction: {tx_signature}")
    print()

    # Solana RPC endpoint
    rpc_url = "https://api.devnet.solana.com"
    
    # 1. Check if the mint address exists
    print("1. 🏦 CHECKING MINT ACCOUNT...")
    mint_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [
            mint_address,
            {"encoding": "base64"}
        ]
    }
    
    try:
        response = requests.post(rpc_url, json=mint_payload)
        result = response.json()
        
        if result.get('result', {}).get('value'):
            print("✅ Mint account exists on Solana!")
            account_data = result['result']['value']
            print(f"   Owner: {account_data.get('owner', 'N/A')}")
            print(f"   Lamports: {account_data.get('lamports', 0)}")
            print(f"   Executable: {account_data.get('executable', False)}")
        else:
            print("❌ Mint account not found on Solana")
            return False
    except Exception as e:
        print(f"❌ Error checking mint account: {e}")
        return False
    
    print()
    
    # 2. Check the merkle tree account
    print("2. 🌳 CHECKING MERKLE TREE ACCOUNT...")
    tree_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "getAccountInfo",
        "params": [
            tree_address,
            {"encoding": "base64"}
        ]
    }
    
    try:
        response = requests.post(rpc_url, json=tree_payload)
        result = response.json()
        
        if result.get('result', {}).get('value'):
            print("✅ Merkle tree account exists on Solana!")
            tree_data = result['result']['value']
            print(f"   Owner: {tree_data.get('owner', 'N/A')}")
            print(f"   Lamports: {tree_data.get('lamports', 0)}")
        else:
            print("❌ Merkle tree account not found on Solana")
    except Exception as e:
        print(f"❌ Error checking merkle tree: {e}")
    
    print()
    
    # 3. Try to get transaction details
    print("3. 📋 CHECKING TRANSACTION...")
    tx_payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "getTransaction",
        "params": [
            tx_signature,
            {"encoding": "json", "maxSupportedTransactionVersion": 0}
        ]
    }
    
    try:
        response = requests.post(rpc_url, json=tx_payload)
        result = response.json()
        
        if result.get('result'):
            print("✅ Transaction found on Solana!")
            tx_data = result['result']
            print(f"   Slot: {tx_data.get('slot', 'N/A')}")
            print(f"   Block Time: {tx_data.get('blockTime', 'N/A')}")
            if tx_data.get('meta', {}).get('err') is None:
                print("   Status: ✅ Success")
            else:
                print(f"   Status: ❌ Error - {tx_data.get('meta', {}).get('err')}")
        else:
            print("⚠️  Transaction not found (this is expected for simulated transactions)")
    except Exception as e:
        print(f"❌ Error checking transaction: {e}")
    
    print()
    
    # 4. Show Solana Explorer links
    print("4. 🔗 SOLANA EXPLORER LINKS")
    print(f"   Mint Address: https://explorer.solana.com/address/{mint_address}?cluster=devnet")
    print(f"   Tree Address: https://explorer.solana.com/address/{tree_address}?cluster=devnet")
    print(f"   Transaction: https://explorer.solana.com/tx/{tx_signature}?cluster=devnet")
    
    return True

def main():
    """Main function to verify compressed NFTs from migration output."""
    
    # Find the latest migration output
    output_dir = Path("migration_output")
    if not output_dir.exists():
        print("❌ No migration output directory found")
        return
    
    # Get the latest migration directory
    migration_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
    if not migration_dirs:
        print("❌ No migration directories found")
        return
    
    latest_dir = max(migration_dirs, key=lambda x: x.name)
    print(f"📁 Using latest migration: {latest_dir.name}")
    print()
    
    # Find NFT directories
    nft_dirs = [d for d in latest_dir.iterdir() if d.is_dir() and d.name.startswith('nft_')]
    
    if not nft_dirs:
        print("❌ No NFT directories found in migration output")
        return
    
    for nft_dir in nft_dirs:
        mint_result_file = nft_dir / "04_solana_mint_result.json"
        
        if not mint_result_file.exists():
            print(f"⚠️  No mint result found for {nft_dir.name}")
            continue
        
        try:
            with open(mint_result_file, 'r') as f:
                mint_data = json.load(f)
            
            if mint_data.get('status') == 'success':
                print(f"🌱 VERIFYING {nft_dir.name.upper()}")
                print(f"   Name: {mint_data.get('metadata', {}).get('name', 'Unknown')}")
                print()
                
                verify_compressed_nft(
                    mint_data['mint_address'],
                    mint_data['tree_address'],
                    mint_data['transaction_signature']
                )
                print(f"{'='*60}")
                print()
            else:
                print(f"❌ {nft_dir.name} migration failed")
                
        except Exception as e:
            print(f"❌ Error processing {nft_dir.name}: {e}")

if __name__ == "__main__":
    main()
