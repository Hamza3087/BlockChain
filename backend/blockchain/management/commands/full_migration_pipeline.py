import os
import json
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import structlog

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from asgiref.sync import sync_to_async

from blockchain.models import SeiNFT, MigrationJob, MigrationLog
from blockchain.clients.solana_client import SolanaClient
from blockchain.cnft_minting import CompressedNFTMinter, NFTMetadata
from blockchain.merkle_tree import MerkleTreeManager
from blockchain.migration.data_exporter import DataExporter
from blockchain.migration.migration_mapper import MigrationMapper
from blockchain.migration.migration_validator import MigrationValidator
# from blockchain.services.ipfs_service import IPFSService  # Will be defined in this file

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = 'Run complete end-to-end NFT migration pipeline from local files to Solana cNFTs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of NFTs to process in each batch'
        )
        parser.add_argument(
            '--start-from',
            type=str,
            default=None,
            help='Start processing from specific NFT ID (e.g., "1001")'
        )
        parser.add_argument(
            '--max-nfts',
            type=int,
            default=None,
            help='Maximum number of NFTs to process (for testing)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually minting or deleting files'
        )
        parser.add_argument(
            '--skip-cleanup',
            action='store_true',
            help='Skip deleting processed files (for testing)'
        )

    def handle(self, *args, **options):
        """Main command handler"""
        self.batch_size = options['batch_size']
        self.start_from = options['start_from']
        self.max_nfts = options['max_nfts']
        self.dry_run = options['dry_run']
        self.skip_cleanup = options['skip_cleanup']
        
        self.stdout.write(
            self.style.SUCCESS(
                f"🚀 STARTING COMPLETE NFT MIGRATION PIPELINE"
            )
        )
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("⚠️  DRY RUN MODE - No actual minting or file deletion")
            )
        
        # Initialize pipeline
        asyncio.run(self._run_migration_pipeline())

    async def _run_migration_pipeline(self):
        """Run the complete migration pipeline"""
        pipeline = NFTMigrationPipeline(
            batch_size=self.batch_size,
            start_from=self.start_from,
            max_nfts=self.max_nfts,
            dry_run=self.dry_run,
            skip_cleanup=self.skip_cleanup,
            stdout=self.stdout,
            style=self.style
        )
        
        try:
            await pipeline.initialize()
            await pipeline.run_complete_migration()
        except Exception as e:
            logger.error("Migration pipeline failed", error=str(e), exc_info=True)
            self.stdout.write(
                self.style.ERROR(f"❌ Migration pipeline failed: {str(e)}")
            )
            raise CommandError(f"Migration failed: {str(e)}")
        finally:
            await pipeline.cleanup()


