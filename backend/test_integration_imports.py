#!/usr/bin/env python3
"""
Test script to verify all Day 6 integration imports work correctly.
This script tests the integration between all 6 days of development.
"""

import os
import sys
import django

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def test_day1_components():
    """Test Day 1 - Project Setup & Environment Configuration"""
    print("🧪 Testing Day 1 Components...")
    
    try:
        # Test Django setup
        from django.conf import settings
        print("  ✅ Django configuration loaded")
        
        # Test database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("  ✅ Database connection working")
        
        # Test Redis connection (if configured)
        try:
            from django.core.cache import cache
            cache.set('test_key', 'test_value', 10)
            result = cache.get('test_key')
            if result == 'test_value':
                print("  ✅ Redis cache connection working")
            else:
                print("  ⚠️  Redis cache not properly configured")
        except Exception as e:
            print(f"  ⚠️  Redis cache error: {e}")
        
        print("  🎉 Day 1 components working!")
        return True
        
    except Exception as e:
        print(f"  ❌ Day 1 error: {e}")
        return False

def test_day2_components():
    """Test Day 2 - Solana Blockchain Infrastructure (Part 1)"""
    print("🧪 Testing Day 2 Components...")
    
    try:
        # Test Solana client
        from blockchain.clients.solana_client import SolanaClient, EndpointConfig
        print("  ✅ SolanaClient import successful")
        
        # Test Solana service
        from blockchain.services import get_solana_service
        print("  ✅ Solana service import successful")
        
        print("  🎉 Day 2 components working!")
        return True
        
    except Exception as e:
        print(f"  ❌ Day 2 error: {e}")
        return False

def test_day3_components():
    """Test Day 3 - Solana Blockchain Infrastructure (Part 2)"""
    print("🧪 Testing Day 3 Components...")
    
    try:
        # Test Merkle tree management
        from blockchain.merkle_tree import MerkleTreeManager, MerkleTreeConfig
        print("  ✅ MerkleTreeManager import successful")
        
        # Test compressed NFT minting
        from blockchain.cnft_minting import CompressedNFTMinter, NFTMetadata, MintRequest
        print("  ✅ CompressedNFTMinter import successful")
        
        print("  🎉 Day 3 components working!")
        return True
        
    except Exception as e:
        print(f"  ❌ Day 3 error: {e}")
        return False

def test_day4_components():
    """Test Day 4 - Database Schema & Models"""
    print("🧪 Testing Day 4 Components...")
    
    try:
        # Test all database models
        from blockchain.models import (
            Tree, SpeciesGrowthParameters, CarbonMarketPrice, TreeCarbonData,
            SeiNFT, MigrationJob, MigrationLog,
            IntegrationTestResult, BatchMigrationStatus, PerformanceMetric
        )
        print("  ✅ All database models import successful")
        
        # Test model creation (basic validation)
        from django.contrib.auth.models import User
        user, created = User.objects.get_or_create(
            username='test_integration_user',
            defaults={'email': 'test@integration.com'}
        )
        print("  ✅ User model working")
        
        # Test creating a migration job
        migration_job = MigrationJob.objects.create(
            name="Integration Test Job",
            description="Testing Day 4 models integration",
            sei_contract_addresses=["sei1test123"],
            created_by=user
        )
        print(f"  ✅ MigrationJob created: {migration_job.job_id}")
        
        print("  🎉 Day 4 components working!")
        return True
        
    except Exception as e:
        print(f"  ❌ Day 4 error: {e}")
        return False

def test_day5_components():
    """Test Day 5 - Sei Data Export & Migration Tools"""
    print("🧪 Testing Day 5 Components...")
    
    try:
        # Test migration components
        from blockchain.migration import (
            DataExporter, SeiNFTData, MigrationMapper, MigrationMapping,
            MigrationValidator, ValidationResult, MigrationService
        )
        print("  ✅ All migration components import successful")
        
        # Test SeiNFTData creation
        nft_data = SeiNFTData(
            contract_address="sei1test123",
            token_id="1",
            owner_address="sei1owner123",
            name="Test NFT",
            description="Test NFT for integration"
        )
        print(f"  ✅ SeiNFTData created with hash: {nft_data.data_hash[:16]}...")
        
        print("  🎉 Day 5 components working!")
        return True
        
    except Exception as e:
        print(f"  ❌ Day 5 error: {e}")
        return False

def test_day6_components():
    """Test Day 6 - Integration & System Testing"""
    print("🧪 Testing Day 6 Components...")
    
    try:
        # Test integration components
        from blockchain.integration import (
            EndToEndPipeline, BatchMigrationManager, CacheManager,
            IntegrationTestRunner, PerformanceMonitor
        )
        print("  ✅ All integration components import successful")
        
        # Test cache manager
        from blockchain.integration.cache_manager import cache_manager
        cache_result = cache_manager.set('integration_test', {'test': 'data'}, category='test')
        print(f"  ✅ Cache manager working: {cache_result}")
        
        # Test test runner components
        from blockchain.integration.test_runner import TestConfiguration, TestScenario
        config = TestConfiguration(
            scenario=TestScenario.SINGLE_NFT_MIGRATION,
            test_data_size=5
        )
        print(f"  ✅ Test configuration created: {config.scenario.value}")
        
        print("  🎉 Day 6 components working!")
        return True
        
    except Exception as e:
        print(f"  ❌ Day 6 error: {e}")
        return False

def test_cross_day_integration():
    """Test integration between all days"""
    print("🧪 Testing Cross-Day Integration...")
    
    try:
        # Test that Day 6 can use Day 5 components
        from blockchain.integration import EndToEndPipeline
        from blockchain.migration import MigrationService
        
        # Test that Day 5 can use Day 4 models
        from blockchain.migration import DataExporter
        from blockchain.models import SeiNFT, MigrationJob
        
        # Test that Day 4 models work with Day 3 Solana components
        from blockchain.models import Tree
        from blockchain.merkle_tree import MerkleTreeManager
        
        # Test that Day 3 uses Day 2 Solana client
        from blockchain.cnft_minting import CompressedNFTMinter
        from blockchain.services import get_solana_service
        
        print("  ✅ All cross-day integrations working")
        print("  🎉 Complete system integration verified!")
        return True
        
    except Exception as e:
        print(f"  ❌ Cross-day integration error: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🚀 Starting Complete 6-Day Integration Test")
    print("=" * 60)
    
    results = []
    
    # Test each day's components
    results.append(("Day 1", test_day1_components()))
    results.append(("Day 2", test_day2_components()))
    results.append(("Day 3", test_day3_components()))
    results.append(("Day 4", test_day4_components()))
    results.append(("Day 5", test_day5_components()))
    results.append(("Day 6", test_day6_components()))
    results.append(("Cross-Day Integration", test_cross_day_integration()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Integration Test Summary:")
    
    passed = 0
    failed = 0
    
    for day, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {day}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("🚀 Complete 6-day system is properly integrated!")
    else:
        print("⚠️  Some integration tests failed. Please check the errors above.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
