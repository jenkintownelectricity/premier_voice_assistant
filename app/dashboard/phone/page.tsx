'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { phoneApi } from '@/lib/api';

interface PhoneNumber {
  id: string;
  phone_number: string;
  phone_type: string;
  is_verified: boolean;
  is_primary: boolean;
  created_at: string;
}

export default function PhonePage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [phoneNumbers, setPhoneNumbers] = useState<PhoneNumber[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newPhone, setNewPhone] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [pendingPhone, setPendingPhone] = useState('');
  const [step, setStep] = useState<'add' | 'verify'>('add');
  const [devCode, setDevCode] = useState<string | null>(null);

  const fetchPhones = async () => {
    if (!user?.id) return;
    try {
      const response = await phoneApi.getPhoneNumbers(user.id);
      setPhoneNumbers(response.phone_numbers);
    } catch (error) {
      console.error('Failed to load phone numbers:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPhones();
  }, [user?.id]);

  const handleAddPhone = async () => {
    if (!user?.id || !newPhone) return;
    try {
      const response = await phoneApi.addPhoneNumber(user.id, newPhone);
      setPendingPhone(newPhone);
      setDevCode(response.dev_code || null);
      setStep('verify');
    } catch (error) {
      console.error('Failed to add phone:', error);
    }
  };

  const handleVerify = async () => {
    if (!user?.id || !verificationCode) return;
    try {
      await phoneApi.verifyPhone(user.id, pendingPhone, verificationCode);
      setShowAddModal(false);
      setNewPhone('');
      setVerificationCode('');
      setPendingPhone('');
      setStep('add');
      setDevCode(null);
      fetchPhones();
    } catch (error) {
      console.error('Failed to verify:', error);
    }
  };

  const handleDelete = async (phoneId: string) => {
    if (!user?.id) return;
    if (!confirm('Delete this phone number?')) return;
    try {
      await phoneApi.deletePhone(user.id, phoneId);
      fetchPhones();
    } catch (error) {
      console.error('Failed to delete:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading phone numbers...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">Phone Numbers</h1>
          <p className="text-gray-400 mt-1">Manage your business phone lines</p>
        </div>
        <HoneycombButton onClick={() => setShowAddModal(true)}>
          Add Phone Number
        </HoneycombButton>
      </div>

      {phoneNumbers.length === 0 ? (
        <Card>
          <CardContent>
            <div className="text-center py-12">
              <div className="text-6xl mb-4">phone</div>
              <h3 className="text-xl text-white mb-2">No Phone Numbers</h3>
              <p className="text-gray-400 mb-6">Add a phone number to start receiving AI-powered calls</p>
              <HoneycombButton onClick={() => setShowAddModal(true)}>
                Add Your First Number
              </HoneycombButton>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {phoneNumbers.map((phone) => (
            <Card key={phone.id}>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gold/10 rounded-full flex items-center justify-center">
                      <svg className="w-6 h-6 text-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                      </svg>
                    </div>
                    <div>
                      <div className="text-xl font-semibold text-white">{phone.phone_number}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-gray-400 text-sm">{phone.phone_type}</span>
                        {phone.is_primary && (
                          <span className="px-2 py-0.5 bg-gold/20 text-gold text-xs rounded-full">Primary</span>
                        )}
                        {phone.is_verified ? (
                          <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">Verified</span>
                        ) : (
                          <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">Pending</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(phone.id)}
                    className="p-2 text-gray-500 hover:text-red-500 transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add Phone Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-oled-dark border border-gray-800 rounded-2xl p-6 max-w-md w-full">
            <h2 className="text-2xl font-bold text-gold mb-4">
              {step === 'add' ? 'Add Phone Number' : 'Verify Phone'}
            </h2>

            {step === 'add' ? (
              <>
                <div className="mb-4">
                  <label className="block text-sm text-gray-400 mb-2">Phone Number</label>
                  <input
                    type="tel"
                    value={newPhone}
                    onChange={(e) => setNewPhone(e.target.value)}
                    placeholder="+1 (555) 123-4567"
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
                  />
                </div>
                <div className="flex gap-3">
                  <HoneycombButton variant="outline" onClick={() => setShowAddModal(false)}>
                    Cancel
                  </HoneycombButton>
                  <HoneycombButton onClick={handleAddPhone}>
                    Send Code
                  </HoneycombButton>
                </div>
              </>
            ) : (
              <>
                <p className="text-gray-400 mb-4">
                  Enter the verification code sent to {pendingPhone}
                </p>
                {devCode && (
                  <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                    <p className="text-yellow-400 text-sm">Dev Mode: Code is {devCode}</p>
                  </div>
                )}
                <div className="mb-4">
                  <label className="block text-sm text-gray-400 mb-2">Verification Code</label>
                  <input
                    type="text"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder="123456"
                    maxLength={6}
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white text-center text-2xl tracking-widest placeholder-gray-500 focus:border-gold focus:outline-none"
                  />
                </div>
                <div className="flex gap-3">
                  <HoneycombButton variant="outline" onClick={() => { setStep('add'); setDevCode(null); }}>
                    Back
                  </HoneycombButton>
                  <HoneycombButton onClick={handleVerify}>
                    Verify
                  </HoneycombButton>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
