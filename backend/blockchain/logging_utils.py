"""
Enhanced logging utilities for blockchain operations.

This module provides specialized logging functionality for tracking
blockchain operations, performance metrics, and operational events.
"""

import time
import functools
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class OperationType(Enum):
    """Types of blockchain operations for logging."""
    TREE_CREATION = "tree_creation"
    TREE_MANAGEMENT = "tree_management"
    NFT_MINTING = "nft_minting"
    RPC_CALL = "rpc_call"
    TRANSACTION = "transaction"
    HEALTH_CHECK = "health_check"
    CONFIGURATION = "configuration"
    ERROR_RECOVERY = "error_recovery"


class LogLevel(Enum):
    """Log levels for blockchain operations."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def log_blockchain_operation(
    operation_type: OperationType,
    operation_name: str,
    level: LogLevel = LogLevel.INFO,
    include_performance: bool = True
):
    """
    Decorator for logging blockchain operations with performance metrics.
    
    Args:
        operation_type: Type of blockchain operation
        operation_name: Name of the operation
        level: Log level for the operation
        include_performance: Whether to include performance metrics
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_name}_{int(start_time)}"
            
            # Log operation start
            log_data = {
                "operation_id": operation_id,
                "operation_type": operation_type.value,
                "operation_name": operation_name,
                "status": "started",
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            }
            
            getattr(logger, level.value)("Blockchain operation started", **log_data)
            
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Calculate performance metrics
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Log successful completion
                success_data = {
                    "operation_id": operation_id,
                    "operation_type": operation_type.value,
                    "operation_name": operation_name,
                    "status": "completed",
                    "success": True
                }
                
                if include_performance:
                    success_data.update({
                        "execution_time_seconds": execution_time,
                        "performance_category": _categorize_performance(execution_time)
                    })
                
                getattr(logger, level.value)("Blockchain operation completed", **success_data)
                
                return result
                
            except Exception as e:
                # Calculate performance metrics for failed operations
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Log operation failure
                error_data = {
                    "operation_id": operation_id,
                    "operation_type": operation_type.value,
                    "operation_name": operation_name,
                    "status": "failed",
                    "success": False,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
                
                if include_performance:
                    error_data.update({
                        "execution_time_seconds": execution_time,
                        "performance_category": _categorize_performance(execution_time)
                    })
                
                logger.error("Blockchain operation failed", **error_data)
                
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_name}_{int(start_time)}"
            
            # Log operation start
            log_data = {
                "operation_id": operation_id,
                "operation_type": operation_type.value,
                "operation_name": operation_name,
                "status": "started",
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            }
            
            getattr(logger, level.value)("Blockchain operation started", **log_data)
            
            try:
                # Execute the function
                result = func(*args, **kwargs)
                
                # Calculate performance metrics
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Log successful completion
                success_data = {
                    "operation_id": operation_id,
                    "operation_type": operation_type.value,
                    "operation_name": operation_name,
                    "status": "completed",
                    "success": True
                }
                
                if include_performance:
                    success_data.update({
                        "execution_time_seconds": execution_time,
                        "performance_category": _categorize_performance(execution_time)
                    })
                
                getattr(logger, level.value)("Blockchain operation completed", **success_data)
                
                return result
                
            except Exception as e:
                # Calculate performance metrics for failed operations
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Log operation failure
                error_data = {
                    "operation_id": operation_id,
                    "operation_type": operation_type.value,
                    "operation_name": operation_name,
                    "status": "failed",
                    "success": False,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
                
                if include_performance:
                    error_data.update({
                        "execution_time_seconds": execution_time,
                        "performance_category": _categorize_performance(execution_time)
                    })
                
                logger.error("Blockchain operation failed", **error_data)
                
                raise
        
        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@contextmanager
def log_operation_context(
    operation_type: OperationType,
    operation_name: str,
    context_data: Optional[Dict[str, Any]] = None,
    level: LogLevel = LogLevel.INFO
):
    """
    Context manager for logging blockchain operations.
    
    Args:
        operation_type: Type of blockchain operation
        operation_name: Name of the operation
        context_data: Additional context data to log
        level: Log level for the operation
    """
    start_time = time.time()
    operation_id = f"{operation_name}_{int(start_time)}"
    
    # Prepare log data
    log_data = {
        "operation_id": operation_id,
        "operation_type": operation_type.value,
        "operation_name": operation_name,
        "status": "started"
    }
    
    if context_data:
        log_data.update(context_data)
    
    # Log operation start
    getattr(logger, level.value)("Blockchain operation context started", **log_data)
    
    try:
        yield operation_id
        
        # Log successful completion
        end_time = time.time()
        execution_time = end_time - start_time
        
        success_data = {
            "operation_id": operation_id,
            "operation_type": operation_type.value,
            "operation_name": operation_name,
            "status": "completed",
            "success": True,
            "execution_time_seconds": execution_time,
            "performance_category": _categorize_performance(execution_time)
        }
        
        if context_data:
            success_data.update(context_data)
        
        getattr(logger, level.value)("Blockchain operation context completed", **success_data)
        
    except Exception as e:
        # Log operation failure
        end_time = time.time()
        execution_time = end_time - start_time
        
        error_data = {
            "operation_id": operation_id,
            "operation_type": operation_type.value,
            "operation_name": operation_name,
            "status": "failed",
            "success": False,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "execution_time_seconds": execution_time,
            "performance_category": _categorize_performance(execution_time)
        }
        
        if context_data:
            error_data.update(context_data)
        
        logger.error("Blockchain operation context failed", **error_data)
        
        raise


def log_tree_event(
    event_type: str,
    tree_address: str,
    additional_data: Optional[Dict[str, Any]] = None,
    level: LogLevel = LogLevel.INFO
):
    """
    Log Merkle tree related events.
    
    Args:
        event_type: Type of tree event (created, updated, etc.)
        tree_address: Address of the tree
        additional_data: Additional event data
        level: Log level
    """
    log_data = {
        "event_type": "tree_event",
        "tree_event_type": event_type,
        "tree_address": tree_address,
        "timestamp": time.time()
    }
    
    if additional_data:
        log_data.update(additional_data)
    
    getattr(logger, level.value)("Merkle tree event", **log_data)


def log_mint_event(
    event_type: str,
    mint_id: str,
    tree_address: str,
    recipient: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None,
    level: LogLevel = LogLevel.INFO
):
    """
    Log NFT minting related events.
    
    Args:
        event_type: Type of mint event (started, completed, failed)
        mint_id: Unique mint identifier
        tree_address: Address of the target tree
        recipient: NFT recipient address
        additional_data: Additional event data
        level: Log level
    """
    log_data = {
        "event_type": "mint_event",
        "mint_event_type": event_type,
        "mint_id": mint_id,
        "tree_address": tree_address,
        "timestamp": time.time()
    }
    
    if recipient:
        log_data["recipient"] = recipient
    
    if additional_data:
        log_data.update(additional_data)
    
    getattr(logger, level.value)("NFT mint event", **log_data)


def log_rpc_metrics(
    endpoint_name: str,
    method: str,
    response_time: float,
    success: bool,
    error_message: Optional[str] = None
):
    """
    Log RPC call metrics.
    
    Args:
        endpoint_name: Name of the RPC endpoint
        method: RPC method called
        response_time: Response time in seconds
        success: Whether the call was successful
        error_message: Error message if failed
    """
    log_data = {
        "event_type": "rpc_metrics",
        "endpoint_name": endpoint_name,
        "rpc_method": method,
        "response_time_seconds": response_time,
        "success": success,
        "performance_category": _categorize_performance(response_time),
        "timestamp": time.time()
    }
    
    if error_message:
        log_data["error_message"] = error_message
    
    if success:
        logger.info("RPC call metrics", **log_data)
    else:
        logger.warning("RPC call failed", **log_data)


def _categorize_performance(execution_time: float) -> str:
    """
    Categorize performance based on execution time.
    
    Args:
        execution_time: Execution time in seconds
        
    Returns:
        Performance category string
    """
    if execution_time < 0.1:
        return "excellent"
    elif execution_time < 0.5:
        return "good"
    elif execution_time < 2.0:
        return "acceptable"
    elif execution_time < 10.0:
        return "slow"
    else:
        return "very_slow"


def create_operation_logger(component_name: str) -> structlog.BoundLogger:
    """
    Create a specialized logger for a specific component.
    
    Args:
        component_name: Name of the component
        
    Returns:
        Bound logger with component context
    """
    return logger.bind(component=component_name)
