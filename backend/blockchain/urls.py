"""
URL patterns for blockchain API endpoints.
"""

from django.urls import path
from . import views

app_name = 'blockchain'

urlpatterns = [
    # Day 2 endpoints
    path('health/', views.solana_health, name='solana_health'),
    path('network-info/', views.solana_network_info, name='solana_network_info'),
    path('test-connection/', views.solana_test_connection, name='solana_test_connection'),

    # Day 3 endpoints - Merkle Trees
    path('merkle-trees/create/', views.create_merkle_tree, name='create_merkle_tree'),
    path('merkle-trees/', views.list_merkle_trees, name='list_merkle_trees'),
    path('merkle-trees/<str:tree_address>/', views.get_tree_info, name='get_tree_info'),

    # Day 3 endpoints - Compressed NFTs
    path('cnft/mint/', views.mint_compressed_nft, name='mint_compressed_nft'),

    # Day 4 endpoints - Database Models
    path('trees/', views.trees_list, name='trees_list'),
    path('carbon-prices/', views.carbon_market_prices, name='carbon_market_prices'),

    # Day 5 endpoints - Sei to Solana Migration
    path('migration/jobs/', views.create_migration_job, name='create_migration_job'),
    path('migration/jobs/list/', views.list_migration_jobs, name='list_migration_jobs'),

    # Day 6 - Integration & System Testing
    path('integration/run-pipeline/', views.run_end_to_end_pipeline, name='run_end_to_end_pipeline'),
    path('integration/run-batch/', views.run_batch_migration, name='run_batch_migration'),
    path('integration/cache-stats/', views.get_cache_stats, name='get_cache_stats'),
    path('integration/run-test/', views.run_integration_test, name='run_integration_test'),
    path('integration/performance-metrics/', views.get_performance_metrics, name='get_performance_metrics'),
    path('integration/test-results/', views.list_integration_test_results, name='list_integration_test_results'),
]
