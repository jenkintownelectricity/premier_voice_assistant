'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { ProgressBar } from '@/components/ProgressBar';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

interface UsageData {
  minutes_used: number;
  bonus_minutes: number;
  conversations_count: number;
  voice_clones_count: number;
  assistants_count: number;
}

interface LimitsData {
  plan: string;
  display_name: string;
  limits: {
    max_minutes: number;
    max_assistants: number;
    max_voice_clones: number;
    custom_voices: boolean;
    api_access: boolean;
    priority_support: boolean;
  };
}

interface CallData {
  id: string;
  assistant_name: string;
  started_at: string;
  duration_seconds: number;
  summary: string | null;
}

export default function UsagePage() {
  const { user } = useAuth();
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [limits, setLimits] = useState<LimitsData | null>(null);
  const [recentCalls, setRecentCalls] = useState<CallData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!user?.id) return;

      try {
        setError(null);
        const [usageRes, limitsRes, callsRes] = await Promise.all([
          api.getUsage(user.id),
          api.getFeatureLimits(user.id),
          api.getCalls(user.id, 5, 0),
        ]);

        setUsage({
          minutes_used: usageRes.usage.minutes_used,
          bonus_minutes: usageRes.usage.bonus_minutes || 0,
          conversations_count: usageRes.usage.conversations_count,
          voice_clones_count: usageRes.usage.voice_clones_count,
          assistants_count: usageRes.usage.assistants_count,
        });
        setLimits(limitsRes);
        setRecentCalls(callsRes.calls);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load usage data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [user?.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading usage data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gold">Usage Dashboard</h1>
          <p className="text-gray-400 mt-1">Track your voice assistant usage</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      </div>
    );
  }

  const totalMinutes = (limits?.limits.max_minutes || 100) + (usage?.bonus_minutes || 0);
  const usedMinutes = usage?.minutes_used || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">Usage Dashboard</h1>
        <p className="text-gray-400 mt-1">Track your voice assistant usage</p>
      </div>

      {/* Main Usage Card */}
      <Card glow>
        <CardTitle>Current Billing Period</CardTitle>
        <CardContent>
          <div className="mt-4">
            <ProgressBar
              current={usedMinutes}
              max={totalMinutes}
              label="Minutes Used"
              size="lg"
            />
            <div className="grid grid-cols-3 gap-4 mt-6">
              <div className="text-center">
                <div className="text-sm text-gray-400">Used</div>
                <div className="text-2xl font-bold text-gold">
                  {usedMinutes.toLocaleString()}
                </div>
              </div>
              <div className="text-center">
                <div className="text-sm text-gray-400">Bonus</div>
                <div className="text-2xl font-bold text-green-500">
                  +{usage?.bonus_minutes || 0}
                </div>
              </div>
              <div className="text-center">
                <div className="text-sm text-gray-400">Remaining</div>
                <div className="text-2xl font-bold text-gold">
                  {(totalMinutes - usedMinutes).toLocaleString()}
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Conversations</div>
            <div className="text-2xl font-bold text-gold">{usage?.conversations_count || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Assistants</div>
            <div className="text-2xl font-bold text-gold">{usage?.assistants_count || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Voice Clones</div>
            <div className="text-2xl font-bold text-gold">{usage?.voice_clones_count || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Plan</div>
            <div className="text-2xl font-bold text-gold">{limits?.display_name || 'Free'}</div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Sessions */}
      <Card>
        <CardTitle>Recent Sessions</CardTitle>
        <CardContent>
          <div className="mt-4 space-y-3">
            {recentCalls.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No calls yet. Start using your voice assistants to see activity here.
              </div>
            ) : (
              recentCalls.map((call) => (
                <div
                  key={call.id}
                  className="flex items-center justify-between py-3 border-b border-gold/10 last:border-0"
                >
                  <div>
                    <div className="text-sm text-white">{call.summary || call.assistant_name}</div>
                    <div className="text-xs text-gray-500">
                      {new Date(call.started_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="text-gold font-semibold">
                    {Math.ceil(call.duration_seconds / 60)} min
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Usage Tips */}
      <Card>
        <CardTitle>Tips to Optimize Usage</CardTitle>
        <CardContent>
          <ul className="mt-4 space-y-2 text-sm text-gray-300">
            <li className="flex items-start gap-2">
              <span className="text-gold">•</span>
              Keep conversations focused to reduce minutes used
            </li>
            <li className="flex items-start gap-2">
              <span className="text-gold">•</span>
              Use the web interface for quick tasks instead of voice
            </li>
            <li className="flex items-start gap-2">
              <span className="text-gold">•</span>
              Redeem discount codes for bonus minutes
            </li>
            <li className="flex items-start gap-2">
              <span className="text-gold">•</span>
              Upgrade your plan for better value per minute
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
