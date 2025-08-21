import { useState, useEffect } from 'react';
import axios from 'axios';

interface HealthStatus {
  status: string;
  timestamp: string;
  services: {
    database: {
      status: string;
      error?: string;
    };
    redis: {
      status: string;
      error?: string;
    };
  };
}

const HealthCheck = () => {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealthStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.get('http://localhost:8000/api/healthz/', {
        timeout: 5000,
      });
      
      setHealthStatus(response.data);
    } catch (err) {
      console.error('Health check failed:', err);
      if (axios.isAxiosError(err)) {
        if (err.code === 'ECONNREFUSED') {
          setError('Backend server is not running');
        } else if (err.response) {
          setError(`Server error: ${err.response.status} ${err.response.statusText}`);
        } else if (err.request) {
          setError('No response from server');
        } else {
          setError('Request failed');
        }
      } else {
        setError('Unknown error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealthStatus();
    
    // Set up polling every 30 seconds
    const interval = setInterval(fetchHealthStatus, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'ok':
        return 'text-green-600';
      case 'unhealthy':
      case 'degraded':
        return 'text-red-600';
      default:
        return 'text-yellow-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'ok':
        return '✅';
      case 'unhealthy':
      case 'degraded':
        return '❌';
      default:
        return '⚠️';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        <span className="ml-2">Checking system health...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded">
        <div className="flex items-center mb-2">
          <span className="text-2xl mr-2">❌</span>
          <h3 className="text-lg font-semibold text-red-800">Health Check Failed</h3>
        </div>
        <p className="text-red-600 mb-3">{error}</p>
        <button
          onClick={fetchHealthStatus}
          className="bg-red-500 hover:bg-red-600 text-white font-bold py-1 px-3 rounded text-sm"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!healthStatus) {
    return (
      <div className="p-4 bg-gray-50 border border-gray-200 rounded">
        <p className="text-gray-600">No health data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">System Health</h3>
        <button
          onClick={fetchHealthStatus}
          className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-1 px-3 rounded text-sm"
        >
          Refresh
        </button>
      </div>

      <div className="space-y-3">
        {/* Overall Status */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
          <span className="font-medium">Overall Status</span>
          <div className="flex items-center">
            <span className="mr-2">{getStatusIcon(healthStatus.status)}</span>
            <span className={`font-semibold ${getStatusColor(healthStatus.status)}`}>
              {healthStatus.status.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Database Status */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
          <span className="font-medium">Database (PostgreSQL)</span>
          <div className="flex items-center">
            <span className="mr-2">{getStatusIcon(healthStatus.services.database.status)}</span>
            <span className={`font-semibold ${getStatusColor(healthStatus.services.database.status)}`}>
              {healthStatus.services.database.status.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Redis Status */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
          <span className="font-medium">Redis Cache</span>
          <div className="flex items-center">
            <span className="mr-2">{getStatusIcon(healthStatus.services.redis.status)}</span>
            <span className={`font-semibold ${getStatusColor(healthStatus.services.redis.status)}`}>
              {healthStatus.services.redis.status.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      <div className="text-xs text-gray-500 text-center">
        Last updated: {new Date(healthStatus.timestamp).toLocaleString()}
      </div>
    </div>
  );
};

export default HealthCheck;
