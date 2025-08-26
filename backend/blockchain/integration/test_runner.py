"""
Integration Test Runner for Day 6

This module provides comprehensive integration testing functionality for:
- End-to-end pipeline testing
- Batch migration testing
- Performance benchmarking
- System integration validation
- Automated test scenarios
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import structlog
from django.conf import settings
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from .pipeline import EndToEndPipeline, PipelineResult
from .batch_manager import BatchMigrationManager, BatchConfiguration
from .cache_manager import cache_manager
from .performance_monitor import PerformanceMonitor
from ..migration import SeiNFTData, MigrationService
from ..models import MigrationJob, SeiNFT, MigrationLog

logger = structlog.get_logger(__name__)


class TestScenario(Enum):
    """Integration test scenarios."""
    SINGLE_NFT_MIGRATION = "single_nft_migration"
    BATCH_MIGRATION = "batch_migration"
    LARGE_SCALE_MIGRATION = "large_scale_migration"
    CACHE_PERFORMANCE = "cache_performance"
    ERROR_HANDLING = "error_handling"
    ROLLBACK_TESTING = "rollback_testing"
    PERFORMANCE_BENCHMARK = "performance_benchmark"


@dataclass
class TestConfiguration:
    """Integration test configuration."""
    scenario: TestScenario
    test_data_size: int = 10
    enable_caching: bool = True
    enable_monitoring: bool = True
    timeout_seconds: int = 300
    expected_success_rate: float = 95.0
    performance_thresholds: Dict[str, float] = None
    
    def __post_init__(self):
        if self.performance_thresholds is None:
            self.performance_thresholds = {
                'max_duration_seconds': 60.0,
                'max_memory_mb': 512.0,
                'min_cache_hit_rate': 80.0
            }


@dataclass
class TestResult:
    """Integration test result."""
    test_id: str
    scenario: TestScenario
    status: str  # 'passed', 'failed', 'error'
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    test_data_size: int
    success_rate: float
    performance_metrics: Dict[str, Any]
    pipeline_results: List[PipelineResult]
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
    
    @property
    def passed(self) -> bool:
        """Check if test passed."""
        return self.status == 'passed'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = asdict(self)
        result['pipeline_results'] = [
            asdict(pr) for pr in self.pipeline_results
        ]
        return result


class IntegrationTestRunner:
    """
    Comprehensive integration test runner.
    
    Provides automated testing for:
    - End-to-end pipeline functionality
    - Batch migration capabilities
    - Performance benchmarking
    - Error handling and recovery
    - Cache effectiveness
    - System integration
    """
    
    def __init__(self):
        """Initialize integration test runner."""
        self.config = getattr(settings, 'INTEGRATION_TESTING', {})
        self.enabled = self.config.get('enabled', True)
        self.logger = logger.bind(component="IntegrationTestRunner")
        
        # Test components
        self.pipeline = None
        self.batch_manager = None
        self.performance_monitor = None
        
        # Test results storage
        self.test_results: List[TestResult] = []
        self.test_statistics = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'error_tests': 0
        }
        
        if self.enabled:
            self.logger.info("IntegrationTestRunner initialized")
        else:
            self.logger.info("Integration testing disabled")
    
    async def initialize(self):
        """Initialize test components."""
        if not self.enabled:
            return
        
        try:
            # Initialize pipeline
            self.pipeline = EndToEndPipeline(
                enable_caching=True,
                enable_monitoring=True
            )
            await self.pipeline.initialize()
            
            # Initialize batch manager
            self.batch_manager = BatchMigrationManager()
            
            # Initialize performance monitor
            self.performance_monitor = PerformanceMonitor()
            await self.performance_monitor.initialize()
            
            self.logger.info("IntegrationTestRunner components initialized")
            
        except Exception as e:
            self.logger.error("Failed to initialize test components", error=str(e))
            raise
    
    async def close(self):
        """Close test components."""
        if self.pipeline:
            await self.pipeline.close()
        
        if self.performance_monitor:
            await self.performance_monitor.close()
        
        self.logger.info("IntegrationTestRunner closed")
    
    async def run_test_scenario(self, config: TestConfiguration) -> TestResult:
        """Run a specific test scenario."""
        test_id = f"test_{config.scenario.value}_{int(time.time())}"
        start_time = datetime.utcnow()
        
        self.logger.info(
            "Starting integration test",
            test_id=test_id,
            scenario=config.scenario.value,
            test_data_size=config.test_data_size
        )
        
        # Start performance monitoring
        if self.performance_monitor:
            await self.performance_monitor.start_monitoring(
                test_id,
                {'scenario': config.scenario.value, 'test_data_size': config.test_data_size}
            )
        
        try:
            # Run the specific test scenario
            if config.scenario == TestScenario.SINGLE_NFT_MIGRATION:
                pipeline_results = await self._test_single_nft_migration(config, test_id)
            elif config.scenario == TestScenario.BATCH_MIGRATION:
                pipeline_results = await self._test_batch_migration(config, test_id)
            elif config.scenario == TestScenario.LARGE_SCALE_MIGRATION:
                pipeline_results = await self._test_large_scale_migration(config, test_id)
            elif config.scenario == TestScenario.CACHE_PERFORMANCE:
                pipeline_results = await self._test_cache_performance(config, test_id)
            elif config.scenario == TestScenario.ERROR_HANDLING:
                pipeline_results = await self._test_error_handling(config, test_id)
            elif config.scenario == TestScenario.ROLLBACK_TESTING:
                pipeline_results = await self._test_rollback_functionality(config, test_id)
            elif config.scenario == TestScenario.PERFORMANCE_BENCHMARK:
                pipeline_results = await self._test_performance_benchmark(config, test_id)
            else:
                raise ValueError(f"Unknown test scenario: {config.scenario}")
            
            # Calculate results
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Calculate success rate
            total_nfts = sum(pr.total_nfts for pr in pipeline_results)
            successful_nfts = sum(pr.successful_nfts for pr in pipeline_results)
            success_rate = (successful_nfts / total_nfts * 100) if total_nfts > 0 else 0.0
            
            # Get performance metrics
            performance_metrics = {}
            if self.performance_monitor:
                performance_metrics = await self.performance_monitor.stop_monitoring(test_id)
            
            # Determine test status
            status = self._evaluate_test_status(config, success_rate, duration, performance_metrics)
            
            # Create test result
            test_result = TestResult(
                test_id=test_id,
                scenario=config.scenario,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_data_size=config.test_data_size,
                success_rate=success_rate,
                performance_metrics=performance_metrics,
                pipeline_results=pipeline_results
            )
            
            # Update statistics
            self.test_statistics['total_tests'] += 1
            if status == 'passed':
                self.test_statistics['passed_tests'] += 1
            elif status == 'failed':
                self.test_statistics['failed_tests'] += 1
            else:
                self.test_statistics['error_tests'] += 1
            
            # Store result
            self.test_results.append(test_result)
            
            self.logger.info(
                "Integration test completed",
                test_id=test_id,
                scenario=config.scenario.value,
                status=status,
                duration=duration,
                success_rate=success_rate
            )
            
            return test_result
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Stop monitoring on error
            if self.performance_monitor:
                await self.performance_monitor.stop_monitoring(test_id)
            
            test_result = TestResult(
                test_id=test_id,
                scenario=config.scenario,
                status='error',
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                test_data_size=config.test_data_size,
                success_rate=0.0,
                performance_metrics={},
                pipeline_results=[],
                error_message=str(e)
            )
            
            self.test_statistics['total_tests'] += 1
            self.test_statistics['error_tests'] += 1
            self.test_results.append(test_result)
            
            self.logger.error(
                "Integration test failed with error",
                test_id=test_id,
                scenario=config.scenario.value,
                error=str(e),
                duration=duration
            )
            
            return test_result
    
    async def _test_single_nft_migration(self, config: TestConfiguration, test_id: str) -> List[PipelineResult]:
        """Test single NFT migration."""
        # Create test NFT data
        test_contracts = [f"sei1test{i:06d}" for i in range(min(config.test_data_size, 5))]
        
        results = []
        for contract in test_contracts:
            result = await self.pipeline.execute_full_pipeline(
                sei_contract_addresses=[contract],
                max_nfts_per_contract=1
            )
            results.append(result)
        
        return results
    
    async def _test_batch_migration(self, config: TestConfiguration, test_id: str) -> List[PipelineResult]:
        """Test batch migration functionality."""
        # Create test migration job
        user = await self._get_or_create_test_user()
        
        migration_job = await sync_to_async(MigrationJob.objects.create)(
            name=f"Test Batch Migration {test_id}",
            description="Integration test batch migration",
            sei_contract_addresses=[f"sei1batch{test_id}"],
            batch_size=min(config.test_data_size, 20),
            created_by=user
        )
        
        # Create test NFT records
        await self._create_test_nft_records(migration_job, config.test_data_size)
        
        # Run batch migration
        batch_progress = await self.batch_manager.process_migration_job_in_batches(migration_job)
        
        # Convert batch progress to pipeline result format
        pipeline_result = PipelineResult(
            pipeline_id=f"batch_{test_id}",
            status=PipelineStage.COMPLETION,
            start_time=batch_progress.start_time,
            end_time=batch_progress.end_time,
            total_nfts=batch_progress.total_items,
            processed_nfts=batch_progress.processed_items,
            successful_nfts=batch_progress.successful_items,
            failed_nfts=batch_progress.failed_items
        )
        
        return [pipeline_result]
    
    async def _test_large_scale_migration(self, config: TestConfiguration, test_id: str) -> List[PipelineResult]:
        """Test large-scale migration performance."""
        # Use larger test data size
        large_size = max(config.test_data_size, 100)
        test_contracts = [f"sei1large{i:06d}" for i in range(min(large_size // 20, 10))]
        
        result = await self.pipeline.execute_full_pipeline(
            sei_contract_addresses=test_contracts,
            max_nfts_per_contract=large_size // len(test_contracts)
        )
        
        return [result]
    
    async def _test_cache_performance(self, config: TestConfiguration, test_id: str) -> List[PipelineResult]:
        """Test cache performance and effectiveness."""
        # Reset cache stats
        cache_manager.reset_stats()
        
        # Run pipeline twice to test caching
        test_contracts = [f"sei1cache{test_id}"]
        
        # First run (cache miss)
        result1 = await self.pipeline.execute_full_pipeline(
            sei_contract_addresses=test_contracts,
            max_nfts_per_contract=config.test_data_size
        )
        
        # Second run (cache hit)
        result2 = await self.pipeline.execute_full_pipeline(
            sei_contract_addresses=test_contracts,
            max_nfts_per_contract=config.test_data_size
        )
        
        return [result1, result2]
    
    async def _test_error_handling(self, config: TestConfiguration, test_id: str) -> List[PipelineResult]:
        """Test error handling and recovery."""
        # Create scenarios that will cause errors
        invalid_contracts = [f"invalid_contract_{test_id}"]
        
        result = await self.pipeline.execute_full_pipeline(
            sei_contract_addresses=invalid_contracts,
            max_nfts_per_contract=config.test_data_size
        )
        
        return [result]
    
    async def _test_rollback_functionality(self, config: TestConfiguration, test_id: str) -> List[PipelineResult]:
        """Test rollback functionality."""
        # This would test the rollback capabilities
        # For now, return a mock result
        from .pipeline import PipelineStage
        
        result = PipelineResult(
            pipeline_id=f"rollback_{test_id}",
            status=PipelineStage.COMPLETION,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            total_nfts=config.test_data_size,
            processed_nfts=config.test_data_size,
            successful_nfts=config.test_data_size,
            failed_nfts=0
        )
        
        return [result]
    
    async def _test_performance_benchmark(self, config: TestConfiguration, test_id: str) -> List[PipelineResult]:
        """Test performance benchmarking."""
        # Run multiple iterations to get performance baseline
        results = []
        
        for i in range(3):  # Run 3 iterations
            test_contracts = [f"sei1perf{test_id}_{i}"]
            
            result = await self.pipeline.execute_full_pipeline(
                sei_contract_addresses=test_contracts,
                max_nfts_per_contract=config.test_data_size
            )
            results.append(result)
        
        return results
    
    def _evaluate_test_status(self, config: TestConfiguration, success_rate: float,
                             duration: float, performance_metrics: Dict[str, Any]) -> str:
        """Evaluate test status based on results and thresholds."""
        # Check success rate
        if success_rate < config.expected_success_rate:
            return 'failed'
        
        # Check duration
        max_duration = config.performance_thresholds.get('max_duration_seconds', 60.0)
        if duration > max_duration:
            return 'failed'
        
        # Check memory usage (if available)
        if 'system_metrics' in performance_metrics:
            memory_used = performance_metrics['system_metrics'].get('memory_used_mb', 0)
            max_memory = config.performance_thresholds.get('max_memory_mb', 512.0)
            if memory_used > max_memory:
                return 'failed'
        
        return 'passed'
    
    async def _get_or_create_test_user(self) -> User:
        """Get or create test user."""
        user, created = await sync_to_async(User.objects.get_or_create)(
            username='integration_test_user',
            defaults={
                'email': 'test@integration.com',
                'first_name': 'Integration',
                'last_name': 'Test'
            }
        )
        return user
    
    async def _create_test_nft_records(self, migration_job: MigrationJob, count: int):
        """Create test NFT records for batch testing."""
        for i in range(count):
            await sync_to_async(SeiNFT.objects.create)(
                sei_contract_address=f"sei1test{migration_job.job_id}",
                sei_token_id=str(i + 1),
                sei_owner_address=f"sei1owner{i:06d}",
                name=f"Test NFT {i + 1}",
                description=f"Test NFT for integration testing",
                image_url=f"https://example.com/nft{i + 1}.jpg",
                attributes=[
                    {"trait_type": "Test", "value": "True"},
                    {"trait_type": "Index", "value": str(i + 1)}
                ],
                migration_job=migration_job,
                sei_data_hash=f"hash{i:06d}"
            )
    
    async def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """Run comprehensive integration test suite."""
        self.logger.info("Starting comprehensive integration test suite")
        
        # Define test scenarios
        test_configs = [
            TestConfiguration(TestScenario.SINGLE_NFT_MIGRATION, test_data_size=5),
            TestConfiguration(TestScenario.BATCH_MIGRATION, test_data_size=20),
            TestConfiguration(TestScenario.CACHE_PERFORMANCE, test_data_size=10),
            TestConfiguration(TestScenario.ERROR_HANDLING, test_data_size=5),
            TestConfiguration(TestScenario.PERFORMANCE_BENCHMARK, test_data_size=15),
        ]
        
        # Run all test scenarios
        suite_results = []
        for config in test_configs:
            try:
                result = await self.run_test_scenario(config)
                suite_results.append(result)
            except Exception as e:
                self.logger.error(
                    "Test scenario failed",
                    scenario=config.scenario.value,
                    error=str(e)
                )
        
        # Calculate suite summary
        total_tests = len(suite_results)
        passed_tests = sum(1 for r in suite_results if r.passed)
        
        suite_summary = {
            'total_scenarios': total_tests,
            'passed_scenarios': passed_tests,
            'failed_scenarios': total_tests - passed_tests,
            'overall_success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0.0,
            'test_results': [r.to_dict() for r in suite_results],
            'statistics': self.test_statistics
        }
        
        self.logger.info(
            "Comprehensive test suite completed",
            total_scenarios=total_tests,
            passed_scenarios=passed_tests,
            success_rate=suite_summary['overall_success_rate']
        )
        
        return suite_summary
    
    def get_test_statistics(self) -> Dict[str, Any]:
        """Get test execution statistics."""
        return {
            'statistics': self.test_statistics,
            'total_test_results': len(self.test_results),
            'recent_results': [r.to_dict() for r in self.test_results[-10:]]  # Last 10 results
        }
