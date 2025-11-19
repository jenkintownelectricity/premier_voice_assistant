'use client';

import { Card, CardTitle, CardContent } from '@/components/Card';
import { ProgressBar } from '@/components/ProgressBar';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

// Mock usage history
const usageHistory = [
  { date: 'Week 1', minutes: 420 },
  { date: 'Week 2', minutes: 680 },
  { date: 'Week 3', minutes: 890 },
  { date: 'Week 4', minutes: 1255 },
];

const recentSessions = [
  { id: 1, date: '2024-02-03', duration: 12, topic: 'Customer inquiry - pricing' },
  { id: 2, date: '2024-02-02', duration: 8, topic: 'Appointment scheduling' },
  { id: 3, date: '2024-02-02', duration: 23, topic: 'Technical support' },
  { id: 4, date: '2024-02-01', duration: 5, topic: 'Quick question' },
  { id: 5, date: '2024-02-01', duration: 15, topic: 'Service consultation' },
];

export default function UsagePage() {
  const totalMinutes = 10500; // including bonus
  const usedMinutes = 3245;
  const bonusMinutes = 500;

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
                  +{bonusMinutes}
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

      {/* Usage Chart */}
      <Card>
        <CardTitle>Usage Trend</CardTitle>
        <CardContent>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={usageHistory}>
                <defs>
                  <linearGradient id="goldGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#D4AF37" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#D4AF37" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="date" stroke="#666" />
                <YAxis stroke="#666" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e1e1e',
                    border: '1px solid #D4AF37',
                    borderRadius: '8px',
                  }}
                  formatter={(value: number) => [`${value} min`, 'Usage']}
                />
                <Area
                  type="monotone"
                  dataKey="minutes"
                  stroke="#D4AF37"
                  strokeWidth={2}
                  fill="url(#goldGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Recent Sessions */}
      <Card>
        <CardTitle>Recent Sessions</CardTitle>
        <CardContent>
          <div className="mt-4 space-y-3">
            {recentSessions.map((session) => (
              <div
                key={session.id}
                className="flex items-center justify-between py-3 border-b border-gold/10 last:border-0"
              >
                <div>
                  <div className="text-sm text-white">{session.topic}</div>
                  <div className="text-xs text-gray-500">{session.date}</div>
                </div>
                <div className="text-gold font-semibold">
                  {session.duration} min
                </div>
              </div>
            ))}
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
