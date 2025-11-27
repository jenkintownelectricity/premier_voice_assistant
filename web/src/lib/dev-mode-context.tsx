'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

// Feature flags that can be toggled
export interface FeatureFlags {
  voiceCalls: boolean;
  smsMessaging: boolean;
  voiceCloning: boolean;
  teamCollaboration: boolean;
  apiAccess: boolean;
  webhooks: boolean;
  customVoices: boolean;
  callRecording: boolean;
  callTranscription: boolean;
  aiSummaries: boolean;
  budgetAlerts: boolean;
  advancedAnalytics: boolean;
  prioritySupport: boolean;
}

// Plan definitions with their feature sets
export const PLAN_FEATURES: Record<string, Partial<FeatureFlags>> = {
  free: {
    voiceCalls: true,
    smsMessaging: false,
    voiceCloning: false,
    teamCollaboration: false,
    apiAccess: false,
    webhooks: false,
    customVoices: false,
    callRecording: false,
    callTranscription: true,
    aiSummaries: false,
    budgetAlerts: false,
    advancedAnalytics: false,
    prioritySupport: false,
  },
  starter: {
    voiceCalls: true,
    smsMessaging: true,
    voiceCloning: false,
    teamCollaboration: false,
    apiAccess: true,
    webhooks: true,
    customVoices: false,
    callRecording: true,
    callTranscription: true,
    aiSummaries: true,
    budgetAlerts: true,
    advancedAnalytics: false,
    prioritySupport: false,
  },
  pro: {
    voiceCalls: true,
    smsMessaging: true,
    voiceCloning: true,
    teamCollaboration: true,
    apiAccess: true,
    webhooks: true,
    customVoices: true,
    callRecording: true,
    callTranscription: true,
    aiSummaries: true,
    budgetAlerts: true,
    advancedAnalytics: true,
    prioritySupport: true,
  },
  enterprise: {
    voiceCalls: true,
    smsMessaging: true,
    voiceCloning: true,
    teamCollaboration: true,
    apiAccess: true,
    webhooks: true,
    customVoices: true,
    callRecording: true,
    callTranscription: true,
    aiSummaries: true,
    budgetAlerts: true,
    advancedAnalytics: true,
    prioritySupport: true,
  },
};

export const PLAN_LIMITS: Record<string, { minutes: number; assistants: number; voiceClones: number }> = {
  free: { minutes: 100, assistants: 1, voiceClones: 0 },
  starter: { minutes: 2000, assistants: 5, voiceClones: 2 },
  pro: { minutes: 10000, assistants: 25, voiceClones: 10 },
  enterprise: { minutes: -1, assistants: -1, voiceClones: -1 }, // unlimited
};

// API call log entry
export interface ApiLogEntry {
  id: string;
  timestamp: Date;
  method: string;
  url: string;
  status: number;
  duration: number;
  requestBody?: any;
  responseBody?: any;
  error?: string;
}

// Dev mode state
interface DevModeState {
  // Core state
  isEnabled: boolean;
  isPanelOpen: boolean;
  activeTab: 'features' | 'plans' | 'actions' | 'console' | 'state';

  // Feature overrides
  featureOverrides: Partial<FeatureFlags>;

  // Plan simulation
  simulatedPlan: string | null;
  simulatedUsage: {
    minutesUsed: number;
    bonusMinutes: number;
  } | null;

  // API logging
  apiLogs: ApiLogEntry[];
  isLoggingEnabled: boolean;

  // Test mode
  mockLatency: number; // ms to add to API calls
  forceErrors: boolean;

  // State snapshots
  stateSnapshots: { name: string; timestamp: Date; state: any }[];
}

interface DevModeContextType extends DevModeState {
  // Actions
  toggleDevMode: () => void;
  togglePanel: () => void;
  setActiveTab: (tab: DevModeState['activeTab']) => void;

  // Feature flags
  toggleFeature: (feature: keyof FeatureFlags) => void;
  resetFeatures: () => void;
  isFeatureEnabled: (feature: keyof FeatureFlags) => boolean;

  // Plan simulation
  simulatePlan: (plan: string | null) => void;
  setSimulatedUsage: (usage: DevModeState['simulatedUsage']) => void;
  getCurrentPlanLimits: () => typeof PLAN_LIMITS['free'];

