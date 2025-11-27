'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';

interface ServiceStatus {
  status: string;
  latency_ms: number | null;
  message: string;
}

interface SystemStatus {
  status: string;
  timestamp: string;
  services: {
    supabase: ServiceStatus;
    anthropic: ServiceStatus;
    modal: ServiceStatus;
    stripe: ServiceStatus;
    twilio: ServiceStatus;
  };
  environment: {
    python_version: string;
    env: string;
    railway_environment: string;
    api_url: string;
  };
  stats: {
    total_users: number;
    total_calls: number;
    total_assistants: number;
  };
}

export default function AdminStatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/admin/status', {
        headers: { 'X-User-ID': 'admin' }
      });
      if (!response.ok) throw new Error('Failed to fetch status');
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (s: string) => {
    switch (s) {
      case 'healthy':
      case 'configured':
        return 'bg-green-500';
      case 'partial':
        return 'bg-yellow-500';
      case 'error':
      case 'not_configured':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading system status...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">System Status</h1>
          <p className="text-gray-400 mt-1">Monitor service health and configuration</p>
        </div>
        <HoneycombButton onClick={fetchStatus} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </HoneycombButton>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      {/* Services */}
      <Card>
        <CardTitle>Services</CardTitle>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
            {status?.services && Object.entries(status.services).map(([name, service]) => (
              <div key={name} className="p-4 bg-oled-gray rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-white font-semibold capitalize">{name}</span>
                  <div className={`w-3 h-3 rounded-full ${getStatusColor(service.status)}`} />
                </div>
                <div className="text-gray-400 text-sm">{service.message}</div>
                {service.latency_ms !== null && (
                  <div className="text-gray-500 text-xs mt-1">{service.latency_ms}ms latency</div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      {status?.stats && (
        <Card>
          <CardTitle>Platform Stats</CardTitle>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
              <div className="p-4 bg-oled-gray rounded-lg text-center">
                <div className="text-3xl font-bold text-gold">{status.stats.total_users}</div>
                <div className="text-gray-400">Total Users</div>
              </div>
              <div className="p-4 bg-oled-gray rounded-lg text-center">
                <div className="text-3xl font-bold text-gold">{status.stats.total_calls}</div>
                <div className="text-gray-400">Total Calls</div>
              </div>
              <div className="p-4 bg-oled-gray rounded-lg text-center">
                <div className="text-3xl font-bold text-gold">{status.stats.total_assistants}</div>
                <div className="text-gray-400">Assistants</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Environment */}
      {status?.environment && (
        <Card>
          <CardTitle>Environment</CardTitle>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <div>
                <div className="text-gray-400 text-sm">Environment</div>
                <div className="text-white">{status.environment.env}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Python Version</div>
                <div className="text-white">{status.environment.python_version}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Railway Environment</div>
                <div className="text-white">{status.environment.railway_environment}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">API URL</div>
                <div className="text-white">{status.environment.api_url}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Timestamp */}
      {status?.timestamp && (
        <div className="text-center text-gray-500 text-sm">
          Last updated: {new Date(status.timestamp).toLocaleString()}
        </div>
      )}
    </div>
  );
}
