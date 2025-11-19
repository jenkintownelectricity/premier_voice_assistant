'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Input, Select } from '@/components/Input';
import { Modal } from '@/components/Modal';
import { adminApi } from '@/lib/api';
import { useAdmin } from '../layout';

interface DiscountCode {
  id: string;
  code: string;
  description: string;
  discount_type: string;
  discount_value: number;
  max_uses: number | null;
  current_uses: number;
  valid_until: string | null;
  is_active: boolean;
}

export default function CodesPage() {
  const { adminKey } = useAdmin();
  const [codes, setCodes] = useState<DiscountCode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newCode, setNewCode] = useState({
    code: '',
    description: '',
    discount_type: 'minutes',
    discount_value: '100',
    max_uses: '',
    valid_until: '',
  });

  const fetchCodes = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await adminApi.getCodes(adminKey, false);
      setCodes(response.codes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load codes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCodes();
  }, [adminKey]);

  const handleCreate = async () => {
    try {
      setCreating(true);
      await adminApi.createCode(
        adminKey,
        newCode.code,
        newCode.discount_type,
        parseInt(newCode.discount_value),
        newCode.description || undefined,
        newCode.max_uses ? parseInt(newCode.max_uses) : undefined,
        newCode.valid_until || undefined
      );
      setShowCreateModal(false);
      setNewCode({
        code: '',
        description: '',
        discount_type: 'minutes',
        discount_value: '100',
        max_uses: '',
        valid_until: '',
      });
      fetchCodes();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create code');
    } finally {
      setCreating(false);
    }
  };

  const handleDeactivate = async (code: string) => {
    try {
      await adminApi.deactivateCode(adminKey, code);
      setCodes(codes.map(c => c.code === code ? { ...c, is_active: false } : c));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to deactivate code');
    }
  };

  const getTypeLabel = (type: string, value: number) => {
    switch (type) {
      case 'minutes':
        return `+${value} min`;
      case 'percentage':
        return `${value}% off`;
      case 'fixed':
        return `$${value} off`;
      case 'upgrade':
        return `${value} mo free`;
      default:
        return value;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading codes...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">Discount Codes</h1>
          <p className="text-gray-400 mt-1">Create and manage promotional codes</p>
        </div>
        <HoneycombButton onClick={() => setShowCreateModal(true)}>
          Create Code
        </HoneycombButton>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Active Codes</div>
            <div className="text-2xl font-bold text-gold">
              {codes.filter(c => c.is_active).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Total Redemptions</div>
            <div className="text-2xl font-bold text-gold">
              {codes.reduce((sum, c) => sum + c.current_uses, 0)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-400">Minutes Given</div>
            <div className="text-2xl font-bold text-gold">
              {codes
                .filter(c => c.discount_type === 'minutes')
                .reduce((sum, c) => sum + c.current_uses * c.discount_value, 0)
                .toLocaleString()}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Codes Table */}
      <Card>
        <CardContent>
          <table className="table-gold">
            <thead>
              <tr>
                <th>Code</th>
                <th>Description</th>
                <th>Value</th>
                <th>Uses</th>
                <th>Expires</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {codes.map((code) => (
                <tr key={code.id}>
                  <td className="font-mono font-bold text-gold">{code.code}</td>
                  <td className="text-gray-400 text-sm">{code.description}</td>
                  <td>
                    <span className="px-2 py-1 bg-gold/10 text-gold rounded text-sm">
                      {getTypeLabel(code.discount_type, code.discount_value)}
                    </span>
                  </td>
                  <td>
                    <span className="text-white">{code.current_uses}</span>
                    {code.max_uses && (
                      <span className="text-gray-500">/{code.max_uses}</span>
                    )}
                  </td>
                  <td className="text-sm">
                    {code.valid_until ? (
                      <span className="text-gray-400">{code.valid_until}</span>
                    ) : (
                      <span className="text-green-500">No expiry</span>
                    )}
                  </td>
                  <td>
                    {code.is_active ? (
                      <span className="text-green-500 text-sm">Active</span>
                    ) : (
                      <span className="text-gray-500 text-sm">Inactive</span>
                    )}
                  </td>
                  <td>
                    {code.is_active && (
                      <button
                        onClick={() => handleDeactivate(code.code)}
                        className="text-xs text-red-400 hover:text-red-300 transition-colors"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Create Code Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create Discount Code"
        size="lg"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Code"
              value={newCode.code}
              onChange={(e) => setNewCode({ ...newCode, code: e.target.value.toUpperCase() })}
              placeholder="SUMMER2024"
            />
            <Select
              label="Type"
              value={newCode.discount_type}
              onChange={(e) => setNewCode({ ...newCode, discount_type: e.target.value })}
              options={[
                { value: 'minutes', label: 'Bonus Minutes' },
                { value: 'percentage', label: 'Percentage Off' },
                { value: 'fixed', label: 'Fixed Amount Off' },
                { value: 'upgrade', label: 'Free Upgrade' },
              ]}
            />
          </div>

          <Input
            label="Description"
            value={newCode.description}
            onChange={(e) => setNewCode({ ...newCode, description: e.target.value })}
            placeholder="Summer promotion bonus"
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label={
                newCode.discount_type === 'minutes'
                  ? 'Minutes'
                  : newCode.discount_type === 'percentage'
                  ? 'Percentage'
                  : newCode.discount_type === 'fixed'
                  ? 'Amount ($)'
                  : 'Months Free'
              }
              type="number"
              value={newCode.discount_value}
              onChange={(e) => setNewCode({ ...newCode, discount_value: e.target.value })}
            />
            <Input
              label="Max Uses (optional)"
              type="number"
              value={newCode.max_uses}
              onChange={(e) => setNewCode({ ...newCode, max_uses: e.target.value })}
              placeholder="Unlimited"
            />
          </div>

          <Input
            label="Valid Until (optional)"
            type="date"
            value={newCode.valid_until}
            onChange={(e) => setNewCode({ ...newCode, valid_until: e.target.value })}
          />

          <div className="flex gap-3 mt-6">
            <HoneycombButton onClick={handleCreate} disabled={creating}>
              {creating ? 'Creating...' : 'Create Code'}
            </HoneycombButton>
            <HoneycombButton
              variant="outline"
              onClick={() => setShowCreateModal(false)}
            >
              Cancel
            </HoneycombButton>
          </div>
        </div>
      </Modal>
    </div>
  );
}
