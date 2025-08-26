#!/usr/bin/env python3
"""
Migration Summary Report

This script generates a comprehensive summary of the NFT migration from Sei to Solana,
showing all the data that was successfully processed and stored.
"""

import json
import os
import django
from pathlib import Path
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_backend.settings')
django.setup()

from blockchain.models import SeiNFT, Tree, MigrationJob

def generate_migration_summary():
    """Generate a comprehensive migration summary."""
    
    print("🚀 COMPLETE NFT MIGRATION SUMMARY")
    print("=" * 80)
    print()
    
    # Database Statistics
    print("📊 DATABASE STATISTICS")
    print("-" * 40)
    sei_nft_count = SeiNFT.objects.count()
    tree_count = Tree.objects.count()
    job_count = MigrationJob.objects.count()
    
    print(f"SeiNFT Records: {sei_nft_count}")
    print(f"Tree Records: {tree_count}")
    print(f"Migration Jobs: {job_count}")
    print()
    
    # Migration Jobs Summary
    if job_count > 0:
        print("📋 MIGRATION JOBS SUMMARY")
        print("-" * 40)
        jobs = MigrationJob.objects.all().order_by('-created_at')[:5]  # Latest 5 jobs
        
        for job in jobs:
            print(f"Job ID: {job.id}")
            print(f"  Name: {job.name}")
            print(f"  Status: {job.status}")
            print(f"  Total NFTs: {job.total_nfts}")
            print(f"  Successful: {job.successful_nfts}")
            print(f"  Failed: {job.failed_nfts}")
            print(f"  Created: {job.created_at}")
            print()
    
    # Detailed NFT Records
    if sei_nft_count > 0:
        print("🌱 MIGRATED NFT DETAILS")
        print("-" * 40)
        
        nfts = SeiNFT.objects.all().order_by('sei_token_id')
        
        for nft in nfts:
            print(f"Token ID: {nft.sei_token_id}")
            print(f"  Name: {nft.name}")
            print(f"  Species: {getattr(nft, 'description', 'N/A')}")
            print(f"  Owner: {nft.sei_owner_address}")
            print(f"  Status: {nft.migration_status}")
            print(f"  Image: {nft.image_url}")
            
            # Find corresponding Tree record
            try:
                # Note: We need to find the tree by matching some criteria
                # since there's no direct foreign key from SeiNFT to Tree
                trees = Tree.objects.filter(species__icontains=nft.name.split()[0] if nft.name else "")
                if trees.exists():
                    tree = trees.first()
                    print(f"  🌳 Solana Data:")
                    print(f"    Mint Address: {tree.mint_address}")
                    print(f"    Merkle Tree: {tree.merkle_tree_address}")
                    print(f"    Species: {tree.species}")
                    print(f"    Location: {tree.location_name}")
                    print(f"    Coordinates: ({tree.location_latitude}, {tree.location_longitude})")
                    print(f"    Planted: {tree.planted_date}")
                    print(f"    Planter: {tree.planter.username if tree.planter else 'Unknown'}")
            except Exception as e:
                print(f"    ⚠️  Tree data lookup error: {e}")
            
            print()
    
    # File System Summary
    print("📁 MIGRATION OUTPUT FILES")
    print("-" * 40)
    
    output_dir = Path("migration_output")
    if output_dir.exists():
        migration_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir()], 
                              key=lambda x: x.name, reverse=True)
        
        for i, migration_dir in enumerate(migration_dirs[:3]):  # Latest 3 migrations
            print(f"Migration {i+1}: {migration_dir.name}")
            
            nft_dirs = [d for d in migration_dir.iterdir() if d.is_dir() and d.name.startswith('nft_')]
            print(f"  NFTs Processed: {len(nft_dirs)}")
            
            for nft_dir in nft_dirs:
                mint_result_file = nft_dir / "04_solana_mint_result.json"
                if mint_result_file.exists():
                    try:
                        with open(mint_result_file, 'r') as f:
                            mint_data = json.load(f)
                        
                        if mint_data.get('status') == 'success':
                            metadata = mint_data.get('metadata', {})
                            print(f"    ✅ {nft_dir.name}: {metadata.get('name', 'Unknown')}")
                            print(f"       Mint: {mint_data.get('mint_address', 'N/A')}")
                            print(f"       Tree: {mint_data.get('tree_address', 'N/A')}")
                        else:
                            print(f"    ❌ {nft_dir.name}: Failed")
                    except Exception as e:
                        print(f"    ⚠️  {nft_dir.name}: Error reading data - {e}")
            print()
    
    # Sample Compressed NFT Data
    print("🎯 SAMPLE COMPRESSED NFT DATA")
    print("-" * 40)
    
    # Find a successful mint result to show as example
    output_dir = Path("migration_output")
    if output_dir.exists():
        latest_dir = max([d for d in output_dir.iterdir() if d.is_dir()], 
                        key=lambda x: x.name, default=None)
        
        if latest_dir:
            nft_dirs = [d for d in latest_dir.iterdir() if d.is_dir() and d.name.startswith('nft_')]
            
            for nft_dir in nft_dirs:
                mint_result_file = nft_dir / "04_solana_mint_result.json"
                if mint_result_file.exists():
                    try:
                        with open(mint_result_file, 'r') as f:
                            mint_data = json.load(f)
                        
                        if mint_data.get('status') == 'success':
                            print(f"Sample NFT: {mint_data.get('metadata', {}).get('name', 'Unknown')}")
                            print(f"Mint Address: {mint_data.get('mint_address', 'N/A')}")
                            print(f"Tree Address: {mint_data.get('tree_address', 'N/A')}")
                            print(f"Transaction: {mint_data.get('transaction_signature', 'N/A')}")
                            print()
                            
                            print("Metadata Attributes:")
                            attributes = mint_data.get('metadata', {}).get('attributes', [])
                            for attr in attributes[:8]:  # Show first 8 attributes
                                print(f"  {attr.get('trait_type', 'Unknown')}: {attr.get('value', 'N/A')}")
                            
                            if len(attributes) > 8:
                                print(f"  ... and {len(attributes) - 8} more attributes")
                            
                            break
                    except Exception as e:
                        continue
    
    print()
    print("=" * 80)
    print("✅ MIGRATION SUMMARY COMPLETE")
    print()
    print("🔗 To verify on Solana testnet (when using real minting):")
    print("   - Visit: https://explorer.solana.com/?cluster=devnet")
    print("   - Search for the mint addresses shown above")
    print()
    print("📝 Note: Current implementation uses simulated minting for testing.")
    print("   To mint real compressed NFTs, update the SolanaClient to use")
    print("   actual Solana transactions instead of simulation.")

if __name__ == "__main__":
    generate_migration_summary()