  // API logging
  logApiCall: (entry: Omit<ApiLogEntry, 'id' | 'timestamp'>) => void;
  clearApiLogs: () => void;
  toggleLogging: () => void;

  // Test controls
  setMockLatency: (ms: number) => void;
  toggleForceErrors: () => void;

  // State management
  saveStateSnapshot: (name: string, state: any) => void;
  loadStateSnapshot: (name: string) => any;
  clearSnapshots: () => void;

  // Computed
  getEffectiveFeatures: () => FeatureFlags;
  getEffectivePlan: () => string;
}

const DevModeContext = createContext<DevModeContextType | null>(null);

const DEFAULT_FEATURES: FeatureFlags = {
  voiceCalls: true,
  smsMessaging: true,
  voiceCloning: true,
  teamCollaboration: true,
  apiAccess: true,
  webhooks: true,
  customVoices: true,
  callRecording: true,
  callTranscription: true,
  aiSummaries: true,
  budgetAlerts: true,
  advancedAnalytics: true,
  prioritySupport: true,
};

export function DevModeProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<DevModeState>({
    isEnabled: false,
    isPanelOpen: false,
    activeTab: 'features',
    featureOverrides: {},
    simulatedPlan: null,
    simulatedUsage: null,
    apiLogs: [],
    isLoggingEnabled: true,
    mockLatency: 0,
    forceErrors: false,
    stateSnapshots: [],
  });

  // Load state from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('hive215_dev_mode');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setState(prev => ({
          ...prev,
          isEnabled: parsed.isEnabled || false,
          featureOverrides: parsed.featureOverrides || {},
          simulatedPlan: parsed.simulatedPlan || null,
          isLoggingEnabled: parsed.isLoggingEnabled ?? true,
          mockLatency: parsed.mockLatency || 0,
        }));
      } catch (e) {
        console.error('Failed to load dev mode state:', e);
      }
    }
  }, []);

  // Save state to localStorage
  useEffect(() => {
    localStorage.setItem('hive215_dev_mode', JSON.stringify({
      isEnabled: state.isEnabled,
      featureOverrides: state.featureOverrides,
      simulatedPlan: state.simulatedPlan,
      isLoggingEnabled: state.isLoggingEnabled,
      mockLatency: state.mockLatency,
    }));
  }, [state.isEnabled, state.featureOverrides, state.simulatedPlan, state.isLoggingEnabled, state.mockLatency]);

  // Keyboard shortcut: Ctrl+Shift+D to toggle dev mode
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        setState(prev => ({ ...prev, isEnabled: !prev.isEnabled, isPanelOpen: !prev.isEnabled }));
      }
      // Ctrl+Shift+P to toggle panel when dev mode is on
      if (e.ctrlKey && e.shiftKey && e.key === 'P' && state.isEnabled) {
        e.preventDefault();
        setState(prev => ({ ...prev, isPanelOpen: !prev.isPanelOpen }));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [state.isEnabled]);

  const toggleDevMode = useCallback(() => {
    setState(prev => ({
      ...prev,
      isEnabled: !prev.isEnabled,
      isPanelOpen: !prev.isEnabled // Open panel when enabling
    }));
  }, []);

  const togglePanel = useCallback(() => {
    setState(prev => ({ ...prev, isPanelOpen: !prev.isPanelOpen }));
  }, []);

  const setActiveTab = useCallback((tab: DevModeState['activeTab']) => {
    setState(prev => ({ ...prev, activeTab: tab }));
  }, []);

  const toggleFeature = useCallback((feature: keyof FeatureFlags) => {
    setState(prev => ({
      ...prev,
      featureOverrides: {
        ...prev.featureOverrides,
        [feature]: prev.featureOverrides[feature] === undefined
          ? !DEFAULT_FEATURES[feature]
          : !prev.featureOverrides[feature],
      },
    }));
  }, []);

  const resetFeatures = useCallback(() => {
    setState(prev => ({ ...prev, featureOverrides: {} }));
  }, []);

  const isFeatureEnabled = useCallback((feature: keyof FeatureFlags): boolean => {
    // Check override first
    if (state.featureOverrides[feature] !== undefined) {
      return state.featureOverrides[feature]!;
    }
    // Then check simulated plan
    if (state.simulatedPlan && PLAN_FEATURES[state.simulatedPlan]) {
      return PLAN_FEATURES[state.simulatedPlan][feature] ?? DEFAULT_FEATURES[feature];
    }
    // Default to all enabled in dev mode
    return DEFAULT_FEATURES[feature];
  }, [state.featureOverrides, state.simulatedPlan]);

  const simulatePlan = useCallback((plan: string | null) => {
    setState(prev => ({ ...prev, simulatedPlan: plan }));
  }, []);

  const setSimulatedUsage = useCallback((usage: DevModeState['simulatedUsage']) => {
    setState(prev => ({ ...prev, simulatedUsage: usage }));
  }, []);

  const getCurrentPlanLimits = useCallback(() => {
    const plan = state.simulatedPlan || 'pro';
    return PLAN_LIMITS[plan] || PLAN_LIMITS.free;
  }, [state.simulatedPlan]);

  const logApiCall = useCallback((entry: Omit<ApiLogEntry, 'id' | 'timestamp'>) => {
    if (!state.isLoggingEnabled) return;
    setState(prev => ({
      ...prev,
      apiLogs: [
        { ...entry, id: crypto.randomUUID(), timestamp: new Date() },
        ...prev.apiLogs.slice(0, 99), // Keep last 100 entries
      ],
    }));
  }, [state.isLoggingEnabled]);

  const clearApiLogs = useCallback(() => {
    setState(prev => ({ ...prev, apiLogs: [] }));
  }, []);

  const toggleLogging = useCallback(() => {
    setState(prev => ({ ...prev, isLoggingEnabled: !prev.isLoggingEnabled }));
  }, []);

  const setMockLatency = useCallback((ms: number) => {
    setState(prev => ({ ...prev, mockLatency: ms }));
  }, []);

  const toggleForceErrors = useCallback(() => {
    setState(prev => ({ ...prev, forceErrors: !prev.forceErrors }));
  }, []);

  const saveStateSnapshot = useCallback((name: string, currentState: any) => {
    setState(prev => ({
      ...prev,
      stateSnapshots: [
        { name, timestamp: new Date(), state: currentState },
        ...prev.stateSnapshots.slice(0, 9), // Keep last 10
      ],
    }));
  }, []);

  const loadStateSnapshot = useCallback((name: string) => {
    return state.stateSnapshots.find(s => s.name === name)?.state;
  }, [state.stateSnapshots]);

  const clearSnapshots = useCallback(() => {
    setState(prev => ({ ...prev, stateSnapshots: [] }));
  }, []);

  const getEffectiveFeatures = useCallback((): FeatureFlags => {
    const base = state.simulatedPlan
      ? { ...DEFAULT_FEATURES, ...PLAN_FEATURES[state.simulatedPlan] }
      : DEFAULT_FEATURES;
    return { ...base, ...state.featureOverrides } as FeatureFlags;
  }, [state.simulatedPlan, state.featureOverrides]);

  const getEffectivePlan = useCallback(() => {
    return state.simulatedPlan || 'pro';
  }, [state.simulatedPlan]);

  const value: DevModeContextType = {
    ...state,
    toggleDevMode,
    togglePanel,
    setActiveTab,
    toggleFeature,
    resetFeatures,
    isFeatureEnabled,
    simulatePlan,
    setSimulatedUsage,
    getCurrentPlanLimits,
    logApiCall,
    clearApiLogs,
    toggleLogging,
    setMockLatency,
    toggleForceErrors,
    saveStateSnapshot,
    loadStateSnapshot,
    clearSnapshots,
    getEffectiveFeatures,
    getEffectivePlan,
  };

  return (
    <DevModeContext.Provider value={value}>
      {children}
    </DevModeContext.Provider>
  );
}

export function useDevMode() {
  const context = useContext(DevModeContext);
  if (!context) {
    throw new Error('useDevMode must be used within DevModeProvider');
  }
  return context;
}

// Hook for checking if dev mode is active (safe to use outside provider)
export function useIsDevMode() {
  const context = useContext(DevModeContext);
  return context?.isEnabled ?? false;
}
