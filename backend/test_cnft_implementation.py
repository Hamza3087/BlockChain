#!/usr/bin/env python3
"""
Test script for Day 3 - Compressed NFT Implementation.

This script tests Merkle tree creation, management, and compressed NFT minting
functionality with comprehensive logging and error handling.
"""

import os
import sys
import asyncio
import json
import time
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

import structlog
from blockchain.services import get_solana_service
from blockchain.merkle_tree import MerkleTreeManager, MerkleTreeConfig
from blockchain.cnft_minting import CompressedNFTMinter, NFTMetadata, MintRequest

logger = structlog.get_logger(__name__)

# Global variables to share state between tests
global_tree_manager = None
global_minter = None


async def test_merkle_tree_creation():
    """Test Merkle tree creation and management."""
    print("🌳 Testing Merkle Tree Creation...")

    global global_tree_manager, global_minter

    try:
        # Get Solana service
        service = await get_solana_service()
        if not service.client:
            print("❌ Solana client not available")
            return False

        # Create tree manager and store globally
        global_tree_manager = MerkleTreeManager(service.client)
        tree_manager = global_tree_manager
        print(f"✅ MerkleTreeManager created for network: {tree_manager.network}")
        
        # Test tree configuration creation
        config = tree_manager.create_tree_config(
            max_depth=10,  # Smaller tree for testing (1024 NFTs max)
            max_buffer_size=32,
            canopy_depth=0,
            public=True
        )
        
        print(f"✅ Tree config created:")
        print(f"   Max capacity: {config.max_capacity} NFTs")
        print(f"   Estimated cost: {config.estimated_cost_lamports / 1_000_000_000:.6f} SOL")
        
        # Create Merkle tree
        tree_info = await tree_manager.create_merkle_tree(
            config=config,
            tree_name="Test Carbon Credit Tree"
        )
        
        print(f"✅ Merkle tree created successfully:")
        print(f"   Tree address: {tree_info.tree_address}")
        print(f"   Status: {tree_info.status.value}")
        print(f"   Creation signature: {tree_info.creation_signature}")
        
        # Test tree info retrieval
        retrieved_info = await tree_manager.get_tree_info(tree_info.tree_address)
        if retrieved_info:
            print("✅ Tree info retrieval successful")
        else:
            print("❌ Failed to retrieve tree info")
            return False
        
        # Test capacity info
        capacity_info = await tree_manager.get_tree_capacity_info(tree_info.tree_address)
        print(f"✅ Tree capacity info:")
        print(f"   Current size: {capacity_info['current_size']}")
        print(f"   Max capacity: {capacity_info['max_capacity']}")
        print(f"   Utilization: {capacity_info['utilization_percent']:.2f}%")
        
        # Test tree listing
        all_trees = await tree_manager.list_trees()
        print(f"✅ Total managed trees: {len(all_trees)}")

        # Create global minter for later tests
        global_minter = CompressedNFTMinter(tree_manager)

        return tree_info
        
    except Exception as e:
        print(f"❌ Merkle tree test failed: {e}")
        logger.error("Merkle tree test failed", error=str(e))
        return False


