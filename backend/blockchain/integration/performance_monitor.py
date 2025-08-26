"""
Performance Monitor for Day 6 Integration

This module provides comprehensive performance monitoring for:
- Pipeline execution metrics
- Database query performance
- Memory and CPU usage tracking
- Cache hit rates and performance
- Solana RPC call metrics
"""

import asyncio
import time
import psutil
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import structlog
from django.conf import settings
from django.db import connection
from asgiref.sync import sync_to_async

from .cache_manager import cache_manager

logger = structlog.get_logger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance metric data structure."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    category: str = "general"
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'name': self.name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category,
            'tags': self.tags
        }


@dataclass
class SystemMetrics:
    """System-level performance metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    active_connections: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class DatabaseMetrics:
    """Database performance metrics."""
    query_count: int
    slow_query_count: int
    average_query_time_ms: float
    total_query_time_ms: float
    active_connections: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.
    
    Monitors:
    - System resources (CPU, memory, disk, network)
    - Database query performance
    - Cache performance
    - Pipeline execution metrics
    - Custom application metrics
    """
    
    def __init__(self):
        """Initialize performance monitor."""
        self.config = getattr(settings, 'PERFORMANCE_MONITORING', {})
        self.enabled = self.config.get('enabled', True)
        self.slow_query_threshold = self.config.get('slow_query_threshold_ms', 1000)
        self.memory_threshold = self.config.get('memory_usage_threshold_mb', 512)
        
        self.logger = logger.bind(component="PerformanceMonitor")
        
        # Metrics storage
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.active_monitors: Dict[str, Dict[str, Any]] = {}
        
        # System monitoring
        self.system_monitor_active = False
        self.system_monitor_task = None
        self.system_monitor_interval = 5  # seconds
        
        # Database monitoring
        self.db_queries_start_time = {}
        self.db_query_count = 0
        self.slow_query_count = 0
        self.total_query_time = 0.0
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        if self.enabled:
            self.logger.info(
                "PerformanceMonitor initialized",
                slow_query_threshold=self.slow_query_threshold,
                memory_threshold=self.memory_threshold
            )
        else:
            self.logger.info("PerformanceMonitor disabled")
    
    async def initialize(self):
        """Initialize monitoring systems."""
        if not self.enabled:
            return
        
        try:
            # Start system monitoring
            await self.start_system_monitoring()
            
            # Initialize database monitoring hooks
            self._setup_database_monitoring()
            
            self.logger.info("PerformanceMonitor initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize PerformanceMonitor", error=str(e))
    
    async def close(self):
        """Close monitoring systems and cleanup."""
        if not self.enabled:
            return
        
        try:
            # Stop system monitoring
            await self.stop_system_monitoring()
            
            self.logger.info("PerformanceMonitor closed")
            
        except Exception as e:
            self.logger.error("Error closing PerformanceMonitor", error=str(e))
    
    async def start_monitoring(self, monitor_id: str, metadata: Dict[str, Any] = None):
        """Start monitoring for a specific operation."""
        if not self.enabled:
            return
        
        monitor_data = {
            'start_time': time.time(),
            'start_datetime': datetime.utcnow(),
            'metadata': metadata or {},
            'metrics': []
        }
        
        self.active_monitors[monitor_id] = monitor_data
        
        self.logger.debug(
            "Started monitoring",
            monitor_id=monitor_id,
            metadata=metadata
        )
    
    async def stop_monitoring(self, monitor_id: str) -> Dict[str, Any]:
        """Stop monitoring and return collected metrics."""
        if not self.enabled or monitor_id not in self.active_monitors:
            return {}
        
        monitor_data = self.active_monitors.pop(monitor_id)
        end_time = time.time()
        duration = end_time - monitor_data['start_time']
        
        # Calculate final metrics
        final_metrics = {
            'monitor_id': monitor_id,
            'start_time': monitor_data['start_datetime'].isoformat(),
            'end_time': datetime.utcnow().isoformat(),
            'duration_seconds': duration,
            'metadata': monitor_data['metadata'],
            'collected_metrics': monitor_data['metrics']
        }
        
        # Store in metrics history
        with self._lock:
            self.metrics[f"monitor_{monitor_id}"].append(final_metrics)
        
        self.logger.debug(
            "Stopped monitoring",
            monitor_id=monitor_id,
            duration=duration
        )
        
        return final_metrics
    
    async def record_metric(self, name: str, value: float, unit: str = "count",
                           category: str = "general", tags: Dict[str, str] = None,
                           monitor_id: str = None):
        """Record a custom metric."""
        if not self.enabled:
            return
        
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.utcnow(),
            category=category,
            tags=tags or {}
        )
        
        # Store in general metrics
        with self._lock:
            self.metrics[category].append(metric.to_dict())
        
        # Add to active monitor if specified
        if monitor_id and monitor_id in self.active_monitors:
            self.active_monitors[monitor_id]['metrics'].append(metric.to_dict())
        
        self.logger.debug(
            "Recorded metric",
            name=name,
            value=value,
            unit=unit,
            category=category,
            monitor_id=monitor_id
        )
    
    async def start_system_monitoring(self):
        """Start system resource monitoring."""
        if self.system_monitor_active:
            return
        
        self.system_monitor_active = True
        self.system_monitor_task = asyncio.create_task(self._system_monitor_loop())
        
        self.logger.info("System monitoring started")
    
    async def stop_system_monitoring(self):
        """Stop system resource monitoring."""
        if not self.system_monitor_active:
            return
        
        self.system_monitor_active = False
        
        if self.system_monitor_task:
            self.system_monitor_task.cancel()
            try:
                await self.system_monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("System monitoring stopped")
    
    async def _system_monitor_loop(self):
        """System monitoring loop."""
        while self.system_monitor_active:
            try:
                # Collect system metrics
                system_metrics = await self._collect_system_metrics()
                
                # Store metrics
                with self._lock:
                    self.metrics['system'].append(system_metrics.to_dict())
                
                # Check thresholds and log warnings
                if system_metrics.memory_used_mb > self.memory_threshold:
                    self.logger.warning(
                        "High memory usage detected",
                        memory_used_mb=system_metrics.memory_used_mb,
                        threshold_mb=self.memory_threshold
                    )
                
                if system_metrics.cpu_percent > 80:
                    self.logger.warning(
                        "High CPU usage detected",
                        cpu_percent=system_metrics.cpu_percent
                    )
                
                await asyncio.sleep(self.system_monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("System monitoring error", error=str(e))
                await asyncio.sleep(self.system_monitor_interval)
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        # Network
        network = psutil.net_io_counters()
        
        # Database connections
        try:
            active_connections = len(connection.queries)
        except:
            active_connections = 0
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            memory_available_mb=memory.available / (1024 * 1024),
            disk_usage_percent=disk.percent,
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            active_connections=active_connections,
            timestamp=datetime.utcnow()
        )
    
    def _setup_database_monitoring(self):
        """Setup database query monitoring hooks."""
        # This is a simplified implementation
        # In production, you might want to use Django's database instrumentation
        pass
    
    async def get_metrics(self, monitor_id: str = None, category: str = None,
                         limit: int = 100) -> Dict[str, Any]:
        """Get collected metrics."""
        if not self.enabled:
            return {}
        
        with self._lock:
            if monitor_id and monitor_id in self.active_monitors:
                return self.active_monitors[monitor_id]
            
            if category:
                metrics_list = list(self.metrics[category])[-limit:]
                return {
                    'category': category,
                    'metrics': metrics_list,
                    'count': len(metrics_list)
                }
            
            # Return all metrics
            all_metrics = {}
            for cat, metrics_deque in self.metrics.items():
                all_metrics[cat] = list(metrics_deque)[-limit:]
            
            return all_metrics
    
    async def get_system_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent system metrics."""
        with self._lock:
            return list(self.metrics['system'])[-limit:]
    
    async def get_database_metrics(self) -> DatabaseMetrics:
        """Get current database metrics."""
        avg_query_time = (
            self.total_query_time / self.db_query_count
            if self.db_query_count > 0 else 0.0
        )
        
        return DatabaseMetrics(
            query_count=self.db_query_count,
            slow_query_count=self.slow_query_count,
            average_query_time_ms=avg_query_time,
            total_query_time_ms=self.total_query_time,
            active_connections=len(connection.queries),
            timestamp=datetime.utcnow()
        )
    
    async def get_cache_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        return cache_manager.get_stats()
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        if not self.enabled:
            return {'monitoring_enabled': False}
        
        # Get latest system metrics
        system_metrics = await self._collect_system_metrics()
        
        # Get database metrics
        db_metrics = await self.get_database_metrics()
        
        # Get cache metrics
        cache_metrics = await self.get_cache_metrics()
        
        # Calculate summary statistics
        with self._lock:
            total_metrics_collected = sum(len(deque_obj) for deque_obj in self.metrics.values())
        
        return {
            'monitoring_enabled': True,
            'timestamp': datetime.utcnow().isoformat(),
            'system_metrics': system_metrics.to_dict(),
            'database_metrics': db_metrics.to_dict(),
            'cache_metrics': cache_metrics,
            'active_monitors': len(self.active_monitors),
            'total_metrics_collected': total_metrics_collected,
            'thresholds': {
                'slow_query_threshold_ms': self.slow_query_threshold,
                'memory_threshold_mb': self.memory_threshold
            }
        }
    
    def reset_metrics(self, category: str = None):
        """Reset collected metrics."""
        with self._lock:
            if category:
                if category in self.metrics:
                    self.metrics[category].clear()
            else:
                self.metrics.clear()
                self.active_monitors.clear()
        
        # Reset database counters
        self.db_query_count = 0
        self.slow_query_count = 0
        self.total_query_time = 0.0
        
        self.logger.info("Performance metrics reset", category=category)
