'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { useDevMode } from '@/lib/dev-mode-context';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';

interface ServiceStatus {
  status: string;
  latency_ms: number | null;
  message: string;
}

interface StreamingStatus {
  enabled: boolean;
  stt_provider: string;
  tts_provider: string;
  target_latency_ms: number;
  message: string;
}

interface SystemStatus {
  status: string;
  timestamp: string;
  services: {
    supabase: ServiceStatus;
    anthropic: ServiceStatus;
    modal: ServiceStatus;
    stripe: ServiceStatus;
    twilio: ServiceStatus;
    deepgram?: ServiceStatus;
    cartesia?: ServiceStatus;
  };
  streaming?: StreamingStatus;
  environment: {
    python_version: string;
    env: string;
    railway_environment: string;
    api_url: string;
  };
  stats: {
    total_users: number;
    total_calls: number;
    total_assistants: number;
  };
}

const SERVICE_LINKS: Record<string, { url: string; docs: string }> = {
  supabase: {
    url: 'https://supabase.com/dashboard',
    docs: 'https://supabase.com/docs'
  },
  anthropic: {
    url: 'https://console.anthropic.com',
    docs: 'https://docs.anthropic.com'
  },
  modal: {
    url: 'https://modal.com/apps',
    docs: 'https://modal.com/docs'
  },
  stripe: {
    url: 'https://dashboard.stripe.com',
    docs: 'https://stripe.com/docs'
  },
  twilio: {
    url: 'https://console.twilio.com',
    docs: 'https://www.twilio.com/docs'
  },
  deepgram: {
    url: 'https://console.deepgram.com',
    docs: 'https://developers.deepgram.com/docs'
  },
  cartesia: {
    url: 'https://play.cartesia.ai',
    docs: 'https://docs.cartesia.ai'
  },
  railway: {
    url: 'https://railway.app/dashboard',
    docs: 'https://docs.railway.app'
  },
  vercel: {
    url: 'https://vercel.com/dashboard',
    docs: 'https://vercel.com/docs'
  },
};

