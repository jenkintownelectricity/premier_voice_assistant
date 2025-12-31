'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { TelephonySettings } from '@/components/TelephonySettings';
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
  // Dashboard visibility settings
  show_phone_numbers: boolean;
  show_call_logs: boolean;
  show_live_monitoring: boolean;
  show_contacts: boolean;
  show_assistants: boolean;
  show_voice_clones: boolean;
  show_usage: boolean;
  show_teams: boolean;
  show_referrals: boolean;
  show_developer: boolean;
}

// LLM Providers for API key configuration
const LLM_PROVIDERS_CONFIG = [
  { id: 'groq', name: 'Groq', docsUrl: 'https://console.groq.com/keys', placeholder: 'gsk_...' },
  { id: 'anthropic', name: 'Anthropic (Claude)', docsUrl: 'https://console.anthropic.com/settings/keys', placeholder: 'sk-ant-...' },
  { id: 'openai', name: 'OpenAI', docsUrl: 'https://platform.openai.com/api-keys', placeholder: 'sk-...' },
  { id: 'google', name: 'Google (Gemini)', docsUrl: 'https://aistudio.google.com/apikey', placeholder: 'AIza...' },
  { id: 'mistral', name: 'Mistral AI', docsUrl: 'https://console.mistral.ai/api-keys/', placeholder: '' },
  { id: 'together', name: 'Together AI', docsUrl: 'https://api.together.xyz/settings/api-keys', placeholder: '' },
  { id: 'fireworks', name: 'Fireworks AI', docsUrl: 'https://fireworks.ai/account/api-keys', placeholder: 'fw_...' },
  { id: 'deepseek', name: 'DeepSeek', docsUrl: 'https://platform.deepseek.com/api_keys', placeholder: 'sk-...' },
  { id: 'xai', name: 'xAI (Grok)', docsUrl: 'https://console.x.ai/', placeholder: 'xai-...' },
  { id: 'cohere', name: 'Cohere', docsUrl: 'https://dashboard.cohere.com/api-keys', placeholder: '' },
  { id: 'perplexity', name: 'Perplexity', docsUrl: 'https://www.perplexity.ai/settings/api', placeholder: 'pplx-...' },
];

interface ApiKeys {
  [key: string]: string;
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
  // Dashboard visibility - all enabled by default
  show_phone_numbers: true,
  show_call_logs: true,
  show_live_monitoring: true,
  show_contacts: true,
  show_assistants: true,
  show_voice_clones: true,
  show_usage: true,
  show_teams: true,
  show_referrals: true,
  show_developer: true,
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

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKeys>({});
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({});
  const [savingKeys, setSavingKeys] = useState(false);
  const [keysSaved, setKeysSaved] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      if (!user?.id) return;
      try {
        const response = await profileApi.getSettings(user.id);
        setSettings({ ...defaultSettings, ...response.settings });

        // Fetch API keys (masked)
        try {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
          const keysResponse = await fetch(`${apiUrl}/user/api-keys`, {
            headers: { 'X-User-ID': user.id },
          });
          if (keysResponse.ok) {
            const data = await keysResponse.json();
            setApiKeys(data.keys || {});
          }
        } catch {
          console.log('API keys endpoint not available yet');
        }
      } catch (error) {
        console.error('Failed to load settings:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, [user?.id]);

  const saveApiKeys = async () => {
    if (!user?.id) return;
    setSavingKeys(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';
      const response = await fetch(`${apiUrl}/user/api-keys`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id,
        },
        body: JSON.stringify({ keys: apiKeys }),
      });
      if (response.ok) {
        setKeysSaved(true);
        setTimeout(() => setKeysSaved(false), 3000);
      }
    } catch (error) {
      console.error('Failed to save API keys:', error);
    } finally {
      setSavingKeys(false);
    }
  };

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

      // Dispatch event for instant sidebar update (no refresh needed)
      const dashboardSettings = {
        show_phone_numbers: settings.show_phone_numbers,
        show_call_logs: settings.show_call_logs,
        show_live_monitoring: settings.show_live_monitoring,
        show_contacts: settings.show_contacts,
        show_assistants: settings.show_assistants,
        show_voice_clones: settings.show_voice_clones,
        show_usage: settings.show_usage,
        show_teams: settings.show_teams,
        show_referrals: settings.show_referrals,
        show_developer: settings.show_developer,
      };
      localStorage.setItem('dashboardSettings', JSON.stringify(dashboardSettings));
      window.dispatchEvent(new CustomEvent('dashboardSettingsUpdated', { detail: dashboardSettings }));
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

