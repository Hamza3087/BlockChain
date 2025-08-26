# Day 6 - Integration & System Testing

This directory contains comprehensive integration and system testing components for the ReplantWorld blockchain system. Day 6 focuses on end-to-end testing, performance monitoring, caching optimization, and batch processing capabilities.

## 🏗️ Architecture Overview

The Day 6 integration system consists of several interconnected components:

```
┌─────────────────────────────────────────────────────────────┐
│                    Integration Layer                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  End-to-End     │  │  Batch          │  │  Cache       │ │
│  │  Pipeline       │  │  Manager        │  │  Manager     │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  Performance    │  │  Integration    │  │  Test        │ │
│  │  Monitor        │  │  Test Runner    │  │  Models      │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Component Structure

### Core Components

- **`pipeline.py`** - End-to-end pipeline orchestration
- **`batch_manager.py`** - Batch processing and migration management
- **`cache_manager.py`** - Redis caching layer with performance optimization
- **`performance_monitor.py`** - System and application performance monitoring
- **`test_runner.py`** - Comprehensive integration test execution
- **`models.py`** - Database models for test results and metrics

### Supporting Files

- **`__init__.py`** - Package initialization and exports
- **`README.md`** - This documentation file

## 🚀 Key Features

### 1. End-to-End Pipeline (`pipeline.py`)

The pipeline orchestrates the complete NFT migration process:

- **Data Export**: Retrieves NFT data from Sei blockchain
- **Data Mapping**: Transforms Sei NFT data to Solana format
- **Data Validation**: Ensures data integrity and compliance
- **Solana Minting**: Creates compressed NFTs on Solana
- **Database Storage**: Persists migration results

```python
from blockchain.integration import EndToEndPipeline

pipeline = EndToEndPipeline(enable_caching=True, enable_monitoring=True)
await pipeline.initialize()

result = await pipeline.execute_full_pipeline(
    sei_contract_addresses=['sei1contract123'],
    max_nfts_per_contract=100
)
```

### 2. Batch Migration Manager (`batch_manager.py`)

Handles large-scale migrations with:

- **Concurrent Processing**: Multiple batches processed simultaneously
- **Progress Tracking**: Real-time progress monitoring
- **Error Handling**: Automatic retry and error recovery
- **Performance Optimization**: Configurable batch sizes and concurrency

```python
from blockchain.integration import BatchMigrationManager

batch_manager = BatchMigrationManager()
progress = await batch_manager.process_migration_job_in_batches(migration_job)
```

### 3. Cache Manager (`cache_manager.py`)

Redis-based caching system providing:

- **Multi-Category Caching**: Organized cache namespaces
- **Performance Metrics**: Hit rates and response times
- **Specialized Methods**: NFT data, migration jobs, validation results
- **Automatic Expiration**: Configurable TTL policies

```python
from blockchain.integration.cache_manager import cache_manager

# Cache NFT data
cache_manager.cache_nft_data(contract_address, token_id, nft_data)

# Retrieve cached data
cached_data = cache_manager.get_cached_nft_data(contract_address, token_id)
```

### 4. Performance Monitor (`performance_monitor.py`)

Comprehensive monitoring system:

- **System Metrics**: CPU, memory, disk, network usage
- **Application Metrics**: Custom performance indicators
- **Real-time Monitoring**: Continuous system observation
- **Threshold Alerts**: Configurable performance warnings

```python
from blockchain.integration import PerformanceMonitor

monitor = PerformanceMonitor()
await monitor.initialize()

await monitor.start_monitoring("operation_id")
# ... perform operations ...
metrics = await monitor.stop_monitoring("operation_id")
```

### 5. Integration Test Runner (`test_runner.py`)

Automated testing framework:

- **Multiple Scenarios**: Various test types and configurations
- **Performance Benchmarking**: Load and stress testing
- **Comprehensive Reporting**: Detailed test results and metrics
- **Configurable Tests**: Customizable test parameters

```python
from blockchain.integration import IntegrationTestRunner
from blockchain.integration.test_runner import TestConfiguration, TestScenario

