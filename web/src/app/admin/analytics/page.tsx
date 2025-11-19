'use client';

import { Card, CardTitle, CardContent } from '@/components/Card';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

// Mock data for charts
const usageData = [
  { date: 'Jan', minutes: 45000, conversations: 2100 },
  { date: 'Feb', minutes: 52000, conversations: 2400 },
  { date: 'Mar', minutes: 48000, conversations: 2200 },
  { date: 'Apr', minutes: 61000, conversations: 2800 },
  { date: 'May', minutes: 75000, conversations: 3400 },
  { date: 'Jun', minutes: 89000, conversations: 4100 },
];

const revenueData = [
  { month: 'Jan', revenue: 45600, users: 890 },
  { month: 'Feb', revenue: 52300, users: 945 },
  { month: 'Mar', revenue: 58100, users: 1020 },
  { month: 'Apr', revenue: 67400, users: 1105 },
  { month: 'May', revenue: 78200, users: 1180 },
  { month: 'Jun', revenue: 89200, users: 1247 },
];

const planDistribution = [
  { name: 'Free', value: 355, color: '#6B7280' },
  { name: 'Starter', value: 612, color: '#FBBF24' },
  { name: 'Pro', value: 245, color: '#D4AF37' },
  { name: 'Enterprise', value: 35, color: '#10B981' },
];

const topUsers = [
  { id: 'user-001', minutes: 8450, plan: 'pro' },
  { id: 'user-002', minutes: 7890, plan: 'pro' },
  { id: 'user-003', minutes: 6234, plan: 'enterprise' },
  { id: 'user-004', minutes: 5678, plan: 'pro' },
  { id: 'user-005', minutes: 4321, plan: 'starter' },
];

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">Analytics</h1>
        <p className="text-gray-400 mt-1">Usage metrics and revenue insights</p>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Usage Trend */}
        <Card>
          <CardTitle>Usage Trend</CardTitle>
          <CardContent>
            <div className="h-64 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={usageData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="date" stroke="#666" />
                  <YAxis stroke="#666" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e1e1e',
                      border: '1px solid #D4AF37',
                      borderRadius: '8px',
                    }}
                    labelStyle={{ color: '#D4AF37' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="minutes"
                    stroke="#D4AF37"
                    strokeWidth={3}
                    dot={{ fill: '#D4AF37', strokeWidth: 2 }}
                    activeDot={{ r: 8, fill: '#FFD700' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="text-center mt-2 text-sm text-gray-400">
              Total minutes used per month
            </div>
          </CardContent>
        </Card>

        {/* Revenue Growth */}
        <Card>
          <CardTitle>Revenue Growth</CardTitle>
          <CardContent>
            <div className="h-64 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={revenueData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="month" stroke="#666" />
                  <YAxis stroke="#666" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e1e1e',
                      border: '1px solid #D4AF37',
                      borderRadius: '8px',
                    }}
                    formatter={(value: number) => [`$${(value / 100).toFixed(0)}`, 'Revenue']}
                  />
                  <Bar
                    dataKey="revenue"
                    fill="#D4AF37"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="text-center mt-2 text-sm text-gray-400">
              Monthly recurring revenue
            </div>
          </CardContent>
        </Card>

        {/* Plan Distribution */}
        <Card>
          <CardTitle>Plan Distribution</CardTitle>
          <CardContent>
            <div className="h-64 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={planDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {planDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e1e1e',
                      border: '1px solid #D4AF37',
                      borderRadius: '8px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-4 mt-2">
              {planDistribution.map((item) => (
                <div key={item.name} className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-xs text-gray-400">
                    {item.name} ({item.value})
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Users */}
        <Card>
          <CardTitle>Top Users by Usage</CardTitle>
          <CardContent>
            <div className="mt-4 space-y-3">
              {topUsers.map((user, index) => (
                <div
                  key={user.id}
                  className="flex items-center justify-between py-2 border-b border-gold/10 last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-gold font-bold w-6">{index + 1}</span>
                    <span className="font-mono text-sm text-gray-300">{user.id}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        user.plan === 'enterprise'
                          ? 'bg-green-500/20 text-green-400'
                          : user.plan === 'pro'
                          ? 'bg-gold/20 text-gold'
                          : 'bg-honey-400/20 text-honey-400'
                      }`}
                    >
                      {user.plan}
                    </span>
                  </div>
                  <span className="text-gold font-semibold">
                    {user.minutes.toLocaleString()} min
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Avg Usage/User</div>
            <div className="text-2xl font-bold text-gold">366 min</div>
            <div className="text-xs text-green-500 mt-1">+12% vs last month</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Conversion Rate</div>
            <div className="text-2xl font-bold text-gold">23%</div>
            <div className="text-xs text-green-500 mt-1">+3% vs last month</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Churn Rate</div>
            <div className="text-2xl font-bold text-gold">2.1%</div>
            <div className="text-xs text-green-500 mt-1">-0.5% vs last month</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">ARPU</div>
            <div className="text-2xl font-bold text-gold">$71.52</div>
            <div className="text-xs text-green-500 mt-1">+8% vs last month</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
