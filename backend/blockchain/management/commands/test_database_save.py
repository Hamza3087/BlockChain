"""
Management command to test database saving functionality.
"""

import asyncio
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from blockchain.migration.data_exporter import DataExporter
from blockchain.migration.migration_mapper import MigrationMapper
from blockchain.models import SeiNFT, MigrationJob, MigrationLog


class Command(BaseCommand):
    help = 'Test database saving functionality'

    def handle(self, *args, **options):
        """Handle the command execution."""
        asyncio.run(self._async_handle())

    async def _async_handle(self):
        """Async command handler."""
        self.stdout.write(
            self.style.SUCCESS('🧪 Testing Database Save Functionality')
        )
        self.stdout.write('=' * 50)

        try:
            # Test 1: Load real NFT data
            self.stdout.write('\n📂 Step 1: Loading real NFT data...')
            exporter = DataExporter(use_solana_retrieval=False)
            await exporter.initialize()
            
            nft_data = await exporter.export_nft_data('sei1replantworld', '1001')
            if not nft_data:
                self.stdout.write(
                    self.style.ERROR('❌ Failed to load NFT data')
                )
                return
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Loaded NFT: "{nft_data.name}"')
            )

            # Test 2: Map NFT data
            self.stdout.write('\n🗺️  Step 2: Mapping NFT data...')
            mapper = MigrationMapper()
            mapping = await mapper.map_nft_data(nft_data)
            
            if not mapping.is_valid:
                self.stdout.write(
                    self.style.ERROR(f'❌ Mapping failed: {mapping.validation_errors}')
                )
                return
            
            self.stdout.write(
                self.style.SUCCESS('✅ NFT data mapped successfully')
            )

            # Test 3: Save to database
            self.stdout.write('\n💾 Step 3: Saving to database...')

            # Create or get test user
            test_user, created = await sync_to_async(User.objects.get_or_create)(
                username='test_migration_user',
                defaults={
                    'email': 'test@example.com',
                    'first_name': 'Test',
                    'last_name': 'User'
                }
            )

            # Create or get SeiNFT record
            sei_nft, created = await sync_to_async(SeiNFT.objects.get_or_create)(
                sei_contract_address=nft_data.contract_address,
                sei_token_id=nft_data.token_id,
                defaults={
                    'sei_owner_address': nft_data.owner_address,
                    'name': nft_data.name,
                    'description': nft_data.description,
                    'image_url': nft_data.image_url,
                    'external_url': nft_data.external_url,
                    'attributes': nft_data.attributes
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ SeiNFT created with ID: {sei_nft.id}')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ SeiNFT found existing with ID: {sei_nft.id}')
                )

            # Create MigrationJob record
            migration_job = await sync_to_async(MigrationJob.objects.create)(
                name=f'Test Migration Job {timezone.now().timestamp()}',
                description='Test migration job for database functionality',
                sei_contract_addresses=['sei1replantworld'],
                status='completed',
                total_nfts=1,
                processed_nfts=1,
                successful_migrations=1,
                failed_migrations=0,
                started_at=timezone.now(),
                completed_at=timezone.now(),
                created_by=test_user
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ MigrationJob saved with ID: {migration_job.job_id}')
            )

            # Create MigrationLog record
            migration_log = await sync_to_async(MigrationLog.objects.create)(
                migration_job=migration_job,
                sei_nft=sei_nft,
                level='info',
                event_type='nft_migration',
                message='Test NFT migration completed successfully',
                details={
                    'solana_mint_address': 'test_mint_address_123',
                    'solana_asset_id': 'test_asset_id_456',
                    'merkle_tree_address': 'test_tree_address_789',
                    'transaction_signature': 'test_signature_abc'
                },
                execution_time_ms=1500
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ MigrationLog saved with ID: {migration_log.log_id}')
            )

            # Test 4: Verify data integrity
            self.stdout.write('\n🔍 Step 4: Verifying data integrity...')
            
            # Check if records exist
            sei_nft_count = await sync_to_async(SeiNFT.objects.count)()
            migration_job_count = await sync_to_async(MigrationJob.objects.count)()
            migration_log_count = await sync_to_async(MigrationLog.objects.count)()

            self.stdout.write(f'   📊 SeiNFT records: {sei_nft_count}')
            self.stdout.write(f'   📊 MigrationJob records: {migration_job_count}')
            self.stdout.write(f'   📊 MigrationLog records: {migration_log_count}')

            # Verify relationships
            retrieved_log = await sync_to_async(
                lambda: MigrationLog.objects.select_related('migration_job', 'sei_nft').first()
            )()
            if retrieved_log:
                self.stdout.write(
                    self.style.SUCCESS('✅ Database relationships working correctly')
                )
                self.stdout.write(f'   🔗 Log -> Job: {retrieved_log.migration_job.job_id}')
                self.stdout.write(f'   🔗 Log -> NFT: {retrieved_log.sei_nft.name}')
            
            await exporter.close()

            self.stdout.write('\n' + '=' * 50)
            self.stdout.write(
                self.style.SUCCESS('🎉 Database save functionality test completed successfully!')
            )
            self.stdout.write(
                self.style.SUCCESS('✅ All database operations working correctly')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Database test failed: {e}')
            )
            import traceback
            traceback.print_exc()