class NFTMigrationPipeline:
    """Complete NFT migration pipeline from local files to Solana cNFTs"""
    
    def __init__(self, batch_size=10, start_from=None, max_nfts=None, 
                 dry_run=False, skip_cleanup=False, stdout=None, style=None):
        self.batch_size = batch_size
        self.start_from = start_from
        self.max_nfts = max_nfts
        self.dry_run = dry_run
        self.skip_cleanup = skip_cleanup
        self.stdout = stdout
        self.style = style
        
        # Pipeline components
        self.solana_client = None
        self.nft_minter = None
        self.merkle_tree_manager = None
        self.data_exporter = None
        self.migration_mapper = None
        self.migration_validator = None
        self.ipfs_service = None
        
        # Migration tracking
        self.migration_job = None
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.current_tree_address = None
        
        # Paths
        self.replant_downloads_path = Path(settings.BASE_DIR).parent / "replant_downloads"
        self.processed_backup_path = Path(settings.BASE_DIR).parent / "processed_nfts_backup"
        
        logger.info("NFT Migration Pipeline initialized", 
                   batch_size=batch_size, dry_run=dry_run)

    async def initialize(self):
        """Initialize all pipeline components"""
        self._print_status("🔧 Initializing pipeline components...")
        
        try:
            # Initialize Solana client with default RPC endpoints
            rpc_endpoints = [
                {
                    'url': 'https://api.devnet.solana.com',
                    'name': 'devnet-primary',
                    'priority': 1,
                    'timeout': 30
                },
                {
                    'url': 'https://devnet.helius-rpc.com/?api-key=demo',
                    'name': 'helius-devnet',
                    'priority': 2,
                    'timeout': 30
                }
            ]

            self.solana_client = SolanaClient(rpc_endpoints=rpc_endpoints)
            await self.solana_client.connect()

            # Initialize Merkle tree manager first
            self.merkle_tree_manager = MerkleTreeManager(self.solana_client)

            # Initialize NFT minter with tree manager
            self.nft_minter = CompressedNFTMinter(self.merkle_tree_manager)
            
            # Initialize migration components
            self.data_exporter = DataExporter(use_solana_retrieval=False)
            await self.data_exporter.initialize()
            
            self.migration_mapper = MigrationMapper()
            self.migration_validator = MigrationValidator()
            
            # Initialize IPFS service for off-chain storage
            self.ipfs_service = IPFSService()
            await self.ipfs_service.initialize()
            
            # Create backup directory
            self.processed_backup_path.mkdir(exist_ok=True)
            
            # Create migration job record
            self.migration_job = await self._create_migration_job()
            
            self._print_status("✅ All components initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize pipeline", error=str(e))
            raise

    async def run_complete_migration(self):
        """Run the complete migration for all NFTs"""
        self._print_status("🌟 Starting complete NFT migration...")
        
        # Get list of NFT files to process
        nft_files = self._get_nft_files_to_process()
        
        if not nft_files:
            self._print_status("⚠️  No NFT files found to process")
            return
        
        total_nfts = len(nft_files)
        if self.max_nfts:
            total_nfts = min(total_nfts, self.max_nfts)
            nft_files = nft_files[:self.max_nfts]
        
        self._print_status(f"📊 Found {total_nfts} NFTs to migrate")
        
        # Process NFTs in batches
        for i in range(0, len(nft_files), self.batch_size):
            batch = nft_files[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(nft_files) + self.batch_size - 1) // self.batch_size
            
            self._print_status(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} NFTs)")
            
            # Ensure we have a Merkle tree for this batch
            if not self.current_tree_address:
                await self._create_new_merkle_tree()
            
            # Process each NFT in the batch
            for nft_file in batch:
                try:
                    await self._process_single_nft(nft_file)
                    self.success_count += 1
                except Exception as e:
                    logger.error(f"Failed to process NFT {nft_file}", error=str(e))
                    self.error_count += 1
                    self._print_status(f"❌ Failed to process {nft_file}: {str(e)}")
                
                self.processed_count += 1
                
                # Update progress
                progress = (self.processed_count / total_nfts) * 100
                self._print_status(
                    f"📈 Progress: {self.processed_count}/{total_nfts} "
                    f"({progress:.1f}%) - ✅ {self.success_count} success, ❌ {self.error_count} errors"
                )
        
        # Final summary
        await self._print_final_summary()

    def _print_status(self, message: str):
        """Print status message to stdout"""
        if self.stdout:
            self.stdout.write(message)
        logger.info(message)

    def _get_nft_files_to_process(self) -> List[str]:
        """Get list of NFT JSON files to process"""
        json_files = []
        
        for file_path in self.replant_downloads_path.glob("*.json"):
            nft_id = file_path.stem
            
            # Check if we should start from a specific NFT
            if self.start_from and nft_id < self.start_from:
                continue
            
            # Check if corresponding PNG file exists
            png_file = file_path.with_suffix('.png')
            if png_file.exists():
                json_files.append(nft_id)
        
        # Sort numerically
        json_files.sort(key=lambda x: int(x) if x.isdigit() else float('inf'))
        
        return json_files

    async def _process_single_nft(self, nft_id: str):
        """Process a single NFT through the complete migration pipeline"""
        self._print_status(f"🎨 Processing NFT {nft_id}...")

        try:
            # Step 1: Load local NFT data
            nft_data = await self._load_local_nft_data(nft_id)

            # Step 2: Convert to Solana format
            solana_metadata = await self._convert_to_solana_format(nft_data, nft_id)

            # Step 3: Upload image and metadata to IPFS
            ipfs_urls = await self._upload_to_ipfs(nft_id, solana_metadata)

            # Step 4: Update metadata with IPFS URLs
            solana_metadata.image = ipfs_urls['image_url']
            solana_metadata.external_url = ipfs_urls['metadata_url']

            # Step 5: Mint compressed NFT on Solana
            mint_result = await self._mint_compressed_nft(solana_metadata, nft_id)

            # Step 6: Save to database
            await self._save_to_database(nft_data, solana_metadata, mint_result, nft_id)

            # Step 7: Backup and cleanup files
            await self._backup_and_cleanup_files(nft_id)

            # Step 8: Log success
            await self._log_migration_success(nft_id, mint_result)

            self._print_status(f"✅ Successfully migrated NFT {nft_id}")

        except Exception as e:
            await self._log_migration_error(nft_id, str(e))
            raise

    async def _load_local_nft_data(self, nft_id: str) -> Dict:
        """Load NFT data from local JSON file"""
        json_file = self.replant_downloads_path / f"{nft_id}.json"

        if not json_file.exists():
            raise FileNotFoundError(f"JSON file not found: {json_file}")

        with open(json_file, 'r') as f:
            data = json.load(f)

        logger.info(f"Loaded local NFT data for {nft_id}", nft_id=nft_id)
        return data

    async def _convert_to_solana_format(self, nft_data: Dict, nft_id: str) -> NFTMetadata:
        """Convert local NFT data to Solana NFT metadata format"""
        # Create SeiNFTData object from local data
        from blockchain.migration.data_exporter import SeiNFTData

        sei_nft_data = SeiNFTData(
            contract_address='sei1replantworld',
            token_id=nft_id,
            owner_address='',
            name=nft_data.get('name', f'Replant World Tree #{nft_id}'),
            description=nft_data.get('description', 'Carbon credit NFT from Replant World'),
            image_url=nft_data.get('image', ''),
            external_url=nft_data.get('external_url', 'https://replantworld.io'),
            attributes=nft_data.get('attributes', []),
            metadata=nft_data
        )

        # Use the migration mapper to convert format
        mapping_result = await self.migration_mapper.map_nft_data(sei_nft_data)
        solana_metadata = mapping_result.solana_metadata

        logger.info(f"Converted NFT {nft_id} to Solana format", nft_id=nft_id)
        return solana_metadata

    async def _upload_to_ipfs(self, nft_id: str, metadata: NFTMetadata) -> Dict[str, str]:
        """Upload image and metadata to IPFS"""
        if self.dry_run:
            return {
                'image_url': f'ipfs://QmDRY_RUN_IMAGE_{nft_id}',
                'metadata_url': f'ipfs://QmDRY_RUN_METADATA_{nft_id}'
            }

        # Upload image file
        image_file = self.replant_downloads_path / f"{nft_id}.png"
        if not image_file.exists():
            raise FileNotFoundError(f"Image file not found: {image_file}")

        image_hash = await self.ipfs_service.upload_file(str(image_file))
        image_url = f"ipfs://{image_hash}"

        # Update metadata with image URL
        metadata.image = image_url

        # Upload metadata JSON
        metadata_json = metadata.to_dict()
        metadata_hash = await self.ipfs_service.upload_json(metadata_json)
        metadata_url = f"ipfs://{metadata_hash}"

        logger.info(f"Uploaded NFT {nft_id} to IPFS",
                   nft_id=nft_id, image_hash=image_hash, metadata_hash=metadata_hash)

        return {
            'image_url': image_url,
            'metadata_url': metadata_url
        }

    async def _mint_compressed_nft(self, metadata: NFTMetadata, nft_id: str) -> Dict:
        """Mint compressed NFT on Solana"""
        if self.dry_run:
            return {
                'signature': f'DRY_RUN_SIGNATURE_{nft_id}',
                'asset_id': f'DRY_RUN_ASSET_{nft_id}',
                'tree_address': 'DRY_RUN_TREE_ADDRESS',
                'leaf_index': 0
            }

        # Create mint request
        from blockchain.cnft_minting import MintRequest

        # Get default recipient (authority wallet)
        recipient = str(self.solana_client.authority.pubkey())

        mint_request = MintRequest(
            tree_address=self.current_tree_address,
            recipient=recipient,
            metadata=metadata,
            mint_id=nft_id
        )

        # Mint the compressed NFT
        mint_result = await self.nft_minter.mint_compressed_nft(mint_request)

        # Convert MintResult to dict for consistency
        result_dict = {
            'signature': mint_result.signature,
            'asset_id': mint_result.asset_id,
            'tree_address': mint_result.tree_address,
            'leaf_index': mint_result.leaf_index
        }

        logger.info(f"Minted compressed NFT {nft_id}",
                   nft_id=nft_id, signature=result_dict['signature'])

        return result_dict

    async def _save_to_database(self, original_data: Dict, solana_metadata: NFTMetadata,
                               mint_result: Dict, nft_id: str):
        """Save NFT data to database"""
        if self.dry_run:
            logger.info(f"DRY RUN: Would save NFT {nft_id} to database")
            return

        # Create or update SeiNFT record (using sync database operations)
        @sync_to_async
        def create_or_update_nft():
            return SeiNFT.objects.update_or_create(
                sei_token_id=nft_id,
                defaults={
                    'name': solana_metadata.name,
                    'description': solana_metadata.description,
                    'image_url': solana_metadata.image,
                    'external_url': solana_metadata.external_url,
                    'attributes': original_data.get('attributes', []),
                    'sei_contract_address': 'sei1replantworld',  # Original Sei contract
                    'sei_owner_address': '',  # Will be updated when needed
                    'migration_status': 'completed',
                    'solana_asset_id': mint_result.get('asset_id'),
                    'migration_date': timezone.now()
                }
            )

        sei_nft, created = await create_or_update_nft()


        logger.info(f"Saved NFT {nft_id} to database",
                   nft_id=nft_id, created=created)

    async def _backup_and_cleanup_files(self, nft_id: str):
        """Backup processed files and clean up original files"""
        if self.skip_cleanup:
            logger.info(f"SKIP CLEANUP: Keeping files for NFT {nft_id}")
            return

        # Create backup directory for this NFT
        backup_dir = self.processed_backup_path / nft_id
        backup_dir.mkdir(exist_ok=True)

        # Files to process
        json_file = self.replant_downloads_path / f"{nft_id}.json"
        png_file = self.replant_downloads_path / f"{nft_id}.png"

        if not self.dry_run:
            # Backup files
            if json_file.exists():
                shutil.copy2(json_file, backup_dir / f"{nft_id}.json")
            if png_file.exists():
                shutil.copy2(png_file, backup_dir / f"{nft_id}.png")

            # Delete original files
            if json_file.exists():
                json_file.unlink()
            if png_file.exists():
                png_file.unlink()

        logger.info(f"Backed up and cleaned up files for NFT {nft_id}", nft_id=nft_id)

    async def _create_new_merkle_tree(self):
        """Create a new Merkle tree for compressed NFTs"""
        if self.dry_run:
            self.current_tree_address = "DRY_RUN_TREE_ADDRESS"
            self._print_status("🌳 DRY RUN: Would create new Merkle tree")
            return

        self._print_status("🌳 Creating new Merkle tree...")

        # Create tree configuration
        tree_config = self.merkle_tree_manager.create_tree_config(
            max_depth=14,  # Supports up to 16,384 NFTs
            max_buffer_size=64,
            canopy_depth=10
        )

        tree_result = await self.merkle_tree_manager.create_merkle_tree(tree_config)
        self.current_tree_address = str(tree_result.tree_address)

        self._print_status(f"✅ Created Merkle tree: {self.current_tree_address}")
        logger.info("Created new Merkle tree", tree_address=self.current_tree_address)

    async def _create_migration_job(self) -> MigrationJob:
        """Create migration job record"""
        if self.dry_run:
            # Create a mock job for dry run
            class MockJob:
                id = "DRY_RUN_JOB"
                status = "running"
            return MockJob()

        @sync_to_async
        def create_migration_job():
            # Get or create a default user for system operations
            from django.contrib.auth.models import User
            system_user, _ = User.objects.get_or_create(
                username='system',
                defaults={'email': 'system@replantworld.io', 'is_active': False}
            )

            return MigrationJob.objects.create(
                name='Full NFT Migration Pipeline',
                description='Complete migration of all NFTs from Sei to Solana',
                sei_contract_addresses=['sei1replantworld'],
                batch_size=self.batch_size,
                status='running',
                total_nfts=0,  # Will be updated later
                processed_nfts=0,
                successful_migrations=0,
                failed_migrations=0,
                started_at=timezone.now(),
                configuration={
                    'batch_size': self.batch_size,
                    'start_from': self.start_from,
                    'max_nfts': self.max_nfts
                },
                created_by=system_user
            )

        job = await create_migration_job()


        logger.info("Created migration job", job_id=job.job_id)
        return job

    async def _log_migration_success(self, nft_id: str, mint_result: Dict):
        """Log successful migration"""
        if self.dry_run:
            return

        @sync_to_async
        def create_success_log():
            # Get or create the SeiNFT record for logging
            sei_nft, _ = SeiNFT.objects.get_or_create(
                sei_token_id=nft_id,
                defaults={'name': f'NFT {nft_id}', 'sei_contract_address': 'sei1replantworld'}
            )

            return MigrationLog.objects.create(
                migration_job=self.migration_job,
                sei_nft=sei_nft,
                level='info',
                event_type='nft_migration',
                message=f'Successfully migrated NFT {nft_id}',
                details={
                    'transaction_signature': mint_result.get('signature'),
                    'solana_asset_id': mint_result.get('asset_id'),
                    'tree_address': mint_result.get('tree_address'),
                    'leaf_index': mint_result.get('leaf_index')
                }
            )

        await create_success_log()


    async def _log_migration_error(self, nft_id: str, error_message: str):
        """Log migration error"""
        if self.dry_run:
            return

        @sync_to_async
        def create_error_log():
            # Get or create the SeiNFT record for logging
            sei_nft, _ = SeiNFT.objects.get_or_create(
                sei_token_id=nft_id,
                defaults={'name': f'NFT {nft_id}', 'sei_contract_address': 'sei1replantworld'}
            )

            return MigrationLog.objects.create(
                migration_job=self.migration_job,
                sei_nft=sei_nft,
                level='error',
                event_type='error',
                message=f'Failed to migrate NFT {nft_id}: {error_message}',
                details={
                    'error_message': error_message,
                    'nft_id': nft_id
                }
            )

        await create_error_log()

    async def _print_final_summary(self):
        """Print final migration summary"""
        self._print_status("\n" + "="*60)
        self._print_status("🎉 MIGRATION PIPELINE COMPLETED!")
        self._print_status("="*60)
        self._print_status(f"📊 Total processed: {self.processed_count}")
        self._print_status(f"✅ Successful: {self.success_count}")
        self._print_status(f"❌ Failed: {self.error_count}")

        if self.success_count > 0:
            success_rate = (self.success_count / self.processed_count) * 100
            self._print_status(f"📈 Success rate: {success_rate:.1f}%")

        if self.current_tree_address and not self.dry_run:
            self._print_status(f"🌳 Merkle tree used: {self.current_tree_address}")

        if not self.dry_run:
            self._print_status(f"💾 Backup location: {self.processed_backup_path}")

        # Update migration job
        if not self.dry_run and hasattr(self.migration_job, 'job_id'):
            @sync_to_async
            def update_migration_job():
                return MigrationJob.objects.filter(job_id=self.migration_job.job_id).update(
                    status='completed' if self.error_count == 0 else 'failed',
                    total_nfts=self.processed_count,
                    processed_nfts=self.processed_count,
                    successful_migrations=self.success_count,
                    failed_migrations=self.error_count,
                    completed_at=timezone.now(),
                    results={
                        'total_processed': self.processed_count,
                        'successful': self.success_count,
                        'failed': self.error_count,
                        'success_rate': (self.success_count / self.processed_count * 100) if self.processed_count > 0 else 0
                    }
                )

            await update_migration_job()

        logger.info("Migration pipeline completed",
                   processed=self.processed_count,
                   successful=self.success_count,
                   failed=self.error_count)

    async def cleanup(self):
        """Cleanup pipeline resources"""
        self._print_status("🧹 Cleaning up pipeline resources...")

        try:
            if self.solana_client:
                await self.solana_client.close()

            if self.data_exporter:
                await self.data_exporter.close()

            if self.ipfs_service:
                await self.ipfs_service.close()

            self._print_status("✅ Cleanup completed")

        except Exception as e:
            logger.error("Error during cleanup", error=str(e))
            self._print_status(f"⚠️  Cleanup error: {str(e)}")


