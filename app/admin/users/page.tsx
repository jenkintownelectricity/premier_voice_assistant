'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Input, Select } from '@/components/Input';
import { Modal } from '@/components/Modal';
import { ProgressBar } from '@/components/ProgressBar';
import { adminApi, api } from '@/lib/api';
import { useAdmin } from '@/lib/admin-context';

interface UserData {
  id: string;
  email: string;
  plan: string;
  status: string;
  minutes_used: number;
  max_minutes: number;
  bonus_minutes: number;
  created_at: string;
}

export default function UsersPage() {
  const { adminKey } = useAdmin();
  const [searchQuery, setSearchQuery] = useState('');
  const [users, setUsers] = useState<UserData[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserData | null>(null);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [showMinutesModal, setShowMinutesModal] = useState(false);
  const [upgradePlan, setUpgradePlan] = useState('pro');
  const [bonusMinutes, setBonusMinutes] = useState('100');
  const [bonusReason, setBonusReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Search for a user by ID
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // First try to get the subscription
      const subResponse = await adminApi.getUserSubscription(adminKey, searchQuery.trim());

      // Get usage data
      const usageResponse = await api.getUsage(searchQuery.trim());
      const limitsResponse = await api.getFeatureLimits(searchQuery.trim());

      const userData: UserData = {
        id: searchQuery.trim(),
        email: searchQuery.trim(), // Will show ID if no email available
        plan: subResponse.subscription?.plan_name || 'free',
        status: subResponse.subscription?.status || 'active',
        minutes_used: usageResponse.usage.minutes_used || 0,
        max_minutes: limitsResponse.limits.max_minutes || 100,
        bonus_minutes: usageResponse.usage.bonus_minutes || 0,
        created_at: subResponse.subscription?.current_period_start || new Date().toISOString(),
      };

      setUsers([userData]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'User not found');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async () => {
    if (!selectedUser) return;

    setActionLoading(true);
    setError(null);

    try {
      await adminApi.upgradeUser(adminKey, selectedUser.id, upgradePlan);
      setSuccess(`User ${selectedUser.id} upgraded to ${upgradePlan}`);
      setShowUpgradeModal(false);
      setSelectedUser(null);
      // Refresh user data
      if (searchQuery) handleSearch();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upgrade user');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddMinutes = async () => {
    if (!selectedUser) return;

    setActionLoading(true);
    setError(null);

    try {
      const result = await adminApi.addBonusMinutes(
        adminKey,
        selectedUser.id,
        parseInt(bonusMinutes),
        bonusReason || undefined
      );
      setSuccess(`Added ${bonusMinutes} minutes to ${selectedUser.id}`);
      setShowMinutesModal(false);
      setSelectedUser(null);
      setBonusMinutes('100');
      setBonusReason('');
      // Refresh user data
      if (searchQuery) handleSearch();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add minutes');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">User Management</h1>
        <p className="text-gray-400 mt-1">Search, manage plans, and add bonus minutes</p>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 text-green-400">
          {success}
        </div>
      )}

      {/* Search */}
      <Card>
        <CardContent>
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Enter user ID to search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <HoneycombButton onClick={handleSearch} disabled={loading}>
              {loading ? 'Searching...' : 'Search'}
            </HoneycombButton>
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardContent>
          <table className="table-gold">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Plan</th>
                <th>Usage</th>
                <th>Bonus</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td className="font-mono text-xs">{user.id.slice(0, 8)}...</td>
                  <td>{user.email}</td>
                  <td>
                    <span
                      className={`px-2 py-1 rounded text-xs font-semibold ${
                        user.plan === 'pro'
                          ? 'bg-gold/20 text-gold'
                          : user.plan === 'starter'
                          ? 'bg-honey-400/20 text-honey-400'
                          : 'bg-gray-500/20 text-gray-400'
                      }`}
                    >
                      {user.plan.toUpperCase()}
                    </span>
                  </td>
                  <td className="w-48">
                    <ProgressBar
                      current={user.minutes_used}
                      max={user.max_minutes + user.bonus_minutes}
                      size="sm"
                    />
                  </td>
                  <td>
                    {user.bonus_minutes > 0 && (
                      <span className="text-green-500 text-sm">
                        +{user.bonus_minutes}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setSelectedUser(user);
                          setShowUpgradeModal(true);
                        }}
                        className="text-xs text-gold hover:text-gold-shine transition-colors"
                      >
                        Upgrade
                      </button>
                      <button
                        onClick={() => {
                          setSelectedUser(user);
                          setShowMinutesModal(true);
                        }}
                        className="text-xs text-honey-400 hover:text-honey-300 transition-colors"
                      >
                        +Minutes
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {users.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              {searchQuery ? 'No user found. Enter a valid user ID.' : 'Enter a user ID to search'}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Upgrade Modal */}
      <Modal
        isOpen={showUpgradeModal}
        onClose={() => setShowUpgradeModal(false)}
        title="Upgrade User Plan"
      >
        <div className="space-y-4">
          <div className="text-sm text-gray-400">
            User: <span className="text-white">{selectedUser?.email}</span>
          </div>
          <div className="text-sm text-gray-400">
            Current Plan:{' '}
            <span className="text-gold">{selectedUser?.plan.toUpperCase()}</span>
          </div>

          <Select
            label="New Plan"
            value={upgradePlan}
            onChange={(e) => setUpgradePlan(e.target.value)}
            options={[
              { value: 'free', label: 'Free (100 min)' },
              { value: 'starter', label: 'Starter (2,000 min) - $99/mo' },
              { value: 'pro', label: 'Pro (10,000 min) - $299/mo' },
              { value: 'enterprise', label: 'Enterprise (Unlimited)' },
            ]}
          />

          <div className="flex gap-3 mt-6">
            <HoneycombButton onClick={handleUpgrade} disabled={actionLoading}>
              {actionLoading ? 'Upgrading...' : 'Confirm Upgrade'}
            </HoneycombButton>
            <HoneycombButton
              variant="outline"
              onClick={() => setShowUpgradeModal(false)}
            >
              Cancel
            </HoneycombButton>
          </div>
        </div>
      </Modal>

      {/* Add Minutes Modal */}
      <Modal
        isOpen={showMinutesModal}
        onClose={() => setShowMinutesModal(false)}
        title="Add Bonus Minutes"
      >
        <div className="space-y-4">
          <div className="text-sm text-gray-400">
            User: <span className="text-white">{selectedUser?.email}</span>
          </div>
          <div className="text-sm text-gray-400">
            Current Bonus:{' '}
            <span className="text-green-500">{selectedUser?.bonus_minutes} min</span>
          </div>

          <Input
            label="Minutes to Add"
            type="number"
            value={bonusMinutes}
            onChange={(e) => setBonusMinutes(e.target.value)}
            placeholder="100"
          />

          <Input
            label="Reason (optional)"
            value={bonusReason}
            onChange={(e) => setBonusReason(e.target.value)}
            placeholder="Customer support compensation..."
          />

          <div className="flex gap-3 mt-6">
            <HoneycombButton onClick={handleAddMinutes} disabled={actionLoading}>
              {actionLoading ? 'Adding...' : 'Add Minutes'}
            </HoneycombButton>
            <HoneycombButton
              variant="outline"
              onClick={() => setShowMinutesModal(false)}
            >
              Cancel
            </HoneycombButton>
          </div>
        </div>
      </Modal>
    </div>
  );
}
