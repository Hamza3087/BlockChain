#!/usr/bin/env python3
"""
Quick Database Metadata Checker

Simple script to check what metadata is stored in the database.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from blockchain.models import SeiNFT, Tree, MigrationJob

def main():
    """Quick metadata check."""
    
    print("🔍 QUICK DATABASE METADATA CHECK")
    print("=" * 60)
    print()
    
    # Statistics
    sei_count = SeiNFT.objects.count()
    tree_count = Tree.objects.count()
    job_count = MigrationJob.objects.count()
    
    print(f"📊 Records: SeiNFT={sei_count}, Tree={tree_count}, Jobs={job_count}")
    print()
    
    if sei_count == 0:
        print("❌ No data found. Run migration first:")
        print("   python manage.py run_complete_migration --max-nfts=1")
        return
    
    # Show latest NFT
    nft = SeiNFT.objects.latest('created_at')
    print(f"🌱 Latest NFT: #{nft.sei_token_id} - {nft.name}")
    print(f"   Contract: {nft.sei_contract_address}")
    print(f"   Owner: {nft.sei_owner_address}")
    print(f"   Status: {nft.migration_status}")
    print(f"   Image: {nft.image_url}")
    print()
    
    # Show attributes
    if nft.attributes:
        print("📋 Attributes:")
        for attr in nft.attributes:
            trait_type = attr.get('trait_type', 'Unknown')
            value = attr.get('value', 'Unknown')
            print(f"   - {trait_type}: {value}")
        print()
    
    # Show latest tree
    if tree_count > 0:
        tree = Tree.objects.latest('created_at')
        print(f"🌳 Latest Tree: {tree.species}")
        print(f"   Mint: {tree.mint_address}")
        print(f"   Tree: {tree.merkle_tree_address}")
        print(f"   Location: {tree.location_name} ({tree.location_latitude}, {tree.location_longitude})")
        print(f"   Planted: {tree.planted_date}")
        print(f"   Status: {tree.status}")
        print()
    
    # Show latest job
    if job_count > 0:
        job = MigrationJob.objects.latest('created_at')
        print(f"📋 Latest Job: {job.name}")
        print(f"   Status: {job.status}")
        print(f"   Processed: {job.processed_nfts}/{job.total_nfts}")
        print(f"   Success: {job.successful_migrations}")
        print(f"   Failed: {job.failed_migrations}")
        print()
    
    print("✅ Metadata check complete!")

if __name__ == "__main__":
    main()
