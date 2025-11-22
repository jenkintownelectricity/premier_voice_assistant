'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardTitle } from '@/components/Card';
import { ProgressBar } from '@/components/ProgressBar';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

interface PercentileData {
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  p99: number;
  min: number;
  max: number;
  mean: number;
  median: number;
  count: number;
}

interface LatencyData {
  period: { start_date: string; end_date: string; days: number };
  overall_percentiles: {
    stt: PercentileData;
    llm: PercentileData;
    tts: PercentileData;
    total: PercentileData;
  };
  by_event_type: Record<string, PercentileData>;
  performance_score: number;
  insights: {
    fastest_component: string;
    slowest_component: string;
    total_requests_analyzed: number;
  };
}

interface ErrorCorrelation {
  summary: {
    total_requests: number;
    error_count: number;
    success_count: number;
    error_rate_percent: number;
    success_rate_percent: number;
  };
  error_types: Record<string, number>;
  latency_correlation: {
    avg_error_latency_ms: number;
    avg_success_latency_ms: number;
    latency_difference_ms: number;
    correlation: string;
  };
  by_event_type: Record<string, any>;
  temporal_patterns: {
    peak_error_hours: Array<{ hour: string; error_count: number }>;
  };
  recommendations: string[];
}

export default function ObservabilityPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [latencyData, setLatencyData] = useState<LatencyData | null>(null);
  const [errorData, setErrorData] = useState<ErrorCorrelation | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => {
    if (!user) {
      router.push('/login');
      return;
    }

    fetchData();
  }, [user, router, days]);

  const fetchData = async () => {
    if (!user?.id) return;

    try {
      setLoading(true);
      const [latency, errors] = await Promise.all([
        api.getLatencyPercentiles(user.id, days),
        api.getErrorCorrelation(user.id, days),
      ]);

      setLatencyData(latency);
      setErrorData(errors);
    } catch (err: any) {
      console.error('Error fetching observability data:', err);
    } finally {
      setLoading(false);
    }
  };

  const getPerformanceColor = (score: number) => {
    if (score >= 90) return 'green';
    if (score >= 75) return 'yellow';
    return 'red';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white p-8">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-3xl font-bold mb-8 text-[#D4AF37]">Advanced Observability</h1>
          <p className="text-gray-400">Loading performance data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-[#D4AF37] mb-2">Advanced Observability</h1>
            <p className="text-gray-400">Latency percentiles and error correlation analysis</p>
          </div>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="bg-gray-900 border border-gray-700 rounded px-4 py-2"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
          </select>
        </div>

        {/* Performance Score */}
        {latencyData && (
          <div className="mb-8">
            <Card>
              <CardTitle>Performance Health Score</CardTitle>
              <CardContent>
                <div className="flex items-center gap-6">
                  <div className="text-6xl font-bold text-[#D4AF37]">
                    {latencyData.performance_score}
                  </div>
                  <div className="flex-1">
                    <ProgressBar
                      current={latencyData.performance_score}
                      max={100}
                      color={getPerformanceColor(latencyData.performance_score)}
                    />
                    <p className="text-sm text-gray-400 mt-2">
                      Based on P95 latency across {latencyData.insights.total_requests_analyzed} requests
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-6">
                  <div className="bg-gray-900 p-4 rounded">
                    <p className="text-gray-400 text-sm">Fastest Component</p>
                    <p className="text-xl font-semibold text-green-400">
                      {latencyData.insights.fastest_component.toUpperCase()}
                    </p>
                  </div>
                  <div className="bg-gray-900 p-4 rounded">
                    <p className="text-gray-400 text-sm">Slowest Component</p>
                    <p className="text-xl font-semibold text-yellow-400">
                      {latencyData.insights.slowest_component.toUpperCase()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Latency Percentiles */}
        {latencyData && (
          <div className="mb-8">
            <Card>
              <CardTitle>Latency Percentiles (ms)</CardTitle>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  {Object.entries(latencyData.overall_percentiles).map(([component, data]) => (
                    <div key={component} className="border border-gray-800 rounded p-4">
                      <h3 className="font-semibold text-[#D4AF37] mb-3 uppercase">{component}</h3>
                      {data.count > 0 ? (
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-400">P50</span>
                            <span className="font-mono">{data.p50.toFixed(0)}ms</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-400">P75</span>
                            <span className="font-mono">{data.p75.toFixed(0)}ms</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-400">P90</span>
                            <span className="font-mono">{data.p90.toFixed(0)}ms</span>
                          </div>
                          <div className="flex justify-between text-sm font-semibold">
                            <span className="text-gray-400">P95</span>
                            <span className="font-mono text-[#D4AF37]">{data.p95.toFixed(0)}ms</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-400">P99</span>
                            <span className="font-mono">{data.p99.toFixed(0)}ms</span>
                          </div>
                          <div className="pt-2 mt-2 border-t border-gray-700">
                            <div className="flex justify-between text-xs text-gray-500">
                              <span>Mean</span>
                              <span>{data.mean.toFixed(0)}ms</span>
                            </div>
                            <div className="flex justify-between text-xs text-gray-500">
                              <span>Range</span>
                              <span>{data.min}-{data.max}ms</span>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <p className="text-gray-500 text-sm">No data</p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Error Correlation */}
        {errorData && (
          <div className="mb-8">
            <Card>
              <CardTitle>Error Analysis</CardTitle>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Total Requests</p>
                    <p className="text-2xl font-bold">{errorData.summary.total_requests}</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Errors</p>
                    <p className="text-2xl font-bold text-red-400">{errorData.summary.error_count}</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Success Rate</p>
                    <p className="text-2xl font-bold text-green-400">
                      {errorData.summary.success_rate_percent.toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Error Rate</p>
                    <p className="text-2xl font-bold text-red-400">
                      {errorData.summary.error_rate_percent.toFixed(1)}%
                    </p>
                  </div>
                </div>

                <div className="mb-6">
                  <h4 className="font-semibold mb-3">Latency Correlation</h4>
                  <div className="bg-gray-900 p-4 rounded">
                    <p className="text-gray-400 mb-2">{errorData.latency_correlation.correlation}</p>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-400">Avg Error Latency</p>
                        <p className="text-xl font-semibold text-red-400">
                          {errorData.latency_correlation.avg_error_latency_ms.toFixed(0)}ms
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-400">Avg Success Latency</p>
                        <p className="text-xl font-semibold text-green-400">
                          {errorData.latency_correlation.avg_success_latency_ms.toFixed(0)}ms
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mb-6">
                  <h4 className="font-semibold mb-3">Top Error Types</h4>
                  <div className="space-y-2">
                    {Object.entries(errorData.error_types).slice(0, 5).map(([type, count], idx) => (
                      <div key={idx} className="flex items-center justify-between bg-gray-900 p-3 rounded">
                        <p className="flex-1 truncate text-sm">{type}</p>
                        <span className="ml-4 px-3 py-1 bg-red-900/30 text-red-400 rounded text-sm font-mono">
                          {count}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-3">Recommendations</h4>
                  <ul className="space-y-2">
                    {errorData.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-[#D4AF37]">•</span>
                        <span className="text-gray-300">{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
