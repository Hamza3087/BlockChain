#!/usr/bin/env python3
"""
Quick verification script to check if Day 6 integration is properly set up.
Run this before attempting migrations.
"""

import os
import sys

def check_file_structure():
    """Check that all required files exist and no duplicates."""
    print("🔍 Checking file structure...")
    
    required_files = [
        'blockchain/models.py',
        'blockchain/integration/__init__.py',
        'blockchain/integration/pipeline.py',
        'blockchain/integration/batch_manager.py',
        'blockchain/integration/cache_manager.py',
        'blockchain/integration/performance_monitor.py',
        'blockchain/integration/test_runner.py',
        'blockchain/management/commands/test_day6_integration.py',
        'blockchain/tests/test_solana_client.py',
        'blockchain/tests/test_models.py',
        'blockchain/tests/test_migration.py',
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            print(f"  ✅ {file_path}")
    
    # Check for files that should NOT exist
    should_not_exist = [
        'blockchain/integration/models.py',  # This should be removed
    ]
    
    conflicting_files = []
    for file_path in should_not_exist:
        if os.path.exists(file_path):
            conflicting_files.append(file_path)
        else:
            print(f"  ✅ {file_path} (correctly removed)")
    
    if missing_files:
        print(f"  ❌ Missing files: {missing_files}")
        return False
    
    if conflicting_files:
        print(f"  ❌ Conflicting files found: {conflicting_files}")
        print("     These files should be removed to avoid model conflicts.")
        return False
    
    print("  🎉 File structure is correct!")
    return True

def check_imports():
    """Check that all imports work without conflicts."""
    print("\n🔍 Checking imports...")
    
    try:
        # Test Django setup
        import django
        from django.conf import settings
        print("  ✅ Django imports working")
        
        # Test blockchain app imports
        import blockchain
        print("  ✅ Blockchain app imports working")
        
        # Test integration imports (this is where conflicts would show up)
        from blockchain.integration import (
            EndToEndPipeline, BatchMigrationManager, CacheManager,
            IntegrationTestRunner, PerformanceMonitor
        )
        print("  ✅ Integration component imports working")
        
        # Test model imports (this is where the conflict was)
        from blockchain.models import (
            Tree, SeiNFT, MigrationJob, 
            IntegrationTestResult, BatchMigrationStatus, PerformanceMetric
        )
        print("  ✅ All model imports working (no conflicts)")
        
        # Test migration imports
        from blockchain.migration import (
            DataExporter, MigrationMapper, MigrationValidator, MigrationService
        )
        print("  ✅ Migration component imports working")
        
        print("  🎉 All imports successful!")
        return True
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False

def check_django_setup():
    """Check Django configuration."""
    print("\n🔍 Checking Django setup...")
    
    try:
        import django
        from django.conf import settings
        
        if not settings.configured:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
            django.setup()
        
        print("  ✅ Django configured successfully")
        
        # Check database configuration
        if hasattr(settings, 'DATABASES'):
            print("  ✅ Database configuration found")
        else:
            print("  ⚠️  Database configuration missing")
        
        # Check cache configuration
        if hasattr(settings, 'CACHES'):
            print("  ✅ Cache configuration found")
        else:
            print("  ⚠️  Cache configuration missing")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Django setup error: {e}")
        return False

def check_integration_exports():
    """Check that integration package exports are correct."""
    print("\n🔍 Checking integration package exports...")
    
    try:
        # Read the __init__.py file
        with open('blockchain/integration/__init__.py', 'r') as f:
            init_content = f.read()
        
        # Check that model imports are removed
        if 'IntegrationTestResult' in init_content and 'from .models import' in init_content:
            print("  ❌ Integration __init__.py still has model imports")
            print("     This will cause conflicts. Models should only be in blockchain.models")
            return False
        
        # Check that component imports are present
        required_exports = [
            'EndToEndPipeline',
            'BatchMigrationManager', 
            'CacheManager',
            'IntegrationTestRunner',
            'PerformanceMonitor'
        ]
        
        missing_exports = []
        for export in required_exports:
            if export not in init_content:
                missing_exports.append(export)
        
        if missing_exports:
            print(f"  ❌ Missing exports: {missing_exports}")
            return False
        
        print("  ✅ Integration package exports are correct")
        return True
        
    except FileNotFoundError:
        print("  ❌ blockchain/integration/__init__.py not found")
        return False
    except Exception as e:
        print(f"  ❌ Error checking exports: {e}")
        return False

def main():
    """Run all verification checks."""
    print("🚀 Day 6 Integration Verification")
    print("=" * 50)
    
    checks = [
        ("File Structure", check_file_structure),
        ("Django Setup", check_django_setup),
        ("Integration Exports", check_integration_exports),
        ("Import Resolution", check_imports),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"  ❌ {check_name} failed with error: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Verification Summary:")
    
    passed = 0
    failed = 0
    
    for check_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {check_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 ALL VERIFICATION CHECKS PASSED!")
        print("✅ You can now run: python manage.py makemigrations blockchain")
        print("✅ Followed by: python manage.py migrate")
    else:
        print("\n⚠️  Some verification checks failed.")
        print("❌ Please fix the issues above before running migrations.")
        print("\n🔧 Common fixes:")
        print("   - Remove blockchain/integration/models.py if it exists")
        print("   - Check that all required files are present")
        print("   - Ensure Django settings are properly configured")
        print("   - Activate virtual environment if needed")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
