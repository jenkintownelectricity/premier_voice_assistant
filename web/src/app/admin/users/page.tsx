'use client';

import { useState } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Input, Select } from '@/components/Input';
import { Modal } from '@/components/Modal';
import { ProgressBar } from '@/components/ProgressBar';

// Mock user data
const mockUsers = [
  {
    id: 'ea97ae74-a597-4dc8-9c6e-1c6981324ce5',
    email: 'test@example.com',
    plan: 'pro',
    status: 'active',
    minutes_used: 3245,
    max_minutes: 10000,
    bonus_minutes: 500,
    created_at: '2024-01-15',
  },
  {
    id: 'user-abc123',
    email: 'john@company.com',
    plan: 'starter',
    status: 'active',
    minutes_used: 1856,
    max_minutes: 2000,
    bonus_minutes: 0,
    created_at: '2024-02-20',
  },
  {
    id: 'user-def456',
    email: 'sarah@business.com',
    plan: 'free',
    status: 'active',
    minutes_used: 87,
    max_minutes: 100,
    bonus_minutes: 50,
    created_at: '2024-03-10',
  },
];

export default function UsersPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedUser, setSelectedUser] = useState<typeof mockUsers[0] | null>(null);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [showMinutesModal, setShowMinutesModal] = useState(false);
  const [upgradePlan, setUpgradePlan] = useState('pro');
  const [bonusMinutes, setBonusMinutes] = useState('100');
  const [bonusReason, setBonusReason] = useState('');

  const filteredUsers = mockUsers.filter(
    (user) =>
      user.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleUpgrade = () => {
    // API call would go here
    console.log('Upgrading', selectedUser?.id, 'to', upgradePlan);
    setShowUpgradeModal(false);
    setSelectedUser(null);
  };

  const handleAddMinutes = () => {
    // API call would go here
    console.log('Adding', bonusMinutes, 'minutes to', selectedUser?.id, 'Reason:', bonusReason);
    setShowMinutesModal(false);
    setSelectedUser(null);
    setBonusMinutes('100');
    setBonusReason('');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">User Management</h1>
        <p className="text-gray-400 mt-1">Search, manage plans, and add bonus minutes</p>
      </div>

      {/* Search */}
      <Card>
        <CardContent>
          <Input
            placeholder="Search by user ID or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardContent>
          <table className="table-gold">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Email</th>
                <th>Plan</th>
                <th>Usage</th>
                <th>Bonus</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((user) => (
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

          {filteredUsers.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No users found matching "{searchQuery}"
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
            <HoneycombButton onClick={handleUpgrade}>
              Confirm Upgrade
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
            <HoneycombButton onClick={handleAddMinutes}>
              Add Minutes
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
