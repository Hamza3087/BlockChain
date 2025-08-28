"""
Complete API endpoints for the NFT migration system.
"""

import asyncio
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from asgiref.sync import sync_to_async
import json

from blockchain.models import SeiNFT, MigrationJob, MigrationLog
from blockchain.services.solana_nft_retriever import SolanaNFTRetriever


class MigrationStatusView(View):
    """Get migration status and statistics."""

    
    
    async def get(self, request):
        """Get overall migration statistics."""
        try:
            # Get database statistics
            total_nfts = await sync_to_async(SeiNFT.objects.count)()
            completed_migrations = await sync_to_async(
                SeiNFT.objects.filter(migration_status='completed').count
            )()
            pending_migrations = await sync_to_async(
                SeiNFT.objects.filter(migration_status='pending').count
            )()
            failed_migrations = await sync_to_async(
                SeiNFT.objects.filter(migration_status='failed').count
            )()
            
            total_jobs = await sync_to_async(MigrationJob.objects.count)()
            completed_jobs = await sync_to_async(
                MigrationJob.objects.filter(status='completed').count
            )()
            
            # Get recent migration jobs
            recent_jobs = await sync_to_async(
                lambda: list(MigrationJob.objects.order_by('-created_at')[:5].values(
                    'job_id', 'name', 'status', 'total_nfts', 'successful_migrations',
                    'failed_migrations', 'created_at', 'completed_at'
                ))
            )()
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'overview': {
                        'total_nfts': total_nfts,
                        'completed_migrations': completed_migrations,
                        'pending_migrations': pending_migrations,
                        'failed_migrations': failed_migrations,
                        'success_rate': (completed_migrations / total_nfts * 100) if total_nfts > 0 else 0
                    },
                    'jobs': {
                        'total_jobs': total_jobs,
                        'completed_jobs': completed_jobs,
                        'recent_jobs': recent_jobs
                    }
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class NFTDetailView(View):
    """Get detailed information about a specific NFT."""
    
    async def get(self, request, asset_id):
        """Get NFT details by Solana asset ID."""
        try:
            # Find NFT by asset ID
            sei_nft = await sync_to_async(
                lambda: SeiNFT.objects.filter(solana_asset_id=asset_id).first()
            )()
            
            if not sei_nft:
                return JsonResponse({
                    'status': 'error',
                    'message': 'NFT not found'
                }, status=404)
            
            # Get migration logs for this NFT
            migration_logs = await sync_to_async(
                lambda: list(sei_nft.logs.order_by('-created_at').values(
                    'level', 'event_type', 'message', 'details', 'created_at'
                ))
            )()
            
            # Try to retrieve from Solana
            retriever = SolanaNFTRetriever()
            await retriever.initialize()
            
            solana_nft = await retriever.retrieve_nft_by_asset_id(asset_id)
            
            await retriever.close()
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'sei_data': {
                        'contract_address': sei_nft.sei_contract_address,
                        'token_id': sei_nft.sei_token_id,
                        'owner_address': sei_nft.sei_owner_address,
                        'name': sei_nft.name,
                        'description': sei_nft.description,
                        'image_url': sei_nft.image_url,
                        'external_url': sei_nft.external_url,
                        'attributes': sei_nft.attributes,
                        'migration_status': sei_nft.migration_status,
                        'migration_date': sei_nft.migration_date
                    },
                    'solana_data': {
                        'asset_id': sei_nft.solana_asset_id,
                        'mint_address': sei_nft.solana_mint_address,
                        'retrieved_from_blockchain': solana_nft is not None,
                        'metadata': solana_nft.metadata if solana_nft else None
                    },
                    'migration_history': migration_logs
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class SearchNFTsView(View):
    """Search NFTs by various criteria."""
    
    async def get(self, request):
        """Search NFTs."""
        try:
            # Get query parameters
            contract = request.GET.get('contract')
            owner = request.GET.get('owner')
            status = request.GET.get('status')
            limit = int(request.GET.get('limit', 10))
            
            # Build query
            queryset = SeiNFT.objects.all()
            
            if contract:
                queryset = queryset.filter(sei_contract_address=contract)
            if owner:
                queryset = queryset.filter(sei_owner_address=owner)
            if status:
                queryset = queryset.filter(migration_status=status)
            
            # Get results
            nfts = await sync_to_async(
                lambda: list(queryset.order_by('-created_at')[:limit].values(
                    'sei_contract_address', 'sei_token_id', 'sei_owner_address',
                    'name', 'description', 'image_url', 'migration_status',
                    'solana_asset_id', 'solana_mint_address', 'migration_date'
                ))
            )()
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'nfts': nfts,
                    'count': len(nfts),
                    'filters': {
                        'contract': contract,
                        'owner': owner,
                        'status': status,
                        'limit': limit
                    }
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class RetrieveFromSolanaView(View):
    """Retrieve NFT data directly from Solana blockchain."""
    
    async def post(self, request):
        """Retrieve NFT from Solana by asset ID."""
        try:
            data = json.loads(request.body)
            asset_id = data.get('asset_id')
            
            if not asset_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'asset_id is required'
                }, status=400)
            
            # Initialize retriever
            retriever = SolanaNFTRetriever()
            await retriever.initialize()
            
            # Retrieve NFT
            solana_nft = await retriever.retrieve_nft_by_asset_id(asset_id)
            
            if not solana_nft:
                await retriever.close()
                return JsonResponse({
                    'status': 'error',
                    'message': 'NFT not found on Solana blockchain'
                }, status=404)
            
            # Convert to Sei format
            sei_format = await retriever.convert_to_sei_format(solana_nft)
            
            await retriever.close()
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'solana_format': {
                        'asset_id': solana_nft.asset_id,
                        'mint_address': solana_nft.mint_address,
                        'tree_address': solana_nft.tree_address,
                        'owner': solana_nft.owner,
                        'metadata': solana_nft.metadata,
                        'compressed': solana_nft.compressed
                    },
                    'sei_format': {
                        'contract_address': sei_format.contract_address,
                        'token_id': sei_format.token_id,
                        'owner_address': sei_format.owner_address,
                        'name': sei_format.name,
                        'description': sei_format.description,
                        'image_url': sei_format.image_url,
                        'external_url': sei_format.external_url,
                        'attributes': sei_format.attributes
                    } if sei_format else None
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class HealthCheckView(View):
    """Health check endpoint."""
    
    async def get(self, request):
        """Check system health."""
        try:
            # Check database connectivity
            nft_count = await sync_to_async(SeiNFT.objects.count)()
            
            # Check Solana connectivity
            retriever = SolanaNFTRetriever()
            await retriever.initialize()
            await retriever.close()
            
            return JsonResponse({
                'status': 'healthy',
                'data': {
                    'database': 'connected',
                    'solana': 'connected',
                    'nft_count': nft_count,
                    'timestamp': '2025-08-25T11:43:44Z'
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'unhealthy',
                'error': str(e)
            }, status=500)


# Async view wrapper
def async_view(view_func):
    """Wrapper to handle async views in Django."""
    def wrapper(request, *args, **kwargs):
        return asyncio.run(view_func(request, *args, **kwargs))
    return wrapper


# Export wrapped views
migration_status = async_view(MigrationStatusView.as_view())
nft_detail = async_view(NFTDetailView.as_view())
search_nfts = async_view(SearchNFTsView.as_view())
retrieve_from_solana = csrf_exempt(async_view(RetrieveFromSolanaView.as_view()))
health_check = async_view(HealthCheckView.as_view())
