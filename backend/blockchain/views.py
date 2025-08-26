"""
Blockchain API views for ReplantWorld.

This module provides REST API endpoints for blockchain operations,
health monitoring, and Solana network information.
"""

import asyncio
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.utils import timezone
from asgiref.sync import sync_to_async
import structlog

from .clients.solana_client import SolanaClient

# Temporary compatibility function
async def get_solana_service():
    """Compatibility function to replace the old service."""
    default_endpoints = [
        {
            'url': 'https://api.devnet.solana.com',
            'name': 'devnet-primary',
            'priority': 1,
            'timeout': 30
        }
    ]
    client = SolanaClient(rpc_endpoints=default_endpoints)
    await client.connect()
    return client
from .merkle_tree import MerkleTreeManager, MerkleTreeConfig
from .cnft_minting import CompressedNFTMinter, NFTMetadata, MintRequest
from .models import (
    Tree, SpeciesGrowthParameters, CarbonMarketPrice, TreeCarbonData,
    SeiNFT, MigrationJob, MigrationLog, IntegrationTestResult,
    BatchMigrationStatus, PerformanceMetric
)
from .migration import MigrationService
from .integration import (
    EndToEndPipeline, BatchMigrationManager, CacheManager,
    IntegrationTestRunner, PerformanceMonitor
)
from .integration.test_runner import TestConfiguration, TestScenario

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