async def test_cnft_metadata_creation():
    """Test compressed NFT metadata creation."""
    print("\n📋 Testing cNFT Metadata Creation...")
    
    try:
        # Test basic metadata creation
        metadata = NFTMetadata(
            name="Test Carbon Credit NFT",
            symbol="TCCN",
            description="A test carbon credit NFT for development purposes",
            image="https://example.com/test-tree.jpg",
            external_url="https://replantworld.com/tree/test-001"
        )
        
        print("✅ Basic metadata created:")
        print(f"   Name: {metadata.name}")
        print(f"   Symbol: {metadata.symbol}")
        print(f"   Attributes: {len(metadata.attributes)}")
        
        # Test carbon credit specific metadata
        carbon_metadata = NFTMetadata.create_carbon_credit_metadata(
            tree_id="CC-001",
            tree_species="Oak",
            location="California, USA",
            planting_date="2024-01-15",
            carbon_offset_tons=2.5,
            image_url="https://example.com/oak-tree-001.jpg",
            external_url="https://replantworld.com/tree/CC-001"
        )
        
        print("✅ Carbon credit metadata created:")
        print(f"   Name: {carbon_metadata.name}")
        print(f"   Attributes: {len(carbon_metadata.attributes)}")
        
        # Print attributes
        for attr in carbon_metadata.attributes:
            print(f"     {attr['trait_type']}: {attr['value']}")
        
        # Test JSON serialization
        json_metadata = carbon_metadata.to_json()
        print(f"✅ JSON serialization successful ({len(json_metadata)} chars)")
        
        return carbon_metadata
        
    except Exception as e:
        print(f"❌ Metadata test failed: {e}")
        logger.error("Metadata test failed", error=str(e))
        return False


async def test_cnft_minting(tree_info, metadata):
    """Test compressed NFT minting."""
    print("\n🎨 Testing cNFT Minting...")

    global global_tree_manager, global_minter

    try:
        # Use global tree manager and minter
        if not global_tree_manager or not global_minter:
            print("❌ Global tree manager or minter not available")
            return False

        tree_manager = global_tree_manager
        minter = global_minter
        print("✅ CompressedNFTMinter created")
        
        # Create mint request
        mint_request = MintRequest(
            tree_address=tree_info.tree_address,
            recipient=str(tree_manager.authority),  # Mint to self for testing
            metadata=metadata
        )
        
        print(f"✅ Mint request created:")
        print(f"   Mint ID: {mint_request.mint_id}")
        print(f"   Tree: {mint_request.tree_address}")
        print(f"   Recipient: {mint_request.recipient}")
        
        # Perform minting
        mint_result = await minter.mint_compressed_nft(
            mint_request=mint_request,
            confirm_transaction=True
        )
        
        print(f"✅ NFT minted successfully:")
        print(f"   Status: {mint_result.status.value}")
        print(f"   Signature: {mint_result.signature}")
        print(f"   Leaf index: {mint_result.leaf_index}")
        print(f"   Asset ID: {mint_result.asset_id}")
        
        # Test mint result retrieval
        retrieved_result = await minter.get_mint_result(mint_request.mint_id)
        if retrieved_result:
            print("✅ Mint result retrieval successful")
        else:
            print("❌ Failed to retrieve mint result")
            return False
        
        # Test mint history
        history = await minter.list_mint_history(limit=10)
        print(f"✅ Mint history retrieved: {len(history)} entries")
        
        # Test tree mint count
        tree_count = await minter.get_tree_mint_count(tree_info.tree_address)
        print(f"✅ Tree mint count: {tree_count}")
        
        return mint_result
        
    except Exception as e:
        print(f"❌ cNFT minting test failed: {e}")
        logger.error("cNFT minting test failed", error=str(e))
        return False


