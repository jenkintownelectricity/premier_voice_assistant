'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

interface CallRecord {
  id: string;
  started_at: string;
  ended_at?: string;
  duration_seconds?: number;
  caller_number?: string;
  direction: string;
  status: string;
  summary?: string;
  sentiment?: string;
  key_info?: string[];
  action_items?: string[];
}

export default function IntelligencePage() {
  const { user } = useAuth();
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState<CallRecord | null>(null);
  const [shareModal, setShareModal] = useState(false);
  const [shareEmail, setShareEmail] = useState('');
  const [sharePhone, setSharePhone] = useState('');

  useEffect(() => {
    const fetchCalls = async () => {
      if (!user?.id) return;
      try {
        const response = await api.getCalls(user.id, 50, 0);
        setCalls(response.calls || []);
      } catch (error) {
        console.error('Failed to load calls:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchCalls();
  }, [user?.id]);

  const handleExport = async (format: 'csv' | 'json') => {
    if (!user?.id) return;
    try {
      const blob = await fetch(`/api/calls/export?format=${format}`, {
        headers: { 'X-User-ID': user.id }
      }).then(r => r.blob());
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `calls.${format}`;
      a.click();
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading call intelligence...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">Call Intelligence</h1>
          <p className="text-gray-400 mt-1">AI-powered insights from your calls</p>
        </div>
        <div className="flex gap-2">
          <HoneycombButton variant="outline" onClick={() => handleExport('csv')}>
            Export CSV
          </HoneycombButton>
          <HoneycombButton variant="outline" onClick={() => handleExport('json')}>
            Export JSON
          </HoneycombButton>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent>
            <div className="text-3xl font-bold text-gold">{calls.length}</div>
            <div className="text-gray-400 text-sm">Total Calls</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-3xl font-bold text-green-500">
              {calls.filter(c => c.sentiment === 'positive').length}
            </div>
            <div className="text-gray-400 text-sm">Positive Sentiment</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-3xl font-bold text-yellow-500">
              {calls.filter(c => c.action_items && c.action_items.length > 0).length}
            </div>
            <div className="text-gray-400 text-sm">With Action Items</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-3xl font-bold text-blue-500">
              {Math.round(calls.reduce((sum, c) => sum + (c.duration_seconds || 0), 0) / 60)}
            </div>
            <div className="text-gray-400 text-sm">Total Minutes</div>
          </CardContent>
        </Card>
      </div>

      {/* Call List */}
      <Card>
        <CardTitle>Recent Calls</CardTitle>
        <CardContent>
          <div className="space-y-3 mt-4">
            {calls.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                No calls yet. Make or receive a call to see intelligence here.
              </div>
            ) : (
              calls.map((call) => (
                <div
                  key={call.id}
                  className="p-4 bg-oled-gray rounded-lg cursor-pointer hover:bg-gray-800 transition-colors"
                  onClick={() => setSelectedCall(call)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          call.direction === 'inbound' ? 'bg-blue-500/20 text-blue-400' : 'bg-green-500/20 text-green-400'
                        }`}>
                          {call.direction}
                        </span>
                        <span className="text-white font-medium">
                          {call.caller_number || 'Unknown'}
                        </span>
                      </div>
                      {call.summary && (
                        <p className="text-gray-400 text-sm mt-1 line-clamp-2">{call.summary}</p>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-gray-400 text-sm">
                        {new Date(call.started_at).toLocaleDateString()}
                      </div>
                      <div className="text-gray-500 text-xs">
                        {call.duration_seconds ? `${Math.round(call.duration_seconds / 60)}m` : '-'}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Call Detail Modal */}
      {selectedCall && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-oled-dark border border-gray-800 rounded-2xl p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-2xl font-bold text-gold">Call Details</h2>
              <button onClick={() => setSelectedCall(null)} className="text-gray-400 hover:text-white">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-gray-400 text-sm">Direction</div>
                  <div className="text-white">{selectedCall.direction}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-sm">Duration</div>
                  <div className="text-white">{selectedCall.duration_seconds ? `${Math.round(selectedCall.duration_seconds / 60)} minutes` : 'N/A'}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-sm">Caller</div>
                  <div className="text-white">{selectedCall.caller_number || 'Unknown'}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-sm">Date</div>
                  <div className="text-white">{new Date(selectedCall.started_at).toLocaleString()}</div>
                </div>
              </div>

              {selectedCall.summary && (
                <div>
                  <div className="text-gray-400 text-sm mb-1">Summary</div>
                  <div className="text-white bg-oled-gray p-3 rounded-lg">{selectedCall.summary}</div>
                </div>
              )}

              {selectedCall.key_info && selectedCall.key_info.length > 0 && (
                <div>
                  <div className="text-gray-400 text-sm mb-1">Key Information</div>
                  <ul className="list-disc list-inside text-white bg-oled-gray p-3 rounded-lg">
                    {selectedCall.key_info.map((info, i) => (
                      <li key={i}>{info}</li>
                    ))}
                  </ul>
                </div>
              )}

              {selectedCall.action_items && selectedCall.action_items.length > 0 && (
                <div>
                  <div className="text-gray-400 text-sm mb-1">Action Items</div>
                  <ul className="list-disc list-inside text-white bg-oled-gray p-3 rounded-lg">
                    {selectedCall.action_items.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex gap-2 pt-4">
                <HoneycombButton variant="outline" onClick={() => setShareModal(true)}>
                  Share
                </HoneycombButton>
                <HoneycombButton variant="outline" onClick={() => setSelectedCall(null)}>
                  Close
                </HoneycombButton>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Share Modal */}
      {shareModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-oled-dark border border-gray-800 rounded-2xl p-6 max-w-md w-full">
            <h2 className="text-xl font-bold text-gold mb-4">Share Call Summary</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Email</label>
                <input
                  type="email"
                  value={shareEmail}
                  onChange={(e) => setShareEmail(e.target.value)}
                  placeholder="recipient@example.com"
                  className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">SMS</label>
                <input
                  type="tel"
                  value={sharePhone}
                  onChange={(e) => setSharePhone(e.target.value)}
                  placeholder="+1234567890"
                  className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-2 text-white"
                />
              </div>
              <div className="flex gap-2">
                <HoneycombButton variant="outline" onClick={() => setShareModal(false)}>
                  Cancel
                </HoneycombButton>
                <HoneycombButton onClick={() => { setShareModal(false); }}>
                  Send
                </HoneycombButton>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
