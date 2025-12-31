'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { ProgressBar } from '@/components/ProgressBar';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAdmin } from '@/lib/admin-context';
import { adminApi } from '@/lib/api';

interface AdminStats {
  totalUsers: number;
  activeSubscriptions: number;
  totalMinutesUsed: number;
  activeCodes: number;
}

interface DiscountCode {
  id: string;
  code: string;
  discount_type: string;
  discount_value: number;
  current_uses: number;
  is_active: boolean;
}

export default function AdminDashboard() {
  const { adminKey } = useAdmin();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [codes, setCodes] = useState<DiscountCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!adminKey) {
        setLoading(false);
        return;
      }

      try {
        setError(null);
        const codesRes = await adminApi.getCodes(adminKey, false);
        setCodes(codesRes.codes || []);

        // Calculate stats from codes data
        const activeCodes = codesRes.codes?.filter(c => c.is_active).length || 0;
        const totalRedemptions = codesRes.codes?.reduce((sum, c) => sum + c.current_uses, 0) || 0;

        setStats({
          totalUsers: 0, // Will be populated when backend supports user list
          activeSubscriptions: 0,
          totalMinutesUsed: totalRedemptions,
          activeCodes,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load admin data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [adminKey]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading admin dashboard...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">Admin Dashboard</h1>
        <p className="text-gray-400 mt-1">Overview of your Premier Voice Assistant</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400 mb-1">Active Codes</div>
            <div className="text-3xl font-bold text-gold">{stats?.activeCodes || 0}</div>
            <div className="text-xs text-gray-500 mt-1">Promotional codes</div>
          </CardContent>
        </Card>

        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400 mb-1">Total Redemptions</div>
            <div className="text-3xl font-bold text-gold">{stats?.totalMinutesUsed || 0}</div>
            <div className="text-xs text-gray-500 mt-1">Code uses</div>
          </CardContent>
        </Card>

        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400 mb-1">Total Codes</div>
            <div className="text-3xl font-bold text-gold">{codes.length}</div>
            <div className="text-xs text-gray-500 mt-1">All time</div>
          </CardContent>
        </Card>

        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400 mb-1">Status</div>
            <div className="text-3xl font-bold text-green-500">Online</div>
            <div className="text-xs text-gray-500 mt-1">System healthy</div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Codes */}
      <Card>
        <CardTitle>Recent Discount Codes</CardTitle>
        <CardContent>
          <div className="mt-4 space-y-3">
            {codes.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No discount codes created yet. Create your first code to get started.
              </div>
            ) : (
              codes.slice(0, 5).map((code) => (
                <div
                  key={code.id}
                  className="flex items-center justify-between py-3 border-b border-gold/10 last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-2 h-2 rounded-full ${code.is_active ? 'bg-green-500' : 'bg-gray-500'}`}
                    />
                    <div>
                      <div className="text-sm text-white font-mono">{code.code}</div>
                      <div className="text-xs text-gray-500">
                        {code.discount_type === 'minutes' ? `+${code.discount_value} min` :
                         code.discount_type === 'percentage' ? `${code.discount_value}% off` :
                         `$${code.discount_value} off`}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500">{code.current_uses} uses</div>
                </div>
              ))
            )}
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
