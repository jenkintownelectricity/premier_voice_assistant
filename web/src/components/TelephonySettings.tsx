'use client';

import { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import { Card, CardHeader, CardTitle, CardContent } from './Card';

// Provider info with display names and features
const PROVIDER_INFO: Record<string, { name: string; description: string; features: string[] }> = {
  twilio: {
    name: 'Twilio',
    description: 'Industry leader with global reach',
    features: ['Voice', 'SMS', 'MMS', 'SIP Trunking'],
  },
  telnyx: {
    name: 'Telnyx',
    description: 'Developer-friendly with competitive pricing',
    features: ['Voice', 'SMS', 'TeXML', 'SIP Trunking'],
  },
  plivo: {
    name: 'Plivo',
    description: 'Cost-effective global communications',
    features: ['Voice', 'SMS', 'SIP Trunking'],
  },
  vonage: {
    name: 'Vonage',
    description: 'Enterprise-grade communications',
    features: ['Voice', 'SMS', 'NCCO', 'Video'],
  },
  signalwire: {
    name: 'SignalWire',
    description: 'Twilio-compatible with lower costs',
    features: ['Voice', 'SMS', 'LaML', 'SIP'],
  },
  voipms: {
    name: 'VoIP.ms',
    description: 'Budget-friendly SIP provider',
    features: ['Voice', 'SMS', 'SIP'],
  },
};

interface ProviderStatus {
  name: string;
  configured: boolean;
  healthy: boolean;
  phone_number: string | null;
  sip_configured: boolean;
  message: string;
}

interface TelephonyStatus {
  default_provider: string | null;
  providers: ProviderStatus[];
  available_providers: string[];
}

interface PhoneNumber {
  number: string;
  provider: string;
  capabilities: string[];
  friendly_name?: string;
  region?: string;
  monthly_cost?: number;
}

interface TelephonySettingsProps {
  apiBaseUrl?: string;
  onProviderChange?: (provider: string) => void;
}

export function TelephonySettings({ apiBaseUrl = '', onProviderChange }: TelephonySettingsProps) {
  const [status, setStatus] = useState<TelephonyStatus | null>(null);
  const [phoneNumbers, setPhoneNumbers] = useState<PhoneNumber[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [settingDefault, setSettingDefault] = useState<string | null>(null);

  // Fetch telephony status
  useEffect(() => {
    async function fetchStatus() {
      try {
        const response = await fetch(`${apiBaseUrl}/telephony/status`);
        if (!response.ok) throw new Error('Failed to fetch telephony status');
        const data = await response.json();
        setStatus(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    fetchStatus();
  }, [apiBaseUrl]);

  // Fetch phone numbers
  useEffect(() => {
    async function fetchNumbers() {
      try {
        const response = await fetch(`${apiBaseUrl}/telephony/numbers`);
        if (response.ok) {
          const data = await response.json();
          setPhoneNumbers(data);
        }
      } catch (err) {
        console.warn('Failed to fetch phone numbers:', err);
      }
    }

    if (status?.providers.some(p => p.configured)) {
      fetchNumbers();
    }
  }, [apiBaseUrl, status]);

  // Set default provider
  async function setDefaultProvider(providerName: string) {
    setSettingDefault(providerName);
    try {
      const response = await fetch(`${apiBaseUrl}/telephony/providers/${providerName}/set-default`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to set default provider');

      // Update local state
      setStatus(prev => prev ? { ...prev, default_provider: providerName } : null);
      onProviderChange?.(providerName);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set default provider');
    } finally {
      setSettingDefault(null);
    }
  }

  if (loading) {
    return (
      <Card className="animate-pulse">
        <CardHeader>
          <CardTitle>Telephony Providers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-32 bg-gray-800/50 rounded" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Provider Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            Telephony Providers
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-red-300 text-sm">
              {error}
            </div>
          )}

          {status?.providers.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <p className="mb-2">No telephony providers configured.</p>
              <p className="text-sm">Set environment variables for your preferred providers.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {status?.providers.map((provider) => {
                const info = PROVIDER_INFO[provider.name] || {
                  name: provider.name,
                  description: 'Telephony provider',
                  features: [],
                };
                const isDefault = status.default_provider === provider.name;

                return (
                  <div
                    key={provider.name}
                    className={clsx(
                      'p-4 rounded-lg border transition-all',
                      isDefault
                        ? 'border-gold/50 bg-gold/5'
                        : 'border-gray-700 bg-gray-800/30 hover:border-gray-600'
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-white">{info.name}</h4>
                          {isDefault && (
                            <span className="px-2 py-0.5 text-xs bg-gold/20 text-gold rounded">
                              Default
                            </span>
                          )}
                          <span
                            className={clsx(
                              'w-2 h-2 rounded-full',
                              provider.healthy ? 'bg-green-500' : 'bg-red-500'
                            )}
                            title={provider.message}
                          />
                        </div>
                        <p className="text-sm text-gray-400 mt-1">{info.description}</p>

                        {/* Features */}
                        <div className="flex flex-wrap gap-1 mt-2">
                          {info.features.map((feature) => (
                            <span
                              key={feature}
                              className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded"
                            >
                              {feature}
                            </span>
                          ))}
                        </div>

                        {/* Phone number if available */}
                        {provider.phone_number && (
                          <p className="text-sm text-gold mt-2">
                            📞 {provider.phone_number}
                          </p>
                        )}
                      </div>

                      {/* Set as default button */}
                      {!isDefault && provider.configured && (
                        <button
                          onClick={() => setDefaultProvider(provider.name)}
                          disabled={settingDefault === provider.name}
                          className={clsx(
                            'px-3 py-1 text-sm rounded border border-gold/30 text-gold',
                            'hover:bg-gold/10 transition-colors',
                            'disabled:opacity-50 disabled:cursor-not-allowed'
                          )}
                        >
                          {settingDefault === provider.name ? 'Setting...' : 'Set Default'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Available but not configured */}
          {status && status.available_providers.length > status.providers.length && (
            <div className="mt-6 pt-4 border-t border-gray-700">
              <h4 className="text-sm font-medium text-gray-400 mb-3">Available Providers</h4>
              <div className="flex flex-wrap gap-2">
                {status.available_providers
                  .filter((p) => !status.providers.find((sp) => sp.name === p))
                  .map((providerName) => {
                    const info = PROVIDER_INFO[providerName];
                    return (
                      <div
                        key={providerName}
                        className="px-3 py-2 bg-gray-800/50 border border-gray-700 rounded-lg text-sm"
                      >
                        <span className="text-gray-300">{info?.name || providerName}</span>
                        <span className="text-gray-500 ml-2">Not configured</span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Phone Numbers Card */}
      {phoneNumbers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              Phone Numbers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-700">
                    <th className="pb-2">Number</th>
                    <th className="pb-2">Provider</th>
                    <th className="pb-2">Capabilities</th>
                    <th className="pb-2">Region</th>
                    <th className="pb-2">Cost/mo</th>
                  </tr>
                </thead>
                <tbody>
                  {phoneNumbers.map((num) => (
                    <tr key={`${num.provider}-${num.number}`} className="border-b border-gray-800">
                      <td className="py-3 font-mono text-white">{num.number}</td>
                      <td className="py-3">
                        <span className="capitalize">{num.provider}</span>
                      </td>
                      <td className="py-3">
                        <div className="flex gap-1">
                          {num.capabilities.map((cap) => (
                            <span
                              key={cap}
                              className="px-1.5 py-0.5 text-xs bg-gray-700 text-gray-300 rounded"
                            >
                              {cap}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3 text-gray-400">{num.region || '-'}</td>
                      <td className="py-3 text-gray-400">
                        {num.monthly_cost ? `$${num.monthly_cost.toFixed(2)}` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Configuration Help */}
      <Card className="bg-gray-900/50">
        <CardHeader>
          <CardTitle className="text-base">Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-400 mb-4">
            Configure providers by setting environment variables:
          </p>
          <div className="space-y-2 font-mono text-xs">
            <div className="p-2 bg-gray-800 rounded">
              <span className="text-gray-500"># Twilio</span><br />
              TWILIO_ACCOUNT_SID=ACxxxx<br />
              TWILIO_AUTH_TOKEN=xxxx<br />
              TWILIO_PHONE_NUMBER=+1234567890
            </div>
            <div className="p-2 bg-gray-800 rounded">
              <span className="text-gray-500"># Telnyx</span><br />
              TELNYX_API_KEY=KEY_xxxx<br />
              TELNYX_PHONE_NUMBER=+1234567890
            </div>
            <div className="p-2 bg-gray-800 rounded">
              <span className="text-gray-500"># Set default provider</span><br />
              TELEPHONY_PROVIDER=twilio
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default TelephonySettings;
