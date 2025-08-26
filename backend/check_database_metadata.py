#!/usr/bin/env python3
"""
Database Metadata Checker

This script checks and displays all metadata stored in the database
for migrated NFTs and trees.
"""

import os
import django
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from blockchain.models import SeiNFT, Tree, MigrationJob

def check_database_metadata():
    """Check and display all metadata stored in the database."""
    
    print("🔍 DATABASE METADATA INSPECTION")
    print("=" * 80)
    print()
    
    # Database statistics
    sei_nft_count = SeiNFT.objects.count()
    tree_count = Tree.objects.count()
    migration_job_count = MigrationJob.objects.count()
    
    print("📊 DATABASE STATISTICS:")
    print(f"   SeiNFT Records: {sei_nft_count}")
    print(f"   Tree Records: {tree_count}")
    print(f"   Migration Jobs: {migration_job_count}")
    print()
    
    if sei_nft_count == 0:
        print("❌ No NFT data found in database")
        print("   Run: python manage.py run_complete_migration --max-nfts=1")
        return
    
    # Check SeiNFT metadata
    print("🌱 SEI NFT METADATA:")
    print("-" * 60)
    
    for i, nft in enumerate(SeiNFT.objects.all().order_by('id'), 1):
        print(f"{i}. TOKEN #{nft.sei_token_id} - {nft.name}")
        print(f"   Contract: {nft.sei_contract_address}")
        print(f"   Owner: {nft.sei_owner_address}")
        print(f"   Migration Status: {nft.migration_status}")
        print(f"   Description: {nft.description}")
        print(f"   Image URL: {nft.image_url}")
        print(f"   External URL: {nft.external_url}")
        print(f"   Solana Mint: {nft.solana_mint_address}")
        print(f"   Created: {nft.created_at}")
        print()

        # Show attributes (stored as JSON)
        if nft.attributes:
            print("   📋 NFT ATTRIBUTES:")
            try:
                attributes = nft.attributes
                if isinstance(attributes, str):
                    attributes = json.loads(attributes)

                if isinstance(attributes, list):
                    for attr in attributes:
                        if isinstance(attr, dict):
                            trait_type = attr.get('trait_type', 'Unknown')
                            trait_value = attr.get('value', 'Unknown')
                            print(f"      - {trait_type}: {trait_value}")
                elif isinstance(attributes, dict):
                    for key, value in attributes.items():
                        print(f"      - {key}: {value}")
                else:
                    print(f"      Raw attributes: {attributes}")
            except Exception as e:
                print(f"      Error parsing attributes: {e}")
        print()
    
    # Check Tree metadata
    print("🌳 TREE METADATA:")
    print("-" * 60)
    
    for i, tree in enumerate(Tree.objects.all().order_by('created_at'), 1):
        print(f"{i}. TREE #{tree.tree_id} - {tree.species}")
        print(f"   Mint Address: {tree.mint_address}")
        print(f"   Tree Address: {tree.merkle_tree_address}")
        print(f"   Location: {tree.location_name}")
        print(f"   Coordinates: ({tree.location_latitude}, {tree.location_longitude})")
        print(f"   Planted Date: {tree.planted_date}")
        print(f"   Planter: {tree.planter}")
        print(f"   Status: {tree.status}")
        print(f"   Created: {tree.created_at}")
        print()
        
        # Show additional metadata if available
        if hasattr(tree, 'metadata') and tree.metadata:
            print("   📋 ADDITIONAL TREE METADATA:")
            try:
                if isinstance(tree.metadata, str):
                    metadata = json.loads(tree.metadata)
                else:
                    metadata = tree.metadata
                
                for key, value in metadata.items():
                    print(f"      {key}: {value}")
            except Exception as e:
                print(f"      Error parsing tree metadata: {e}")
        print()
    
    # Check Migration Jobs
    print("📋 MIGRATION JOB METADATA:")
    print("-" * 60)
    
    recent_jobs = MigrationJob.objects.all().order_by('-created_at')[:5]
    for i, job in enumerate(recent_jobs, 1):
        print(f"{i}. JOB #{job.job_id}")
        print(f"   Name: {job.name}")
        print(f"   Status: {job.status}")
        print(f"   Description: {job.description}")
        print(f"   Contracts: {job.sei_contract_addresses}")
        print(f"   Created: {job.created_at}")
        print(f"   Updated: {job.updated_at}")

        if hasattr(job, 'error_message') and job.error_message:
            print(f"   Error: {job.error_message}")

        if hasattr(job, 'result_data') and job.result_data:
            print("   📋 RESULT DATA:")
            try:
                if isinstance(job.result_data, str):
                    result = json.loads(job.result_data)
                else:
                    result = job.result_data

                for key, value in result.items():
                    if isinstance(value, dict):
                        print(f"      {key}: {json.dumps(value, indent=8)[:100]}...")
                    else:
                        print(f"      {key}: {value}")
            except Exception as e:
                print(f"      Error parsing result data: {e}")
        print()