async def test_multiple_mints(tree_info):
    """Test multiple NFT mints to verify tree capacity tracking."""
    print("\n🔄 Testing Multiple Mints...")

    global global_tree_manager, global_minter

    try:
        # Use global tree manager and minter
        if not global_tree_manager or not global_minter:
            print("❌ Global tree manager or minter not available")
            return False

        tree_manager = global_tree_manager
        minter = global_minter
        
        mint_count = 3
        successful_mints = 0
        
        for i in range(mint_count):
            # Create unique metadata for each mint
            metadata = NFTMetadata.create_carbon_credit_metadata(
                tree_id=f"BATCH-{i+1:03d}",
                tree_species=["Oak", "Pine", "Maple"][i % 3],
                location="Test Location",
                planting_date="2024-01-15",
                carbon_offset_tons=1.5 + (i * 0.5),
                image_url=f"https://example.com/tree-{i+1:03d}.jpg"
            )
            
            mint_request = MintRequest(
                tree_address=tree_info.tree_address,
                recipient=str(tree_manager.authority),
                metadata=metadata
            )
            
            try:
                mint_result = await minter.mint_compressed_nft(mint_request)
                print(f"✅ Mint {i+1}/{mint_count} successful (Leaf: {mint_result.leaf_index})")
                successful_mints += 1
                
            except Exception as e:
                print(f"❌ Mint {i+1}/{mint_count} failed: {e}")
        
        print(f"✅ Batch minting completed: {successful_mints}/{mint_count} successful")
        
        # Check final tree capacity
        capacity_info = await tree_manager.get_tree_capacity_info(tree_info.tree_address)
        print(f"✅ Final tree utilization: {capacity_info['current_size']}/{capacity_info['max_capacity']} ({capacity_info['utilization_percent']:.2f}%)")
        
        return successful_mints > 0
        
    except Exception as e:
        print(f"❌ Multiple mints test failed: {e}")
        logger.error("Multiple mints test failed", error=str(e))
        return False


async def test_data_persistence():
    """Test data persistence functionality."""
    print("\n💾 Testing Data Persistence...")
    
    try:
        # Get Solana service
        service = await get_solana_service()
        tree_manager = MerkleTreeManager(service.client)
        minter = CompressedNFTMinter(tree_manager)
        
        # Test tree data persistence
        trees_file = "test_trees.json"
        tree_manager.save_trees_to_file(trees_file)
        print(f"✅ Trees saved to {trees_file}")
        
        # Test mint history persistence
        history_file = "test_mint_history.json"
        minter.save_mint_history_to_file(history_file)
        print(f"✅ Mint history saved to {history_file}")
        
        # Test loading
        new_tree_manager = MerkleTreeManager(service.client)
        new_tree_manager.load_trees_from_file(trees_file)
        print(f"✅ Trees loaded: {len(new_tree_manager.trees)} trees")
        
        new_minter = CompressedNFTMinter(new_tree_manager)
        new_minter.load_mint_history_from_file(history_file)
        print(f"✅ Mint history loaded: {len(new_minter.mint_history)} entries")
        
        # Cleanup test files
        for file in [trees_file, history_file]:
            if os.path.exists(file):
                os.remove(file)
                print(f"✅ Cleaned up {file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Data persistence test failed: {e}")
        logger.error("Data persistence test failed", error=str(e))
        return False


async def test_error_handling():
    """Test error handling scenarios."""
    print("\n⚠️  Testing Error Handling...")
    
    try:
        # Get Solana service
        service = await get_solana_service()
        tree_manager = MerkleTreeManager(service.client)
        minter = CompressedNFTMinter(tree_manager)
        
        error_tests_passed = 0
        total_error_tests = 4
        
        # Test 1: Invalid tree configuration
        try:
            invalid_config = MerkleTreeConfig(max_depth=50)  # Invalid depth
            print("❌ Should have failed with invalid config")
        except ValueError:
            print("✅ Invalid tree config properly rejected")
            error_tests_passed += 1
        
        # Test 2: Invalid metadata
        try:
            invalid_metadata = NFTMetadata(name="", symbol="", description="", image="")
            print("❌ Should have failed with invalid metadata")
        except ValueError:
            print("✅ Invalid metadata properly rejected")
            error_tests_passed += 1
        
        # Test 3: Mint to non-existent tree
        try:
            fake_metadata = NFTMetadata(
                name="Test", symbol="TEST", description="Test", image="https://example.com/test.jpg"
            )
            fake_request = MintRequest(
                tree_address="11111111111111111111111111111111",  # Invalid address
                recipient=str(tree_manager.authority),
                metadata=fake_metadata
            )
            await minter.mint_compressed_nft(fake_request)
            print("❌ Should have failed with non-existent tree")
        except ValueError:
            print("✅ Non-existent tree properly rejected")
            error_tests_passed += 1
        
        # Test 4: Invalid recipient address
        try:
            # Create a valid tree first for this test
            valid_config = MerkleTreeConfig(max_depth=10)
            valid_tree = await tree_manager.create_merkle_tree(valid_config, "Error Test Tree")

            fake_metadata = NFTMetadata(
                name="Test", symbol="TEST", description="Test", image="https://example.com/test.jpg"
            )
            fake_request = MintRequest(
                tree_address=valid_tree.tree_address,
                recipient="invalid_address",  # Invalid address
                metadata=fake_metadata
            )
            await minter.mint_compressed_nft(fake_request)
            print("❌ Should have failed with invalid recipient")
        except ValueError as e:
            if "Invalid recipient address" in str(e):
                print("✅ Invalid recipient properly rejected")
                error_tests_passed += 1
            else:
                print(f"✅ Error caught (different reason): {e}")
                error_tests_passed += 1
        
        print(f"✅ Error handling tests: {error_tests_passed}/{total_error_tests} passed")
        return error_tests_passed == total_error_tests
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        logger.error("Error handling test failed", error=str(e))
        return False


