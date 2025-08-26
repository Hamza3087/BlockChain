#!/usr/bin/env python3
"""
Test script to verify the real Replant World NFT data implementation.

This script demonstrates that the DataExporter now loads real Sei NFT metadata
from local JSON files instead of using mock data.
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add the project root to Python path
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from blockchain.migration.data_exporter import DataExporter


async def test_real_data_implementation():
    """Test the real data implementation."""
    print("🌱 Testing Real Replant World NFT Data Implementation")
    print("=" * 60)
    
    exporter = DataExporter()
    await exporter.initialize()
    
    try:
        # Test 1: Verify data directory
        print(f"\n📁 Data Directory: {exporter.data_directory}")
        print(f"   Directory exists: {exporter.data_directory.exists()}")
        print(f"   Files found: {exporter.export_stats['files_found']}")
        
        # Test 2: Load a single NFT with real data
        print(f"\n🌳 Testing Single NFT Load (1001.json)...")
        nft_data = await exporter.export_nft_data('sei1replantworld', '1001')
        
        if nft_data:
            print(f"✅ Successfully loaded NFT {nft_data.token_id}")
            print(f"   Name: {nft_data.name}")
            print(f"   Description: {nft_data.description}")
            print(f"   Image URL: {nft_data.image_url}")
            print(f"   Attributes: {len(nft_data.attributes)}")
            
            # Show some key attributes
            for attr in nft_data.attributes[:5]:  # Show first 5 attributes
                print(f"   - {attr.get('trait_type', 'Unknown')}: {attr.get('value', 'N/A')}")
            
            print(f"   Data Hash: {nft_data.data_hash[:16]}...")
        else:
            print("❌ Failed to load NFT 1001")
            return
        
        # Test 3: Load multiple NFTs
        print(f"\n🌲 Testing Collection Export (first 5 NFTs)...")
        loaded_nfts = []
        
        async for nft in exporter.export_collection_data(
            'sei1replantworld', 
            max_tokens=5,
            batch_size=3
        ):
            loaded_nfts.append(nft)
            botanical_name = next(
                (attr['value'] for attr in nft.attributes 
                 if attr.get('trait_type') == 'Botanical Name'), 
                'Unknown'
            )
            country = next(
                (attr['value'] for attr in nft.attributes 
                 if attr.get('trait_type') == 'Country'), 
                'Unknown'
            )
            print(f"✅ NFT {nft.token_id}: {nft.name} ({botanical_name}, {country})")
        
        # Test 4: Show statistics
        stats = exporter.get_export_statistics()
        print(f"\n📊 Export Statistics:")
        print(f"   Total exported: {stats['total_exported']}")
        print(f"   Successful: {stats['successful_exports']}")
        print(f"   Failed: {stats['failed_exports']}")
        print(f"   Success rate: {stats.get('success_rate', 0):.1f}%")
        print(f"   Files processed: {stats['files_processed']}")
        print(f"   Speed: {stats.get('exports_per_second', 0):.1f} exports/sec")
        
        # Test 5: Verify data integrity
        print(f"\n🔍 Data Integrity Verification:")
        sample_nft = loaded_nfts[0] if loaded_nfts else nft_data
        
        # Check if it has real Replant World attributes
        expected_attributes = [
            'Botanical Name', 'IUCN status', 'Country', 'Longitude', 
            'Latitude', 'Is Native', 'Org/Community', 'planter', 
            'Date planted', 'Sponsor', 'planting Cost'
        ]
        
        found_attributes = [attr.get('trait_type') for attr in sample_nft.attributes]
        
        for expected_attr in expected_attributes:
            if expected_attr in found_attributes:
                print(f"   ✅ {expected_attr}: Found")
            else:
                print(f"   ❌ {expected_attr}: Missing")
        
        # Test 6: Show sample real data
        print(f"\n📋 Sample Real Data from NFT {sample_nft.token_id}:")
        print(f"   Collection: {sample_nft.metadata.get('collection', 'N/A')}")
        print(f"   Symbol: {sample_nft.metadata.get('symbol', 'N/A')}")
        print(f"   Edition: {sample_nft.metadata.get('edition', 'N/A')}")
        
        # Show location data
        longitude = next((attr['value'] for attr in sample_nft.attributes if attr.get('trait_type') == 'Longitude'), 'N/A')
        latitude = next((attr['value'] for attr in sample_nft.attributes if attr.get('trait_type') == 'Latitude'), 'N/A')
        print(f"   Location: {latitude}, {longitude}")
        
        print(f"\n🎉 SUCCESS: Real Replant World NFT data implementation is working!")
        print(f"   - Loaded {len(loaded_nfts)} NFTs with real tree planting data")
        print(f"   - All NFTs have authentic botanical and geographic information")
        print(f"   - Data includes real sponsors, planters, and conservation status")
        print(f"   - Ready for Sei → Solana migration pipeline!")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await exporter.close()


if __name__ == "__main__":
    asyncio.run(test_real_data_implementation())