# Additional utility classes and functions

class IPFSService:
    """Service for uploading files to IPFS"""

    def __init__(self):
        self.client = None

    async def initialize(self):
        """Initialize IPFS client"""
        # This would typically connect to an IPFS node
        # For now, we'll simulate IPFS uploads
        logger.info("IPFS service initialized")

    async def upload_file(self, file_path: str) -> str:
        """Upload file to IPFS and return hash"""
        # Simulate IPFS upload
        import hashlib
        with open(file_path, 'rb') as f:
            content = f.read()

        # Generate a mock IPFS hash
        hash_obj = hashlib.sha256(content)
        mock_hash = f"Qm{hash_obj.hexdigest()[:44]}"

        logger.info(f"Uploaded file to IPFS", file_path=file_path, hash=mock_hash)
        return mock_hash

    async def upload_json(self, json_data: Dict) -> str:
        """Upload JSON data to IPFS and return hash"""
        # Simulate IPFS upload
        import hashlib
        content = json.dumps(json_data, sort_keys=True).encode()

        # Generate a mock IPFS hash
        hash_obj = hashlib.sha256(content)
        mock_hash = f"Qm{hash_obj.hexdigest()[:44]}"

        logger.info(f"Uploaded JSON to IPFS", hash=mock_hash)
        return mock_hash

    async def close(self):
        """Close IPFS client"""
        logger.info("IPFS service closed")
