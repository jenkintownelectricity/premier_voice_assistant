'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { ProgressBar } from '@/components/ProgressBar';
import { useAuth } from '@/lib/auth-context';
import { contestApi } from '@/lib/api';

interface Contest {
  id: string;
  contest_id: string;
  name: string;
  description: string;
  status: string;
  trial_days: number;
  tier: string;
}

interface ContestEntry {
  id: string;
  points_balance: number;
  invites_sent: number;
  invites_converted: number;
  trial_start: string;
  trial_end: string;
  features_unlocked: string[];
}

interface PointsHistory {
  id: string;
  action: string;
  points: number;
  created_at: string;
}

const REWARDS = [
  { id: 'trial_extension_7d', name: '+7 Days Trial', points: 200, icon: '7' },
  { id: 'trial_extension_30d', name: '+30 Days Trial', points: 500, icon: '30' },
  { id: 'voice_clone_unlock', name: 'Voice Clone', points: 300, icon: 'VC' },
  { id: 'extra_minutes_100', name: '+100 Minutes', points: 400, icon: '100' },
];

export default function ContestPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [contest, setContest] = useState<Contest | null>(null);
  const [entry, setEntry] = useState<ContestEntry | null>(null);
  const [pointsHistory, setPointsHistory] = useState<PointsHistory[]>([]);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    const fetchContest = async () => {
      if (!user?.id) return;
      try {
        const response = await contestApi.getContestInfo(user.id);
        setContest(response.contest);
        setEntry(response.entry);
        setPointsHistory(response.points_history || []);
      } catch (error) {
        console.error('Failed to load contest:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchContest();
  }, [user?.id]);

  const handleJoin = async () => {
    if (!user?.id) return;
    try {
      const response = await contestApi.joinContest(user.id);
      setMessage({ type: 'success', text: response.message });
      // Refresh data
      const updated = await contestApi.getContestInfo(user.id);
      setEntry(updated.entry);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.message || 'Failed to join contest' });
    }
    setTimeout(() => setMessage(null), 5000);
  };

  const handleRedeem = async (rewardId: string, points: number) => {
    if (!user?.id) return;
    if ((entry?.points_balance || 0) < points) {
      setMessage({ type: 'error', text: 'Not enough points' });
      setTimeout(() => setMessage(null), 3000);
      return;
    }
    try {
      const response = await contestApi.redeemReward(user.id, rewardId, points);
      setMessage({ type: 'success', text: `Redeemed! New balance: ${response.new_balance} pts` });
      // Refresh
      const updated = await contestApi.getContestInfo(user.id);
      setEntry(updated.entry);
      setPointsHistory(updated.points_history || []);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.message || 'Redemption failed' });
    }
    setTimeout(() => setMessage(null), 5000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading contest...</div>
      </div>
    );
  }

  if (!contest) {
    return (
      <div className="text-center py-20">
        <h1 className="text-3xl font-bold text-gray-400">No Active Contest</h1>
        <p className="text-gray-500 mt-4">Check back soon for upcoming promotions.</p>
      </div>
    );
  }

  const daysLeft = entry?.trial_end
    ? Math.max(0, Math.ceil((new Date(entry.trial_end).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
    : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gold">{contest.name}</h1>
        <p className="text-gray-400 mt-1">{contest.description}</p>
      </div>

      {message && (
        <div className={`p-4 rounded-lg ${
          message.type === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
        }`}>
          {message.text}
        </div>
      )}

      {!entry ? (
        /* Not Enrolled */
        <Card glow>
          <CardContent>
            <div className="text-center py-8">
              <div className="text-6xl mb-4">90</div>
              <div className="text-2xl font-bold text-gold mb-2">Days Free Premium</div>
              <p className="text-gray-400 mb-6 max-w-md mx-auto">
                Join the Early Risers Contest and get 90 days of Queen Bee tier access.
                All features unlocked. No credit card required.
              </p>
              <HoneycombButton onClick={handleJoin}>JOIN CONTEST</HoneycombButton>
            </div>
          </CardContent>
        </Card>
      ) : (
        /* Enrolled */
        <>
          {/* Stats Row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent>
                <div className="text-center py-4">
                  <div className="text-4xl font-bold text-gold">{entry.points_balance}</div>
                  <div className="text-gray-400 mt-1">Points</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <div className="text-center py-4">
                  <div className="text-4xl font-bold text-green-400">{daysLeft}</div>
                  <div className="text-gray-400 mt-1">Days Left</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <div className="text-center py-4">
                  <div className="text-4xl font-bold text-blue-400">{entry.invites_converted}</div>
                  <div className="text-gray-400 mt-1">Referrals</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <div className="text-center py-4">
                  <div className="text-4xl font-bold text-purple-400">{entry.features_unlocked?.length || 0}</div>
                  <div className="text-gray-400 mt-1">Unlocked</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Trial Progress */}
          <Card>
            <CardTitle>Trial Progress</CardTitle>
            <CardContent>
              <div className="mt-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Trial ends: {new Date(entry.trial_end).toLocaleDateString()}</span>
                  <span className="text-gold">{daysLeft} days remaining</span>
                </div>
                <ProgressBar current={90 - daysLeft} max={90} size="lg" />
              </div>
            </CardContent>
          </Card>

          {/* Redeem Rewards */}
          <Card glow>
            <CardTitle>Redeem Rewards</CardTitle>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                {REWARDS.map((reward) => (
                  <button
                    key={reward.id}
                    onClick={() => handleRedeem(reward.id, reward.points)}
                    disabled={(entry.points_balance || 0) < reward.points}
                    className={`p-4 rounded-lg border text-center transition-all ${
                      (entry.points_balance || 0) >= reward.points
                        ? 'border-gold bg-gold/10 hover:bg-gold/20 cursor-pointer'
                        : 'border-gray-700 bg-gray-800/50 opacity-50 cursor-not-allowed'
                    }`}
                  >
                    <div className="text-3xl font-bold mb-2">{reward.icon}</div>
                    <div className="text-white font-medium">{reward.name}</div>
                    <div className="text-gold text-sm mt-1">{reward.points} pts</div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Points History */}
          {pointsHistory.length > 0 && (
            <Card>
              <CardTitle>Recent Activity</CardTitle>
              <CardContent>
                <div className="divide-y divide-gray-800 mt-4">
                  {pointsHistory.slice(0, 10).map((item) => (
                    <div key={item.id} className="py-3 flex items-center justify-between">
                      <div>
                        <div className="text-white capitalize">{item.action.replace(/_/g, ' ')}</div>
                        <div className="text-sm text-gray-400">
                          {new Date(item.created_at).toLocaleDateString()}
                        </div>
                      </div>
                      <span className={`font-bold ${item.points > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {item.points > 0 ? '+' : ''}{item.points} pts
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
