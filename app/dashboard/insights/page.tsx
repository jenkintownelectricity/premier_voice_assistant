'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardTitle } from '@/components/Card';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

interface Recommendation {
  title: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
}

interface AIInsights {
  summary: string;
  recommendations: Recommendation[];
  highlight: string;
}

interface WeeklyData {
  period: { start: string; end: string };
  metrics: {
    current_week: {
      cost_dollars: number;
      total_tokens: number;
      total_requests: number;
      error_count: number;
      avg_latency_ms: number;
    };
    changes: {
      cost_percent: number;
      tokens_percent: number;
      requests_percent: number;
    };
  };
  ai_insights: AIInsights;
}

interface CostOptimization {
  period_days: number;
  current_monthly_cost: number;
  total_requests: number;
  optimizations: Array<{
    title: string;
    description: string;
    potential_savings_dollars: number;
    impact: string;
    category: string;
  }>;
  potential_monthly_savings: number;
  top_cost_drivers: Array<{
    event_type: string;
    cost_dollars: number;
    percentage: number;
    count: number;
  }>;
}

export default function InsightsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [weeklyData, setWeeklyData] = useState<WeeklyData | null>(null);
  const [costData, setCostData] = useState<CostOptimization | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      router.push('/login');
      return;
    }

    fetchInsights();
  }, [user, router]);

  const fetchInsights = async () => {
    if (!user?.id) return;

    try {
      setLoading(true);
      const [weekly, cost] = await Promise.all([
        api.getWeeklyInsights(user.id),
        api.getCostOptimizer(user.id),
      ]);

      setWeeklyData(weekly);
      setCostData(cost);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching insights:', err);
      setError(err.message || 'Failed to load insights');
    } finally {
      setLoading(false);
    }
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'high':
        return 'text-green-400';
      case 'medium':
        return 'text-yellow-400';
      case 'low':
        return 'text-gray-400';
      default:
        return 'text-gray-400';
    }
  };

  const getChangeColor = (value: number) => {
    if (value > 0) return 'text-red-400';
    if (value < 0) return 'text-green-400';
    return 'text-gray-400';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white p-8">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-3xl font-bold mb-8 text-[#D4AF37]">AI Usage Coach</h1>
          <p className="text-gray-400">Loading insights...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black text-white p-8">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-3xl font-bold mb-8 text-[#D4AF37]">AI Usage Coach</h1>
          <Card>
            <CardContent>
              <p className="text-red-400">Error: {error}</p>
              <button
                onClick={fetchInsights}
                className="mt-4 px-4 py-2 bg-[#D4AF37] text-black rounded hover:bg-[#B8941F]"
              >
                Retry
              </button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-[#D4AF37] mb-2">AI Usage Coach</h1>
          <p className="text-gray-400">Personalized insights and optimization recommendations</p>
        </div>

        {/* Weekly Summary */}
        {weeklyData && (
          <div className="mb-8">
            <Card>
              <CardTitle>This Week&apos;s Performance</CardTitle>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Total Cost</p>
                    <p className="text-2xl font-bold text-[#D4AF37]">
                      ${weeklyData.metrics.current_week.cost_dollars.toFixed(2)}
                    </p>
                    <p className={`text-sm ${getChangeColor(weeklyData.metrics.changes.cost_percent)}`}>
                      {weeklyData.metrics.changes.cost_percent > 0 ? '+' : ''}
                      {weeklyData.metrics.changes.cost_percent}% vs last week
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Total Tokens</p>
                    <p className="text-2xl font-bold">
                      {weeklyData.metrics.current_week.total_tokens.toLocaleString()}
                    </p>
                    <p className={`text-sm ${getChangeColor(weeklyData.metrics.changes.tokens_percent)}`}>
                      {weeklyData.metrics.changes.tokens_percent > 0 ? '+' : ''}
                      {weeklyData.metrics.changes.tokens_percent}% vs last week
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Requests</p>
                    <p className="text-2xl font-bold">
                      {weeklyData.metrics.current_week.total_requests}
                    </p>
                    <p className={`text-sm ${getChangeColor(weeklyData.metrics.changes.requests_percent)}`}>
                      {weeklyData.metrics.changes.requests_percent > 0 ? '+' : ''}
                      {weeklyData.metrics.changes.requests_percent}% vs last week
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm mb-1">Avg Latency</p>
                    <p className="text-2xl font-bold">
                      {weeklyData.metrics.current_week.avg_latency_ms}ms
                    </p>
                    <p className="text-sm text-gray-400">
                      {weeklyData.metrics.current_week.error_count} errors
                    </p>
                  </div>
                </div>

                <div className="border-t border-gray-800 pt-6">
                  <h3 className="text-lg font-semibold mb-3 text-[#D4AF37]">AI Analysis</h3>
                  <p className="text-gray-300 mb-4">{weeklyData.ai_insights.summary}</p>

                  <div className="bg-green-900/20 border border-green-700 rounded p-4 mb-4">
                    <p className="text-green-400 font-semibold mb-1">Highlight</p>
                    <p className="text-gray-300">{weeklyData.ai_insights.highlight}</p>
                  </div>

                  <h4 className="font-semibold mb-3">Recommendations</h4>
                  <div className="space-y-3">
                    {weeklyData.ai_insights.recommendations.map((rec, idx) => (
                      <div key={idx} className="border border-gray-800 rounded p-4">
                        <div className="flex items-start justify-between mb-2">
                          <h5 className="font-semibold">{rec.title}</h5>
                          <span className={`text-xs uppercase ${getImpactColor(rec.impact)}`}>
                            {rec.impact} impact
                          </span>
                        </div>
                        <p className="text-gray-400 text-sm">{rec.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Cost Optimization */}
        {costData && (
          <Card>
            <CardTitle>Cost Optimization Opportunities</CardTitle>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div>
                  <p className="text-gray-400 text-sm mb-1">Current Monthly Cost</p>
                  <p className="text-2xl font-bold text-[#D4AF37]">
                    ${costData.current_monthly_cost.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm mb-1">Potential Savings</p>
                  <p className="text-2xl font-bold text-green-400">
                    ${costData.potential_monthly_savings.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-gray-400 text-sm mb-1">Total Requests</p>
                  <p className="text-2xl font-bold">{costData.total_requests}</p>
                </div>
              </div>

              <div className="mb-6">
                <h4 className="font-semibold mb-3">Top Cost Drivers</h4>
                <div className="space-y-2">
                  {costData.top_cost_drivers.map((driver, idx) => (
                    <div key={idx} className="flex items-center justify-between bg-gray-900 p-3 rounded">
                      <div className="flex-1">
                        <p className="font-medium">{driver.event_type}</p>
                        <p className="text-sm text-gray-400">{driver.count} requests</p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-[#D4AF37]">${driver.cost_dollars.toFixed(2)}</p>
                        <p className="text-sm text-gray-400">{driver.percentage}%</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-semibold mb-3">Optimization Suggestions</h4>
                <div className="space-y-3">
                  {costData.optimizations.map((opt, idx) => (
                    <div key={idx} className="border border-gray-800 rounded p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <h5 className="font-semibold">{opt.title}</h5>
                          <p className="text-gray-400 text-sm mt-1">{opt.description}</p>
                        </div>
                        <div className="text-right ml-4">
                          <p className="text-green-400 font-semibold">
                            ${opt.potential_savings_dollars.toFixed(2)}/mo
                          </p>
                          <span className={`text-xs uppercase ${getImpactColor(opt.impact)}`}>
                            {opt.impact} impact
                          </span>
                        </div>
                      </div>
                      <span className="text-xs bg-gray-800 px-2 py-1 rounded">{opt.category}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