def check_specific_nft_metadata(token_id: str = None):
    """Check metadata for a specific NFT."""
    
    if token_id:
        nfts = SeiNFT.objects.filter(sei_token_id=token_id)
        trees = Tree.objects.filter(tree_id=token_id)
    else:
        nfts = SeiNFT.objects.all()[:1]
        trees = Tree.objects.all()[:1]
    
    if not nfts.exists():
        print(f"❌ No NFT found with token ID: {token_id}")
        return
    
    nft = nfts.first()
    tree = trees.first() if trees.exists() else None
    
    print(f"🔍 DETAILED METADATA FOR TOKEN #{nft.sei_token_id}")
    print("=" * 80)
    print()
    
    # NFT Model Fields
    print("📋 SEI NFT MODEL FIELDS:")
    for field in nft._meta.fields:
        field_name = field.name
        field_value = getattr(nft, field_name)
        print(f"   {field_name}: {field_value}")
    print()
    
    # Tree Model Fields (if exists)
    if tree:
        print("🌳 TREE MODEL FIELDS:")
        for field in tree._meta.fields:
            field_name = field.name
            field_value = getattr(tree, field_name)
            print(f"   {field_name}: {field_value}")
        print()
    
    # Check migration output files
    print("📁 MIGRATION OUTPUT FILES:")
    migration_dirs = [d for d in os.listdir('migration_output') if os.path.isdir(f'migration_output/{d}')]
    
    if migration_dirs:
        latest_migration = sorted(migration_dirs)[-1]
        nft_dir = f"migration_output/{latest_migration}/nft_{nft.sei_token_id}"
        
        if os.path.exists(nft_dir):
            print(f"   Directory: {nft_dir}")
            files = os.listdir(nft_dir)
            for file in sorted(files):
                file_path = f"{nft_dir}/{file}"
                print(f"   📄 {file}")
                
                if file.endswith('.json'):
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        print(f"      Size: {len(json.dumps(data))} characters")
                        
                        # Show key fields
                        if isinstance(data, dict):
                            key_fields = ['name', 'symbol', 'description', 'image', 'mint_address', 'tree_address', 'status']
                            for key in key_fields:
                                if key in data:
                                    value = data[key]
                                    if len(str(value)) > 50:
                                        print(f"      {key}: {str(value)[:50]}...")
                                    else:
                                        print(f"      {key}: {value}")
                    except Exception as e:
                        print(f"      Error reading file: {e}")
                print()

def show_database_schema():
    """Show the database schema for NFT-related models."""
    
    print("📊 DATABASE SCHEMA:")
    print("=" * 80)
    print()
    
    models = [SeiNFT, Tree, MigrationJob]
    
    for model in models:
        print(f"🏗️  {model.__name__} Model:")
        print(f"   Table: {model._meta.db_table}")
        print("   Fields:")
        
        for field in model._meta.fields:
            field_type = field.__class__.__name__
            field_name = field.name
            max_length = getattr(field, 'max_length', None)
            null = field.null
            blank = field.blank
            
            field_info = f"      {field_name}: {field_type}"
            if max_length:
                field_info += f"(max_length={max_length})"
            if null:
                field_info += " [NULL]"
            if blank:
                field_info += " [BLANK]"
            
            print(field_info)
        print()

def main():
    """Main function with menu options."""
    
    print("🔍 DATABASE METADATA CHECKER")
    print("=" * 50)
    print()
    print("Choose an option:")
    print("1. Check all metadata")
    print("2. Check specific NFT metadata")
    print("3. Show database schema")
    print("4. Quick summary")
    print()
    
    choice = input("Enter choice (1-4) or press Enter for option 1: ").strip()
    
    if choice == "2":
        token_id = input("Enter token ID (or press Enter for first NFT): ").strip()
        check_specific_nft_metadata(token_id if token_id else None)
    elif choice == "3":
        show_database_schema()
    elif choice == "4":
        # Quick summary
        print("📊 QUICK SUMMARY:")
        print(f"   SeiNFT Records: {SeiNFT.objects.count()}")
        print(f"   Tree Records: {Tree.objects.count()}")
        print(f"   Migration Jobs: {MigrationJob.objects.count()}")
        
        if SeiNFT.objects.exists():
            latest_nft = SeiNFT.objects.latest('created_at')
            print(f"   Latest NFT: #{latest_nft.sei_token_id} - {latest_nft.name}")
        
        if Tree.objects.exists():
            latest_tree = Tree.objects.latest('created_at')
            print(f"   Latest Tree: {latest_tree.mint_address}")
    else:
        check_database_metadata()

if __name__ == "__main__":
    main()
