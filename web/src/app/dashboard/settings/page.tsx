'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { profileApi } from '@/lib/api';

interface SettingsState {
  ai_enabled: boolean;
  ai_greeting_enabled: boolean;
  ai_transcription_enabled: boolean;
  ai_summary_enabled: boolean;
  call_screening_enabled: boolean;
  voicemail_enabled: boolean;
  call_recording_enabled: boolean;
  call_forwarding_enabled: boolean;
  sms_enabled: boolean;
  push_notifications_enabled: boolean;
  email_notifications_enabled: boolean;
  sms_notifications_enabled: boolean;
  notify_on_missed_call: boolean;
  notify_on_voicemail: boolean;
  notify_on_urgent: boolean;
  daily_summary_enabled: boolean;
  weekly_summary_enabled: boolean;
  share_call_logs_with_team: boolean;
  theme: string;
  webhook_enabled: boolean;
  webhook_url: string;
}

const defaultSettings: SettingsState = {
  ai_enabled: true,
  ai_greeting_enabled: true,
  ai_transcription_enabled: true,
  ai_summary_enabled: true,
  call_screening_enabled: true,
  voicemail_enabled: true,
  call_recording_enabled: true,
  call_forwarding_enabled: true,
  sms_enabled: true,
  push_notifications_enabled: true,
  email_notifications_enabled: true,
  sms_notifications_enabled: false,
  notify_on_missed_call: true,
  notify_on_voicemail: true,
  notify_on_urgent: true,
  daily_summary_enabled: false,
  weekly_summary_enabled: true,
  share_call_logs_with_team: true,
  theme: 'dark',
  webhook_enabled: false,
  webhook_url: '',
};