test_runner = IntegrationTestRunner()
await test_runner.initialize()

config = TestConfiguration(
    scenario=TestScenario.BATCH_MIGRATION,
    test_data_size=50,
    enable_caching=True
)

result = await test_runner.run_test_scenario(config)
```

## 🧪 Test Scenarios

The integration test runner supports multiple test scenarios:

1. **Single NFT Migration** - Basic migration functionality
2. **Batch Migration** - Large-scale batch processing
3. **Large Scale Migration** - Performance under load
4. **Cache Performance** - Caching effectiveness testing
5. **Error Handling** - Failure recovery testing
6. **Rollback Testing** - Transaction rollback capabilities
7. **Performance Benchmark** - System performance baselines

## 📊 Database Models

### IntegrationTestResult
Stores comprehensive test execution data including performance metrics, success rates, and detailed results.

### BatchMigrationStatus
Tracks batch processing operations with real-time progress updates and performance metrics.

### PerformanceMetric
Captures detailed performance data for monitoring and optimization purposes.

## 🔧 Configuration

### Environment Variables

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Performance Monitoring
PERFORMANCE_MONITORING_ENABLED=true
SLOW_QUERY_THRESHOLD_MS=1000
MEMORY_USAGE_THRESHOLD_MB=512

# Batch Processing
BATCH_MIGRATION_DEFAULT_SIZE=50
BATCH_MIGRATION_CONCURRENT_BATCHES=5
BATCH_MIGRATION_RETRY_ATTEMPTS=3
```

### Django Settings

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

BATCH_MIGRATION = {
    'default_batch_size': 50,
    'concurrent_batches': 5,
    'retry_attempts': 3,
    'retry_delay_seconds': 30,
}

PERFORMANCE_MONITORING = {
    'enabled': True,
    'slow_query_threshold_ms': 1000,
    'memory_usage_threshold_mb': 512,
}
```

## 🚀 Usage Examples

### Running End-to-End Pipeline

```python
import asyncio
from blockchain.integration import EndToEndPipeline

async def run_migration():
    pipeline = EndToEndPipeline(enable_caching=True, enable_monitoring=True)
    await pipeline.initialize()
    
    try:
        result = await pipeline.execute_full_pipeline(
            sei_contract_addresses=['sei1contract123', 'sei1contract456'],
            max_nfts_per_contract=50
        )
        
        print(f"Pipeline completed: {result.pipeline_id}")
        print(f"Success rate: {result.success_rate:.1f}%")
        print(f"Duration: {result.duration:.2f}s")
        
    finally:
        await pipeline.close()

# Run the migration
asyncio.run(run_migration())
```

### Batch Processing

```python
from django.contrib.auth.models import User
from blockchain.models import MigrationJob
from blockchain.integration import BatchMigrationManager

# Create migration job
user = User.objects.get(username='admin')
migration_job = MigrationJob.objects.create(
    name="Large Scale Migration",
    description="Migrating 1000 NFTs",
    sei_contract_addresses=['sei1large_contract'],
    batch_size=100,
    created_by=user
)

# Process in batches
async def process_batches():
    batch_manager = BatchMigrationManager()
    progress = await batch_manager.process_migration_job_in_batches(migration_job)
    
    print(f"Batch processing completed: {progress.batch_id}")
    print(f"Total items: {progress.total_items}")
    print(f"Success rate: {progress.success_rate:.1f}%")

asyncio.run(process_batches())
```

### Performance Monitoring

```python
from blockchain.integration import PerformanceMonitor

