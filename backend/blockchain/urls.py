"""
URL patterns for blockchain API endpoints.
"""

from django.urls import path
from . import views

app_name = 'blockchain'

urlpatterns = [
    path('health/', views.solana_health, name='solana_health'),
    path('network-info/', views.solana_network_info, name='solana_network_info'),
    path('test-connection/', views.solana_test_connection, name='solana_test_connection'),
]
