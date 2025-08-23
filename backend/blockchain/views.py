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
from asgiref.sync import sync_to_async
import structlog

from .services import get_solana_service
from .merkle_tree import MerkleTreeManager, MerkleTreeConfig
from .cnft_minting import CompressedNFTMinter, NFTMetadata, MintRequest
from .models import Tree, SpeciesGrowthParameters, CarbonMarketPrice, TreeCarbonData, SeiNFT, MigrationJob, MigrationLog
from .migration import MigrationService

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