function Toggle({ enabled, onChange, label, description }: {
  enabled: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex-1">
        <div className="text-white font-medium">{label}</div>
        {description && <div className="text-gray-500 text-sm">{description}</div>}
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={`relative w-12 h-6 rounded-full transition-colors ${
          enabled ? 'bg-gold' : 'bg-gray-700'
        }`}
      >
        <div
          className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
            enabled ? 'translate-x-7' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<SettingsState>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      if (!user?.id) return;
      try {
        const response = await profileApi.getSettings(user.id);
        setSettings({ ...defaultSettings, ...response.settings });
      } catch (error) {
        console.error('Failed to load settings:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, [user?.id]);

  const updateSetting = async (key: keyof SettingsState, value: boolean | string) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const saveSettings = async () => {
    if (!user?.id) return;
    setSaving(true);
    try {
      await profileApi.updateSettings(user.id, settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (error) {
      console.error('Failed to save settings:', error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">Settings</h1>
          <p className="text-gray-400 mt-1">Configure your assistant and preferences</p>
        </div>
        <HoneycombButton onClick={saveSettings} disabled={saving}>
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
        </HoneycombButton>
      </div>

      {/* AI Assistant */}
      <Card>
        <CardTitle>AI Assistant</CardTitle>
        <CardContent>
          <div className="divide-y divide-gray-800">
            <Toggle
              enabled={settings.ai_enabled}
              onChange={(v) => updateSetting('ai_enabled', v)}
              label="AI Assistant"
              description="Enable AI to answer and handle your calls"
            />
            <Toggle
              enabled={settings.ai_greeting_enabled}
              onChange={(v) => updateSetting('ai_greeting_enabled', v)}
              label="AI Greeting"
              description="AI greets callers with your custom message"
            />
            <Toggle
              enabled={settings.ai_transcription_enabled}
              onChange={(v) => updateSetting('ai_transcription_enabled', v)}
              label="Call Transcription"
              description="Automatically transcribe all calls"
            />
            <Toggle
              enabled={settings.ai_summary_enabled}
              onChange={(v) => updateSetting('ai_summary_enabled', v)}
              label="AI Summary"
              description="Generate summaries and key info from calls"
            />
          </div>
        </CardContent>
      </Card>

      {/* Call Handling */}
      <Card>
        <CardTitle>Call Handling</CardTitle>
        <CardContent>
          <div className="divide-y divide-gray-800">
            <Toggle
              enabled={settings.call_screening_enabled}
              onChange={(v) => updateSetting('call_screening_enabled', v)}
              label="Call Screening"
              description="AI screens calls and asks for caller info"
            />
            <Toggle
              enabled={settings.voicemail_enabled}
              onChange={(v) => updateSetting('voicemail_enabled', v)}
              label="Voicemail"
              description="Allow callers to leave voicemails"
            />
            <Toggle
              enabled={settings.call_recording_enabled}
              onChange={(v) => updateSetting('call_recording_enabled', v)}
              label="Call Recording"
              description="Record calls for review"
            />
            <Toggle
              enabled={settings.call_forwarding_enabled}
              onChange={(v) => updateSetting('call_forwarding_enabled', v)}
              label="Call Forwarding"
              description="Forward calls to your personal number"
            />
            <Toggle
              enabled={settings.sms_enabled}
              onChange={(v) => updateSetting('sms_enabled', v)}
              label="SMS Messaging"
              description="Enable SMS text messaging"
            />
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardTitle>Notifications</CardTitle>
        <CardContent>
          <div className="divide-y divide-gray-800">
            <Toggle
              enabled={settings.push_notifications_enabled}
              onChange={(v) => updateSetting('push_notifications_enabled', v)}
              label="Push Notifications"
              description="Get notified on your device"
            />
            <Toggle
              enabled={settings.email_notifications_enabled}
              onChange={(v) => updateSetting('email_notifications_enabled', v)}
              label="Email Notifications"
              description="Receive email updates"
            />
            <Toggle
              enabled={settings.sms_notifications_enabled}
              onChange={(v) => updateSetting('sms_notifications_enabled', v)}
              label="SMS Notifications"
              description="Get text message alerts"
            />
            <Toggle
              enabled={settings.notify_on_missed_call}
              onChange={(v) => updateSetting('notify_on_missed_call', v)}
              label="Missed Call Alerts"
              description="Notify when you miss a call"
            />
            <Toggle
              enabled={settings.notify_on_voicemail}
              onChange={(v) => updateSetting('notify_on_voicemail', v)}
              label="Voicemail Alerts"
              description="Notify when you receive a voicemail"
            />
            <Toggle
              enabled={settings.notify_on_urgent}
              onChange={(v) => updateSetting('notify_on_urgent', v)}
              label="Urgent Call Alerts"
              description="Immediate notification for urgent calls"
            />
          </div>
        </CardContent>
      </Card>

      {/* Summary Reports */}
      <Card>
        <CardTitle>Reports</CardTitle>
        <CardContent>
          <div className="divide-y divide-gray-800">
            <Toggle
              enabled={settings.daily_summary_enabled}
              onChange={(v) => updateSetting('daily_summary_enabled', v)}
              label="Daily Summary"
              description="Receive a daily summary of your calls"
            />
            <Toggle
              enabled={settings.weekly_summary_enabled}
              onChange={(v) => updateSetting('weekly_summary_enabled', v)}
              label="Weekly Summary"
              description="Receive a weekly activity report"
            />
          </div>
        </CardContent>
      </Card>

      {/* Team & Privacy */}
      <Card>
        <CardTitle>Team & Privacy</CardTitle>
        <CardContent>
          <div className="divide-y divide-gray-800">
            <Toggle
              enabled={settings.share_call_logs_with_team}
              onChange={(v) => updateSetting('share_call_logs_with_team', v)}
              label="Share with Team"
              description="Allow team members to see your call logs"
            />
          </div>
        </CardContent>
      </Card>

      {/* Webhooks */}
      <Card>
        <CardTitle>Integrations</CardTitle>
        <CardContent>
          <div className="space-y-4">
            <Toggle
              enabled={settings.webhook_enabled}
              onChange={(v) => updateSetting('webhook_enabled', v)}
              label="Webhooks"
              description="Send call events to your server"
            />
            {settings.webhook_enabled && (
              <div>
                <label className="block text-sm text-gray-400 mb-2">Webhook URL</label>
                <input
                  type="url"
                  value={settings.webhook_url}
                  onChange={(e) => updateSetting('webhook_url', e.target.value)}
                  placeholder="https://your-server.com/webhook"
                  className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
                />
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