      {/* LLM API Keys */}
      <Card>
        <CardTitle>
          <div className="flex items-center justify-between">
            <span>LLM API Keys</span>
            <button
              onClick={saveApiKeys}
              disabled={savingKeys}
              className="text-sm px-3 py-1 bg-gold/20 hover:bg-gold/30 text-gold rounded-lg transition-colors disabled:opacity-50"
            >
              {savingKeys ? 'Saving...' : keysSaved ? 'Saved!' : 'Save Keys'}
            </button>
          </div>
        </CardTitle>
        <CardContent>
          <p className="text-gray-400 text-sm mb-4">
            Enter your API keys for the LLM providers you want to use. Keys are encrypted and stored securely.
            You only need keys for the providers you plan to use with your agents.
          </p>
          <div className="space-y-4">
            {LLM_PROVIDERS_CONFIG.map((provider) => (
              <div key={provider.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-white font-medium">{provider.name}</label>
                  <a
                    href={provider.docsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                  >
                    Get API Key
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                </div>
                <div className="relative">
                  <input
                    type={showApiKeys[provider.id] ? 'text' : 'password'}
                    value={apiKeys[provider.id] || ''}
                    onChange={(e) => setApiKeys(prev => ({ ...prev, [provider.id]: e.target.value }))}
                    placeholder={provider.placeholder || 'Enter API key...'}
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-gold focus:outline-none pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKeys(prev => ({ ...prev, [provider.id]: !prev[provider.id] }))}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                  >
                    {showApiKeys[provider.id] ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
                {apiKeys[provider.id] && (
                  <div className="flex items-center gap-1 text-xs text-green-400">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Key configured
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

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

      {/* Dashboard Visibility */}
      <Card>
        <CardTitle>Dashboard Visibility</CardTitle>
        <CardContent>
          <p className="text-gray-400 text-sm mb-4">
            Customize which sections appear in your dashboard sidebar. Hidden sections are still accessible via direct URL.
          </p>
          <div className="divide-y divide-gray-800">
            <Toggle
              enabled={settings.show_phone_numbers}
              onChange={(v) => updateSetting('show_phone_numbers', v)}
              label="Phone Numbers"
              description="Manage your business phone lines"
            />
            <Toggle
              enabled={settings.show_call_logs}
              onChange={(v) => updateSetting('show_call_logs', v)}
              label="Call Logs"
              description="View call history and transcripts"
            />
            <Toggle
              enabled={settings.show_live_monitoring}
              onChange={(v) => updateSetting('show_live_monitoring', v)}
              label="Live Monitoring"
              description="Real-time call monitoring dashboard"
            />
            <Toggle
              enabled={settings.show_contacts}
              onChange={(v) => updateSetting('show_contacts', v)}
              label="Contacts"
              description="Manage your contacts and callers"
            />
            <Toggle
              enabled={settings.show_assistants}
              onChange={(v) => updateSetting('show_assistants', v)}
              label="Assistants"
              description="Configure AI assistants"
            />
            <Toggle
              enabled={settings.show_voice_clones}
              onChange={(v) => updateSetting('show_voice_clones', v)}
              label="Voice Clones"
              description="Custom voice cloning feature"
            />
            <Toggle
              enabled={settings.show_usage}
              onChange={(v) => updateSetting('show_usage', v)}
              label="Usage"
              description="Track minutes and usage stats"
            />
            <Toggle
              enabled={settings.show_teams}
              onChange={(v) => updateSetting('show_teams', v)}
              label="Teams"
              description="Team collaboration features"
            />
            <Toggle
              enabled={settings.show_referrals}
              onChange={(v) => updateSetting('show_referrals', v)}
              label="Referrals"
              description="Referral program and rewards"
            />
            <Toggle
              enabled={settings.show_developer}
              onChange={(v) => updateSetting('show_developer', v)}
              label="Developer"
              description="API keys and developer tools"
            />
          </div>
        </CardContent>
      </Card>

      {/* Telephony Providers */}
      <TelephonySettings
        apiBaseUrl={process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app'}
      />
    </div>
  );
}
