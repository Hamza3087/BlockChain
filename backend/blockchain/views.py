"""
Blockchain API views for ReplantWorld.

This module provides REST API endpoints for blockchain operations,
health monitoring, and Solana network information.
"""

import asyncio
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import structlog

from .services import get_solana_service

logger = structlog.get_logger(__name__)


@api_view(['GET'])
def solana_health(request):
    """
    Get comprehensive health status of Solana connections.

    Returns:
        - Connection status
        - Current endpoint information
        - Health summary of all endpoints
        - Network information
    """
    try:
        # Run async health check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            service = loop.run_until_complete(get_solana_service())
            health_status = loop.run_until_complete(service.get_health_status())

            # Determine HTTP status code based on health
            if health_status.get('status') == 'initialized' and health_status.get('connectivity') == 'connected':
                http_status = status.HTTP_200_OK
            else:
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE

            logger.info(
                "Solana health check completed",
                status=health_status.get('status'),
                connectivity=health_status.get('connectivity'),
                current_slot=health_status.get('current_slot')
            )

            return Response(health_status, status=http_status)

        finally:
            loop.close()

    except Exception as e:
        logger.error("Solana health check failed", error=str(e))
        return Response(
            {
                "status": "error",
                "message": f"Health check failed: {str(e)}"
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@api_view(['GET'])
def solana_network_info(request):
    """
    Get current Solana network information.

    Returns:
        - Network name (devnet/mainnet/testnet)
        - Current slot and block height
        - Bubblegum program ID
        - Current endpoint information
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            service = loop.run_until_complete(get_solana_service())
            network_info = loop.run_until_complete(service.get_network_info())

            logger.info(
                "Network info retrieved",
                network=network_info.get('network'),
                current_slot=network_info.get('current_slot'),
                block_height=network_info.get('block_height')
            )

            return Response(network_info, status=status.HTTP_200_OK)

        finally:
            loop.close()

    except Exception as e:
        logger.error("Failed to get network info", error=str(e))
        return Response(
            {
                "status": "error",
                "message": f"Failed to get network info: {str(e)}"
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@api_view(['POST'])
def solana_test_connection(request):
    """
    Test the connection to Solana RPC endpoints.

    This endpoint performs a comprehensive connection test including:
    - Basic RPC calls (get_slot, get_block_height)
    - Response time measurement
    - Endpoint failover testing
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            service = loop.run_until_complete(get_solana_service())
            test_result = loop.run_until_complete(service.test_connection())

            if test_result.get('status') == 'success':
                http_status = status.HTTP_200_OK
                logger.info(
                    "Connection test successful",
                    response_time=test_result.get('response_time'),
                    current_slot=test_result.get('current_slot')
                )
            else:
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE
                logger.warning(
                    "Connection test failed",
                    message=test_result.get('message')
                )

            return Response(test_result, status=http_status)

        finally:
            loop.close()

    except Exception as e:
        logger.error("Connection test error", error=str(e))
        return Response(
            {
                "status": "error",
                "message": f"Connection test failed: {str(e)}"
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
