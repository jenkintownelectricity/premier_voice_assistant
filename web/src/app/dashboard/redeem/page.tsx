'use client';

import { useState } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Input } from '@/components/Input';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

export default function RedeemPage() {
  const { user } = useAuth();
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const handleRedeem = async () => {
    if (!code.trim() || !user?.id) return;

    setLoading(true);
    setResult(null);

    try {
      const response = await api.redeemCode(user.id, code.trim());
      setResult({
        success: response.success,
        message: response.message,
      });
      if (response.success) {
        setCode('');
      }
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : 'Failed to redeem code',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-xl mx-auto">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gold">Redeem Code</h1>
        <p className="text-gray-400 mt-1">
          Enter your promotional code to claim bonus minutes or discounts
        </p>
      </div>

      {/* Redemption Card */}
      <Card glow>
        <CardContent>
          <div className="space-y-4">
            <Input
              label="Discount Code"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="Enter your code..."
              className="text-center text-xl tracking-widest font-mono"
            />

            <HoneycombButton
              className="w-full"
              onClick={handleRedeem}
              disabled={loading || !code.trim()}
            >
              {loading ? 'Redeeming...' : 'Redeem Code'}
            </HoneycombButton>
          </div>

          {/* Result Message */}
          {result && (
            <div
              className={`mt-4 p-4 rounded-lg ${
                result.success
                  ? 'bg-green-500/10 border border-green-500/30'
                  : 'bg-red-500/10 border border-red-500/30'
              }`}
            >
              <div
                className={`text-sm ${
                  result.success ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {result.success ? '✓ ' : '✗ '}
                {result.message}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info */}
      <Card>
        <CardTitle>Where to Find Codes</CardTitle>
        <CardContent>
          <ul className="mt-4 space-y-3 text-sm text-gray-300">
            <li className="flex items-start gap-2">
              <span className="text-gold">•</span>
              <span>
                <strong className="text-gold">Welcome Email</strong> - New users receive a welcome code
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-gold">•</span>
              <span>
                <strong className="text-gold">Partner Promotions</strong> - Check our partner websites
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-gold">•</span>
              <span>
                <strong className="text-gold">Social Media</strong> - Follow us for exclusive codes
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-gold">•</span>
              <span>
                <strong className="text-gold">Customer Support</strong> - May receive compensation codes
              </span>
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* Recent Redemptions */}
      <Card>
        <CardTitle>Your Redemption History</CardTitle>
        <CardContent>
          <div className="mt-4 space-y-3">
            <div className="flex justify-between py-2 border-b border-gold/10">
              <div>
                <div className="text-sm text-white">WELCOME2024</div>
                <div className="text-xs text-gray-500">Jan 15, 2024</div>
              </div>
              <div className="text-green-500 text-sm">+100 min</div>
            </div>
            <div className="flex justify-between py-2">
              <div>
                <div className="text-sm text-white">REFER50</div>
                <div className="text-xs text-gray-500">Dec 20, 2023</div>
              </div>
              <div className="text-green-500 text-sm">+50 min</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
