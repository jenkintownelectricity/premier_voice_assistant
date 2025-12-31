'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

// ============================================================================
// HIPAA COMPLIANCE CONFIGURATION
// ============================================================================

export interface HIPAACompliance {
  // Data Protection
  phiMaskingEnabled: boolean;        // Mask PHI in logs and displays
  dataRedactionLevel: 'none' | 'partial' | 'full';
  auditLoggingEnabled: boolean;      // Log all dev mode actions

  // Session Security
  sessionTimeoutMinutes: number;     // Auto-disable dev mode after timeout
  requireReauth: boolean;            // Require re-authentication for sensitive actions

  // Access Controls
  allowedEnvironments: string[];     // Environments where dev mode is allowed
  ipWhitelist: string[];             // IPs allowed to use dev mode (empty = all)

  // Compliance Status
  lastAuditDate: string | null;
  complianceOfficer: string | null;
  baaSignedDate: string | null;
}

export const DEFAULT_HIPAA_CONFIG: HIPAACompliance = {
  phiMaskingEnabled: true,
  dataRedactionLevel: 'partial',
  auditLoggingEnabled: true,
  sessionTimeoutMinutes: 30,
  requireReauth: false,
  allowedEnvironments: ['development', 'staging', 'production'],
  ipWhitelist: [],
  lastAuditDate: null,
  complianceOfficer: null,
  baaSignedDate: null,
};

// ============================================================================
// AUDIT LOG TYPES
// ============================================================================

export interface AuditLogEntry {
  id: string;
  timestamp: Date;
  action: string;
  category: 'feature_toggle' | 'plan_change' | 'data_access' | 'config_change' | 'session' | 'api_call';
  userId: string | null;
  details: Record<string, any>;
  ipAddress?: string;
  userAgent?: string;
  riskLevel: 'low' | 'medium' | 'high';
  phiAccessed: boolean;
}

// ============================================================================
// FEATURE FLAGS
// ============================================================================

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
  enterprise: { minutes: -1, assistants: -1, voiceClones: -1 },
};

// ============================================================================
// API LOGGING
// ============================================================================

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
  containsPHI?: boolean;
}

// ============================================================================
// DEV MODE STATE
// ============================================================================

interface DevModeState {
  // Core state
  isEnabled: boolean;
  isPanelOpen: boolean;
  activeTab: 'features' | 'plans' | 'actions' | 'console' | 'state' | 'hipaa';

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
  mockLatency: number;
  forceErrors: boolean;

  // State snapshots
  stateSnapshots: { name: string; timestamp: Date; state: any }[];

  // HIPAA Compliance
  hipaaConfig: HIPAACompliance;
  auditLogs: AuditLogEntry[];
  sessionStartTime: Date | null;
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