export default function DeveloperDashboard() {
  const { user } = useAuth();
  const devMode = useDevMode();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/admin/status`, {
        headers: { 'X-User-ID': user?.id || 'admin' }
      });
      if (!response.ok) throw new Error('Failed to fetch status');
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to connect to backend');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [user?.id]);

  const getStatusColor = (s: string) => {
    switch (s) {
      case 'healthy':
      case 'configured':
        return 'bg-green-500';
      case 'partial':
        return 'bg-yellow-500';
      case 'error':
      case 'not_configured':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusText = (s: string) => {
    switch (s) {
      case 'healthy':
      case 'configured':
        return 'Connected';
      case 'partial':
        return 'Partial';
      case 'error':
        return 'Error';
      case 'not_configured':
        return 'Not Configured';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">Developer Dashboard</h1>
          <p className="text-gray-400 mt-1">Service connections and configuration status</p>
        </div>
        <HoneycombButton onClick={fetchStatus} disabled={loading}>
          {loading ? 'Checking...' : 'Refresh Status'}
        </HoneycombButton>
      </div>

      {error && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 text-yellow-400">
          Backend connection issue: {error}. Some status data may be unavailable.
        </div>
      )}

      {/* Developer Test Mode */}
      <Card className={devMode.isEnabled ? 'border-purple-500/50 bg-purple-900/10' : ''}>
        <CardTitle>Developer Test Mode</CardTitle>
        <CardContent>
          <div className="mt-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-white font-semibold">Test Mode</h3>
                <p className="text-gray-400 text-sm mt-1">
                  Enable developer tools to test features, simulate plans, and debug the application.
                </p>
              </div>
              <button
                onClick={devMode.toggleDevMode}
                className={`relative w-14 h-7 rounded-full transition-colors ${
                  devMode.isEnabled ? 'bg-purple-500' : 'bg-gray-600'
                }`}
              >
                <span
                  className={`absolute top-1 left-1 w-5 h-5 bg-white rounded-full transition-transform ${
                    devMode.isEnabled ? 'translate-x-7' : ''
                  }`}
                />
              </button>
            </div>

            {devMode.isEnabled && (
              <div className="p-4 bg-purple-900/20 border border-purple-500/30 rounded-lg">
                <div className="flex items-center gap-2 mb-3">
                  <span className="animate-pulse text-purple-400">●</span>
                  <span className="text-purple-300 font-medium">Test Mode Active</span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
                    <span className="text-gray-400">Simulated Plan</span>
                    <span className="text-white font-medium">{devMode.simulatedPlan || 'None'}</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
                    <span className="text-gray-400">Feature Overrides</span>
                    <span className="text-white font-medium">{Object.keys(devMode.featureOverrides).length}</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
                    <span className="text-gray-400">Mock Latency</span>
                    <span className="text-white font-medium">{devMode.mockLatency}ms</span>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
                    <span className="text-gray-400">API Logs</span>
                    <span className="text-white font-medium">{devMode.apiLogs.length}</span>
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={devMode.togglePanel}
                    className="flex-1 p-2 bg-purple-600 hover:bg-purple-500 rounded text-white text-sm font-medium transition-colors"
                  >
                    {devMode.isPanelOpen ? 'Hide DevTools Panel' : 'Open DevTools Panel'}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-3 text-center">
                  Keyboard shortcuts: Ctrl+Shift+D (toggle mode) | Ctrl+Shift+P (toggle panel)
                </p>
              </div>
            )}

            {!devMode.isEnabled && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                <div className="p-3 bg-oled-gray rounded-lg text-center">
                  <div className="text-2xl mb-1">🎛️</div>
                  <div className="text-white text-sm font-medium">Feature Flags</div>
                  <div className="text-gray-500 text-xs">Toggle features</div>
                </div>
                <div className="p-3 bg-oled-gray rounded-lg text-center">
                  <div className="text-2xl mb-1">💳</div>
                  <div className="text-white text-sm font-medium">Plan Simulator</div>
                  <div className="text-gray-500 text-xs">Test subscription tiers</div>
                </div>
                <div className="p-3 bg-oled-gray rounded-lg text-center">
                  <div className="text-2xl mb-1">⚡</div>
                  <div className="text-white text-sm font-medium">Test Actions</div>
                  <div className="text-gray-500 text-xs">Quick test operations</div>
                </div>
                <div className="p-3 bg-oled-gray rounded-lg text-center">
                  <div className="text-2xl mb-1">📊</div>
                  <div className="text-white text-sm font-medium">Debug Console</div>
                  <div className="text-gray-500 text-xs">API call logging</div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Service Connections */}
      <Card>
        <CardTitle>Service Connections</CardTitle>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
            {/* Backend Services */}
            {status?.services && Object.entries(status.services).map(([name, service]) => (
              <div key={name} className="p-4 bg-oled-gray rounded-lg border border-gray-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-white font-semibold capitalize">{name}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs ${service.status === 'healthy' || service.status === 'configured' ? 'text-green-400' : 'text-red-400'}`}>
                      {getStatusText(service.status)}
                    </span>
                    <div className={`w-3 h-3 rounded-full ${getStatusColor(service.status)}`} />
                  </div>
                </div>
                <div className="text-gray-400 text-sm mb-3">{service.message}</div>
                {service.latency_ms !== null && (
                  <div className="text-gray-500 text-xs mb-3">{service.latency_ms}ms latency</div>
                )}
                <div className="flex gap-2">
                  <a
                    href={SERVICE_LINKS[name]?.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-gold hover:text-gold-shine"
                  >
                    Dashboard
                  </a>
                  <span className="text-gray-600">|</span>
                  <a
                    href={SERVICE_LINKS[name]?.docs}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-gray-400 hover:text-white"
                  >
                    Docs
                  </a>
                </div>
              </div>
            ))}

            {/* Frontend Services (always show) */}
            <div className="p-4 bg-oled-gray rounded-lg border border-gray-800">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-semibold">Vercel</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-green-400">Hosting</span>
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                </div>
              </div>
              <div className="text-gray-400 text-sm mb-3">Frontend hosting & deployment</div>
              <div className="flex gap-2">
                <a href={SERVICE_LINKS.vercel.url} target="_blank" rel="noopener noreferrer" className="text-xs text-gold hover:text-gold-shine">
                  Dashboard
                </a>
                <span className="text-gray-600">|</span>
                <a href={SERVICE_LINKS.vercel.docs} target="_blank" rel="noopener noreferrer" className="text-xs text-gray-400 hover:text-white">
                  Docs
                </a>
              </div>
            </div>

            <div className="p-4 bg-oled-gray rounded-lg border border-gray-800">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-semibold">Railway</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-green-400">Backend</span>
                  <div className={`w-3 h-3 rounded-full ${status ? 'bg-green-500' : 'bg-yellow-500'}`} />
                </div>
              </div>
              <div className="text-gray-400 text-sm mb-3">Backend API hosting</div>
              {status?.environment?.railway_environment && (
                <div className="text-gray-500 text-xs mb-3">Env: {status.environment.railway_environment}</div>
              )}
              <div className="flex gap-2">
                <a href={SERVICE_LINKS.railway.url} target="_blank" rel="noopener noreferrer" className="text-xs text-gold hover:text-gold-shine">
                  Dashboard
                </a>
                <span className="text-gray-600">|</span>
                <a href={SERVICE_LINKS.railway.docs} target="_blank" rel="noopener noreferrer" className="text-xs text-gray-400 hover:text-white">
                  Docs
                </a>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Streaming Voice Pipeline */}
      <Card className={status?.streaming?.enabled ? 'border-green-500/30 bg-green-900/5' : 'border-yellow-500/30 bg-yellow-900/5'}>
        <CardTitle>
          <div className="flex items-center gap-3">
            <span>Streaming Voice Pipeline</span>
            {status?.streaming?.enabled ? (
              <span className="px-2 py-1 bg-green-500/20 text-green-400 text-xs rounded-full font-medium">
                Active
              </span>
            ) : (
              <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs rounded-full font-medium">
                Fallback Mode
              </span>
            )}
          </div>
        </CardTitle>
        <CardContent>
          <div className="mt-4">
            {/* Pipeline Status Banner */}
            <div className={`p-4 rounded-lg mb-4 ${status?.streaming?.enabled ? 'bg-green-500/10 border border-green-500/30' : 'bg-yellow-500/10 border border-yellow-500/30'}`}>
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-3 h-3 rounded-full ${status?.streaming?.enabled ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'}`} />
                <span className={`font-semibold ${status?.streaming?.enabled ? 'text-green-400' : 'text-yellow-400'}`}>
                  {status?.streaming?.message || 'Checking status...'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Target Latency:</span>
                  <span className={`ml-2 font-mono ${status?.streaming?.enabled ? 'text-green-400' : 'text-yellow-400'}`}>
                    {status?.streaming?.target_latency_ms || 2000}ms
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">STT Provider:</span>
                  <span className="ml-2 text-white capitalize">
                    {status?.streaming?.stt_provider || 'modal'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">TTS Provider:</span>
                  <span className="ml-2 text-white capitalize">
                    {status?.streaming?.tts_provider || 'modal'}
                  </span>
                </div>
              </div>
            </div>

            {/* Streaming Services */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Deepgram */}
              <div className={`p-4 rounded-lg border ${status?.services?.deepgram?.status === 'configured' ? 'bg-oled-gray border-green-500/30' : 'bg-oled-gray border-gray-800'}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">🎙️</span>
                    <span className="text-white font-semibold">Deepgram</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs ${status?.services?.deepgram?.status === 'configured' ? 'text-green-400' : 'text-gray-400'}`}>
                      {status?.services?.deepgram?.status === 'configured' ? 'Connected' : 'Not Configured'}
                    </span>
                    <div className={`w-3 h-3 rounded-full ${status?.services?.deepgram?.status === 'configured' ? 'bg-green-500' : 'bg-gray-500'}`} />
                  </div>
                </div>
                <div className="text-gray-400 text-sm mb-2">{status?.services?.deepgram?.message || 'Streaming STT'}</div>
                <div className="text-xs text-gray-500 mb-3">Real-time speech-to-text with &lt;300ms latency</div>
                <div className="flex gap-2">
                  <a href={SERVICE_LINKS.deepgram.url} target="_blank" rel="noopener noreferrer" className="text-xs text-gold hover:text-gold-shine">
                    Dashboard
                  </a>
                  <span className="text-gray-600">|</span>
                  <a href={SERVICE_LINKS.deepgram.docs} target="_blank" rel="noopener noreferrer" className="text-xs text-gray-400 hover:text-white">
                    Docs
                  </a>
                </div>
              </div>

              {/* Cartesia */}
              <div className={`p-4 rounded-lg border ${status?.services?.cartesia?.status === 'configured' ? 'bg-oled-gray border-green-500/30' : 'bg-oled-gray border-gray-800'}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">🔊</span>
                    <span className="text-white font-semibold">Cartesia</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs ${status?.services?.cartesia?.status === 'configured' ? 'text-green-400' : 'text-gray-400'}`}>
                      {status?.services?.cartesia?.status === 'configured' ? 'Connected' : 'Not Configured'}
                    </span>
                    <div className={`w-3 h-3 rounded-full ${status?.services?.cartesia?.status === 'configured' ? 'bg-green-500' : 'bg-gray-500'}`} />
                  </div>
                </div>
                <div className="text-gray-400 text-sm mb-2">{status?.services?.cartesia?.message || 'Streaming TTS'}</div>
                <div className="text-xs text-gray-500 mb-3">Ultra-low latency TTS with 40ms time-to-first-byte</div>
                <div className="flex gap-2">
                  <a href={SERVICE_LINKS.cartesia.url} target="_blank" rel="noopener noreferrer" className="text-xs text-gold hover:text-gold-shine">
                    Dashboard
                  </a>
                  <span className="text-gray-600">|</span>
                  <a href={SERVICE_LINKS.cartesia.docs} target="_blank" rel="noopener noreferrer" className="text-xs text-gray-400 hover:text-white">
                    Docs
                  </a>
                </div>
              </div>
            </div>

            {/* Setup Instructions */}
            {!status?.streaming?.enabled && (
              <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <h4 className="text-blue-400 font-semibold mb-2">Enable Streaming Pipeline</h4>
                <p className="text-gray-400 text-sm mb-3">
                  Configure Deepgram and Cartesia to enable sub-500ms voice latency:
                </p>
                <ol className="text-sm text-gray-300 space-y-1 list-decimal list-inside">
                  <li>Sign up at <a href="https://console.deepgram.com" target="_blank" rel="noopener noreferrer" className="text-gold hover:underline">console.deepgram.com</a> ($200 free credit)</li>
                  <li>Sign up at <a href="https://play.cartesia.ai" target="_blank" rel="noopener noreferrer" className="text-gold hover:underline">play.cartesia.ai</a></li>
                  <li>Add <code className="text-xs bg-zinc-800 px-1 py-0.5 rounded">DEEPGRAM_API_KEY</code> and <code className="text-xs bg-zinc-800 px-1 py-0.5 rounded">CARTESIA_API_KEY</code> to Railway</li>
                  <li>Optionally set <code className="text-xs bg-zinc-800 px-1 py-0.5 rounded">CARTESIA_VOICE_ID</code> for custom voice</li>
                </ol>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Environment Info */}
      <Card>
        <CardTitle>Environment Configuration</CardTitle>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div className="p-4 bg-oled-gray rounded-lg">
              <div className="text-gray-400 text-sm">API URL</div>
              <div className="text-white font-mono text-sm mt-1 break-all">
                {status?.environment?.api_url || API_URL}
              </div>
            </div>
            <div className="p-4 bg-oled-gray rounded-lg">
              <div className="text-gray-400 text-sm">Environment</div>
              <div className="text-white mt-1">
                {status?.environment?.env || 'production'}
              </div>
            </div>
            <div className="p-4 bg-oled-gray rounded-lg">
              <div className="text-gray-400 text-sm">Python Version</div>
              <div className="text-white mt-1">
                {status?.environment?.python_version || 'N/A'}
              </div>
            </div>
            <div className="p-4 bg-oled-gray rounded-lg">
              <div className="text-gray-400 text-sm">Frontend Build</div>
              <div className="text-white mt-1">Next.js 14 + React 18</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Links */}
      <Card>
        <CardTitle>Quick Links</CardTitle>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
            <a
              href="https://supabase.com/dashboard"
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 bg-oled-gray rounded-lg text-center hover:bg-gray-800 transition-colors"
            >
              <div className="text-2xl mb-1">🗄️</div>
              <div className="text-white text-sm">Supabase</div>
            </a>
            <a
              href="https://railway.app/dashboard"
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 bg-oled-gray rounded-lg text-center hover:bg-gray-800 transition-colors"
            >
              <div className="text-2xl mb-1">🚂</div>
              <div className="text-white text-sm">Railway</div>
            </a>
            <a
              href="https://vercel.com/dashboard"
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 bg-oled-gray rounded-lg text-center hover:bg-gray-800 transition-colors"
            >
              <div className="text-2xl mb-1">▲</div>
              <div className="text-white text-sm">Vercel</div>
            </a>
            <a
              href="https://modal.com/apps"
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 bg-oled-gray rounded-lg text-center hover:bg-gray-800 transition-colors"
            >
              <div className="text-2xl mb-1">⚡</div>
              <div className="text-white text-sm">Modal</div>
            </a>
            <a
              href="https://console.anthropic.com"
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 bg-oled-gray rounded-lg text-center hover:bg-gray-800 transition-colors"
            >
              <div className="text-2xl mb-1">🤖</div>
              <div className="text-white text-sm">Anthropic</div>
            </a>
            <a
              href="https://dashboard.stripe.com"
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 bg-oled-gray rounded-lg text-center hover:bg-gray-800 transition-colors"
            >
              <div className="text-2xl mb-1">💳</div>
              <div className="text-white text-sm">Stripe</div>
            </a>
            <a
              href="https://console.twilio.com"
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 bg-oled-gray rounded-lg text-center hover:bg-gray-800 transition-colors"
            >
              <div className="text-2xl mb-1">📞</div>
              <div className="text-white text-sm">Twilio</div>
            </a>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 bg-oled-gray rounded-lg text-center hover:bg-gray-800 transition-colors"
            >
              <div className="text-2xl mb-1">🐙</div>
              <div className="text-white text-sm">GitHub</div>
            </a>
          </div>
        </CardContent>
      </Card>

      {/* API Keys Status */}
      <Card>
        <CardTitle>Required Environment Variables</CardTitle>
        <CardContent>
          <div className="mt-4 space-y-2 text-sm">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {[
                'SUPABASE_URL',
                'SUPABASE_SERVICE_ROLE_KEY',
                'ANTHROPIC_API_KEY',
                'STRIPE_SECRET_KEY',
                'STRIPE_WEBHOOK_SECRET',
                'TWILIO_ACCOUNT_SID',
                'TWILIO_AUTH_TOKEN',
                'TWILIO_PHONE_NUMBER',
                'MODAL_TOKEN_ID',
                'API_URL',
              ].map((key) => (
                <div key={key} className="flex items-center gap-2 p-2 bg-oled-gray rounded">
                  <div className={`w-2 h-2 rounded-full ${
                    status?.services ? 'bg-green-500' : 'bg-gray-500'
                  }`} />
                  <span className="text-gray-400 font-mono text-xs">{key}</span>
                </div>
              ))}
            </div>
            <p className="text-gray-500 text-xs mt-4">
              Configure these in Railway dashboard under Variables section.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Last Updated */}
      {status?.timestamp && (
        <div className="text-center text-gray-500 text-sm">
          Last checked: {new Date(status.timestamp).toLocaleString()}
        </div>
      )}
    </div>
  );
}
