"""
Migration Validator for Sei to Solana NFT Migration

This module provides comprehensive validation for migration integrity,
progress tracking, and rollback capabilities.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import structlog
from asgiref.sync import sync_to_async

from .data_exporter import SeiNFTData
from .migration_mapper import MigrationMapping
from ..models import SeiNFT, MigrationJob, MigrationLog
from ..config import get_migration_config

logger = structlog.get_logger(__name__)


class MigrationStatus(Enum):
    """Migration status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ValidationResult:
    """
    Data structure for validation results.
    
    This represents the comprehensive validation results for a migration
    including integrity checks, progress tracking, and rollback information.
    """
    
    # Validation metadata
    validation_id: str
    validation_timestamp: float
    validator_version: str = "1.0"
    
    # Validation results
    is_valid: bool = True
    validation_errors: List[str] = None
    validation_warnings: List[str] = None
    
    # Integrity checks
    data_integrity_valid: bool = True
    metadata_integrity_valid: bool = True
    blockchain_integrity_valid: bool = True
    
    # Progress tracking
    total_items: int = 0
    validated_items: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    
    # Performance metrics
    validation_duration_ms: float = 0
    items_per_second: float = 0
    
    # Rollback information
    rollback_required: bool = False
    rollback_reason: str = ""
    rollback_steps: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.validation_errors is None:
            self.validation_errors = []
        if self.validation_warnings is None:
            self.validation_warnings = []
        if self.rollback_steps is None:
            self.rollback_steps = []
    
    def add_error(self, error: str):
        """Add validation error."""
        self.validation_errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add validation warning."""
        self.validation_warnings.append(warning)
    
    def add_rollback_step(self, step_type: str, description: str, data: Dict[str, Any] = None):
        """Add rollback step."""
        self.rollback_steps.append({
            'step_type': step_type,
            'description': description,
            'data': data or {},
            'timestamp': time.time()
        })
        self.rollback_required = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class MigrationValidator:
    """
    Comprehensive migration validator for Sei to Solana NFT migration.
    
    This class provides validation for data integrity, metadata consistency,
    progress tracking, and rollback capabilities.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the migration validator.
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or get_migration_config()
        self.logger = logger.bind(component="MigrationValidator")
        
        # Validation statistics
        self.validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'rollbacks_performed': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Load validation rules
        self.validation_rules = self._load_validation_rules()
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load validation rules from configuration."""
        return self.config.get('validation_rules', {
            'data_integrity': {
                'hash_validation': True,
                'required_fields': ['contract_address', 'token_id', 'name'],
                'max_field_lengths': {
                    'name': 200,
                    'description': 1000,
                    'image_url': 500
                }
            },
            'metadata_integrity': {
                'validate_json_structure': True,
                'validate_attributes': True,
                'max_attributes': 50,
                'required_metadata_fields': ['name']
            },
            'blockchain_integrity': {
                'validate_addresses': True,
                'validate_token_ids': True,
                'check_duplicates': True
            },
            'progress_tracking': {
                'checkpoint_interval': 100,
                'progress_report_interval': 10
            },
            'rollback': {
                'max_rollback_depth': 1000,
                'rollback_timeout_seconds': 300,
                'preserve_logs': True
            }
        })
    
    async def validate_migration_data(self, sei_nft_data: SeiNFTData) -> ValidationResult:
        """
        Validate individual NFT migration data.
        
        Args:
            sei_nft_data: Sei NFT data to validate
            
        Returns:
            ValidationResult instance
        """
        start_time = time.time()
        validation_id = f"val_{int(start_time)}_{sei_nft_data.contract_address[-8:]}_{sei_nft_data.token_id}"
        
        result = ValidationResult(
            validation_id=validation_id,
            validation_timestamp=start_time,
            total_items=1
        )
        
        try:
            self.logger.info(
                "Starting migration data validation",
                validation_id=validation_id,
                contract_address=sei_nft_data.contract_address,
                token_id=sei_nft_data.token_id
            )
            
            # Perform validation checks
            await self._validate_data_integrity(sei_nft_data, result)
            await self._validate_metadata_integrity(sei_nft_data, result)
            await self._validate_blockchain_integrity(sei_nft_data, result)
            
            # Update statistics
            result.validated_items = 1
            if result.is_valid:
                result.successful_validations = 1
                self.validation_stats['successful_validations'] += 1
            else:
                result.failed_validations = 1
                self.validation_stats['failed_validations'] += 1
            
            # Calculate performance metrics
            end_time = time.time()
            result.validation_duration_ms = (end_time - start_time) * 1000
            result.items_per_second = 1 / (end_time - start_time) if end_time > start_time else 0
            
            self.logger.info(
                "Migration data validation completed",
                validation_id=validation_id,
                is_valid=result.is_valid,
                errors_count=len(result.validation_errors),
                warnings_count=len(result.validation_warnings),
                duration_ms=result.validation_duration_ms
            )
            
            return result
            
        except Exception as e:
            end_time = time.time()
            result.validation_duration_ms = (end_time - start_time) * 1000
            result.add_error(f"Validation failed: {str(e)}")
            result.failed_validations = 1
            
            self.logger.error(
                "Migration data validation failed",
                validation_id=validation_id,
                error=str(e),
                duration_ms=result.validation_duration_ms
            )
            
            self.validation_stats['failed_validations'] += 1
            return result
        
        finally:
            self.validation_stats['total_validations'] += 1
    
    async def validate_migration_mapping(self, mapping: MigrationMapping) -> ValidationResult:
        """
        Validate migration mapping results.
        
        Args:
            mapping: Migration mapping to validate
            
        Returns:
            ValidationResult instance
        """
        start_time = time.time()
        validation_id = f"map_val_{int(start_time)}_{mapping.sei_nft_data.contract_address[-8:]}"
        
        result = ValidationResult(
            validation_id=validation_id,
            validation_timestamp=start_time,
            total_items=1
        )
        
        try:
            self.logger.info(
                "Starting migration mapping validation",
                validation_id=validation_id,
                mapping_valid=mapping.is_valid
            )
            
            # Check mapping validity
            if not mapping.is_valid:
                result.add_error("Mapping is marked as invalid")
                for error in mapping.validation_errors:
                    result.add_error(f"Mapping error: {error}")
            
            # Validate Solana metadata
            if mapping.solana_metadata:
                await self._validate_solana_metadata(mapping.solana_metadata, result)
            else:
                result.add_error("No Solana metadata generated")
            
            # Check transformations
            if mapping.transformations:
                for warning in mapping.warnings:
                    result.add_warning(f"Mapping warning: {warning}")
            
            # Update statistics
            result.validated_items = 1
            if result.is_valid:
                result.successful_validations = 1
            else:
                result.failed_validations = 1
            
            # Calculate performance metrics
            end_time = time.time()
            result.validation_duration_ms = (end_time - start_time) * 1000
            result.items_per_second = 1 / (end_time - start_time) if end_time > start_time else 0
            
            return result
            
        except Exception as e:
            end_time = time.time()
            result.validation_duration_ms = (end_time - start_time) * 1000
            result.add_error(f"Mapping validation failed: {str(e)}")
            result.failed_validations = 1
            
            return result
    
    async def validate_migration_progress(self, migration_job_id: str) -> ValidationResult:
        """
        Validate migration job progress and integrity.
        
        Args:
            migration_job_id: Migration job ID to validate
            
        Returns:
            ValidationResult instance
        """
        start_time = time.time()
        validation_id = f"progress_val_{int(start_time)}_{migration_job_id[-8:]}"
        
        result = ValidationResult(
            validation_id=validation_id,
            validation_timestamp=start_time
        )
        
        try:
            # Get migration job
            migration_job = await sync_to_async(
                lambda: MigrationJob.objects.get(job_id=migration_job_id)
            )()
            
            result.total_items = migration_job.total_nfts
            result.validated_items = migration_job.processed_nfts
            result.successful_validations = migration_job.successful_migrations
            result.failed_validations = migration_job.failed_migrations
            
            self.logger.info(
                "Validating migration progress",
                validation_id=validation_id,
                job_id=migration_job_id,
                progress=f"{migration_job.processed_nfts}/{migration_job.total_nfts}"
            )
            
            # Validate progress consistency
            if migration_job.processed_nfts > migration_job.total_nfts:
                result.add_error("Processed NFTs exceed total NFTs")
            
            if (migration_job.successful_migrations + migration_job.failed_migrations) != migration_job.processed_nfts:
                result.add_error("Success + failure count doesn't match processed count")
            
            # Check for stalled migration
            if migration_job.status == 'running' and migration_job.started_at:
                time_since_start = time.time() - migration_job.started_at.timestamp()
                max_duration = self.config.get('max_migration_duration_hours', 24) * 3600
                
                if time_since_start > max_duration:
                    result.add_warning(f"Migration has been running for {time_since_start/3600:.1f} hours")
                    result.add_rollback_step(
                        'cancel_job', 
                        'Cancel stalled migration job',
                        {'job_id': migration_job_id, 'reason': 'timeout'}
                    )
            
            # Validate database consistency
            await self._validate_database_consistency(migration_job, result)
            
            return result
            
        except Exception as e:
            result.add_error(f"Progress validation failed: {str(e)}")
            return result

    async def perform_rollback(self, migration_job_id: str, reason: str = "") -> ValidationResult:
        """
        Perform rollback of a migration job.

        Args:
            migration_job_id: Migration job ID to rollback
            reason: Reason for rollback

        Returns:
            ValidationResult with rollback details
        """
        start_time = time.time()
        validation_id = f"rollback_{int(start_time)}_{migration_job_id[-8:]}"

        result = ValidationResult(
            validation_id=validation_id,
            validation_timestamp=start_time,
            rollback_required=True,
            rollback_reason=reason
        )

        try:
            self.logger.info(
                "Starting migration rollback",
                validation_id=validation_id,
                job_id=migration_job_id,
                reason=reason
            )

            # Get migration job and related NFTs
            migration_job = await sync_to_async(
                lambda: MigrationJob.objects.get(job_id=migration_job_id)
            )()

            sei_nfts = await sync_to_async(
                lambda: list(migration_job.sei_nfts.filter(migration_status='completed'))
            )()

            result.total_items = len(sei_nfts)

            # Log rollback start
            await sync_to_async(MigrationLog.log_event)(
                migration_job=migration_job,
                event_type='rollback',
                message=f"Starting rollback: {reason}",
                level='warning',
                details={'validation_id': validation_id, 'reason': reason}
            )

            # Rollback each NFT
            rollback_count = 0
            for sei_nft in sei_nfts:
                try:
                    # Reset migration status
                    sei_nft.migration_status = 'pending'
                    sei_nft.solana_mint_address = ''
                    sei_nft.solana_asset_id = ''
                    sei_nft.migration_date = None

                    await sync_to_async(sei_nft.save)()

                    # Log individual rollback
                    await sync_to_async(MigrationLog.log_event)(
                        migration_job=migration_job,
                        event_type='rollback',
                        message=f"Rolled back NFT {sei_nft.sei_token_id}",
                        level='info',
                        sei_nft=sei_nft,
                        details={'original_status': 'completed'}
                    )

                    rollback_count += 1
                    result.successful_validations += 1

                except Exception as e:
                    self.logger.error(
                        "Failed to rollback NFT",
                        sei_nft_id=sei_nft.id,
                        error=str(e)
                    )
                    result.add_error(f"Failed to rollback NFT {sei_nft.sei_token_id}: {str(e)}")
                    result.failed_validations += 1

            # Update migration job status
            migration_job.status = 'cancelled'
            migration_job.successful_migrations -= rollback_count
            migration_job.processed_nfts -= rollback_count
            migration_job.error_message = f"Rolled back due to: {reason}"

            await sync_to_async(migration_job.save)()

            # Log rollback completion
            await sync_to_async(MigrationLog.log_event)(
                migration_job=migration_job,
                event_type='rollback',
                message=f"Rollback completed: {rollback_count} NFTs rolled back",
                level='info',
                details={
                    'validation_id': validation_id,
                    'rollback_count': rollback_count,
                    'reason': reason
                }
            )

            result.validated_items = len(sei_nfts)

            self.logger.info(
                "Migration rollback completed",
                validation_id=validation_id,
                job_id=migration_job_id,
                rollback_count=rollback_count,
                failed_rollbacks=result.failed_validations
            )

            self.validation_stats['rollbacks_performed'] += 1

            return result

        except Exception as e:
            result.add_error(f"Rollback failed: {str(e)}")

            self.logger.error(
                "Migration rollback failed",
                validation_id=validation_id,
                job_id=migration_job_id,
                error=str(e)
            )

            return result

    async def _validate_data_integrity(self, sei_nft_data: SeiNFTData, result: ValidationResult):
        """Validate data integrity."""
        rules = self.validation_rules['data_integrity']

        # Hash validation
        if rules['hash_validation']:
            expected_hash = sei_nft_data.calculate_hash()
            if sei_nft_data.data_hash != expected_hash:
                result.add_error(f"Data hash mismatch: expected {expected_hash}, got {sei_nft_data.data_hash}")
                result.data_integrity_valid = False

        # Required fields validation
        for field in rules['required_fields']:
            if not getattr(sei_nft_data, field, None):
                result.add_error(f"Required field '{field}' is missing or empty")
                result.data_integrity_valid = False

        # Field length validation
        max_lengths = rules['max_field_lengths']
        for field, max_length in max_lengths.items():
            value = getattr(sei_nft_data, field, '')
            if len(str(value)) > max_length:
                result.add_error(f"Field '{field}' exceeds maximum length of {max_length}")
                result.data_integrity_valid = False

    async def _validate_metadata_integrity(self, sei_nft_data: SeiNFTData, result: ValidationResult):
        """Validate metadata integrity."""
        rules = self.validation_rules['metadata_integrity']

        # JSON structure validation
        if rules['validate_json_structure']:
            try:
                json.dumps(sei_nft_data.metadata)
                json.dumps(sei_nft_data.attributes)
            except (TypeError, ValueError) as e:
                result.add_error(f"Invalid JSON structure in metadata: {str(e)}")
                result.metadata_integrity_valid = False

        # Attributes validation
        if rules['validate_attributes'] and sei_nft_data.attributes:
            if len(sei_nft_data.attributes) > rules['max_attributes']:
                result.add_warning(f"NFT has {len(sei_nft_data.attributes)} attributes, exceeding recommended maximum of {rules['max_attributes']}")

            for i, attr in enumerate(sei_nft_data.attributes):
                if not isinstance(attr, dict):
                    result.add_error(f"Attribute {i} is not a valid dictionary")
                    result.metadata_integrity_valid = False

        # Required metadata fields
        for field in rules['required_metadata_fields']:
            if field not in sei_nft_data.metadata or not sei_nft_data.metadata[field]:
                result.add_error(f"Required metadata field '{field}' is missing or empty")
                result.metadata_integrity_valid = False

    async def _validate_blockchain_integrity(self, sei_nft_data: SeiNFTData, result: ValidationResult):
        """Validate blockchain-specific integrity."""
        rules = self.validation_rules['blockchain_integrity']

        # Address validation
        if rules['validate_addresses']:
            if not sei_nft_data.contract_address or len(sei_nft_data.contract_address) < 20:
                result.add_error("Invalid contract address")
                result.blockchain_integrity_valid = False

            if not sei_nft_data.owner_address or len(sei_nft_data.owner_address) < 20:
                result.add_error("Invalid owner address")
                result.blockchain_integrity_valid = False

        # Token ID validation
        if rules['validate_token_ids']:
            if not sei_nft_data.token_id:
                result.add_error("Token ID is missing")
                result.blockchain_integrity_valid = False

        # Duplicate check
        if rules['check_duplicates']:
            existing_nft = await sync_to_async(
                lambda: SeiNFT.objects.filter(
                    sei_contract_address=sei_nft_data.contract_address,
                    sei_token_id=sei_nft_data.token_id
                ).first()
            )()

            if existing_nft:
                result.add_warning(f"NFT already exists in database with status: {existing_nft.migration_status}")

    async def _validate_solana_metadata(self, solana_metadata, result: ValidationResult):
        """Validate Solana metadata structure."""
        if not solana_metadata.name:
            result.add_error("Solana metadata missing name")

        if not solana_metadata.symbol:
            result.add_error("Solana metadata missing symbol")

        if not solana_metadata.image:
            result.add_warning("Solana metadata missing image URL")

        # Validate attributes structure
        if solana_metadata.attributes:
            for i, attr in enumerate(solana_metadata.attributes):
                if not isinstance(attr, dict):
                    result.add_error(f"Solana metadata attribute {i} is not a dictionary")
                elif 'trait_type' not in attr:
                    result.add_warning(f"Solana metadata attribute {i} missing trait_type")

    async def _validate_database_consistency(self, migration_job, result: ValidationResult):
        """Validate database consistency for migration job."""
        # Check NFT count consistency
        db_nft_count = await sync_to_async(
            lambda: migration_job.sei_nfts.count()
        )()

        if db_nft_count != migration_job.total_nfts:
            result.add_error(f"Database NFT count ({db_nft_count}) doesn't match job total ({migration_job.total_nfts})")

        # Check status consistency
        status_counts = await sync_to_async(
            lambda: {
                'completed': migration_job.sei_nfts.filter(migration_status='completed').count(),
                'failed': migration_job.sei_nfts.filter(migration_status='failed').count(),
                'pending': migration_job.sei_nfts.filter(migration_status='pending').count(),
                'in_progress': migration_job.sei_nfts.filter(migration_status='in_progress').count()
            }
        )()

        if status_counts['completed'] != migration_job.successful_migrations:
            result.add_error(f"Completed NFT count mismatch: DB={status_counts['completed']}, Job={migration_job.successful_migrations}")

        if status_counts['failed'] != migration_job.failed_migrations:
            result.add_error(f"Failed NFT count mismatch: DB={status_counts['failed']}, Job={migration_job.failed_migrations}")

    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation statistics."""
        stats = self.validation_stats.copy()

        if stats['total_validations'] > 0:
            stats['success_rate'] = (stats['successful_validations'] / stats['total_validations']) * 100

        return stats
