from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import structlog
import redis
import asyncio
from django.conf import settings

logger = structlog.get_logger(__name__)


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint that verifies:
    - Database connection (PostgreSQL)
    - Redis cache connectivity
    """
    health_status = {
        'status': 'ok',
        'timestamp': None,
        'services': {
            'database': {'status': 'unknown'},
            'redis': {'status': 'unknown'},
            'solana': {'status': 'unknown'}
        }
    }
    
    overall_status = True
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status['services']['database']['status'] = 'healthy'
        logger.info("Database health check passed")
    except Exception as e:
        health_status['services']['database']['status'] = 'unhealthy'
        health_status['services']['database']['error'] = str(e)
        overall_status = False
        logger.error("Database health check failed", error=str(e))
    
    # Check Redis connection
    try:
        # Test cache connection
        cache.set('health_check', 'test', 10)
        test_value = cache.get('health_check')
        if test_value == 'test':
            health_status['services']['redis']['status'] = 'healthy'
            logger.info("Redis health check passed")
        else:
            raise Exception("Cache test failed")
    except Exception as e:
        health_status['services']['redis']['status'] = 'unhealthy'
        health_status['services']['redis']['error'] = str(e)
        overall_status = False
        logger.error("Redis health check failed", error=str(e))

    # Check Solana connection
    try:
        from blockchain.services import get_solana_service

        # Run async Solana health check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            service = loop.run_until_complete(get_solana_service())
            solana_health = loop.run_until_complete(service.get_health_status())

            if solana_health.get('connectivity') == 'connected':
                health_status['services']['solana']['status'] = 'healthy'
                health_status['services']['solana']['current_slot'] = solana_health.get('current_slot')
                health_status['services']['solana']['network'] = solana_health.get('network')
                logger.info("Solana health check passed")
            else:
                health_status['services']['solana']['status'] = 'degraded'
                health_status['services']['solana']['message'] = 'Not connected'
                logger.warning("Solana health check degraded")

        finally:
            loop.close()

    except Exception as e:
        health_status['services']['solana']['status'] = 'unhealthy'
        health_status['services']['solana']['error'] = str(e)
        logger.error("Solana health check failed", error=str(e))
        # Don't fail overall health check for Solana issues during initial setup

    # Set overall status
    if not overall_status:
        health_status['status'] = 'degraded'
    
    # Add timestamp
    from datetime import datetime
    health_status['timestamp'] = datetime.utcnow().isoformat()
    
    # Return appropriate HTTP status code
    http_status = status.HTTP_200_OK if overall_status else status.HTTP_503_SERVICE_UNAVAILABLE
    
    logger.info("Health check completed",
                overall_status=health_status['status'],
                database_status=health_status['services']['database']['status'],
                redis_status=health_status['services']['redis']['status'],
                solana_status=health_status['services']['solana']['status'])
    
    return Response(health_status, status=http_status)
