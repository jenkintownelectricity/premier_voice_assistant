'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { ProgressBar } from '@/components/ProgressBar';
import { useAuth } from '@/lib/auth-context';
import { referralApi } from '@/lib/api';

interface ReferralCode {
  id: string;
  code: string;
  referrer_reward_value: number;
  referee_reward_value: number;
  total_referrals: number;
  successful_referrals: number;
  total_rewards_earned: number;
}

interface Referral {
  id: string;
  referee_id: string;
  status: string;
  signed_up_at?: string;
  converted_at?: string;
}

export default function ReferralsPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [referralCode, setReferralCode] = useState<ReferralCode | null>(null);
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [shareUrl, setShareUrl] = useState('');
  const [copied, setCopied] = useState(false);
  const [redeemCode, setRedeemCode] = useState('');
  const [redeemMessage, setRedeemMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    const fetchReferral = async () => {
      if (!user?.id) return;
      try {
        const response = await referralApi.getReferralInfo(user.id);
        setReferralCode(response.referral_code);
        setReferrals(response.referrals);
        setShareUrl(response.share_url);
      } catch (error) {
        console.error('Failed to load referral info:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchReferral();
  }, [user?.id]);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const handleRedeem = async () => {
    if (!user?.id || !redeemCode) return;
    try {
      const response = await referralApi.redeemReferral(user.id, redeemCode);
      setRedeemMessage({ type: 'success', text: response.message });
      setRedeemCode('');
    } catch (error: any) {
      setRedeemMessage({ type: 'error', text: error.message || 'Failed to redeem code' });
    }
    setTimeout(() => setRedeemMessage(null), 5000);
  };

  const shareVia = (method: string) => {
    const text = `Join HIVE215 and get ${referralCode?.referee_reward_value || 50} free minutes! Use my code: ${referralCode?.code}`;
    switch (method) {
      case 'twitter':
        window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(shareUrl)}`, '_blank');
        break;
      case 'facebook':
        window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`, '_blank');
        break;
      case 'email':
        window.open(`mailto:?subject=Join HIVE215&body=${encodeURIComponent(text + '\n\n' + shareUrl)}`, '_blank');
        break;
      case 'sms':
        window.open(`sms:?body=${encodeURIComponent(text + ' ' + shareUrl)}`, '_blank');
        break;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading referrals...</div>
      </div>
    );
  }

  const milestones = [
    { count: 5, reward: 100, label: 'Bronze' },
    { count: 10, reward: 200, label: 'Silver' },
    { count: 25, reward: 500, label: 'Gold' },
  ];

  const currentMilestone = milestones.find(m => (referralCode?.successful_referrals || 0) < m.count) || milestones[milestones.length - 1];
  const progress = ((referralCode?.successful_referrals || 0) / currentMilestone.count) * 100;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gold">Referrals</h1>
        <p className="text-gray-400 mt-1">Invite friends and earn free minutes</p>
      </div>

      {/* Your Referral Code */}
      <Card glow>
        <CardTitle>Your Referral Code</CardTitle>
        <CardContent>
          <div className="flex items-center justify-center gap-4 py-6">
            <div className="text-4xl font-bold text-gold tracking-wider">
              {referralCode?.code || 'HIVE-XXXXX'}
            </div>
            <button
              onClick={copyToClipboard}
              className="px-4 py-2 bg-gold/20 text-gold rounded-lg hover:bg-gold/30 transition-colors"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>

          <div className="text-center text-gray-400 mb-6">
            Share this code and you both get <span className="text-gold font-semibold">{referralCode?.referrer_reward_value || 50} minutes</span> free!
          </div>

          {/* Share Buttons */}
          <div className="flex justify-center gap-3 flex-wrap">
            <button onClick={() => shareVia('twitter')} className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors">
              Twitter
            </button>
            <button onClick={() => shareVia('facebook')} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
              Facebook
            </button>
            <button onClick={() => shareVia('email')} className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors">
              Email
            </button>
            <button onClick={() => shareVia('sms')} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
              SMS
            </button>
          </div>

          <div className="mt-6 p-3 bg-oled-gray rounded-lg">
            <div className="text-sm text-gray-400 mb-2">Share Link</div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={shareUrl}
                readOnly
                className="flex-1 bg-transparent text-white text-sm truncate"
              />
              <button onClick={copyToClipboard} className="text-gold hover:text-gold/80">
                Copy
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent>
            <div className="text-center py-4">
              <div className="text-4xl font-bold text-gold">{referralCode?.total_referrals || 0}</div>
              <div className="text-gray-400 mt-1">Total Referrals</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-center py-4">
              <div className="text-4xl font-bold text-green-400">{referralCode?.successful_referrals || 0}</div>
              <div className="text-gray-400 mt-1">Successful</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-center py-4">
              <div className="text-4xl font-bold text-gold">{referralCode?.total_rewards_earned || 0}</div>
              <div className="text-gray-400 mt-1">Minutes Earned</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Milestone Progress */}
      <Card>
        <CardTitle>Milestone Progress</CardTitle>
        <CardContent>
          <div className="mt-4">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-gray-400">Next milestone: {currentMilestone.label}</span>
              <span className="text-gold">{referralCode?.successful_referrals || 0} / {currentMilestone.count} referrals</span>
            </div>
            <ProgressBar current={referralCode?.successful_referrals || 0} max={currentMilestone.count} size="lg" />
            <p className="text-center text-gray-400 mt-4">
              Reach {currentMilestone.count} referrals to earn <span className="text-gold font-semibold">{currentMilestone.reward} bonus minutes</span>!
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4 mt-6">
            {milestones.map((milestone, i) => (
              <div
                key={i}
                className={`text-center p-4 rounded-lg border ${
                  (referralCode?.successful_referrals || 0) >= milestone.count
                    ? 'border-gold bg-gold/10'
                    : 'border-gray-700'
                }`}
              >
                <div className={`text-2xl mb-1 ${
                  (referralCode?.successful_referrals || 0) >= milestone.count ? 'text-gold' : 'text-gray-500'
                }`}>
                  {milestone.label}
                </div>
                <div className="text-sm text-gray-400">{milestone.count} referrals</div>
                <div className="text-gold font-semibold">+{milestone.reward} min</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Redeem a Code */}
      <Card>
        <CardTitle>Have a Referral Code?</CardTitle>
        <CardContent>
          <div className="flex gap-3 mt-4">
            <input
              type="text"
              value={redeemCode}
              onChange={(e) => setRedeemCode(e.target.value.toUpperCase())}
              placeholder="Enter code (e.g., HIVE-ABC123)"
              className="flex-1 bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
            />
            <HoneycombButton onClick={handleRedeem}>Redeem</HoneycombButton>
          </div>
          {redeemMessage && (
            <div className={`mt-3 p-3 rounded-lg ${
              redeemMessage.type === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
            }`}>
              {redeemMessage.text}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Referrals */}
      {referrals.length > 0 && (
        <Card>
          <CardTitle>Recent Referrals</CardTitle>
          <CardContent>
            <div className="divide-y divide-gray-800 mt-4">
              {referrals.slice(0, 10).map((referral) => (
                <div key={referral.id} className="py-3 flex items-center justify-between">
                  <div>
                    <div className="text-white">User #{referral.referee_id.slice(0, 8)}...</div>
                    <div className="text-sm text-gray-400">
                      {referral.signed_up_at && new Date(referral.signed_up_at).toLocaleDateString()}
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-sm ${
                    referral.status === 'converted' ? 'bg-green-500/20 text-green-400' :
                    referral.status === 'signed_up' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {referral.status}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