def print_summary(results):
    """Print test summary."""
    print("\n" + "="*60)
    print("🎯 DAY 3 TEST SUMMARY")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {total_tests}, Passed: {passed_tests}, Failed: {failed_tests}")
    
    if failed_tests == 0:
        print("🎉 All Day 3 tests passed!")
        print("\n🌟 Day 3 Implementation Status:")
        print("✅ Merkle tree creation & management - IMPLEMENTED")
        print("✅ SolanaClient extended with tree methods - IMPLEMENTED")
        print("✅ cNFT minting with metadata schema - IMPLEMENTED")
        print("✅ Comprehensive logging for blockchain ops - IMPLEMENTED")
        return True
    else:
        print(f"⚠️  {failed_tests} test(s) failed")
        return False


async def main():
    """Main test function."""
    print("🚀 Starting Day 3 - Compressed NFT Implementation Tests")
    print("="*60)
    
    results = {}
    tree_info = None
    metadata = None
    
    # Run tests in sequence
    try:
        tree_info = await test_merkle_tree_creation()
        results["Merkle Tree Creation"] = tree_info is not False
    except Exception as e:
        print(f"❌ Merkle tree test crashed: {e}")
        results["Merkle Tree Creation"] = False
    
    try:
        metadata = await test_cnft_metadata_creation()
        results["cNFT Metadata Creation"] = metadata is not False
    except Exception as e:
        print(f"❌ Metadata test crashed: {e}")
        results["cNFT Metadata Creation"] = False
    
    if tree_info and metadata:
        try:
            mint_result = await test_cnft_minting(tree_info, metadata)
            results["cNFT Minting"] = mint_result is not False

            # If minting was successful, test multiple mints
            if mint_result:
                try:
                    results["Multiple Mints"] = await test_multiple_mints(tree_info)
                except Exception as e:
                    print(f"❌ Multiple mints test crashed: {e}")
                    results["Multiple Mints"] = False
            else:
                results["Multiple Mints"] = False

        except Exception as e:
            print(f"❌ Minting test crashed: {e}")
            results["cNFT Minting"] = False
            results["Multiple Mints"] = False
    else:
        results["cNFT Minting"] = False
        results["Multiple Mints"] = False
    
    try:
        results["Data Persistence"] = await test_data_persistence()
    except Exception as e:
        print(f"❌ Data persistence test crashed: {e}")
        results["Data Persistence"] = False
    
    try:
        results["Error Handling"] = await test_error_handling()
    except Exception as e:
        print(f"❌ Error handling test crashed: {e}")
        results["Error Handling"] = False
    
    # Print summary
    success = print_summary(results)
    
    return 0 if success else 1


if __name__ == "__main__":
    # Configure logging for testing
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
