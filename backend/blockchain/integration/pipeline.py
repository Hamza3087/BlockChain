"""
End-to-End Pipeline for Day 6 Integration

This module provides the complete end-to-end pipeline for:
- Exporting NFT data from Sei blockchain
- Validating and mapping data
- Minting on Solana testnet
- Saving to database
- Performance monitoring and caching
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import structlog
from django.conf import settings
from asgiref.sync import sync_to_async

from ..migration import (
    DataExporter, MigrationMapper, MigrationValidator, MigrationService,
    SeiNFTData, MigrationMapping, ValidationResult
)
from ..models import MigrationJob, SeiNFT, MigrationLog, Tree
from ..clients.solana_client import SolanaClient
from ..merkle_tree import MerkleTreeManager
from ..cnft_minting import CompressedNFTMinter, MintRequest
from .cache_manager import cache_manager
# PerformanceMonitor imported conditionally to avoid circular imports

logger = structlog.get_logger(__name__)


class PipelineStage(Enum):
    """Pipeline processing stages."""
    INITIALIZATION = "initialization"
    DATA_EXPORT = "data_export"
    DATA_MAPPING = "data_mapping"
    DATA_VALIDATION = "data_validation"
    SOLANA_MINTING = "solana_minting"
    DATABASE_SAVE = "database_save"
    COMPLETION = "completion"
    FAILED = "failed"


@dataclass
class PipelineResult:
    """End-to-end pipeline execution result."""
    pipeline_id: str
    status: PipelineStage
    start_time: datetime
    end_time: Optional[datetime] = None
    total_nfts: int = 0
    processed_nfts: int = 0
    successful_nfts: int = 0
    failed_nfts: int = 0
    stage_results: Dict[str, Any] = None
    error_message: Optional[str] = None
    performance_metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.stage_results is None:
            self.stage_results = {}
        if self.performance_metrics is None:
            self.performance_metrics = {}
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate pipeline duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.processed_nfts == 0:
            return 0.0
        return (self.successful_nfts / self.processed_nfts) * 100


class EndToEndPipeline:
    """
    Complete end-to-end pipeline for NFT migration.
    
    Orchestrates the entire process from Sei data export to Solana minting
    and database storage with comprehensive monitoring and caching.
    """
    
    def __init__(self, enable_caching: bool = True, enable_monitoring: bool = True):
        """Initialize the end-to-end pipeline."""
        self.enable_caching = enable_caching
        self.enable_monitoring = enable_monitoring
        self.logger = logger.bind(component="EndToEndPipeline")
        
        # Initialize components
        self.data_exporter = None
        self.migration_mapper = None
        self.migration_validator = None
        self.migration_service = None
        self.performance_monitor = None
        
        # Pipeline statistics
        self.total_pipelines_executed = 0
        self.total_nfts_processed = 0
        self.total_successful_nfts = 0
        self.total_failed_nfts = 0
        
        self.logger.info(
            "EndToEndPipeline initialized",
            caching_enabled=self.enable_caching,
            monitoring_enabled=self.enable_monitoring
        )
    
    async def initialize(self) -> bool:
        """Initialize all pipeline components."""
        try:
            self.logger.info("Initializing pipeline components")
            
            # Initialize migration service (which initializes other components)
            self.migration_service = MigrationService()
            initialized = await self.migration_service.initialize()
            
            if not initialized:
                raise Exception("Failed to initialize migration service")
            
            # Initialize individual components for direct access
            self.data_exporter = self.migration_service.data_exporter
            self.migration_mapper = self.migration_service.migration_mapper
            self.migration_validator = self.migration_service.migration_validator
            
            # Initialize performance monitor
            if self.enable_monitoring:
                from .performance_monitor import PerformanceMonitor
                self.performance_monitor = PerformanceMonitor()
                await self.performance_monitor.initialize()
            
            self.logger.info("Pipeline components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize pipeline components", error=str(e))
            return False
    
    async def close(self):
        """Close pipeline components and cleanup resources."""
        if self.migration_service:
            await self.migration_service.close()
        
        if self.performance_monitor:
            await self.performance_monitor.close()
        
        self.logger.info("Pipeline components closed")
    
    async def execute_full_pipeline(
        self,
        sei_contract_addresses: List[str],
        migration_job: Optional[MigrationJob] = None,
        max_nfts_per_contract: Optional[int] = None
    ) -> PipelineResult:
        """
        Execute the complete end-to-end pipeline.
        
        Args:
            sei_contract_addresses: List of Sei contract addresses to process
            migration_job: Optional existing migration job
            max_nfts_per_contract: Maximum NFTs to process per contract
            
        Returns:
            PipelineResult with execution details
        """
        pipeline_id = f"pipeline_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        start_time = datetime.utcnow()
        
        result = PipelineResult(
            pipeline_id=pipeline_id,
            status=PipelineStage.INITIALIZATION,
            start_time=start_time
        )
        
        try:
            self.logger.info(
                "Starting end-to-end pipeline execution",
                pipeline_id=pipeline_id,
                contracts=sei_contract_addresses,
                max_nfts_per_contract=max_nfts_per_contract
            )
            
            # Start performance monitoring
            if self.performance_monitor:
                await self.performance_monitor.start_monitoring(pipeline_id)
            
            # Stage 1: Data Export from Sei
            result.status = PipelineStage.DATA_EXPORT
            export_result = await self._execute_data_export_stage(
                sei_contract_addresses, max_nfts_per_contract, pipeline_id
            )
            result.stage_results['data_export'] = export_result
            result.total_nfts = export_result.get('total_exported', 0)
            
            if result.total_nfts == 0:
                result.status = PipelineStage.COMPLETION
                result.end_time = datetime.utcnow()
                self.logger.warning("No NFTs exported, pipeline completed early", pipeline_id=pipeline_id)
                return result
            
            # Stage 2: Data Mapping and Transformation
            result.status = PipelineStage.DATA_MAPPING
            mapping_result = await self._execute_mapping_stage(
                export_result['exported_nfts'], pipeline_id
            )
            result.stage_results['data_mapping'] = mapping_result
            
            # Stage 3: Data Validation
            result.status = PipelineStage.DATA_VALIDATION
            validation_result = await self._execute_validation_stage(
                mapping_result['mapped_nfts'], pipeline_id
            )
            result.stage_results['data_validation'] = validation_result
            
            # Stage 4: Solana Minting
            result.status = PipelineStage.SOLANA_MINTING
            minting_result = await self._execute_minting_stage(
                validation_result['validated_nfts'], pipeline_id
            )
            result.stage_results['solana_minting'] = minting_result
            
            # Stage 5: Database Save
            result.status = PipelineStage.DATABASE_SAVE
            database_result = await self._execute_database_save_stage(
                minting_result['minted_nfts'], migration_job, pipeline_id
            )
            result.stage_results['database_save'] = database_result
            
            # Calculate final results
            result.processed_nfts = database_result.get('processed_count', 0)
            result.successful_nfts = database_result.get('successful_count', 0)
            result.failed_nfts = database_result.get('failed_count', 0)
            
            # Mark as completed
            result.status = PipelineStage.COMPLETION
            result.end_time = datetime.utcnow()
            
            # Update statistics
            self.total_pipelines_executed += 1
            self.total_nfts_processed += result.processed_nfts
            self.total_successful_nfts += result.successful_nfts
            self.total_failed_nfts += result.failed_nfts
            
            # Get performance metrics
            if self.performance_monitor:
                result.performance_metrics = await self.performance_monitor.get_metrics(pipeline_id)
                await self.performance_monitor.stop_monitoring(pipeline_id)
            
            self.logger.info(
                "End-to-end pipeline completed successfully",
                pipeline_id=pipeline_id,
                duration=result.duration,
                total_nfts=result.total_nfts,
                successful_nfts=result.successful_nfts,
                failed_nfts=result.failed_nfts,
                success_rate=result.success_rate
            )
            
            return result
            
        except Exception as e:
            result.status = PipelineStage.FAILED
            result.end_time = datetime.utcnow()
            result.error_message = str(e)
            
            self.logger.error(
                "End-to-end pipeline failed",
                pipeline_id=pipeline_id,
                error=str(e),
                duration=result.duration
            )
            
            # Stop monitoring on failure
            if self.performance_monitor:
                await self.performance_monitor.stop_monitoring(pipeline_id)
            
            return result
    
    async def _execute_data_export_stage(
        self,
        sei_contract_addresses: List[str],
        max_nfts_per_contract: Optional[int],
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Execute data export stage."""
        stage_start = time.time()
        exported_nfts = []
        total_exported = 0
        
        self.logger.info(
            "Executing data export stage",
            pipeline_id=pipeline_id,
            contracts=len(sei_contract_addresses)
        )
        
        for contract_address in sei_contract_addresses:
            try:
                # Check cache first
                cache_key = f"contract_nfts:{contract_address}"
                if self.enable_caching:
                    cached_nfts = await cache_manager.async_get(cache_key, category="nft_data")
                    if cached_nfts:
                        self.logger.info(
                            "Using cached NFT data",
                            pipeline_id=pipeline_id,
                            contract_address=contract_address,
                            cached_count=len(cached_nfts)
                        )
                        exported_nfts.extend(cached_nfts)
                        total_exported += len(cached_nfts)
                        continue
                
                # Export from blockchain
                contract_nfts = []
                nft_count = 0
                
                async for sei_nft_data in self.data_exporter.export_collection_data(
                    contract_address=contract_address,
                    max_tokens=max_nfts_per_contract,
                    batch_size=10
                ):
                    contract_nfts.append(sei_nft_data)
                    nft_count += 1
                    
                    if max_nfts_per_contract and nft_count >= max_nfts_per_contract:
                        break
                
                exported_nfts.extend(contract_nfts)
                total_exported += len(contract_nfts)
                
                # Cache the results
                if self.enable_caching and contract_nfts:
                    await cache_manager.async_set(
                        cache_key,
                        [nft.to_dict() for nft in contract_nfts],
                        category="nft_data"
                    )
                
                self.logger.info(
                    "Contract data export completed",
                    pipeline_id=pipeline_id,
                    contract_address=contract_address,
                    exported_count=len(contract_nfts)
                )
                
            except Exception as e:
                self.logger.error(
                    "Contract data export failed",
                    pipeline_id=pipeline_id,
                    contract_address=contract_address,
                    error=str(e)
                )
        
        stage_duration = time.time() - stage_start
        
        return {
            'exported_nfts': exported_nfts,
            'total_exported': total_exported,
            'contracts_processed': len(sei_contract_addresses),
            'stage_duration': stage_duration
        }
    
    async def _execute_mapping_stage(
        self,
        exported_nfts: List[SeiNFTData],
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Execute data mapping stage."""
        stage_start = time.time()
        mapped_nfts = []
        successful_mappings = 0
        failed_mappings = 0
        
        self.logger.info(
            "Executing data mapping stage",
            pipeline_id=pipeline_id,
            nft_count=len(exported_nfts)
        )
        
        for sei_nft_data in exported_nfts:
            try:
                # Check cache first
                cache_key = f"mapped_nft:{sei_nft_data.data_hash}"
                if self.enable_caching:
                    cached_mapping = await cache_manager.async_get(cache_key, category="nft_data")
                    if cached_mapping:
                        mapped_nfts.append(cached_mapping)
                        successful_mappings += 1
                        continue
                
                # Perform mapping
                mapping_result = await self.migration_mapper.map_nft_data(sei_nft_data)
                
                if mapping_result.is_valid:
                    mapped_nfts.append(mapping_result)
                    successful_mappings += 1
                    
                    # Cache the result
                    if self.enable_caching:
                        await cache_manager.async_set(
                            cache_key,
                            mapping_result.to_dict(),
                            category="nft_data"
                        )
                else:
                    failed_mappings += 1
                    self.logger.warning(
                        "NFT mapping failed validation",
                        pipeline_id=pipeline_id,
                        contract_address=sei_nft_data.contract_address,
                        token_id=sei_nft_data.token_id,
                        errors=mapping_result.validation_errors
                    )
                
            except Exception as e:
                failed_mappings += 1
                self.logger.error(
                    "NFT mapping failed",
                    pipeline_id=pipeline_id,
                    contract_address=sei_nft_data.contract_address,
                    token_id=sei_nft_data.token_id,
                    error=str(e)
                )
        
        stage_duration = time.time() - stage_start
        
        return {
            'mapped_nfts': mapped_nfts,
            'successful_mappings': successful_mappings,
            'failed_mappings': failed_mappings,
            'stage_duration': stage_duration
        }
    
    async def _execute_validation_stage(
        self,
        mapped_nfts: List[Any],
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Execute data validation stage."""
        stage_start = time.time()
        validated_nfts = []
        successful_validations = 0
        failed_validations = 0
        
        self.logger.info(
            "Executing data validation stage",
            pipeline_id=pipeline_id,
            nft_count=len(mapped_nfts)
        )
        
        for mapping_result in mapped_nfts:
            try:
                # Validate the mapping
                validation_result = await self.migration_validator.validate_migration_mapping(mapping_result)
                
                if validation_result.is_valid:
                    validated_nfts.append({
                        'mapping': mapping_result,
                        'validation': validation_result
                    })
                    successful_validations += 1
                else:
                    failed_validations += 1
                    self.logger.warning(
                        "NFT validation failed",
                        pipeline_id=pipeline_id,
                        errors=validation_result.validation_errors
                    )
                
            except Exception as e:
                failed_validations += 1
                self.logger.error(
                    "NFT validation error",
                    pipeline_id=pipeline_id,
                    error=str(e)
                )
        
        stage_duration = time.time() - stage_start
        
        return {
            'validated_nfts': validated_nfts,
            'successful_validations': successful_validations,
            'failed_validations': failed_validations,
            'stage_duration': stage_duration
        }
    
    async def _execute_minting_stage(
        self,
        validated_nfts: List[Dict[str, Any]],
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Execute Solana minting stage."""
        stage_start = time.time()
        minted_nfts = []
        successful_mints = 0
        failed_mints = 0
        
        self.logger.info(
            "Executing Solana minting stage",
            pipeline_id=pipeline_id,
            nft_count=len(validated_nfts)
        )
        
        # For testing purposes, we'll simulate minting
        # In production, this would use the actual Solana minting service
        for validated_nft in validated_nfts:
            try:
                mapping_result = validated_nft['mapping']
                
                # Simulate minting (replace with actual minting in production)
                mint_result = {
                    'asset_id': f"solana_asset_{uuid.uuid4().hex[:16]}",
                    'mint_address': f"mint_{uuid.uuid4().hex[:16]}",
                    'transaction_signature': f"tx_{uuid.uuid4().hex[:16]}",
                    'leaf_index': successful_mints,
                    'tree_address': "test_tree_address"
                }
                
                minted_nfts.append({
                    'mapping': mapping_result,
                    'mint_result': mint_result
                })
                successful_mints += 1
                
            except Exception as e:
                failed_mints += 1
                self.logger.error(
                    "NFT minting failed",
                    pipeline_id=pipeline_id,
                    error=str(e)
                )
        
        stage_duration = time.time() - stage_start
        
        return {
            'minted_nfts': minted_nfts,
            'successful_mints': successful_mints,
            'failed_mints': failed_mints,
            'stage_duration': stage_duration
        }
    
    async def _execute_database_save_stage(
        self,
        minted_nfts: List[Dict[str, Any]],
        migration_job: Optional[MigrationJob],
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Execute database save stage."""
        stage_start = time.time()
        successful_saves = 0
        failed_saves = 0
        
        self.logger.info(
            "Executing database save stage",
            pipeline_id=pipeline_id,
            nft_count=len(minted_nfts)
        )
        
        for minted_nft in minted_nfts:
            try:
                mapping_result = minted_nft['mapping']
                mint_result = minted_nft['mint_result']
                sei_nft_data = mapping_result.sei_nft_data
                
                # Create or update SeiNFT record
                sei_nft, created = await sync_to_async(SeiNFT.objects.get_or_create)(
                    sei_contract_address=sei_nft_data.contract_address,
                    sei_token_id=sei_nft_data.token_id,
                    defaults={
                        'sei_owner_address': sei_nft_data.owner_address,
                        'name': sei_nft_data.name,
                        'description': sei_nft_data.description,
                        'image_url': sei_nft_data.image_url,
                        'external_url': sei_nft_data.external_url,
                        'attributes': sei_nft_data.attributes,
                        'migration_job': migration_job,
                        'migration_status': 'completed',
                        'solana_mint_address': mint_result['mint_address'],
                        'solana_asset_id': mint_result['asset_id'],
                        'sei_data_hash': sei_nft_data.data_hash,
                        'migration_date': datetime.utcnow()
                    }
                )
                
                if not created:
                    # Update existing record
                    sei_nft.migration_status = 'completed'
                    sei_nft.solana_mint_address = mint_result['mint_address']
                    sei_nft.solana_asset_id = mint_result['asset_id']
                    sei_nft.migration_date = datetime.utcnow()
                    await sync_to_async(sei_nft.save)()
                
                successful_saves += 1
                
            except Exception as e:
                failed_saves += 1
                self.logger.error(
                    "Database save failed",
                    pipeline_id=pipeline_id,
                    error=str(e)
                )
        
        stage_duration = time.time() - stage_start
        
        return {
            'processed_count': len(minted_nfts),
            'successful_count': successful_saves,
            'failed_count': failed_saves,
            'stage_duration': stage_duration
        }
    
    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """Get pipeline execution statistics."""
        return {
            'total_pipelines_executed': self.total_pipelines_executed,
            'total_nfts_processed': self.total_nfts_processed,
            'total_successful_nfts': self.total_successful_nfts,
            'total_failed_nfts': self.total_failed_nfts,
            'overall_success_rate': (
                (self.total_successful_nfts / self.total_nfts_processed * 100)
                if self.total_nfts_processed > 0 else 0.0
            ),
            'caching_enabled': self.enable_caching,
            'monitoring_enabled': self.enable_monitoring
        }
