"""
Migration Service for Sei to Solana NFT Migration

This module provides the main orchestration service for migrating NFTs
from Sei blockchain to Solana compressed NFTs with comprehensive logging,
validation, and rollback capabilities.
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from decimal import Decimal
from datetime import date
import structlog
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone

from .data_exporter import DataExporter, SeiNFTData
from .migration_mapper import MigrationMapper, MigrationMapping
from .migration_validator import MigrationValidator, ValidationResult, MigrationStatus
from ..models import SeiNFT, MigrationJob, MigrationLog, Tree
from ..services import get_solana_service
from ..merkle_tree import MerkleTreeManager
from ..cnft_minting import CompressedNFTMinter, MintRequest
from ..config import get_migration_config

logger = structlog.get_logger(__name__)


class MigrationService:
    """
    Comprehensive migration service for Sei to Solana NFT migration.
    
    This service orchestrates the entire migration pipeline including:
    - Data export from Sei blockchain
    - Data mapping and transformation
    - Validation and integrity checks
    - Solana compressed NFT minting
    - Progress tracking and logging
    - Rollback capabilities
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the migration service.
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or get_migration_config()
        self.logger = logger.bind(component="MigrationService")
        
        # Initialize components
        self.data_exporter = None
        self.migration_mapper = None
        self.migration_validator = None
        self.solana_service = None
        self.merkle_tree_manager = None
        self.cnft_minter = None
        
        # Service statistics
        self.service_stats = {
            'migrations_started': 0,
            'migrations_completed': 0,
            'migrations_failed': 0,
            'total_nfts_migrated': 0,
            'total_rollbacks': 0,
            'service_start_time': None
        }
    
    async def initialize(self):
        """Initialize all migration components."""
        try:
            self.logger.info("Initializing migration service")
            
            # Initialize components
            self.data_exporter = DataExporter(self.config)
            await self.data_exporter.initialize()
            
            self.migration_mapper = MigrationMapper(self.config)
            self.migration_validator = MigrationValidator(self.config)
            
            # Initialize Solana components
            self.solana_service = await get_solana_service()
            self.merkle_tree_manager = MerkleTreeManager(self.solana_service.client)
            self.cnft_minter = CompressedNFTMinter(self.merkle_tree_manager)
            
            # Load existing trees
            try:
                self.merkle_tree_manager.load_trees_from_file('managed_trees.json')
            except FileNotFoundError:
                self.logger.info("No existing Merkle trees found")
            
            self.service_stats['service_start_time'] = time.time()
            
            self.logger.info("Migration service initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize migration service", error=str(e))
            return False
    
    async def close(self):
        """Close migration service and cleanup resources."""
        if self.data_exporter:
            await self.data_exporter.close()
        
        if self.solana_service:
            await self.solana_service.close()
        
        self.logger.info("Migration service closed", stats=self.service_stats)
    
    async def create_migration_job(
        self,
        name: str,
        description: str,
        sei_contract_addresses: List[str],
        created_by: User,
        batch_size: int = 100,
        configuration: Dict[str, Any] = None
    ) -> MigrationJob:
        """
        Create a new migration job.
        
        Args:
            name: Job name
            description: Job description
            sei_contract_addresses: List of Sei contract addresses to migrate
            created_by: User creating the job
            batch_size: Batch size for processing
            configuration: Additional configuration
            
        Returns:
            MigrationJob instance
        """
        try:
            self.logger.info(
                "Creating migration job",
                name=name,
                contracts=len(sei_contract_addresses),
                batch_size=batch_size
            )
            
            # Create migration job
            migration_job = await sync_to_async(MigrationJob.objects.create)(
                name=name,
                description=description,
                sei_contract_addresses=sei_contract_addresses,
                batch_size=batch_size,
                configuration=configuration or {},
                created_by=created_by
            )
            
            # Log job creation
            await sync_to_async(MigrationLog.log_event)(
                migration_job=migration_job,
                event_type='job_started',
                message=f"Migration job created: {name}",
                level='info',
                details={
                    'contracts': sei_contract_addresses,
                    'batch_size': batch_size,
                    'configuration': configuration or {}
                }
            )
            
            self.logger.info(
                "Migration job created",
                job_id=str(migration_job.job_id),
                name=name
            )
            
            return migration_job
            
        except Exception as e:
            self.logger.error("Failed to create migration job", error=str(e))
            raise
    
    async def start_migration(self, migration_job_id: str) -> bool:
        """
        Start a migration job.
        
        Args:
            migration_job_id: Migration job ID
            
        Returns:
            True if migration started successfully
        """
        try:
            # Get migration job
            migration_job = await sync_to_async(
                lambda: MigrationJob.objects.get(job_id=migration_job_id)
            )()
            
            if migration_job.status != 'created':
                raise ValueError(f"Migration job is not in 'created' status: {migration_job.status}")
            
            self.logger.info(
                "Starting migration job",
                job_id=migration_job_id,
                name=migration_job.name
            )
            
            # Update job status
            migration_job.status = 'running'
            migration_job.started_at = timezone.now()
            await sync_to_async(migration_job.save)()
            
            # Log job start
            await sync_to_async(MigrationLog.log_event)(
                migration_job=migration_job,
                event_type='job_started',
                message=f"Migration job started",
                level='info'
            )
            
            # Start migration process
            asyncio.create_task(self._execute_migration(migration_job))
            
            self.service_stats['migrations_started'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to start migration job",
                job_id=migration_job_id,
                error=str(e)
            )
            return False
    
    async def _execute_migration(self, migration_job: MigrationJob):
        """Execute the migration job."""
        try:
            self.logger.info(
                "Executing migration job",
                job_id=str(migration_job.job_id),
                contracts=len(migration_job.sei_contract_addresses)
            )
            
            # Phase 1: Export NFT data from Sei
            await self._export_phase(migration_job)
            
            # Phase 2: Map and validate data
            await self._mapping_phase(migration_job)
            
            # Phase 3: Mint on Solana
            await self._minting_phase(migration_job)
            
            # Complete migration
            await self._complete_migration(migration_job)
            
        except Exception as e:
            await self._fail_migration(migration_job, str(e))
    
    async def _export_phase(self, migration_job: MigrationJob):
        """Export NFT data from Sei blockchain."""
        self.logger.info(
            "Starting export phase",
            job_id=str(migration_job.job_id)
        )
        
        await sync_to_async(MigrationLog.log_event)(
            migration_job=migration_job,
            event_type='data_export',
            message="Starting data export from Sei blockchain",
            level='info'
        )
        
        total_exported = 0
        
        for contract_address in migration_job.sei_contract_addresses:
            self.logger.info(
                "Exporting from contract",
                job_id=str(migration_job.job_id),
                contract_address=contract_address
            )
            
            # Export collection data
            async for sei_nft_data in self.data_exporter.export_collection_data(
                contract_address=contract_address,
                batch_size=migration_job.batch_size
            ):
                # Store in database
                await self._store_sei_nft_data(sei_nft_data, migration_job)
                total_exported += 1
                
                # Update progress
                migration_job.total_nfts = total_exported
                if total_exported % 10 == 0:  # Update every 10 NFTs
                    await sync_to_async(migration_job.save)()
        
        # Final update
        migration_job.total_nfts = total_exported
        await sync_to_async(migration_job.save)()
        
        await sync_to_async(MigrationLog.log_event)(
            migration_job=migration_job,
            event_type='data_export',
            message=f"Data export completed: {total_exported} NFTs exported",
            level='info',
            details={'total_exported': total_exported}
        )
        
        self.logger.info(
            "Export phase completed",
            job_id=str(migration_job.job_id),
            total_exported=total_exported
        )
    
    async def _mapping_phase(self, migration_job: MigrationJob):
        """Map and validate NFT data."""
        self.logger.info(
            "Starting mapping phase",
            job_id=str(migration_job.job_id)
        )
        
        await sync_to_async(MigrationLog.log_event)(
            migration_job=migration_job,
            event_type='data_mapping',
            message="Starting data mapping and validation",
            level='info'
        )
        
        # Get pending NFTs
        sei_nfts = await sync_to_async(
            lambda: list(migration_job.sei_nfts.filter(migration_status='pending'))
        )()
        
        for sei_nft in sei_nfts:
            try:
                # Convert to SeiNFTData
                sei_nft_data = SeiNFTData(
                    contract_address=sei_nft.sei_contract_address,
                    token_id=sei_nft.sei_token_id,
                    owner_address=sei_nft.sei_owner_address,
                    name=sei_nft.name,
                    description=sei_nft.description,
                    image_url=sei_nft.image_url,
                    external_url=sei_nft.external_url,
                    attributes=sei_nft.attributes,
                    metadata=sei_nft.attributes,  # Use attributes as metadata
                    data_hash=sei_nft.sei_data_hash
                )
                
                # Validate data
                validation_result = await self.migration_validator.validate_migration_data(sei_nft_data)
                
                if not validation_result.is_valid:
                    sei_nft.migration_status = 'failed'
                    sei_nft.validation_errors = validation_result.validation_errors
                    await sync_to_async(sei_nft.save)()
                    
                    migration_job.failed_migrations += 1
                    continue
                
                # Map data
                mapping = await self.migration_mapper.map_nft_data(sei_nft_data)
                
                # Validate mapping
                mapping_validation = await self.migration_validator.validate_migration_mapping(mapping)
                
                if not mapping_validation.is_valid:
                    sei_nft.migration_status = 'failed'
                    sei_nft.validation_errors = mapping_validation.validation_errors
                    await sync_to_async(sei_nft.save)()
                    
                    migration_job.failed_migrations += 1
                    continue
                
                # Store mapping results (you could extend SeiNFT model to store this)
                sei_nft.migration_status = 'in_progress'
                await sync_to_async(sei_nft.save)()
                
            except Exception as e:
                self.logger.error(
                    "Failed to map NFT",
                    job_id=str(migration_job.job_id),
                    sei_nft_id=sei_nft.id,
                    error=str(e)
                )
                
                sei_nft.migration_status = 'failed'
                sei_nft.validation_errors = [f"Mapping failed: {str(e)}"]
                await sync_to_async(sei_nft.save)()
                
                migration_job.failed_migrations += 1
        
        # Update job progress
        migration_job.processed_nfts = await sync_to_async(
            lambda: migration_job.sei_nfts.exclude(migration_status='pending').count()
        )()
        await sync_to_async(migration_job.save)()
        
        self.logger.info(
            "Mapping phase completed",
            job_id=str(migration_job.job_id),
            processed=migration_job.processed_nfts,
            failed=migration_job.failed_migrations
        )

    async def _minting_phase(self, migration_job: MigrationJob):
        """Mint NFTs on Solana blockchain."""
        self.logger.info(
            "Starting minting phase",
            job_id=str(migration_job.job_id)
        )

        await sync_to_async(MigrationLog.log_event)(
            migration_job=migration_job,
            event_type='nft_migration',
            message="Starting Solana NFT minting",
            level='info'
        )

        # Get or create Merkle tree
        trees = await self.merkle_tree_manager.list_trees()
        if not trees:
            config = self.merkle_tree_manager.create_tree_config(max_depth=14)
            merkle_tree = await self.merkle_tree_manager.create_merkle_tree(
                config, f"Migration Tree - {migration_job.name}"
            )
            self.merkle_tree_manager.save_trees_to_file('managed_trees.json')
        else:
            merkle_tree = trees[0]  # Use first available tree

        # Get NFTs ready for minting
        sei_nfts = await sync_to_async(
            lambda: list(migration_job.sei_nfts.filter(migration_status='in_progress'))
        )()

        for sei_nft in sei_nfts:
            try:
                # Create Solana metadata (simplified - in real implementation,
                # you'd retrieve the mapped metadata from the mapping phase)
                from ..cnft_minting import NFTMetadata

                solana_metadata = NFTMetadata(
                    name=sei_nft.name,
                    symbol="TREE",  # Default symbol
                    description=sei_nft.description,
                    image=sei_nft.image_url,
                    external_url=sei_nft.external_url,
                    attributes=sei_nft.attributes
                )

                # Create mint request
                mint_request = MintRequest(
                    tree_address=merkle_tree.tree_address,
                    recipient=str(self.merkle_tree_manager.authority),
                    metadata=solana_metadata
                )

                # Mint compressed NFT
                mint_result = await self.cnft_minter.mint_compressed_nft(
                    mint_request, confirm_transaction=True
                )

                # Update NFT record
                sei_nft.migration_status = 'completed'
                sei_nft.solana_mint_address = mint_result.asset_id
                sei_nft.solana_asset_id = mint_result.asset_id
                sei_nft.migration_date = timezone.now()
                await sync_to_async(sei_nft.save)()

                # Create Tree record in database
                await self._create_tree_record(sei_nft, mint_result, merkle_tree)

                # Log successful migration
                await sync_to_async(MigrationLog.log_event)(
                    migration_job=migration_job,
                    event_type='nft_migration',
                    message=f"Successfully migrated NFT {sei_nft.sei_token_id}",
                    level='info',
                    sei_nft=sei_nft,
                    details={
                        'solana_asset_id': mint_result.asset_id,
                        'merkle_tree': merkle_tree.tree_address
                    }
                )

                migration_job.successful_migrations += 1

            except Exception as e:
                self.logger.error(
                    "Failed to mint NFT",
                    job_id=str(migration_job.job_id),
                    sei_nft_id=sei_nft.id,
                    error=str(e)
                )

                sei_nft.migration_status = 'failed'
                sei_nft.validation_errors.append(f"Minting failed: {str(e)}")
                await sync_to_async(sei_nft.save)()

                migration_job.failed_migrations += 1

                # Log failed migration
                await sync_to_async(MigrationLog.log_event)(
                    migration_job=migration_job,
                    event_type='error',
                    message=f"Failed to migrate NFT {sei_nft.sei_token_id}: {str(e)}",
                    level='error',
                    sei_nft=sei_nft,
                    error_code='MINT_FAILED',
                    details={'error': str(e)}
                )

        # Update job progress
        migration_job.processed_nfts = await sync_to_async(
            lambda: migration_job.sei_nfts.exclude(migration_status='pending').count()
        )()
        await sync_to_async(migration_job.save)()

        self.logger.info(
            "Minting phase completed",
            job_id=str(migration_job.job_id),
            successful=migration_job.successful_migrations,
            failed=migration_job.failed_migrations
        )

    async def _create_tree_record(self, sei_nft: SeiNFT, mint_result, merkle_tree):
        """Create Tree record in database for migrated NFT."""
        try:
            # Get or create user for the tree owner
            owner, created = await sync_to_async(User.objects.get_or_create)(
                username=f"migrated_user_{sei_nft.sei_owner_address[-8:]}",
                defaults={
                    'email': f"migrated_{sei_nft.sei_owner_address[-8:]}@replantworld.com",
                    'first_name': 'Migrated',
                    'last_name': 'User'
                }
            )

            # Extract tree information from attributes
            species = 'Unknown Species'
            location_name = 'Unknown Location'

            for attr in sei_nft.attributes:
                trait_type = attr.get('trait_type', '').lower()
                if 'species' in trait_type:
                    species = str(attr.get('value', species))
                elif 'location' in trait_type:
                    location_name = str(attr.get('value', location_name))

            # Create Tree record
            tree = await sync_to_async(Tree.objects.create)(
                mint_address=mint_result.asset_id,
                merkle_tree_address=merkle_tree.tree_address,
                leaf_index=mint_result.leaf_index,
                asset_id=mint_result.asset_id,
                species=species,
                planted_date=date.today(),  # Default to today
                location_latitude=Decimal('0.0'),  # Default coordinates
                location_longitude=Decimal('0.0'),
                location_name=location_name,
                status='growing',
                estimated_carbon_kg=Decimal('1.0'),  # Default value
                owner=owner,
                planter=owner,
                notes=f'Migrated from Sei blockchain. Original contract: {sei_nft.sei_contract_address}, Token ID: {sei_nft.sei_token_id}',
                image_url=sei_nft.image_url,
                verification_status='pending'
            )

            self.logger.info(
                "Created Tree record for migrated NFT",
                tree_id=str(tree.tree_id),
                sei_nft_id=sei_nft.id
            )

        except Exception as e:
            self.logger.error(
                "Failed to create Tree record",
                sei_nft_id=sei_nft.id,
                error=str(e)
            )

    async def _complete_migration(self, migration_job: MigrationJob):
        """Complete the migration job."""
        migration_job.status = 'completed'
        migration_job.completed_at = timezone.now()
        await sync_to_async(migration_job.save)()

        await sync_to_async(MigrationLog.log_event)(
            migration_job=migration_job,
            event_type='job_completed',
            message=f"Migration job completed successfully",
            level='info',
            details={
                'total_nfts': migration_job.total_nfts,
                'successful_migrations': migration_job.successful_migrations,
                'failed_migrations': migration_job.failed_migrations,
                'success_rate': migration_job.success_rate
            }
        )

        self.service_stats['migrations_completed'] += 1
        self.service_stats['total_nfts_migrated'] += migration_job.successful_migrations

        self.logger.info(
            "Migration job completed",
            job_id=str(migration_job.job_id),
            success_rate=migration_job.success_rate,
            duration=migration_job.duration
        )

    async def _fail_migration(self, migration_job: MigrationJob, error: str):
        """Mark migration job as failed."""
        migration_job.status = 'failed'
        migration_job.error_message = error
        migration_job.completed_at = timezone.now()
        await sync_to_async(migration_job.save)()

        await sync_to_async(MigrationLog.log_event)(
            migration_job=migration_job,
            event_type='job_failed',
            message=f"Migration job failed: {error}",
            level='error',
            error_code='JOB_FAILED',
            details={'error': error}
        )

        self.service_stats['migrations_failed'] += 1

        self.logger.error(
            "Migration job failed",
            job_id=str(migration_job.job_id),
            error=error
        )

    async def _store_sei_nft_data(self, sei_nft_data: SeiNFTData, migration_job: MigrationJob):
        """Store Sei NFT data in database."""
        try:
            sei_nft = await sync_to_async(SeiNFT.objects.create)(
                sei_contract_address=sei_nft_data.contract_address,
                sei_token_id=sei_nft_data.token_id,
                sei_owner_address=sei_nft_data.owner_address,
                name=sei_nft_data.name,
                description=sei_nft_data.description,
                image_url=sei_nft_data.image_url,
                external_url=sei_nft_data.external_url,
                attributes=sei_nft_data.attributes,
                migration_job=migration_job,
                sei_data_hash=sei_nft_data.data_hash
            )

            return sei_nft

        except Exception as e:
            self.logger.error(
                "Failed to store Sei NFT data",
                contract_address=sei_nft_data.contract_address,
                token_id=sei_nft_data.token_id,
                error=str(e)
            )
            raise

    async def rollback_migration(self, migration_job_id: str, reason: str = "") -> ValidationResult:
        """
        Rollback a migration job.

        Args:
            migration_job_id: Migration job ID to rollback
            reason: Reason for rollback

        Returns:
            ValidationResult with rollback details
        """
        result = await self.migration_validator.perform_rollback(migration_job_id, reason)

        if result.successful_validations > 0:
            self.service_stats['total_rollbacks'] += 1

        return result

    def get_service_statistics(self) -> Dict[str, Any]:
        """Get migration service statistics."""
        stats = self.service_stats.copy()

        if stats['service_start_time']:
            stats['uptime_seconds'] = time.time() - stats['service_start_time']

        if stats['migrations_started'] > 0:
            stats['completion_rate'] = (stats['migrations_completed'] / stats['migrations_started']) * 100

        return stats