  // HIPAA Compliance
  updateHIPAAConfig: (config: Partial<HIPAACompliance>) => void;
  addAuditLog: (entry: Omit<AuditLogEntry, 'id' | 'timestamp'>) => void;
  exportAuditLogs: () => string;
  clearAuditLogs: () => void;
  maskPHI: (data: string) => string;
  getComplianceStatus: () => { compliant: boolean; issues: string[] };
  getSessionTimeRemaining: () => number;
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

// ============================================================================
// PHI MASKING UTILITIES
// ============================================================================

const PHI_PATTERNS = {
  ssn: /\b\d{3}-\d{2}-\d{4}\b/g,
  phone: /\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/g,
  email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
  mrn: /\bMRN[:\s]?\d{6,10}\b/gi,
  dob: /\b(0[1-9]|1[0-2])\/(0[1-9]|[12]\d|3[01])\/\d{4}\b/g,
  creditCard: /\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b/g,
};

function maskPHIData(data: string, level: 'none' | 'partial' | 'full'): string {
  if (level === 'none') return data;

  let masked = data;

  if (level === 'partial') {
    // Partial masking - show first/last characters
    masked = masked.replace(PHI_PATTERNS.ssn, '***-**-$&'.slice(-4));
    masked = masked.replace(PHI_PATTERNS.phone, (match) => `***-***-${match.slice(-4)}`);
    masked = masked.replace(PHI_PATTERNS.email, (match) => {
      const [local, domain] = match.split('@');
      return `${local[0]}***@${domain}`;
    });
  } else {
    // Full masking - replace entirely
    masked = masked.replace(PHI_PATTERNS.ssn, '[SSN REDACTED]');
    masked = masked.replace(PHI_PATTERNS.phone, '[PHONE REDACTED]');
    masked = masked.replace(PHI_PATTERNS.email, '[EMAIL REDACTED]');
    masked = masked.replace(PHI_PATTERNS.mrn, '[MRN REDACTED]');
    masked = masked.replace(PHI_PATTERNS.dob, '[DOB REDACTED]');
    masked = masked.replace(PHI_PATTERNS.creditCard, '[CC REDACTED]');
  }

  return masked;
}

// ============================================================================
// PROVIDER COMPONENT
// ============================================================================

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
    hipaaConfig: DEFAULT_HIPAA_CONFIG,
    auditLogs: [],
    sessionStartTime: null,
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
          hipaaConfig: { ...DEFAULT_HIPAA_CONFIG, ...parsed.hipaaConfig },
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
      hipaaConfig: state.hipaaConfig,
    }));
  }, [state.isEnabled, state.featureOverrides, state.simulatedPlan, state.isLoggingEnabled, state.mockLatency, state.hipaaConfig]);

  // Session timeout handler
  useEffect(() => {
    if (!state.isEnabled || !state.sessionStartTime) return;

    const timeoutMs = state.hipaaConfig.sessionTimeoutMinutes * 60 * 1000;
    const elapsed = Date.now() - state.sessionStartTime.getTime();
    const remaining = timeoutMs - elapsed;

    if (remaining <= 0) {
      // Session expired - disable dev mode
      setState(prev => ({
        ...prev,
        isEnabled: false,
        isPanelOpen: false,
        sessionStartTime: null,
      }));
      return;
    }

    const timeout = setTimeout(() => {
      setState(prev => ({
        ...prev,
        isEnabled: false,
        isPanelOpen: false,
        sessionStartTime: null,
      }));
    }, remaining);

    return () => clearTimeout(timeout);
  }, [state.isEnabled, state.sessionStartTime, state.hipaaConfig.sessionTimeoutMinutes]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        setState(prev => ({
          ...prev,
          isEnabled: !prev.isEnabled,
          isPanelOpen: !prev.isEnabled,
          sessionStartTime: !prev.isEnabled ? new Date() : null,
        }));
      }
      if (e.ctrlKey && e.shiftKey && e.key === 'P' && state.isEnabled) {
        e.preventDefault();
        setState(prev => ({ ...prev, isPanelOpen: !prev.isPanelOpen }));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [state.isEnabled]);

  // ============================================================================
  // ACTION HANDLERS
  // ============================================================================

  const addAuditLog = useCallback((entry: Omit<AuditLogEntry, 'id' | 'timestamp'>) => {
    if (!state.hipaaConfig.auditLoggingEnabled) return;

    setState(prev => ({
      ...prev,
      auditLogs: [
        {
          ...entry,
          id: crypto.randomUUID(),
          timestamp: new Date(),
        },
        ...prev.auditLogs.slice(0, 999), // Keep last 1000 entries
      ],
    }));
  }, [state.hipaaConfig.auditLoggingEnabled]);

  const toggleDevMode = useCallback(() => {
    setState(prev => {
      const newEnabled = !prev.isEnabled;
      return {
        ...prev,
        isEnabled: newEnabled,
        isPanelOpen: newEnabled,
        sessionStartTime: newEnabled ? new Date() : null,
      };
    });

    addAuditLog({
      action: state.isEnabled ? 'dev_mode_disabled' : 'dev_mode_enabled',
      category: 'session',
      userId: null,
      details: {},
      riskLevel: 'medium',
      phiAccessed: false,
    });
  }, [state.isEnabled, addAuditLog]);

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

    addAuditLog({
      action: `feature_toggle_${feature}`,
      category: 'feature_toggle',
      userId: null,
      details: { feature },
      riskLevel: 'low',
      phiAccessed: false,
    });
  }, [addAuditLog]);

  const resetFeatures = useCallback(() => {
    setState(prev => ({ ...prev, featureOverrides: {} }));
    addAuditLog({
      action: 'features_reset',
      category: 'feature_toggle',
      userId: null,
      details: {},
      riskLevel: 'low',
      phiAccessed: false,
    });
  }, [addAuditLog]);

  const isFeatureEnabled = useCallback((feature: keyof FeatureFlags): boolean => {
    if (state.featureOverrides[feature] !== undefined) {
      return state.featureOverrides[feature]!;
    }
    if (state.simulatedPlan && PLAN_FEATURES[state.simulatedPlan]) {
      return PLAN_FEATURES[state.simulatedPlan][feature] ?? DEFAULT_FEATURES[feature];
    }
    return DEFAULT_FEATURES[feature];
  }, [state.featureOverrides, state.simulatedPlan]);

  const simulatePlan = useCallback((plan: string | null) => {
    setState(prev => ({ ...prev, simulatedPlan: plan }));
    addAuditLog({
      action: 'plan_simulation_changed',
      category: 'plan_change',
      userId: null,
      details: { plan },
      riskLevel: 'low',
      phiAccessed: false,
    });
  }, [addAuditLog]);

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
        ...prev.apiLogs.slice(0, 99),
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
        ...prev.stateSnapshots.slice(0, 9),
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

  // HIPAA-specific functions
  const updateHIPAAConfig = useCallback((config: Partial<HIPAACompliance>) => {
    setState(prev => ({
      ...prev,
      hipaaConfig: { ...prev.hipaaConfig, ...config },
    }));
    addAuditLog({
      action: 'hipaa_config_updated',
      category: 'config_change',
      userId: null,
      details: { changes: Object.keys(config) },
      riskLevel: 'high',
      phiAccessed: false,
    });
  }, [addAuditLog]);

  const exportAuditLogs = useCallback(() => {
    const logs = state.auditLogs.map(log => ({
      ...log,
      timestamp: log.timestamp.toISOString(),
    }));
    return JSON.stringify(logs, null, 2);
  }, [state.auditLogs]);

  const clearAuditLogs = useCallback(() => {
    addAuditLog({
      action: 'audit_logs_cleared',
      category: 'config_change',
      userId: null,
      details: { clearedCount: state.auditLogs.length },
      riskLevel: 'high',
      phiAccessed: false,
    });
    setState(prev => ({ ...prev, auditLogs: [] }));
  }, [state.auditLogs.length, addAuditLog]);

  const maskPHI = useCallback((data: string) => {
    return maskPHIData(data, state.hipaaConfig.dataRedactionLevel);
  }, [state.hipaaConfig.dataRedactionLevel]);

  const getComplianceStatus = useCallback(() => {
    const issues: string[] = [];

    if (!state.hipaaConfig.auditLoggingEnabled) {
      issues.push('Audit logging is disabled');
    }
    if (!state.hipaaConfig.phiMaskingEnabled) {
      issues.push('PHI masking is disabled');
    }
    if (state.hipaaConfig.sessionTimeoutMinutes > 60) {
      issues.push('Session timeout exceeds recommended 60 minutes');
    }
    if (state.hipaaConfig.dataRedactionLevel === 'none') {
      issues.push('Data redaction is disabled');
    }

    return {
      compliant: issues.length === 0,
      issues,
    };
  }, [state.hipaaConfig]);

  const getSessionTimeRemaining = useCallback(() => {
    if (!state.sessionStartTime) return 0;
    const timeoutMs = state.hipaaConfig.sessionTimeoutMinutes * 60 * 1000;
    const elapsed = Date.now() - state.sessionStartTime.getTime();
    return Math.max(0, Math.floor((timeoutMs - elapsed) / 1000));
  }, [state.sessionStartTime, state.hipaaConfig.sessionTimeoutMinutes]);

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
    updateHIPAAConfig,
    addAuditLog,
    exportAuditLogs,
    clearAuditLogs,
    maskPHI,
    getComplianceStatus,
    getSessionTimeRemaining,
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

export function useIsDevMode() {
  const context = useContext(DevModeContext);
  return context?.isEnabled ?? false;
}
