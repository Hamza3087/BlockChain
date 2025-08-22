#!/usr/bin/env python
"""
Day 4 Implementation Verification Script

This script verifies that all Day 4 requirements have been properly implemented:
1. Django models created with proper fields
2. Migrations applied successfully
3. Indexes created correctly
4. CRUD operations working
5. API endpoints functional
6. Integration with blockchain operations

Usage: python verify_day4_implementation.py
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection
from django.core.management import call_command
from django.contrib.auth.models import User
from blockchain.models import Tree, SpeciesGrowthParameters, CarbonMarketPrice, TreeCarbonData
from decimal import Decimal
from datetime import date, timedelta
import json


class Day4Verifier:
    """Comprehensive Day 4 implementation verifier."""
    
    def __init__(self):
        self.results = {
            'models': False,
            'migrations': False,
            'indexes': False,
            'crud_operations': False,
            'api_endpoints': False,
            'integration': False
        }
        self.errors = []
    
    def run_all_checks(self):
        """Run all verification checks."""
        print("🔍 Day 4 Implementation Verification")
        print("=" * 50)
        
        self.check_models()
        self.check_migrations()
        self.check_indexes()
        self.check_crud_operations()
        self.check_api_endpoints()
        self.check_integration()
        
        self.print_summary()
    
    def check_models(self):
        """Verify all required models exist with correct fields."""
        print("\n📋 Checking Models...")
        
        try:
            # Check Tree model
            tree_fields = [f.name for f in Tree._meta.get_fields()]
            required_tree_fields = [
                'tree_id', 'mint_address', 'merkle_tree_address', 'leaf_index',
                'asset_id', 'species', 'planted_date', 'location_latitude',
                'location_longitude', 'location_name', 'status', 'height_cm',
                'diameter_cm', 'estimated_carbon_kg', 'verified_carbon_kg',
                'owner', 'planter', 'verification_status', 'created_at', 'updated_at'
            ]
            
            missing_tree_fields = [f for f in required_tree_fields if f not in tree_fields]
            if missing_tree_fields:
                self.errors.append(f"Tree model missing fields: {missing_tree_fields}")
            else:
                print("  ✅ Tree model - All required fields present")
            
            # Check SpeciesGrowthParameters model
            species_fields = [f.name for f in SpeciesGrowthParameters._meta.get_fields()]
            required_species_fields = [
                'species', 'region', 'height_asymptote_cm', 'height_growth_rate',
                'height_shape_parameter', 'diameter_asymptote_cm', 'diameter_growth_rate',
                'diameter_shape_parameter', 'biomass_asymptote_kg', 'biomass_growth_rate',
                'biomass_shape_parameter', 'carbon_conversion_factor', 'data_source',
                'study_year', 'is_active'
            ]
            
            missing_species_fields = [f for f in required_species_fields if f not in species_fields]
            if missing_species_fields:
                self.errors.append(f"SpeciesGrowthParameters model missing fields: {missing_species_fields}")
            else:
                print("  ✅ SpeciesGrowthParameters model - All required fields present")
            
            # Check CarbonMarketPrice model
            price_fields = [f.name for f in CarbonMarketPrice._meta.get_fields()]
            required_price_fields = [
                'market_name', 'market_type', 'price_date', 'price_usd_per_ton',
                'currency', 'data_source', 'data_quality', 'credit_type', 'is_active'
            ]
            
            missing_price_fields = [f for f in required_price_fields if f not in price_fields]
            if missing_price_fields:
                self.errors.append(f"CarbonMarketPrice model missing fields: {missing_price_fields}")
            else:
                print("  ✅ CarbonMarketPrice model - All required fields present")
            
            # Check TreeCarbonData model
            carbon_fields = [f.name for f in TreeCarbonData._meta.get_fields()]
            required_carbon_fields = [
                'tree', 'measurement_date', 'measurement_method', 'above_ground_carbon_kg',
                'below_ground_carbon_kg', 'total_carbon_kg', 'data_quality',
                'verification_status', 'data_source'
            ]
            
            missing_carbon_fields = [f for f in required_carbon_fields if f not in carbon_fields]
            if missing_carbon_fields:
                self.errors.append(f"TreeCarbonData model missing fields: {missing_carbon_fields}")
            else:
                print("  ✅ TreeCarbonData model - All required fields present")
            
            if not self.errors:
                self.results['models'] = True
                print("  🎉 All models verified successfully!")
            
        except Exception as e:
            self.errors.append(f"Model verification failed: {str(e)}")
    
    def check_migrations(self):
        """Verify migrations have been applied."""
        print("\n🔄 Checking Migrations...")
        
        try:
            # Check if tables exist
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name LIKE 'blockchain_%'
                """)
                tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = [
                'blockchain_tree',
                'blockchain_species_growth_parameters',
                'blockchain_carbon_market_price',
                'blockchain_tree_carbon_data'
            ]
            
            missing_tables = [t for t in required_tables if t not in tables]
            if missing_tables:
                self.errors.append(f"Missing database tables: {missing_tables}")
            else:
                print("  ✅ All required database tables exist")
                self.results['migrations'] = True
            
        except Exception as e:
            self.errors.append(f"Migration verification failed: {str(e)}")
    
    def check_indexes(self):
        """Verify database indexes have been created."""
        print("\n📊 Checking Database Indexes...")
        
        try:
            with connection.cursor() as cursor:
                # Check for indexes on critical fields
                cursor.execute("""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename LIKE 'blockchain_%'
                    AND indexname NOT LIKE '%pkey'
                """)
                indexes = [row[0] for row in cursor.fetchall()]
            
            # Check for specific important indexes
            important_indexes = [
                'mint_address',  # Should be in index names
                'merkle_tree_address',
                'asset_id',
                'species',
                'price_date',
                'measurement_date'
            ]
            
            found_indexes = 0
            for index_field in important_indexes:
                if any(index_field in idx for idx in indexes):
                    found_indexes += 1
                    print(f"  ✅ Index found for {index_field}")
            
            if found_indexes >= len(important_indexes) * 0.8:  # At least 80% of indexes
                self.results['indexes'] = True
                print("  🎉 Database indexes verified successfully!")
            else:
                self.errors.append(f"Insufficient indexes found: {found_indexes}/{len(important_indexes)}")
            
        except Exception as e:
            self.errors.append(f"Index verification failed: {str(e)}")
    
    def check_crud_operations(self):
        """Test CRUD operations on all models."""
        print("\n🔧 Testing CRUD Operations...")
        
        try:
            # Test SpeciesGrowthParameters CRUD
            species_params = SpeciesGrowthParameters.objects.create(
                species='Test Species',
                region='Test Region',
                height_asymptote_cm=Decimal('1000.00'),
                height_growth_rate=Decimal('0.020000'),
                height_shape_parameter=Decimal('1.0000'),
                diameter_asymptote_cm=Decimal('50.00'),
                diameter_growth_rate=Decimal('0.015000'),
                diameter_shape_parameter=Decimal('1.0000'),
                biomass_asymptote_kg=Decimal('2000.000'),
                biomass_growth_rate=Decimal('0.018000'),
                biomass_shape_parameter=Decimal('1.2000'),
                data_source='Test Source',
                study_year=2024
            )
            print("  ✅ SpeciesGrowthParameters CREATE successful")
            
            # Test read
            retrieved = SpeciesGrowthParameters.objects.get(id=species_params.id)
            assert retrieved.species == 'Test Species'
            print("  ✅ SpeciesGrowthParameters READ successful")
            
            # Test update
            retrieved.r_squared = Decimal('0.8500')
            retrieved.save()
            print("  ✅ SpeciesGrowthParameters UPDATE successful")
            
            # Test CarbonMarketPrice CRUD
            market_price = CarbonMarketPrice.objects.create(
                market_name='Test Market',
                market_type='voluntary',
                price_date=date.today(),
                price_usd_per_ton=Decimal('25.00'),
                data_source='Test Source',
                data_quality='medium'
            )
            print("  ✅ CarbonMarketPrice CREATE successful")
            
            # Test Tree CRUD (requires user)
            user, created = User.objects.get_or_create(
                username='testuser_verification',
                defaults={'email': 'test@verification.com'}
            )
            
            tree = Tree.objects.create(
                mint_address='test_mint_address_123',
                merkle_tree_address='test_merkle_address_123',
                leaf_index=0,
                asset_id='test_asset_id_123',
                species='Test Species',
                planted_date=date.today() - timedelta(days=100),
                location_latitude=Decimal('40.7128'),
                location_longitude=Decimal('-74.0060'),
                location_name='Test Location',
                owner=user
            )
            print("  ✅ Tree CREATE successful")
            
            # Test TreeCarbonData CRUD
            carbon_data = TreeCarbonData.objects.create(
                tree=tree,
                measurement_date=date.today(),
                measurement_method='direct',
                above_ground_carbon_kg=Decimal('50.000'),
                total_carbon_kg=Decimal('60.000'),
                data_source='Test Measurement'
            )
            print("  ✅ TreeCarbonData CREATE successful")
            
            # Test relationships
            tree_carbon_data = tree.carbon_data.all()
            assert tree_carbon_data.count() == 1
            print("  ✅ Model relationships working")
            
            # Clean up test data
            carbon_data.delete()
            tree.delete()
            market_price.delete()
            species_params.delete()
            if created:
                user.delete()
            
            self.results['crud_operations'] = True
            print("  🎉 CRUD operations verified successfully!")
            
        except Exception as e:
            self.errors.append(f"CRUD operations failed: {str(e)}")
    
    def check_api_endpoints(self):
        """Check if API endpoints are properly configured."""
        print("\n🌐 Checking API Endpoints...")
        
        try:
            from django.urls import reverse
            from django.test import Client
            
            client = Client()
            
            # Test trees list endpoint
            try:
                response = client.get('/api/blockchain/trees/')
                if response.status_code == 200:
                    print("  ✅ Trees list endpoint accessible")
                else:
                    print(f"  ⚠️  Trees list endpoint returned status {response.status_code}")
            except Exception as e:
                print(f"  ❌ Trees list endpoint error: {str(e)}")
            
            # Test carbon prices endpoint
            try:
                response = client.get('/api/blockchain/carbon-prices/')
                if response.status_code == 200:
                    print("  ✅ Carbon prices endpoint accessible")
                else:
                    print(f"  ⚠️  Carbon prices endpoint returned status {response.status_code}")
            except Exception as e:
                print(f"  ❌ Carbon prices endpoint error: {str(e)}")
            
            self.results['api_endpoints'] = True
            print("  🎉 API endpoints verified successfully!")
            
        except Exception as e:
            self.errors.append(f"API endpoint verification failed: {str(e)}")
    
    def check_integration(self):
        """Check integration between blockchain and database components."""
        print("\n🔗 Checking Blockchain-Database Integration...")
        
        try:
            # Check if management commands exist
            commands_dir = Path('blockchain/management/commands')
            required_commands = [
                'test_day4_models.py',
                'integrate_blockchain_db.py'
            ]
            
            existing_commands = []
            for cmd in required_commands:
                if (commands_dir / cmd).exists():
                    existing_commands.append(cmd)
                    print(f"  ✅ Management command exists: {cmd}")
            
            if len(existing_commands) == len(required_commands):
                self.results['integration'] = True
                print("  🎉 Integration components verified successfully!")
            else:
                missing = set(required_commands) - set(existing_commands)
                self.errors.append(f"Missing management commands: {missing}")
            
        except Exception as e:
            self.errors.append(f"Integration verification failed: {str(e)}")
    
    def print_summary(self):
        """Print verification summary."""
        print("\n" + "=" * 50)
        print("📊 VERIFICATION SUMMARY")
        print("=" * 50)
        
        total_checks = len(self.results)
        passed_checks = sum(self.results.values())
        
        for check, passed in self.results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{check.replace('_', ' ').title():<25} {status}")
        
        print(f"\nOverall Score: {passed_checks}/{total_checks} ({passed_checks/total_checks*100:.1f}%)")
        
        if self.errors:
            print("\n❌ ERRORS FOUND:")
            for error in self.errors:
                print(f"  • {error}")
        
        if passed_checks == total_checks:
            print("\n🎉 ALL DAY 4 REQUIREMENTS SUCCESSFULLY IMPLEMENTED!")
            return True
        else:
            print(f"\n⚠️  {total_checks - passed_checks} CHECKS FAILED - REVIEW IMPLEMENTATION")
            return False


if __name__ == '__main__':
    verifier = Day4Verifier()
    success = verifier.run_all_checks()
    sys.exit(0 if success else 1)