async def monitor_operation():
    monitor = PerformanceMonitor()
    await monitor.initialize()
    
    try:
        # Start monitoring
        await monitor.start_monitoring("my_operation")
        
        # Record custom metrics
        await monitor.record_metric("items_processed", 100, "count", "application")
        await monitor.record_metric("processing_time", 45.2, "seconds", "performance")
        
        # Stop monitoring and get results
        metrics = await monitor.stop_monitoring("my_operation")
        
        print(f"Operation duration: {metrics['duration_seconds']:.2f}s")
        print(f"Metrics collected: {len(metrics['collected_metrics'])}")
        
    finally:
        await monitor.close()

asyncio.run(monitor_operation())
```

## 🧪 Testing

### Running Integration Tests

```bash
# Run comprehensive test suite
python manage.py test_day6_integration

# Run specific test categories
python manage.py test_day6_integration --test-pipeline
python manage.py test_day6_integration --test-batch
python manage.py test_day6_integration --test-cache
python manage.py test_day6_integration --test-performance

# Run performance benchmarks
python manage.py test_day6_integration --benchmark

# Clean up test data
python manage.py test_day6_integration --cleanup
```

### Unit Tests

```bash
# Run unit tests for specific modules
python manage.py test blockchain.tests.test_solana_client
python manage.py test blockchain.tests.test_models
python manage.py test blockchain.tests.test_migration
```

## 📈 Performance Metrics

The system tracks various performance metrics:

- **System Metrics**: CPU usage, memory consumption, disk I/O
- **Application Metrics**: Request rates, response times, error rates
- **Cache Metrics**: Hit rates, miss rates, eviction rates
- **Database Metrics**: Query counts, slow queries, connection pools

## 🔍 Monitoring and Alerting

### Performance Thresholds

- **Memory Usage**: Alert when > 512MB
- **CPU Usage**: Alert when > 80%
- **Slow Queries**: Alert when > 1000ms
- **Cache Hit Rate**: Alert when < 80%

### Health Checks

The system provides comprehensive health checks:

```python
# Check system health
health_status = await monitor.get_performance_summary()

# Check cache health
cache_stats = cache_manager.get_stats()

# Check pipeline health
pipeline_stats = pipeline.get_pipeline_statistics()
```

## 🚨 Error Handling

The integration system implements robust error handling:

- **Automatic Retry**: Failed operations are automatically retried
- **Circuit Breaker**: Prevents cascade failures
- **Graceful Degradation**: System continues operating with reduced functionality
- **Comprehensive Logging**: Detailed error tracking and reporting

## 📝 API Endpoints

Day 6 provides REST API endpoints for integration testing:

- `POST /api/integration/run-pipeline/` - Execute end-to-end pipeline
- `POST /api/integration/run-batch/` - Run batch migration
- `GET /api/integration/cache-stats/` - Get cache statistics
- `POST /api/integration/run-test/` - Execute integration test
- `GET /api/integration/performance-metrics/` - Get performance metrics
- `GET /api/integration/test-results/` - List test results

## 🔧 Troubleshooting

### Common Issues

1. **Redis Connection Errors**
   - Ensure Redis server is running
   - Check connection string in settings
   - Verify network connectivity

2. **Performance Issues**
   - Monitor system resources
   - Check cache hit rates
   - Review batch sizes and concurrency settings

3. **Test Failures**
   - Check system dependencies
   - Verify test data setup
   - Review error logs for details

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('blockchain.integration').setLevel(logging.DEBUG)
```

## 🎯 Best Practices

1. **Caching Strategy**: Use appropriate TTL values and cache invalidation
2. **Batch Sizing**: Optimize batch sizes based on system resources
3. **Monitoring**: Regularly review performance metrics and alerts
4. **Testing**: Run integration tests before production deployments
5. **Error Handling**: Implement comprehensive error recovery mechanisms

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Redis Documentation](https://redis.io/documentation)
- [Solana Documentation](https://docs.solana.com/)
- [Performance Testing Best Practices](https://docs.python.org/3/library/asyncio.html)

---

For questions or support, please refer to the main project documentation or contact the development team.
