'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { ProgressBar } from '@/components/ProgressBar';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

export default function DashboardPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userData, setUserData] = useState({
    plan: 'free',
    display_name: 'Free',
    price: 0,
    limits: {
      max_minutes: 100,
      max_assistants: 1,
      max_voice_clones: 0,
    },
    usage: {
      minutes_used: 0,
      bonus_minutes: 0,
      conversations_count: 0,
      voice_clones_count: 0,
    },
    billing: {
      period_end: '',
      days_remaining: 0,
    },
  });
  const [analytics, setAnalytics] = useState<{
    totals: {
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
      cost_cents: number;
      cost_dollars: number;
      total_requests: number;
    };
    averages: {
      tokens_per_request: number;
      cost_per_request_cents: number;
      requests_per_day: number;
    };
  } | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!user?.id) return;

      try {
        setLoading(true);
        setError(null);

        const [subResponse, usageResponse, limitsResponse, analyticsResponse] = await Promise.all([
          api.getSubscription(user.id),
          api.getUsage(user.id),
          api.getFeatureLimits(user.id),
          api.getUsageAnalytics(user.id, 30),
        ]);

        // Calculate days remaining
        const periodEnd = subResponse.subscription?.current_period_end
          ? new Date(subResponse.subscription.current_period_end)
          : new Date();
        const now = new Date();
        const daysRemaining = Math.max(0, Math.ceil((periodEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));

        setUserData({
          plan: limitsResponse.plan || 'free',
          display_name: limitsResponse.display_name || 'Free',
          price: subResponse.subscription?.price_cents ? subResponse.subscription.price_cents / 100 : 0,
          limits: {
            max_minutes: limitsResponse.limits.max_minutes || 100,
            max_assistants: limitsResponse.limits.max_assistants || 1,
            max_voice_clones: limitsResponse.limits.max_voice_clones || 0,
          },
          usage: {
            minutes_used: usageResponse.usage.minutes_used || 0,
            bonus_minutes: usageResponse.usage.bonus_minutes || 0,
            conversations_count: usageResponse.usage.conversations_count || 0,
            voice_clones_count: usageResponse.usage.voice_clones_count || 0,
          },
          billing: {
            period_end: subResponse.subscription?.current_period_end
              ? new Date(subResponse.subscription.current_period_end).toLocaleDateString()
              : 'N/A',
            days_remaining: daysRemaining,
          },
        });

        // Set analytics data
        setAnalytics({
          totals: analyticsResponse.totals,
          averages: analyticsResponse.averages,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [user?.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
        {error}
      </div>
    );
  }

  const { plan, display_name, price, limits, usage, billing } = userData;
  const totalMinutes = limits.max_minutes + usage.bonus_minutes;
  const usagePercent = totalMinutes > 0 ? (usage.minutes_used / totalMinutes) * 100 : 0;

  return (
    <div className="space-y-8">
      {/* Welcome Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">Dashboard</h1>
        <p className="text-gray-400 mt-1">
          Welcome back! Here's your usage overview.
        </p>
      </div>

      {/* Current Plan Card */}
      <Card glow>
        <CardContent>
          <div className="flex justify-between items-start">
            <div>
              <div className="text-sm text-gray-400 mb-1">Current Plan</div>
              <div className="text-3xl font-bold text-gold">{display_name}</div>
              <div className="text-lg text-gray-300 mt-1">${price}/month</div>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-400">Billing Period Ends</div>
              <div className="text-lg text-white">{billing.period_end}</div>
              <div className="text-sm text-honey-400">{billing.days_remaining} days left</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Usage Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Minutes Used */}
        <Card className="md:col-span-2">
          <CardTitle>Minutes Used</CardTitle>
          <CardContent>
            <div className="mt-4">
              <ProgressBar
                current={usage.minutes_used}
                max={totalMinutes}
                size="lg"
              />
              <div className="flex justify-between mt-2 text-sm">
                <span className="text-gray-400">
                  {usage.bonus_minutes > 0 && (
                    <span className="text-green-500">+{usage.bonus_minutes} bonus</span>
                  )}
                </span>
                <span className={`font-medium ${
                  usagePercent >= 80 ? 'text-yellow-500' :
                  usagePercent >= 100 ? 'text-red-500' :
                  'text-green-500'
                }`}>
                  {(totalMinutes - usage.minutes_used).toLocaleString()} minutes remaining
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <Card>
          <CardTitle>Activity</CardTitle>
          <CardContent>
            <div className="space-y-4 mt-4">
              <div>
                <div className="text-sm text-gray-400">Conversations</div>
                <div className="text-2xl font-bold text-gold">
                  {usage.conversations_count}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Voice Clones</div>
                <div className="text-2xl font-bold text-gold">
                  {usage.voice_clones_count}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Token Usage & Costs (Last 30 Days) */}
      {analytics && (
        <Card glow>
          <CardTitle>Token Usage & Running Costs (Last 30 Days)</CardTitle>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
              <div className="text-center p-4 bg-oled-gray rounded-lg">
                <div className="text-sm text-gray-400">Total Tokens</div>
                <div className="text-2xl font-bold text-gold">
                  {analytics.totals.total_tokens.toLocaleString()}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {analytics.averages.tokens_per_request.toLocaleString()} avg/request
                </div>
              </div>
              <div className="text-center p-4 bg-oled-gray rounded-lg">
                <div className="text-sm text-gray-400">Input Tokens</div>
                <div className="text-2xl font-bold text-blue-400">
                  {analytics.totals.input_tokens.toLocaleString()}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {((analytics.totals.input_tokens / analytics.totals.total_tokens) * 100).toFixed(1)}% of total
                </div>
              </div>
              <div className="text-center p-4 bg-oled-gray rounded-lg">
                <div className="text-sm text-gray-400">Output Tokens</div>
                <div className="text-2xl font-bold text-purple-400">
                  {analytics.totals.output_tokens.toLocaleString()}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {((analytics.totals.output_tokens / analytics.totals.total_tokens) * 100).toFixed(1)}% of total
                </div>
              </div>
              <div className="text-center p-4 bg-gradient-to-br from-green-900/30 to-green-800/20 rounded-lg border border-green-500/20">
                <div className="text-sm text-gray-400">Total Cost</div>
                <div className="text-2xl font-bold text-green-400">
                  ${analytics.totals.cost_dollars.toFixed(4)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  ${(analytics.averages.cost_per_request_cents / 100).toFixed(4)} avg/request
                </div>
              </div>
            </div>
            <div className="mt-4 p-3 bg-honey-900/10 border border-honey-500/20 rounded-lg">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">API Requests (30 days)</span>
                <span className="text-gold font-semibold">{analytics.totals.total_requests} requests</span>
              </div>
              <div className="flex items-center justify-between text-sm mt-2">
                <span className="text-gray-400">Average per day</span>
                <span className="text-gold font-semibold">{analytics.averages.requests_per_day.toFixed(1)} requests/day</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Plan Features */}
      <Card>
        <CardTitle>Plan Features</CardTitle>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
            <div className="text-center p-4 bg-oled-gray rounded-lg">
              <div className="text-2xl font-bold text-gold">
                {limits.max_minutes.toLocaleString()}
              </div>
              <div className="text-sm text-gray-400">Minutes/month</div>
            </div>
            <div className="text-center p-4 bg-oled-gray rounded-lg">
              <div className="text-2xl font-bold text-gold">
                {limits.max_assistants === -1 ? '∞' : limits.max_assistants}
              </div>
              <div className="text-sm text-gray-400">Assistants</div>
            </div>
            <div className="text-center p-4 bg-oled-gray rounded-lg">
              <div className="text-2xl font-bold text-gold">
                {limits.max_voice_clones === -1 ? '∞' : limits.max_voice_clones}
              </div>
              <div className="text-sm text-gray-400">Voice Clones</div>
            </div>
            <div className="text-center p-4 bg-oled-gray rounded-lg">
              <div className="text-2xl font-bold text-green-500">✓</div>
              <div className="text-sm text-gray-400">Priority Support</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="flex gap-4">
        <HoneycombButton onClick={() => window.location.href = '/dashboard/subscription'}>
          Manage Subscription
        </HoneycombButton>
        <HoneycombButton variant="outline" onClick={() => window.location.href = '/dashboard/redeem'}>
          Redeem Code
        </HoneycombButton>
      </div>
    </div>
  );
}
