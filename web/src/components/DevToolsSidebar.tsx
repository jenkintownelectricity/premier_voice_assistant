'use client';

import { useState } from 'react';
import { useDevMode, PLAN_FEATURES, PLAN_LIMITS, FeatureFlags } from '@/lib/dev-mode-context';
import { useAuth } from '@/lib/auth-context';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';

// Tab icons
const FeatureIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
  </svg>
);

const PlanIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
  </svg>
);

const ActionsIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const ConsoleIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
);

const StateIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
  </svg>
);

// Feature Flags Panel
function FeatureFlagsPanel() {
  const { featureOverrides, toggleFeature, resetFeatures, simulatedPlan, getEffectiveFeatures } = useDevMode();
  const effectiveFeatures = getEffectiveFeatures();

  const featureLabels: Record<keyof FeatureFlags, string> = {
    voiceCalls: 'Voice Calls',
    smsMessaging: 'SMS Messaging',
    voiceCloning: 'Voice Cloning',
    teamCollaboration: 'Team Collaboration',
    apiAccess: 'API Access',
    webhooks: 'Webhooks',
    customVoices: 'Custom Voices',
    callRecording: 'Call Recording',
    callTranscription: 'Call Transcription',
    aiSummaries: 'AI Summaries',
    budgetAlerts: 'Budget Alerts',
    advancedAnalytics: 'Advanced Analytics',
    prioritySupport: 'Priority Support',
  };

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-xs text-gray-400">Feature Flags</span>
        <button
          onClick={resetFeatures}
          className="text-xs text-gold hover:text-gold-shine"
        >
          Reset All
        </button>
      </div>
      <div className="space-y-1 max-h-80 overflow-y-auto">
        {(Object.keys(featureLabels) as Array<keyof FeatureFlags>).map((feature) => {
          const isOverridden = featureOverrides[feature] !== undefined;
          const planDefault = simulatedPlan ? PLAN_FEATURES[simulatedPlan]?.[feature] : undefined;

          return (
            <div
              key={feature}
              className={`flex items-center justify-between p-2 rounded text-xs ${
                isOverridden ? 'bg-gold/10 border border-gold/30' : 'bg-zinc-800/50'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-white">{featureLabels[feature]}</span>
                {isOverridden && (
                  <span className="text-[10px] text-gold px-1 bg-gold/20 rounded">OVERRIDE</span>
                )}
              </div>
              <button
                onClick={() => toggleFeature(feature)}
                className={`relative w-10 h-5 rounded-full transition-colors ${
                  effectiveFeatures[feature] ? 'bg-green-500' : 'bg-gray-600'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
                    effectiveFeatures[feature] ? 'translate-x-5' : ''
                  }`}
                />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Plan Simulator Panel
function PlanSimulatorPanel() {
  const { simulatedPlan, simulatePlan, simulatedUsage, setSimulatedUsage, getCurrentPlanLimits } = useDevMode();
  const limits = getCurrentPlanLimits();

  const plans = [
    { id: null, name: 'Actual Plan', color: 'gray' },
    { id: 'free', name: 'Free', color: 'gray' },
    { id: 'starter', name: 'Starter', color: 'blue' },
    { id: 'pro', name: 'Pro', color: 'gold' },
    { id: 'enterprise', name: 'Enterprise', color: 'purple' },
  ];

  return (
    <div className="space-y-4">
      <div>
        <span className="text-xs text-gray-400">Simulate Plan</span>
        <div className="grid grid-cols-2 gap-2 mt-2">
          {plans.map((plan) => (
            <button
              key={plan.id ?? 'actual'}
              onClick={() => simulatePlan(plan.id)}
              className={`p-2 rounded text-xs font-medium transition-all ${
                simulatedPlan === plan.id
                  ? 'bg-gold text-black'
                  : 'bg-zinc-800 text-white hover:bg-zinc-700'
              }`}
            >
              {plan.name}
            </button>
          ))}
        </div>
      </div>

      {simulatedPlan && (
        <div className="p-3 bg-zinc-800/50 rounded-lg space-y-2">
          <div className="text-xs text-gray-400">Plan Limits</div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-lg font-bold text-gold">
                {limits.minutes === -1 ? '∞' : limits.minutes.toLocaleString()}
              </div>
              <div className="text-[10px] text-gray-500">Minutes</div>
            </div>
            <div>
              <div className="text-lg font-bold text-gold">
                {limits.assistants === -1 ? '∞' : limits.assistants}
              </div>
              <div className="text-[10px] text-gray-500">Assistants</div>
            </div>
            <div>
              <div className="text-lg font-bold text-gold">
                {limits.voiceClones === -1 ? '∞' : limits.voiceClones}
              </div>
              <div className="text-[10px] text-gray-500">Voice Clones</div>
            </div>
          </div>
        </div>
      )}

      <div>
        <span className="text-xs text-gray-400">Simulate Usage</span>
        <div className="mt-2 space-y-2">
          <div>
            <label className="text-[10px] text-gray-500">Minutes Used</label>
            <input
              type="number"
              value={simulatedUsage?.minutesUsed ?? 0}
              onChange={(e) => setSimulatedUsage({
                minutesUsed: parseInt(e.target.value) || 0,
                bonusMinutes: simulatedUsage?.bonusMinutes ?? 0,
              })}
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-white text-xs"
            />
          </div>
          <div>
            <label className="text-[10px] text-gray-500">Bonus Minutes</label>
            <input
              type="number"
              value={simulatedUsage?.bonusMinutes ?? 0}
              onChange={(e) => setSimulatedUsage({
                minutesUsed: simulatedUsage?.minutesUsed ?? 0,
                bonusMinutes: parseInt(e.target.value) || 0,
              })}
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-white text-xs"
            />
          </div>
          <button
            onClick={() => setSimulatedUsage(null)}
            className="w-full text-xs text-gray-400 hover:text-white"
          >
            Clear Usage Simulation
          </button>
        </div>
      </div>
    </div>
  );
}

// Test Actions Panel
function TestActionsPanel() {
  const { user } = useAuth();
  const { mockLatency, setMockLatency, forceErrors, toggleForceErrors, logApiCall } = useDevMode();
  const [actionStatus, setActionStatus] = useState<Record<string, 'idle' | 'loading' | 'success' | 'error'>>({});

  const runAction = async (actionId: string, action: () => Promise<void>) => {
    setActionStatus(prev => ({ ...prev, [actionId]: 'loading' }));
    try {
      await action();
      setActionStatus(prev => ({ ...prev, [actionId]: 'success' }));
      setTimeout(() => setActionStatus(prev => ({ ...prev, [actionId]: 'idle' })), 2000);
    } catch (e) {
      setActionStatus(prev => ({ ...prev, [actionId]: 'error' }));
      setTimeout(() => setActionStatus(prev => ({ ...prev, [actionId]: 'idle' })), 3000);
    }
  };

  const actions = [
    {
      id: 'test-call',
      label: 'Simulate Test Call',
      icon: '📞',
      action: async () => {
        const start = Date.now();
        const res = await fetch(`${API_URL}/health`);
        logApiCall({
          method: 'GET',
          url: '/health',
          status: res.status,
          duration: Date.now() - start,
        });
      },
    },
    {
      id: 'add-minutes',
      label: 'Add 100 Test Minutes',
      icon: '⏱️',
      action: async () => {
        // Simulated - would call actual API in production
        await new Promise(r => setTimeout(r, 500));
      },
    },
    {
      id: 'trigger-webhook',
      label: 'Trigger Test Webhook',
      icon: '🔔',
      action: async () => {
        await new Promise(r => setTimeout(r, 300));
      },
    },
    {
      id: 'generate-data',
      label: 'Generate Sample Data',
      icon: '📊',
      action: async () => {
        await new Promise(r => setTimeout(r, 800));
      },
    },
    {
      id: 'clear-cache',
      label: 'Clear Local Cache',
      icon: '🗑️',
      action: async () => {
        localStorage.removeItem('hive215_cache');
        sessionStorage.clear();
      },
    },
    {
      id: 'test-error',
      label: 'Trigger Test Error',
      icon: '💥',
      action: async () => {
        throw new Error('Test error triggered');
      },
    },
  ];

  const getButtonClass = (status: string) => {
    switch (status) {
      case 'loading':
        return 'bg-zinc-700 cursor-wait';
      case 'success':
        return 'bg-green-600';
      case 'error':
        return 'bg-red-600';
      default:
        return 'bg-zinc-800 hover:bg-zinc-700';
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <span className="text-xs text-gray-400">Quick Actions</span>
        <div className="grid grid-cols-2 gap-2 mt-2">
          {actions.map((action) => (
            <button
              key={action.id}
              onClick={() => runAction(action.id, action.action)}
              disabled={actionStatus[action.id] === 'loading'}
              className={`p-2 rounded text-xs transition-colors ${getButtonClass(actionStatus[action.id] || 'idle')}`}
            >
              <span className="mr-1">{action.icon}</span>
              {actionStatus[action.id] === 'loading' ? 'Running...' : action.label}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-zinc-700 pt-4">
        <span className="text-xs text-gray-400">Network Simulation</span>
        <div className="mt-2 space-y-3">
          <div>
            <label className="text-[10px] text-gray-500">Mock Latency (ms)</label>
            <input
              type="range"
              min="0"
              max="5000"
              step="100"
              value={mockLatency}
              onChange={(e) => setMockLatency(parseInt(e.target.value))}
              className="w-full"
            />
            <div className="text-xs text-center text-gold">{mockLatency}ms</div>
          </div>

          <div className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
            <span className="text-xs text-white">Force API Errors</span>
            <button
              onClick={toggleForceErrors}
              className={`relative w-10 h-5 rounded-full transition-colors ${
                forceErrors ? 'bg-red-500' : 'bg-gray-600'
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
                  forceErrors ? 'translate-x-5' : ''
                }`}
              />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Debug Console Panel
function DebugConsolePanel() {
  const { apiLogs, clearApiLogs, isLoggingEnabled, toggleLogging } = useDevMode();

  const getStatusColor = (status: number) => {
    if (status >= 200 && status < 300) return 'text-green-400';
    if (status >= 400 && status < 500) return 'text-yellow-400';
    if (status >= 500) return 'text-red-400';
    return 'text-gray-400';
  };

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">API Console</span>
          <span className={`w-2 h-2 rounded-full ${isLoggingEnabled ? 'bg-green-500' : 'bg-gray-500'}`} />
        </div>
        <div className="flex gap-2">
          <button
            onClick={toggleLogging}
            className="text-xs text-gray-400 hover:text-white"
          >
            {isLoggingEnabled ? 'Pause' : 'Resume'}
          </button>
          <button
            onClick={clearApiLogs}
            className="text-xs text-red-400 hover:text-red-300"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="bg-zinc-900 rounded-lg p-2 h-64 overflow-y-auto font-mono text-[10px]">
        {apiLogs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">No API calls logged yet</div>
        ) : (
          apiLogs.map((log) => (
            <div key={log.id} className="border-b border-zinc-800 py-1 hover:bg-zinc-800/50">
              <div className="flex items-center gap-2">
                <span className={`font-bold ${
                  log.method === 'GET' ? 'text-blue-400' :
                  log.method === 'POST' ? 'text-green-400' :
                  log.method === 'PUT' ? 'text-yellow-400' :
                  log.method === 'DELETE' ? 'text-red-400' : 'text-gray-400'
                }`}>
                  {log.method}
                </span>
                <span className="text-gray-300 truncate flex-1">{log.url}</span>
                <span className={getStatusColor(log.status)}>{log.status}</span>
                <span className="text-gray-500">{log.duration}ms</span>
              </div>
              {log.error && (
                <div className="text-red-400 mt-1 pl-4">{log.error}</div>
              )}
            </div>
          ))
        )}
      </div>

      <div className="text-[10px] text-gray-500 text-center">
        {apiLogs.length} requests logged
      </div>
    </div>
  );
}

// State Inspector Panel
function StateInspectorPanel() {
  const { user } = useAuth();
  const devMode = useDevMode();
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const stateData = {
    'User': {
      id: user?.id || 'Not logged in',
      email: user?.email || '-',
    },
    'Dev Mode': {
      simulatedPlan: devMode.simulatedPlan || 'None',
      mockLatency: `${devMode.mockLatency}ms`,
      forceErrors: devMode.forceErrors ? 'Yes' : 'No',
      loggingEnabled: devMode.isLoggingEnabled ? 'Yes' : 'No',
    },
    'Feature Overrides': devMode.featureOverrides,
    'Simulated Usage': devMode.simulatedUsage || 'None',
    'Environment': {
      apiUrl: API_URL,
      nodeEnv: process.env.NODE_ENV,
    },
  };

  return (
    <div className="space-y-2">
      <span className="text-xs text-gray-400">State Inspector</span>
      {Object.entries(stateData).map(([section, data]) => (
        <div key={section} className="bg-zinc-800/50 rounded overflow-hidden">
          <button
            onClick={() => toggleSection(section)}
            className="w-full flex justify-between items-center p-2 text-xs text-white hover:bg-zinc-700/50"
          >
            <span>{section}</span>
            <span className="text-gray-500">{expandedSections[section] ? '−' : '+'}</span>
          </button>
          {expandedSections[section] && (
            <div className="p-2 border-t border-zinc-700 font-mono text-[10px]">
              <pre className="text-gray-300 whitespace-pre-wrap overflow-x-auto">
                {JSON.stringify(data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      ))}

      <div className="pt-2 space-y-2">
        <button
          onClick={() => {
            const state = { user, devMode: devMode.getEffectiveFeatures() };
            devMode.saveStateSnapshot(`Snapshot ${Date.now()}`, state);
          }}
          className="w-full p-2 bg-zinc-800 hover:bg-zinc-700 rounded text-xs text-white"
        >
          Save State Snapshot
        </button>
        {devMode.stateSnapshots.length > 0 && (
          <div className="text-[10px] text-gray-500">
            {devMode.stateSnapshots.length} snapshots saved
          </div>
        )}
      </div>
    </div>
  );
}

// Main DevTools Sidebar Component
export function DevToolsSidebar() {
  const { isEnabled, isPanelOpen, togglePanel, activeTab, setActiveTab, toggleDevMode } = useDevMode();

  if (!isEnabled) return null;

  const tabs = [
    { id: 'features' as const, icon: <FeatureIcon />, label: 'Features' },
    { id: 'plans' as const, icon: <PlanIcon />, label: 'Plans' },
    { id: 'actions' as const, icon: <ActionsIcon />, label: 'Actions' },
    { id: 'console' as const, icon: <ConsoleIcon />, label: 'Console' },
    { id: 'state' as const, icon: <StateIcon />, label: 'State' },
  ];

  return (
    <>
      {/* Dev Mode Banner */}
      <div className="fixed top-0 left-0 right-0 bg-gradient-to-r from-purple-600 via-pink-500 to-purple-600 text-white text-xs py-1 px-4 flex justify-between items-center z-[100]">
        <div className="flex items-center gap-2">
          <span className="animate-pulse">●</span>
          <span className="font-semibold">DEVELOPER MODE</span>
          <span className="text-white/70">|</span>
          <span className="text-white/70">Ctrl+Shift+D to toggle</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={togglePanel}
            className="hover:text-white/80 transition-colors"
          >
            {isPanelOpen ? 'Hide Panel' : 'Show Panel'}
          </button>
          <button
            onClick={toggleDevMode}
            className="bg-white/20 hover:bg-white/30 px-2 py-0.5 rounded transition-colors"
          >
            Exit Dev Mode
          </button>
        </div>
      </div>

      {/* Floating Toggle Button (when panel is closed) */}
      {!isPanelOpen && (
        <button
          onClick={togglePanel}
          className="fixed right-4 bottom-4 w-12 h-12 bg-purple-600 hover:bg-purple-500 rounded-full shadow-lg flex items-center justify-center z-[99] transition-all hover:scale-110"
          title="Open DevTools (Ctrl+Shift+P)"
        >
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
        </button>
      )}

      {/* DevTools Panel */}
      {isPanelOpen && (
        <div className="fixed right-0 top-7 bottom-0 w-80 bg-zinc-900 border-l border-zinc-700 shadow-2xl z-[99] flex flex-col">
          {/* Panel Header */}
          <div className="p-3 border-b border-zinc-700 flex justify-between items-center bg-zinc-800">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              <span className="font-semibold text-white text-sm">DevTools</span>
            </div>
            <button
              onClick={togglePanel}
              className="text-gray-400 hover:text-white"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Tab Bar */}
          <div className="flex border-b border-zinc-700 bg-zinc-800/50">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 p-2 flex flex-col items-center gap-1 transition-colors ${
                  activeTab === tab.id
                    ? 'text-purple-400 border-b-2 border-purple-400 bg-zinc-800'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
                title={tab.label}
              >
                {tab.icon}
                <span className="text-[10px]">{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Panel Content */}
          <div className="flex-1 overflow-y-auto p-3">
            {activeTab === 'features' && <FeatureFlagsPanel />}
            {activeTab === 'plans' && <PlanSimulatorPanel />}
            {activeTab === 'actions' && <TestActionsPanel />}
            {activeTab === 'console' && <DebugConsolePanel />}
            {activeTab === 'state' && <StateInspectorPanel />}
          </div>

          {/* Panel Footer */}
          <div className="p-2 border-t border-zinc-700 bg-zinc-800/50">
            <div className="text-[10px] text-gray-500 text-center">
              HIVE215 DevTools v1.0 | Ctrl+Shift+P to toggle
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default DevToolsSidebar;