@api_view(['POST'])
def create_merkle_tree(request):
    """
    Create a new Merkle tree for compressed NFTs.

    Expected JSON payload:
    {
        "max_depth": 14,
        "max_buffer_size": 64,
        "canopy_depth": 0,
        "public": true,
        "tree_name": "My Tree"
    }
    """
    try:
        # Parse request data
        data = json.loads(request.body) if request.body else {}

        max_depth = data.get('max_depth', 14)
        max_buffer_size = data.get('max_buffer_size', 64)
        canopy_depth = data.get('canopy_depth', 0)
        public = data.get('public', True)
        tree_name = data.get('tree_name')

        async def _create_tree():
            service = await get_solana_service()
            tree_manager = MerkleTreeManager(service.client)

            # Load existing trees from persistent storage
            try:
                tree_manager.load_trees_from_file('managed_trees.json')
            except FileNotFoundError:
                # No existing trees file, that's okay
                pass

            # Create tree configuration
            config = tree_manager.create_tree_config(
                max_depth=max_depth,
                max_buffer_size=max_buffer_size,
                canopy_depth=canopy_depth,
                public=public
            )

            # Create the tree
            tree_info = await tree_manager.create_merkle_tree(config=config, tree_name=tree_name)

            # Save tree data to persistent storage
            tree_manager.save_trees_to_file('managed_trees.json')
            return tree_info, config

        # Run the async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        tree_info, config = loop.run_until_complete(_create_tree())

        logger.info(
            "Merkle tree created via API",
            tree_address=tree_info.tree_address,
            max_capacity=config.max_capacity,
            tree_name=tree_name
        )

        return Response(tree_info.to_dict(), status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error("Failed to create Merkle tree via API", error=str(e))
        return Response(
            {
                "status": "error",
                "message": f"Failed to create Merkle tree: {str(e)}"
            },
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
def list_merkle_trees(request):
    """List all managed Merkle trees."""
    try:
        async def _list_trees():
            service = await get_solana_service()
            tree_manager = MerkleTreeManager(service.client)

            # Load existing trees from persistent storage
            try:
                tree_manager.load_trees_from_file('managed_trees.json')
            except FileNotFoundError:
                # No existing trees file, that's okay
                pass

            trees = await tree_manager.list_trees()
            return trees

        # Run the async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        trees = loop.run_until_complete(_list_trees())

        trees_data = [tree.to_dict() for tree in trees]

        return Response({
            "trees": trees_data,
            "count": len(trees_data)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to list Merkle trees", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to list trees: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_tree_info(request, tree_address):
    """Get information about a specific Merkle tree."""
    try:
        async def _get_tree_info():
            service = await get_solana_service()
            tree_manager = MerkleTreeManager(service.client)

            # Load existing trees from persistent storage
            try:
                tree_manager.load_trees_from_file('managed_trees.json')
            except FileNotFoundError:
                # No existing trees file, that's okay
                pass

            tree_info = await tree_manager.get_tree_info(tree_address)

            if not tree_info:
                return None

            # Get capacity info
            capacity_info = await tree_manager.get_tree_capacity_info(tree_address)
            return tree_info, capacity_info

        # Run the async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_get_tree_info())

        if not result:
            return Response(
                {"status": "error", "message": "Tree not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        tree_info, capacity_info = result
        response_data = tree_info.to_dict()
        response_data['capacity_info'] = capacity_info

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get tree info", tree_address=tree_address, error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to get tree info: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def mint_compressed_nft(request):
    """
    Mint a compressed NFT to a Merkle tree.

    Expected JSON payload:
    {
        "tree_address": "...",
        "recipient": "...",
        "metadata": {
            "name": "...",
            "symbol": "...",
            "description": "...",
            "image": "...",
            "external_url": "..."
        }
    }
    """
    try:
        data = json.loads(request.body) if request.body else {}

        tree_address = data.get('tree_address')
        recipient = data.get('recipient')
        metadata_data = data.get('metadata', {})

        if not tree_address:
            return Response(
                {"status": "error", "message": "tree_address is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        async def _mint_nft():
            service = await get_solana_service()
            tree_manager = MerkleTreeManager(service.client)

            # Load existing trees from persistent storage
            try:
                tree_manager.load_trees_from_file('managed_trees.json')
            except FileNotFoundError:
                # No existing trees file, that's okay
                pass

            minter = CompressedNFTMinter(tree_manager)

            # Use tree authority as recipient if not specified
            nonlocal recipient
            if not recipient:
                recipient = str(tree_manager.authority)

            # Create metadata
            metadata = NFTMetadata(**metadata_data)

            # Create mint request
            mint_request = MintRequest(
                tree_address=tree_address,
                recipient=recipient,
                metadata=metadata
            )

            # Perform minting
            mint_result = await minter.mint_compressed_nft(mint_request, confirm_transaction=True)
            return mint_result, metadata

        # Run the async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        mint_result, metadata = loop.run_until_complete(_mint_nft())

        logger.info(
            "Compressed NFT minted via API",
            mint_id=mint_result.mint_id,
            tree_address=tree_address,
            recipient=recipient,
            nft_name=metadata.name
        )

        return Response(mint_result.to_dict(), status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error("Failed to mint compressed NFT via API", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to mint NFT: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST
        )


# Day 4 API Endpoints - Database Models Integration

@api_view(['GET'])
def trees_list(request):
    """
    API endpoint to list trees with filtering options.

    Query parameters:
    - species: Filter by tree species
    - status: Filter by tree status
    - verification_status: Filter by verification status
    - location: Filter by location name (contains)
    - limit: Number of results to return (default: 50)
    - offset: Number of results to skip (default: 0)
    """
    try:
        # Get query parameters for filtering
        species = request.GET.get('species')
        tree_status = request.GET.get('status')
        verification_status = request.GET.get('verification_status')
        location = request.GET.get('location')
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))

        # Build queryset with filters
        queryset = Tree.objects.select_related('owner', 'planter').all()

        if species:
            queryset = queryset.filter(species__icontains=species)
        if tree_status:
            queryset = queryset.filter(status=tree_status)
        if verification_status:
            queryset = queryset.filter(verification_status=verification_status)
        if location:
            queryset = queryset.filter(location_name__icontains=location)

        # Apply pagination
        total_count = queryset.count()
        trees = queryset[offset:offset + limit]

        # Serialize tree data
        trees_data = []
        for tree in trees:
            tree_data = {
                'tree_id': str(tree.tree_id),
                'mint_address': tree.mint_address,
                'merkle_tree_address': tree.merkle_tree_address,
                'asset_id': tree.asset_id,
                'species': tree.species,
                'planted_date': tree.planted_date.isoformat(),
                'location': {
                    'name': tree.location_name,
                    'latitude': float(tree.location_latitude),
                    'longitude': float(tree.location_longitude)
                },
                'status': tree.status,
                'height_cm': tree.height_cm,
                'diameter_cm': float(tree.diameter_cm) if tree.diameter_cm else None,
                'estimated_carbon_kg': float(tree.estimated_carbon_kg),
                'verified_carbon_kg': float(tree.verified_carbon_kg) if tree.verified_carbon_kg else None,
                'verification_status': tree.verification_status,
                'owner': tree.owner.username,
                'age_days': tree.age_days,
                'carbon_per_day': float(tree.carbon_per_day),
                'image_url': tree.image_url,
                'created_at': tree.created_at.isoformat(),
                'updated_at': tree.updated_at.isoformat()
            }
            trees_data.append(tree_data)

        return Response({
            'trees': trees_data,
            'pagination': {
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_next': offset + limit < total_count
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to retrieve trees", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to retrieve trees: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def carbon_market_prices(request):
    """
    API endpoint to get carbon market prices.

    Query parameters:
    - market_name: Filter by market name
    - market_type: Filter by market type
    - credit_type: Filter by credit type (default: forestry)
    - days: Number of days to look back (default: 30)
    - latest: Get only the latest price (true/false)
    """
    try:
        market_name = request.GET.get('market_name')
        market_type = request.GET.get('market_type')
        credit_type = request.GET.get('credit_type', 'forestry')
        days = int(request.GET.get('days', 30))
        latest_only = request.GET.get('latest', '').lower() == 'true'

        # Build queryset
        from django.utils import timezone
        cutoff_date = timezone.now().date() - timezone.timedelta(days=days)

        queryset = CarbonMarketPrice.objects.filter(
            price_date__gte=cutoff_date,
            is_active=True,
            credit_type=credit_type
        )

        if market_name:
            queryset = queryset.filter(market_name__icontains=market_name)
        if market_type:
            queryset = queryset.filter(market_type=market_type)

        if latest_only:
            queryset = queryset.order_by('-price_date')[:1]
        else:
            queryset = queryset.order_by('-price_date')[:100]  # Limit to 100 results

        # Serialize data
        prices_data = []
        for price in queryset:
            price_data = {
                'market_name': price.market_name,
                'market_type': price.market_type,
                'price_date': price.price_date.isoformat(),
                'price_usd_per_ton': float(price.price_usd_per_ton),
                'currency': price.currency,
                'volume_tons': float(price.volume_tons) if price.volume_tons else None,
                'credit_type': price.credit_type,
                'vintage_year': price.vintage_year,
                'data_quality': price.data_quality,
                'data_source': price.data_source,
                'created_at': price.created_at.isoformat()
            }
            prices_data.append(price_data)

        # Calculate average price
        from django.db.models import Avg
        avg_price = queryset.aggregate(avg_price=Avg('price_usd_per_ton'))['avg_price']

        return Response({
            'prices': prices_data,
            'summary': {
                'count': len(prices_data),
                'average_price_usd_per_ton': float(avg_price) if avg_price else None,
                'credit_type': credit_type,
                'period_days': days
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to retrieve carbon market prices", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to retrieve prices: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Day 5 API Endpoints - Sei to Solana Migration

@api_view(['POST'])
def create_migration_job(request):
    """
    API endpoint to create a new migration job.

    POST data:
    - name: Job name
    - description: Job description
    - sei_contract_addresses: List of Sei contract addresses
    - batch_size: Batch size (optional, default: 100)
    - configuration: Additional configuration (optional)
    """
    try:
        data = json.loads(request.body) if request.body else {}

        # Validate required fields
        required_fields = ['name', 'description', 'sei_contract_addresses']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return Response(
                {"status": "error", "message": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create user (in production, use authenticated user)
        from django.contrib.auth.models import User
        user, created = User.objects.get_or_create(
            username='api_user',
            defaults={'email': 'api@replantworld.com'}
        )

        # Create migration job
        migration_job = MigrationJob.objects.create(
            name=data['name'],
            description=data['description'],
            sei_contract_addresses=data['sei_contract_addresses'],
            batch_size=data.get('batch_size', 100),
            configuration=data.get('configuration', {}),
            created_by=user
        )

        logger.info(
            "Migration job created via API",
            job_id=str(migration_job.job_id),
            name=migration_job.name,
            contracts=len(migration_job.sei_contract_addresses)
        )

        return Response({
            'job_id': str(migration_job.job_id),
            'name': migration_job.name,
            'status': migration_job.status,
            'sei_contract_addresses': migration_job.sei_contract_addresses,
            'batch_size': migration_job.batch_size,
            'created_at': migration_job.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error("Failed to create migration job", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to create migration job: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def list_migration_jobs(request):
    """
    API endpoint to list migration jobs.

    Query parameters:
    - status: Filter by job status
    - limit: Number of results (default: 50)
    - offset: Offset for pagination (default: 0)
    """
    try:
        # Get query parameters
        job_status = request.GET.get('status')
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))

        # Build queryset
        queryset = MigrationJob.objects.select_related('created_by').all()

        if job_status:
            queryset = queryset.filter(status=job_status)

        # Apply pagination
        total_count = queryset.count()
        jobs = queryset[offset:offset + limit]

        # Serialize job data
        jobs_data = []
        for job in jobs:
            job_data = {
                'job_id': str(job.job_id),
                'name': job.name,
                'description': job.description,
                'status': job.status,
                'sei_contract_addresses': job.sei_contract_addresses,
                'batch_size': job.batch_size,
                'total_nfts': job.total_nfts,
                'processed_nfts': job.processed_nfts,
                'successful_migrations': job.successful_migrations,
                'failed_migrations': job.failed_migrations,
                'progress_percentage': job.progress_percentage,
                'success_rate': job.success_rate,
                'created_by': job.created_by.username,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'duration': str(job.duration) if job.duration else None
            }
            jobs_data.append(job_data)

        return Response({
            'jobs': jobs_data,
            'pagination': {
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_next': offset + limit < total_count
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to list migration jobs", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to list migration jobs: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Day 6 API Endpoints - Integration & System Testing

@api_view(['POST'])
def run_end_to_end_pipeline(request):
    """
    API endpoint to run end-to-end pipeline.

    POST data:
    - sei_contract_addresses: List of Sei contract addresses
    - max_nfts_per_contract: Maximum NFTs per contract (optional)
    - enable_caching: Enable caching (optional, default: true)
    - enable_monitoring: Enable monitoring (optional, default: true)
    """
    try:
        data = json.loads(request.body) if request.body else {}

        # Validate required fields
        if not data.get('sei_contract_addresses'):
            return Response(
                {"status": "error", "message": "sei_contract_addresses is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        async def run_pipeline():
            pipeline = EndToEndPipeline(
                enable_caching=data.get('enable_caching', True),
                enable_monitoring=data.get('enable_monitoring', True)
            )

            initialized = await pipeline.initialize()
            if not initialized:
                return {"status": "error", "message": "Failed to initialize pipeline"}

            try:
                result = await pipeline.execute_full_pipeline(
                    sei_contract_addresses=data['sei_contract_addresses'],
                    max_nfts_per_contract=data.get('max_nfts_per_contract')
                )

                return {
                    "status": "success",
                    "pipeline_id": result.pipeline_id,
                    "pipeline_status": result.status.value,
                    "total_nfts": result.total_nfts,
                    "processed_nfts": result.processed_nfts,
                    "successful_nfts": result.successful_nfts,
                    "failed_nfts": result.failed_nfts,
                    "success_rate": result.success_rate,
                    "duration": result.duration,
                    "stage_results": result.stage_results,
                    "performance_metrics": result.performance_metrics
                }

            finally:
                await pipeline.close()

        # Run the async pipeline
        result = asyncio.run(run_pipeline())

        if result.get("status") == "error":
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info(
            "End-to-end pipeline executed via API",
            pipeline_id=result.get("pipeline_id"),
            success_rate=result.get("success_rate")
        )

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to run end-to-end pipeline", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to run pipeline: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def run_batch_migration(request):
    """
    API endpoint to run batch migration.

    POST data:
    - migration_job_id: Migration job ID to process in batches
    """
    try:
        data = json.loads(request.body) if request.body else {}

        if not data.get('migration_job_id'):
            return Response(
                {"status": "error", "message": "migration_job_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get migration job
        try:
            migration_job = MigrationJob.objects.get(job_id=data['migration_job_id'])
        except MigrationJob.DoesNotExist:
            return Response(
                {"status": "error", "message": "Migration job not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        async def run_batch():
            batch_manager = BatchMigrationManager()

            progress = await batch_manager.process_migration_job_in_batches(migration_job)

            return {
                "status": "success",
                "batch_id": progress.batch_id,
                "batch_status": progress.status.value,
                "total_items": progress.total_items,
                "processed_items": progress.processed_items,
                "successful_items": progress.successful_items,
                "failed_items": progress.failed_items,
                "progress_percentage": progress.progress_percentage,
                "success_rate": progress.success_rate,
                "duration": str(progress.duration) if progress.duration else None,
                "start_time": progress.start_time.isoformat(),
                "end_time": progress.end_time.isoformat() if progress.end_time else None
            }

        # Run the async batch migration
        result = asyncio.run(run_batch())

        logger.info(
            "Batch migration executed via API",
            batch_id=result.get("batch_id"),
            success_rate=result.get("success_rate")
        )

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to run batch migration", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to run batch migration: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_cache_stats(request):
    """
    API endpoint to get Redis cache statistics.
    """
    try:
        from .integration.cache_manager import cache_manager

        stats = cache_manager.get_stats()

        return Response({
            "status": "success",
            "cache_stats": stats,
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to get cache stats: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def run_integration_test(request):
    """
    API endpoint to run integration tests.

    POST data:
    - scenario: Test scenario (single_nft_migration, batch_migration, etc.)
    - test_data_size: Size of test data (optional, default: 10)
    - enable_caching: Enable caching (optional, default: true)
    - enable_monitoring: Enable monitoring (optional, default: true)
    """
    try:
        data = json.loads(request.body) if request.body else {}

        scenario_name = data.get('scenario', 'single_nft_migration')

        # Validate scenario
        try:
            scenario = TestScenario(scenario_name)
        except ValueError:
            return Response(
                {"status": "error", "message": f"Invalid scenario: {scenario_name}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        async def run_test():
            test_runner = IntegrationTestRunner()
            await test_runner.initialize()

            try:
                test_config = TestConfiguration(
                    scenario=scenario,
                    test_data_size=data.get('test_data_size', 10),
                    enable_caching=data.get('enable_caching', True),
                    enable_monitoring=data.get('enable_monitoring', True),
                    timeout_seconds=data.get('timeout_seconds', 300)
                )

                test_result = await test_runner.run_test_scenario(test_config)

                return {
                    "status": "success",
                    "test_id": test_result.test_id,
                    "scenario": test_result.scenario.value,
                    "test_status": test_result.status,
                    "duration_seconds": test_result.duration_seconds,
                    "success_rate": test_result.success_rate,
                    "test_data_size": test_result.test_data_size,
                    "performance_metrics": test_result.performance_metrics,
                    "warnings": test_result.warnings,
                    "error_message": test_result.error_message
                }

            finally:
                await test_runner.close()

        # Run the async test
        result = asyncio.run(run_test())

        logger.info(
            "Integration test executed via API",
            test_id=result.get("test_id"),
            scenario=result.get("scenario"),
            test_status=result.get("test_status")
        )

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to run integration test", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to run integration test: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_performance_metrics(request):
    """
    API endpoint to get performance metrics.

    Query parameters:
    - category: Metric category (optional)
    - limit: Number of results (default: 100)
    """
    try:
        category = request.GET.get('category')
        limit = int(request.GET.get('limit', 100))

        async def get_metrics():
            monitor = PerformanceMonitor()
            await monitor.initialize()

            try:
                if category:
                    metrics = await monitor.get_metrics(category=category, limit=limit)
                else:
                    metrics = await monitor.get_metrics(limit=limit)

                # Get performance summary
                summary = await monitor.get_performance_summary()

                return {
                    "status": "success",
                    "metrics": metrics,
                    "summary": summary,
                    "timestamp": timezone.now().isoformat()
                }

            finally:
                await monitor.close()

        # Run the async function
        result = asyncio.run(get_metrics())

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get performance metrics", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to get performance metrics: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def list_integration_test_results(request):
    """
    API endpoint to list integration test results.

    Query parameters:
    - scenario: Filter by test scenario
    - status: Filter by test status
    - limit: Number of results (default: 50)
    - offset: Offset for pagination (default: 0)
    """
    try:
        scenario = request.GET.get('scenario')
        test_status = request.GET.get('status')
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))

        # Build queryset
        queryset = IntegrationTestResult.objects.select_related('executed_by').all()

        if scenario:
            queryset = queryset.filter(scenario=scenario)
        if test_status:
            queryset = queryset.filter(status=test_status)

        # Apply pagination
        total_count = queryset.count()
        test_results = queryset[offset:offset + limit]

        # Serialize data
        results_data = []
        for test_result in test_results:
            result_data = {
                'test_id': str(test_result.test_id),
                'scenario': test_result.scenario,
                'status': test_result.status,
                'test_data_size': test_result.test_data_size,
                'duration_seconds': test_result.duration_seconds,
                'success_rate': test_result.success_rate,
                'total_nfts_processed': test_result.total_nfts_processed,
                'successful_nfts': test_result.successful_nfts,
                'failed_nfts': test_result.failed_nfts,
                'executed_by': test_result.executed_by.username if test_result.executed_by else None,
                'environment': test_result.environment,
                'start_time': test_result.start_time.isoformat(),
                'end_time': test_result.end_time.isoformat() if test_result.end_time else None,
                'created_at': test_result.created_at.isoformat()
            }
            results_data.append(result_data)

        return Response({
            'test_results': results_data,
            'pagination': {
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_next': offset + limit < total_count
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to list integration test results", error=str(e))
        return Response(
            {"status": "error", "message": f"Failed to list integration test results: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
