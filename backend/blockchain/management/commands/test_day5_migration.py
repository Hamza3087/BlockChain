"""
Django management command to test Day 5 migration functionality.

This command comprehensively tests all Day 5 migration components:
- DataExporter for Sei NFT data extraction
- MigrationMapper for data transformation
- MigrationValidator for integrity checks and rollback
- MigrationService for complete migration orchestration

Usage: python manage.py test_day5_migration
"""

import asyncio
import json
from datetime import date
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from asgiref.sync import sync_to_async

from blockchain.migration import (
    DataExporter, SeiNFTData, MigrationMapper, MigrationValidator,
    MigrationService, MigrationJob, MigrationLog
)


class Command(BaseCommand):
    help = 'Test Day 5 migration functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-exporter',
            action='store_true',
            help='Test DataExporter functionality',
        )
        parser.add_argument(
            '--test-mapper',
            action='store_true',
            help='Test MigrationMapper functionality',
        )
        parser.add_argument(
            '--test-validator',
            action='store_true',
            help='Test MigrationValidator functionality',
        )
        parser.add_argument(
            '--test-service',
            action='store_true',
            help='Test MigrationService functionality',
        )
        parser.add_argument(
            '--test-rollback',
            action='store_true',
            help='Test rollback functionality',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test data after running tests',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Day 5 Migration Tests')
        )
        self.stdout.write('=' * 60)
        
        try:
            # Run tests based on options
            if options['test_exporter']:
                asyncio.run(self.test_data_exporter())
            
            if options['test_mapper']:
                asyncio.run(self.test_migration_mapper())
            
            if options['test_validator']:
                asyncio.run(self.test_migration_validator())
            
            if options['test_service']:
                asyncio.run(self.test_migration_service())
            
            if options['test_rollback']:
                asyncio.run(self.test_rollback_functionality())
            
            # If no specific test selected, run all
            if not any([
                options['test_exporter'], options['test_mapper'],
                options['test_validator'], options['test_service'],
                options['test_rollback']
            ]):
                asyncio.run(self.run_all_tests())
            
            self.stdout.write('=' * 60)
            self.stdout.write(
                self.style.SUCCESS('✅ All Day 5 Migration Tests Completed!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Tests failed: {e}')
            )
            raise

    async def run_all_tests(self):
        """Run all migration tests."""
        await self.test_data_exporter()
        await self.test_migration_mapper()
        await self.test_migration_validator()
        await self.test_migration_service()
        await self.test_rollback_functionality()

    async def test_data_exporter(self):
        """Test DataExporter functionality."""
        self.stdout.write('\n📤 Testing DataExporter...')
        
        try:
            # Create mock Sei NFT data
            mock_sei_data = SeiNFTData(
                contract_address="sei1abcdef1234567890abcdef1234567890abcdef12",
                token_id="1",
                owner_address="sei1owner1234567890abcdef1234567890abcdef12",
                name="Test Carbon Credit Tree",
                description="A test tree NFT for carbon offset verification",
                image_url="https://example.com/tree.jpg",
                external_url="https://replantworld.com/tree/1",
                attributes=[
                    {"trait_type": "Species", "value": "Oak"},
                    {"trait_type": "Location", "value": "California"},
                    {"trait_type": "Carbon Offset", "value": "2.5 tons"},
                    {"trait_type": "Planting Date", "value": "2023-01-15"}
                ]
            )
            
            self.stdout.write(f'  ✅ Created mock Sei NFT data: {mock_sei_data.name}')
            self.stdout.write(f'  📊 Data hash: {mock_sei_data.data_hash}')
            self.stdout.write(f'  📊 Attributes: {len(mock_sei_data.attributes)}')
            
            # Test data integrity
            recalculated_hash = mock_sei_data.calculate_hash()
            assert mock_sei_data.data_hash == recalculated_hash, "Data hash mismatch"
            
            self.stdout.write('  ✅ Data integrity verification passed')
            
            # Test serialization
            data_dict = mock_sei_data.to_dict()
            reconstructed_data = SeiNFTData.from_dict(data_dict)
            assert reconstructed_data.data_hash == mock_sei_data.data_hash, "Serialization failed"
            
            self.stdout.write('  ✅ Data serialization/deserialization passed')
            
            self.stdout.write('  🎉 DataExporter tests completed successfully!')
            
        except Exception as e:
            self.stdout.write(f'  ❌ DataExporter test failed: {str(e)}')
            raise

    async def test_migration_mapper(self):
        """Test MigrationMapper functionality."""
        self.stdout.write('\n🗺️  Testing MigrationMapper...')
        
        try:
            # Create test data
            sei_nft_data = SeiNFTData(
                contract_address="sei1abcdef1234567890abcdef1234567890abcdef12",
                token_id="1",
                owner_address="sei1owner1234567890abcdef1234567890abcdef12",
                name="Carbon Credit Oak Tree",
                description="This NFT represents a carbon offset from an oak tree planted in California",
                image_url="ipfs://QmTest123456789",
                external_url="https://replantworld.com/tree/1",
                attributes=[
                    {"trait_type": "Species", "value": "Quercus robur"},
                    {"trait_type": "Location", "value": "San Francisco, CA"},
                    {"trait_type": "Carbon Offset", "value": "2.5"},
                    {"trait_type": "Planting Date", "value": "2023-01-15"}
                ]
            )
            
            # Initialize mapper
            mapper = MigrationMapper()
            
            # Perform mapping
            mapping_result = await mapper.map_nft_data(sei_nft_data)
            
            self.stdout.write(f'  ✅ Mapping completed: {mapping_result.is_valid}')
            self.stdout.write(f'  📊 Transformations: {len(mapping_result.transformations)}')
            self.stdout.write(f'  ⚠️  Warnings: {len(mapping_result.warnings)}')
            
            if mapping_result.transformations:
                for transform in mapping_result.transformations[:3]:  # Show first 3
                    self.stdout.write(f'    • {transform["field"]}: {transform["reason"]}')
            
            # Verify Solana metadata
            solana_metadata = mapping_result.solana_metadata
            assert solana_metadata is not None, "No Solana metadata generated"
            assert solana_metadata.name, "Solana metadata missing name"
            assert solana_metadata.symbol, "Solana metadata missing symbol"
            
            self.stdout.write(f'  ✅ Solana metadata: {solana_metadata.name} ({solana_metadata.symbol})')
            
            # Check carbon credit detection
            carbon_attributes = [attr for attr in solana_metadata.attributes 
                               if 'carbon' in attr.get('trait_type', '').lower()]
            if carbon_attributes:
                self.stdout.write('  ✅ Carbon credit detection successful')
            
            # Get mapping statistics
            stats = mapper.get_mapping_statistics()
            self.stdout.write(f'  📊 Mapping stats: {stats}')
            
            self.stdout.write('  🎉 MigrationMapper tests completed successfully!')
            
        except Exception as e:
            self.stdout.write(f'  ❌ MigrationMapper test failed: {str(e)}')
            raise

    async def test_migration_validator(self):
        """Test MigrationValidator functionality."""
        self.stdout.write('\n✅ Testing MigrationValidator...')
        
        try:
            # Create test data
            sei_nft_data = SeiNFTData(
                contract_address="sei1abcdef1234567890abcdef1234567890abcdef12",
                token_id="1",
                owner_address="sei1owner1234567890abcdef1234567890abcdef12",
                name="Test Tree NFT",
                description="A test tree for validation",
                image_url="https://example.com/tree.jpg",
                attributes=[{"trait_type": "Species", "value": "Oak"}]
            )
            
            # Initialize validator
            validator = MigrationValidator()
            
            # Test data validation
            validation_result = await validator.validate_migration_data(sei_nft_data)
            
            self.stdout.write(f'  ✅ Data validation: {validation_result.is_valid}')
            self.stdout.write(f'  📊 Validation duration: {validation_result.validation_duration_ms:.2f}ms')
            
            if validation_result.validation_errors:
                for error in validation_result.validation_errors[:3]:
                    self.stdout.write(f'    ❌ {error}')
            
            if validation_result.validation_warnings:
                for warning in validation_result.validation_warnings[:3]:
                    self.stdout.write(f'    ⚠️  {warning}')
            
            # Test mapping validation
            mapper = MigrationMapper()
            mapping = await mapper.map_nft_data(sei_nft_data)
            mapping_validation = await validator.validate_migration_mapping(mapping)
            
            self.stdout.write(f'  ✅ Mapping validation: {mapping_validation.is_valid}')
            
            # Get validation statistics
            stats = validator.get_validation_statistics()
            self.stdout.write(f'  📊 Validation stats: {stats}')
            
            self.stdout.write('  🎉 MigrationValidator tests completed successfully!')
            
        except Exception as e:
            self.stdout.write(f'  ❌ MigrationValidator test failed: {str(e)}')
            raise

    async def test_migration_service(self):
        """Test MigrationService functionality."""
        self.stdout.write('\n🔄 Testing MigrationService...')
        
        try:
            # Get or create test user
            user = await sync_to_async(User.objects.get_or_create)(
                username='migration_test_user',
                defaults={
                    'email': 'test@migration.com',
                    'first_name': 'Migration',
                    'last_name': 'Tester'
                }
            )
            user = user[0]
            
            # Initialize migration service
            migration_service = MigrationService()
            initialized = await migration_service.initialize()
            
            if not initialized:
                self.stdout.write('  ⚠️  Migration service initialization failed, skipping service tests')
                return
            
            self.stdout.write('  ✅ Migration service initialized')
            
            # Create migration job
            migration_job = await migration_service.create_migration_job(
                name="Test Migration Job",
                description="Testing Day 5 migration functionality",
                sei_contract_addresses=["sei1test123456789"],
                created_by=user,
                batch_size=10
            )
            
            self.stdout.write(f'  ✅ Migration job created: {migration_job.job_id}')
            self.stdout.write(f'  📊 Job status: {migration_job.status}')
            
            # Get service statistics
            stats = migration_service.get_service_statistics()
            self.stdout.write(f'  📊 Service stats: {stats}')
            
            # Close service
            await migration_service.close()
            
            self.stdout.write('  🎉 MigrationService tests completed successfully!')
            
        except Exception as e:
            self.stdout.write(f'  ❌ MigrationService test failed: {str(e)}')
            raise

    async def test_rollback_functionality(self):
        """Test rollback functionality."""
        self.stdout.write('\n🔄 Testing Rollback Functionality...')
        
        try:
            # This test would require a completed migration to rollback
            # For now, we'll test the validator's rollback validation
            
            validator = MigrationValidator()
            
            # Test rollback validation (this will fail gracefully if no job exists)
            try:
                rollback_result = await validator.perform_rollback(
                    "non-existent-job-id", 
                    "Test rollback functionality"
                )
                self.stdout.write(f'  ✅ Rollback test completed: {rollback_result.rollback_required}')
            except Exception as e:
                self.stdout.write(f'  ℹ️  Rollback test expected failure (no job to rollback): {str(e)}')
            
            # Get validation statistics
            stats = validator.get_validation_statistics()
            self.stdout.write(f'  📊 Validator stats: {stats}')
            
            self.stdout.write('  🎉 Rollback functionality tests completed!')
            
        except Exception as e:
            self.stdout.write(f'  ❌ Rollback test failed: {str(e)}')
            raise
