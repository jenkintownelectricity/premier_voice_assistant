'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';

interface Webhook {
  id: string;
  name: string;
  url: string;
  events: string[];
  is_active: boolean;
  created_at: string;
}

const WEBHOOK_EVENTS = [
  { id: 'call.started', label: 'Call Started' },
  { id: 'call.ended', label: 'Call Ended' },
  { id: 'call.transcribed', label: 'Call Transcribed' },
  { id: 'sms.received', label: 'SMS Received' },
  { id: 'sms.sent', label: 'SMS Sent' },
];

export default function IntegrationsPage() {
  const { user } = useAuth();
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newWebhook, setNewWebhook] = useState({ name: '', url: '', events: [] as string[] });

  useEffect(() => {
    fetchWebhooks();
  }, [user?.id]);

  const fetchWebhooks = async () => {
    if (!user?.id) return;
    try {
      // Simulated for now - would call actual API
      setWebhooks([]);
    } catch (error) {
      console.error('Failed to load webhooks:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddWebhook = async () => {
    if (!user?.id || !newWebhook.name || !newWebhook.url) return;
    // Add webhook logic here
    setShowAddModal(false);
    setNewWebhook({ name: '', url: '', events: [] });
    fetchWebhooks();
  };

  const toggleEvent = (eventId: string) => {
    setNewWebhook(prev => ({
      ...prev,
      events: prev.events.includes(eventId)
        ? prev.events.filter(e => e !== eventId)
        : [...prev.events, eventId]
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading integrations...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">Integrations</h1>
          <p className="text-gray-400 mt-1">Connect webhooks and external services</p>
        </div>
        <HoneycombButton onClick={() => setShowAddModal(true)}>
          Add Webhook
        </HoneycombButton>
      </div>

      {/* Webhooks */}
      <Card>
        <CardTitle>Webhooks</CardTitle>
        <CardContent>
          {webhooks.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              No webhooks configured. Add one to receive real-time notifications.
            </div>
          ) : (
            <div className="space-y-3 mt-4">
              {webhooks.map((webhook) => (
                <div key={webhook.id} className="p-4 bg-oled-gray rounded-lg">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-white font-medium">{webhook.name}</div>
                      <div className="text-gray-400 text-sm">{webhook.url}</div>
                      <div className="flex gap-1 mt-2">
                        {webhook.events.map(event => (
                          <span key={event} className="px-2 py-0.5 bg-gold/20 text-gold text-xs rounded">
                            {event}
                          </span>
                        ))}
                      </div>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      webhook.is_active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {webhook.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Available Integrations */}
      <Card>
        <CardTitle>Available Integrations</CardTitle>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
            <div className="p-4 bg-oled-gray rounded-lg">
              <div className="text-lg font-semibold text-white">Slack</div>
              <div className="text-gray-400 text-sm mt-1">Get call notifications in Slack</div>
              <HoneycombButton variant="outline" className="mt-3" size="sm">
                Coming Soon
              </HoneycombButton>
            </div>
            <div className="p-4 bg-oled-gray rounded-lg">
              <div className="text-lg font-semibold text-white">Zapier</div>
              <div className="text-gray-400 text-sm mt-1">Connect to 5000+ apps</div>
              <HoneycombButton variant="outline" className="mt-3" size="sm">
                Coming Soon
              </HoneycombButton>
            </div>
            <div className="p-4 bg-oled-gray rounded-lg">
              <div className="text-lg font-semibold text-white">Google Sheets</div>
              <div className="text-gray-400 text-sm mt-1">Auto-log calls to spreadsheet</div>
              <HoneycombButton variant="outline" className="mt-3" size="sm">
                Coming Soon
              </HoneycombButton>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Add Webhook Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-oled-dark border border-gray-800 rounded-2xl p-6 max-w-md w-full">
            <h2 className="text-2xl font-bold text-gold mb-4">Add Webhook</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Name</label>
                <input
                  type="text"
                  value={newWebhook.name}
                  onChange={(e) => setNewWebhook({ ...newWebhook, name: e.target.value })}
                  placeholder="My Webhook"
                  className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">URL</label>
                <input
                  type="url"
                  value={newWebhook.url}
                  onChange={(e) => setNewWebhook({ ...newWebhook, url: e.target.value })}
                  placeholder="https://your-server.com/webhook"
                  className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Events</label>
                <div className="space-y-2">
                  {WEBHOOK_EVENTS.map(event => (
                    <label key={event.id} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={newWebhook.events.includes(event.id)}
                        onChange={() => toggleEvent(event.id)}
                        className="rounded border-gray-700 bg-oled-gray text-gold focus:ring-gold"
                      />
                      <span className="text-white">{event.label}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <HoneycombButton variant="outline" onClick={() => setShowAddModal(false)}>
                  Cancel
                </HoneycombButton>
                <HoneycombButton onClick={handleAddWebhook}>
                  Add Webhook
                </HoneycombButton>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
