"""
API URLs for the NFT migration system.
"""

from django.urls import path
from . import views

app_name = 'blockchain_api'

urlpatterns = [
    # Migration status and statistics
    path('migration/status/', views.migration_status, name='migration_status'),
    
    # NFT operations
    path('nft/search/', views.search_nfts, name='search_nfts'),
    path('nft/<str:asset_id>/', views.nft_detail, name='nft_detail'),
    
    # Solana blockchain operations
    path('solana/retrieve/', views.retrieve_from_solana, name='retrieve_from_solana'),
    
    # System health
    path('health/', views.health_check, name='health_check'),
]
