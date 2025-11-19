'use client';

import { Card, CardTitle, CardContent } from '@/components/Card';
import { ProgressBar } from '@/components/ProgressBar';
import { HoneycombButton } from '@/components/HoneycombButton';

// Mock user data - would come from API
const mockUserData = {
  plan: 'pro',
  display_name: 'Pro',
  price: 299,
  limits: {
    max_minutes: 10000,
    max_assistants: -1, // unlimited
    max_voice_clones: -1, // unlimited
  },
  usage: {
    minutes_used: 3245,
    bonus_minutes: 500,
    conversations_count: 156,
    voice_clones_count: 3,
  },
  billing: {
    period_end: '2024-02-15',
    days_remaining: 12,
  },
};

export default function DashboardPage() {
  const { plan, display_name, price, limits, usage, billing } = mockUserData;
  const totalMinutes = limits.max_minutes + usage.bonus_minutes;
  const usagePercent = (usage.minutes_used / totalMinutes) * 100;

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
