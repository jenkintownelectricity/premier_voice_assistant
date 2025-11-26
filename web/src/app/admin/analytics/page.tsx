'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { ProgressBar } from '@/components/ProgressBar';
import { useAdmin } from '../layout';
import { adminApi } from '@/lib/api';

interface DiscountCode {
  id: string;
  code: string;
  discount_type: string;
  discount_value: number;
  current_uses: number;
  max_uses: number | null;
  is_active: boolean;
}

export default function AnalyticsPage() {
  const { adminKey } = useAdmin();
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
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load analytics');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [adminKey]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading analytics...</div>
      </div>
    );
  }

  // Calculate analytics from available data
  const totalRedemptions = codes.reduce((sum, c) => sum + c.current_uses, 0);
  const activeCodes = codes.filter(c => c.is_active).length;
  const minutesCodes = codes.filter(c => c.discount_type === 'minutes');
  const totalMinutesGiven = minutesCodes.reduce((sum, c) => sum + (c.current_uses * c.discount_value), 0);

  // Top performing codes
  const topCodes = [...codes].sort((a, b) => b.current_uses - a.current_uses).slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">Analytics</h1>
        <p className="text-gray-400 mt-1">Usage metrics and insights</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      {/* Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400">Total Redemptions</div>
            <div className="text-2xl font-bold text-gold">{totalRedemptions}</div>
            <div className="text-xs text-gray-500 mt-1">All codes</div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400">Active Codes</div>
            <div className="text-2xl font-bold text-gold">{activeCodes}</div>
            <div className="text-xs text-gray-500 mt-1">Currently valid</div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400">Minutes Given</div>
            <div className="text-2xl font-bold text-gold">{totalMinutesGiven.toLocaleString()}</div>
            <div className="text-xs text-gray-500 mt-1">Via codes</div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent>
            <div className="text-sm text-gray-400">Total Codes</div>
            <div className="text-2xl font-bold text-gold">{codes.length}</div>
            <div className="text-xs text-gray-500 mt-1">Created</div>
          </CardContent>
        </Card>
      </div>

      {/* Top Performing Codes */}
      <Card>
        <CardTitle>Top Performing Codes</CardTitle>
        <CardContent>
          <div className="mt-4 space-y-3">
            {topCodes.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No code usage data yet. Create and share codes to see analytics.
              </div>
            ) : (
              topCodes.map((code, index) => (
                <div
                  key={code.id}
                  className="flex items-center justify-between py-2 border-b border-gold/10 last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-gold font-bold w-6">{index + 1}</span>
                    <div>
                      <span className="font-mono text-sm text-white">{code.code}</span>
                      <div className="text-xs text-gray-500">
                        {code.discount_type === 'minutes' ? `+${code.discount_value} min` :
                         code.discount_type === 'percentage' ? `${code.discount_value}% off` :
                         `$${code.discount_value} off`}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-gold font-semibold">
                      {code.current_uses} uses
                    </div>
                    {code.max_uses && (
                      <div className="text-xs text-gray-500">
                        of {code.max_uses} max
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Code Type Distribution */}
      <Card>
        <CardTitle>Code Type Distribution</CardTitle>
        <CardContent>
          <div className="space-y-4 mt-4">
            {['minutes', 'percentage', 'fixed', 'upgrade'].map((type) => {
              const typeCodes = codes.filter(c => c.discount_type === type);
              const typeUses = typeCodes.reduce((sum, c) => sum + c.current_uses, 0);
              return (
                <div key={type}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-400 capitalize">{type}</span>
                    <span className="text-gold">{typeCodes.length} codes ({typeUses} uses)</span>
                  </div>
                  <ProgressBar
                    current={typeCodes.length}
                    max={Math.max(codes.length, 1)}
                    showPercentage={false}
                  />
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Info Box */}
      <Card>
        <CardContent>
          <div className="flex items-start gap-3">
            <div className="text-2xl">📊</div>
            <div>
              <h3 className="text-gold font-semibold">More Analytics Coming Soon</h3>
              <p className="text-gray-400 text-sm mt-1">
                User growth charts, revenue tracking, and detailed usage metrics will be available
                as more data is collected. Check back soon for comprehensive analytics.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
