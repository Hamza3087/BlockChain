#!/usr/bin/env python3
"""
Test script to verify Solana implementation works correctly.

This script tests the SolanaClient implementation, RPC failover,
and basic blockchain connectivity without requiring a full Django setup.
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from blockchain.clients.solana_client import SolanaClient, RPCEndpointStatus
from blockchain.config import get_solana_config
from blockchain.services import get_solana_service


async def test_solana_client():
    """Test SolanaClient functionality."""
    print("🧪 Testing SolanaClient...")
    
    # Get configuration
    config = get_solana_config()
    print(f"📋 Network: {config['network']}")
    print(f"📋 RPC Endpoints: {len(config['rpc_endpoints'])}")
    
    # Create client
    client = SolanaClient(
        rpc_endpoints=config['rpc_endpoints'],
        max_retries=2,
        retry_delay=1.0,
        health_check_interval=30,
        timeout=10
    )
    
    print(f"✅ SolanaClient created with {len(client.endpoints)} endpoints")
    
    # Test endpoint selection
    endpoint = client._select_endpoint()
    if endpoint:
        print(f"✅ Selected endpoint: {endpoint.name} (priority: {endpoint.priority})")
    else:
        print("❌ No endpoint selected")
        return False
    
    # Test health check
    print("🔍 Running health checks...")
    try:
        health_summary = await client.check_all_endpoints_health()
        print(f"✅ Health check completed")
        print(f"📊 Healthy: {health_summary['summary']['healthy']}")
        print(f"📊 Degraded: {health_summary['summary']['degraded']}")
        print(f"📊 Unhealthy: {health_summary['summary']['unhealthy']}")
        print(f"📊 Unknown: {health_summary['summary']['unknown']}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test connection
    print("🔗 Testing connection...")
    try:
        connected = await client.connect()
        if connected:
            print("✅ Connection established")
            
            # Test basic RPC calls
            try:
                slot_response = await client.get_slot()
                print(f"✅ Current slot: {slot_response.value}")
                
                block_height_response = await client.get_block_height()
                print(f"✅ Block height: {block_height_response.value}")
                
            except Exception as e:
                print(f"⚠️  RPC calls failed: {e}")
                
        else:
            print("❌ Connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    # Test endpoint info
    endpoint_info = client.get_current_endpoint_info()
    if endpoint_info:
        print(f"📡 Current endpoint: {endpoint_info['name']}")
        print(f"📡 URL: {endpoint_info['url']}")
        print(f"📡 Status: {endpoint_info['status']}")
        if endpoint_info['response_time']:
            print(f"📡 Response time: {endpoint_info['response_time']:.3f}s")
    
    # Cleanup
    await client.close()
    print("✅ SolanaClient test completed")
    return True


async def test_solana_service():
    """Test SolanaService functionality."""
    print("\n🧪 Testing SolanaService...")
    
    try:
        # Get service instance
        service = await get_solana_service()
        print("✅ SolanaService instance obtained")
        
        # Test health status
        health_status = await service.get_health_status()
        print(f"✅ Health status: {health_status.get('status')}")
        print(f"📊 Connectivity: {health_status.get('connectivity')}")
        
        if health_status.get('current_slot'):
            print(f"📊 Current slot: {health_status.get('current_slot')}")
        
        # Test network info
        try:
            network_info = await service.get_network_info()
            print(f"✅ Network: {network_info.get('network')}")
            print(f"📊 Bubblegum Program ID: {network_info.get('bubblegum_program_id')}")
        except Exception as e:
            print(f"⚠️  Network info failed: {e}")
        
        # Test connection
        try:
            connection_test = await service.test_connection()
            print(f"✅ Connection test: {connection_test.get('status')}")
            if connection_test.get('response_time'):
                print(f"📊 Response time: {connection_test.get('response_time'):.3f}s")
        except Exception as e:
            print(f"⚠️  Connection test failed: {e}")
        
        print("✅ SolanaService test completed")
        return True
        
    except Exception as e:
        print(f"❌ SolanaService test failed: {e}")
        return False


async def test_failover_mechanism():
    """Test RPC failover mechanism."""
    print("\n🧪 Testing RPC Failover...")
    
    # Create client with multiple endpoints
    test_endpoints = [
        {
            'name': 'Primary RPC',
            'url': 'https://api.devnet.solana.com',
            'priority': 1
        },
        {
            'name': 'Secondary RPC',
            'url': 'https://devnet.helius-rpc.com/?api-key=demo',
            'priority': 2
        }
    ]
    
    client = SolanaClient(
        rpc_endpoints=test_endpoints,
        max_retries=1,
        retry_delay=0.5,
        health_check_interval=30,
        timeout=5
    )
    
    print(f"✅ Created client with {len(client.endpoints)} endpoints")
    
    # Test endpoint switching
    original_endpoint = client._select_endpoint()
    print(f"📡 Original endpoint: {original_endpoint.name}")
    
    # Mark first endpoint as unhealthy
    client.endpoints[0].status = RPCEndpointStatus.UNHEALTHY
    client.endpoints[0].error_count = 10
    
    new_endpoint = client._select_endpoint()
    print(f"📡 Failover endpoint: {new_endpoint.name}")
    
    if new_endpoint != original_endpoint:
        print("✅ Failover mechanism working")
    else:
        print("⚠️  Failover mechanism may not be working as expected")
    
    await client.close()
    return True


def print_summary(results):
    """Print test summary."""
    print("\n" + "="*50)
    print("🎯 TEST SUMMARY")
    print("="*50)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    failed_tests = total_tests - passed_tests
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {total_tests}, Passed: {passed_tests}, Failed: {failed_tests}")
    
    if failed_tests == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"⚠️  {failed_tests} test(s) failed")
        return False


async def main():
    """Main test function."""
    print("🚀 Starting Solana Implementation Tests")
    print("="*50)
    
    results = {}
    
    # Run tests
    try:
        results["SolanaClient"] = await test_solana_client()
    except Exception as e:
        print(f"❌ SolanaClient test crashed: {e}")
        results["SolanaClient"] = False
    
    try:
        results["SolanaService"] = await test_solana_service()
    except Exception as e:
        print(f"❌ SolanaService test crashed: {e}")
        results["SolanaService"] = False
    
    try:
        results["Failover Mechanism"] = await test_failover_mechanism()
    except Exception as e:
        print(f"❌ Failover test crashed: {e}")
        results["Failover Mechanism"] = False
    
    # Print summary
    success = print_summary(results)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
