'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { ProgressBar } from '@/components/ProgressBar';
import { HoneycombButton } from '@/components/HoneycombButton';

// Mock data - replace with API calls
const mockStats = {
  totalUsers: 1247,
  activeSubscriptions: 892,
  monthlyRevenue: 89200,
  minutesUsed: 456789,
};

const mockRecentActivity = [
  { id: 1, type: 'signup', user: 'user-abc123', plan: 'starter', time: '5 min ago' },
  { id: 2, type: 'upgrade', user: 'user-def456', plan: 'pro', time: '23 min ago' },
  { id: 3, type: 'redemption', user: 'user-ghi789', code: 'WELCOME2024', time: '1 hr ago' },
  { id: 4, type: 'signup', user: 'user-jkl012', plan: 'free', time: '2 hrs ago' },
];

export default function AdminDashboard() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Simulate loading
    setTimeout(() => setIsLoading(false), 500);
  }, []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">Admin Dashboard</h1>
        <p className="text-gray-400 mt-1">Overview of your Premier Voice Assistant</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400 mb-1">Total Users</div>
            <div className="text-3xl font-bold text-gold">{mockStats.totalUsers.toLocaleString()}</div>
            <div className="text-xs text-green-500 mt-1">+12% from last month</div>
          </CardContent>
        </Card>

        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400 mb-1">Active Subscriptions</div>
            <div className="text-3xl font-bold text-gold">{mockStats.activeSubscriptions.toLocaleString()}</div>
            <div className="text-xs text-green-500 mt-1">+8% from last month</div>
          </CardContent>
        </Card>

        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400 mb-1">Monthly Revenue</div>
            <div className="text-3xl font-bold text-gold">${(mockStats.monthlyRevenue / 100).toLocaleString()}</div>
            <div className="text-xs text-green-500 mt-1">+15% from last month</div>
          </CardContent>
        </Card>

        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400 mb-1">Minutes Used</div>
            <div className="text-3xl font-bold text-gold">{mockStats.minutesUsed.toLocaleString()}</div>
            <div className="text-xs text-honey-400 mt-1">+23% from last month</div>
          </CardContent>
        </Card>
      </div>

      {/* Plan Distribution */}
      <Card>
        <CardTitle>Plan Distribution</CardTitle>
        <CardContent>
          <div className="space-y-4 mt-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">Free</span>
                <span className="text-gold">355 users (28%)</span>
              </div>
              <ProgressBar current={355} max={1247} showPercentage={false} />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">Starter ($99/mo)</span>
                <span className="text-gold">612 users (49%)</span>
              </div>
              <ProgressBar current={612} max={1247} showPercentage={false} />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">Pro ($299/mo)</span>
                <span className="text-gold">245 users (20%)</span>
              </div>
              <ProgressBar current={245} max={1247} showPercentage={false} />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">Enterprise</span>
                <span className="text-gold">35 users (3%)</span>
              </div>
              <ProgressBar current={35} max={1247} showPercentage={false} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <Card>
        <CardTitle>Recent Activity</CardTitle>
        <CardContent>
          <div className="mt-4 space-y-3">
            {mockRecentActivity.map((activity) => (
              <div
                key={activity.id}
                className="flex items-center justify-between py-3 border-b border-gold/10 last:border-0"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      activity.type === 'upgrade'
                        ? 'bg-green-500'
                        : activity.type === 'redemption'
                        ? 'bg-honey-400'
                        : 'bg-gold'
                    }`}
                  />
                  <div>
                    <div className="text-sm text-white">
                      {activity.type === 'signup' && `New signup: ${activity.plan} plan`}
                      {activity.type === 'upgrade' && `Upgraded to ${activity.plan}`}
                      {activity.type === 'redemption' && `Code redeemed: ${activity.code}`}
                    </div>
                    <div className="text-xs text-gray-500">{activity.user}</div>
                  </div>
                </div>
                <div className="text-xs text-gray-500">{activity.time}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="flex gap-4">
        <HoneycombButton onClick={() => window.location.href = '/admin/users'}>
          Manage Users
        </HoneycombButton>
        <HoneycombButton variant="outline" onClick={() => window.location.href = '/admin/codes'}>
          Create Code
        </HoneycombButton>
      </div>
    </div>
  );
}
