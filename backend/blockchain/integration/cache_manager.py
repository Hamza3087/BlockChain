"""
Redis Cache Manager for Day 6 Integration

This module provides comprehensive Redis caching functionality for:
- NFT data caching
- Migration job status caching
- Solana blockchain data caching
- Query result caching
- Performance optimization
"""

import json
import time
import hashlib
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import structlog
from django.core.cache import cache
from django.conf import settings
from asgiref.sync import sync_to_async

logger = structlog.get_logger(__name__)


@dataclass
class CacheStats:
    """Cache statistics data structure."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0
    last_reset: datetime = None
    
    def __post_init__(self):
        if self.last_reset is None:
            self.last_reset = datetime.utcnow()
    
    def calculate_hit_rate(self):
        """Calculate cache hit rate."""
        if self.total_requests > 0:
            self.hit_rate = (self.hits / self.total_requests) * 100
        else:
            self.hit_rate = 0.0


class CacheManager:
    """
    Comprehensive Redis cache manager for blockchain operations.
    
    Provides caching for:
    - NFT metadata and data
    - Migration job status and progress
    - Solana blockchain queries
    - Database query results
    - API responses
    """
    
    def __init__(self):
        """Initialize cache manager."""
        self.config = getattr(settings, 'REDIS_CACHE_CONFIG', {})
        self.key_prefix = self.config.get('key_prefix', 'replantworld')
        self.version = self.config.get('version', 1)
        self.logger = logger.bind(component="CacheManager")
        
        # Cache timeouts
        self.default_timeout = self.config.get('default_timeout', 300)
        self.nft_data_timeout = self.config.get('nft_data_timeout', 1800)
        self.migration_job_timeout = self.config.get('migration_job_timeout', 3600)
        self.solana_data_timeout = self.config.get('solana_data_timeout', 600)
        
        # Statistics tracking
        self.stats = CacheStats()
        
        self.logger.info(
            "CacheManager initialized",
            key_prefix=self.key_prefix,
            version=self.version,
            timeouts={
                'default': self.default_timeout,
                'nft_data': self.nft_data_timeout,
                'migration_job': self.migration_job_timeout,
                'solana_data': self.solana_data_timeout
            }
        )
    
    def _make_key(self, key: str, category: str = "general") -> str:
        """Create a standardized cache key."""
        return f"{self.key_prefix}:{category}:{key}"
    
    def _hash_key(self, data: Union[str, Dict, List]) -> str:
        """Create a hash from complex data for use as cache key."""
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def get(self, key: str, category: str = "general", default: Any = None) -> Any:
        """Get value from cache."""
        cache_key = self._make_key(key, category)
        
        try:
            value = cache.get(cache_key, version=self.version)
            
            if value is not None:
                self.stats.hits += 1
                self.logger.debug(
                    "Cache hit",
                    key=cache_key,
                    category=category
                )
                return value
            else:
                self.stats.misses += 1
                self.logger.debug(
                    "Cache miss",
                    key=cache_key,
                    category=category
                )
                return default
                
        except Exception as e:
            self.stats.errors += 1
            self.logger.error(
                "Cache get error",
                key=cache_key,
                error=str(e)
            )
            return default
        
        finally:
            self.stats.total_requests += 1
            self.stats.calculate_hit_rate()
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None, 
            category: str = "general") -> bool:
        """Set value in cache."""
        cache_key = self._make_key(key, category)
        
        if timeout is None:
            timeout = self._get_timeout_for_category(category)
        
        try:
            cache.set(cache_key, value, timeout=timeout, version=self.version)
            self.stats.sets += 1
            
            self.logger.debug(
                "Cache set",
                key=cache_key,
                category=category,
                timeout=timeout
            )
            return True
            
        except Exception as e:
            self.stats.errors += 1
            self.logger.error(
                "Cache set error",
                key=cache_key,
                error=str(e)
            )
            return False
    
    def delete(self, key: str, category: str = "general") -> bool:
        """Delete value from cache."""
        cache_key = self._make_key(key, category)
        
        try:
            cache.delete(cache_key, version=self.version)
            self.stats.deletes += 1
            
            self.logger.debug(
                "Cache delete",
                key=cache_key,
                category=category
            )
            return True
            
        except Exception as e:
            self.stats.errors += 1
            self.logger.error(
                "Cache delete error",
                key=cache_key,
                error=str(e)
            )
            return False
    
    def _get_timeout_for_category(self, category: str) -> int:
        """Get appropriate timeout for cache category."""
        timeout_map = {
            'nft_data': self.nft_data_timeout,
            'migration_job': self.migration_job_timeout,
            'solana_data': self.solana_data_timeout,
            'general': self.default_timeout
        }
        return timeout_map.get(category, self.default_timeout)
    
    # Specialized caching methods
    
    def cache_nft_data(self, contract_address: str, token_id: str, 
                      nft_data: Dict[str, Any]) -> bool:
        """Cache NFT data."""
        key = f"nft:{contract_address}:{token_id}"
        return self.set(key, nft_data, category="nft_data")
    
    def get_cached_nft_data(self, contract_address: str, token_id: str) -> Optional[Dict[str, Any]]:
        """Get cached NFT data."""
        key = f"nft:{contract_address}:{token_id}"
        return self.get(key, category="nft_data")
    
    def cache_migration_job_status(self, job_id: str, status_data: Dict[str, Any]) -> bool:
        """Cache migration job status."""
        key = f"migration_job:{job_id}"
        return self.set(key, status_data, category="migration_job")
    
    def get_cached_migration_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get cached migration job status."""
        key = f"migration_job:{job_id}"
        return self.get(key, category="migration_job")
    
    def cache_solana_query(self, query_hash: str, result: Any) -> bool:
        """Cache Solana blockchain query result."""
        key = f"solana_query:{query_hash}"
        return self.set(key, result, category="solana_data")
    
    def get_cached_solana_query(self, query_hash: str) -> Any:
        """Get cached Solana query result."""
        key = f"solana_query:{query_hash}"
        return self.get(key, category="solana_data")
    
    def cache_database_query(self, query_hash: str, result: Any, 
                           timeout: Optional[int] = None) -> bool:
        """Cache database query result."""
        key = f"db_query:{query_hash}"
        return self.set(key, result, timeout=timeout, category="general")
    
    def get_cached_database_query(self, query_hash: str) -> Any:
        """Get cached database query result."""
        key = f"db_query:{query_hash}"
        return self.get(key, category="general")
    
    def invalidate_pattern(self, pattern: str, category: str = "general") -> int:
        """Invalidate cache keys matching a pattern."""
        try:
            # This is a simplified implementation
            # In production, you might want to use Redis SCAN for better performance
            cache_pattern = self._make_key(pattern, category)
            
            # For Django cache, we'll need to track keys manually
            # This is a limitation of Django's cache framework
            self.logger.warning(
                "Pattern invalidation not fully implemented",
                pattern=cache_pattern,
                note="Consider using Redis directly for pattern operations"
            )
            return 0
            
        except Exception as e:
            self.logger.error(
                "Cache pattern invalidation error",
                pattern=pattern,
                error=str(e)
            )
            return 0
    
    def clear_category(self, category: str) -> bool:
        """Clear all cache entries for a category."""
        try:
            # This would require Redis SCAN in production
            self.logger.warning(
                "Category clearing not fully implemented",
                category=category,
                note="Consider using Redis directly for bulk operations"
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Cache category clear error",
                category=category,
                error=str(e)
            )
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats_dict = asdict(self.stats)
        stats_dict['uptime_seconds'] = (datetime.utcnow() - self.stats.last_reset).total_seconds()
        return stats_dict
    
    def reset_stats(self):
        """Reset cache statistics."""
        self.stats = CacheStats()
        self.logger.info("Cache statistics reset")
    
    async def async_get(self, key: str, category: str = "general", default: Any = None) -> Any:
        """Async version of get method."""
        return await sync_to_async(self.get)(key, category, default)
    
    async def async_set(self, key: str, value: Any, timeout: Optional[int] = None, 
                       category: str = "general") -> bool:
        """Async version of set method."""
        return await sync_to_async(self.set)(key, value, timeout, category)
    
    async def async_delete(self, key: str, category: str = "general") -> bool:
        """Async version of delete method."""
        return await sync_to_async(self.delete)(key, category)


# Global cache manager instance
cache_manager = CacheManager()
