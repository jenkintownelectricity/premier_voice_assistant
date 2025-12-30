const API_URL = 'https://web-production-1b085.up.railway.app';

async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {},
  userId?: string
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (userId) {
    headers['X-User-ID'] = userId;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string>) },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  return response.json();
}

export const api = {
  getSubscription: (userId: string) =>
    fetchAPI<{ subscription: Subscription | null }>('/subscription', {}, userId),

  getUsage: (userId: string) =>
    fetchAPI<{ usage: Usage }>('/usage', {}, userId),

  getFeatureLimits: (userId: string) =>
    fetchAPI<FeatureLimits>('/feature-limits', {}, userId),

  redeemCode: (userId: string, code: string) =>
    fetchAPI<RedeemResult>(
      '/codes/redeem',
      {
        method: 'POST',
        body: JSON.stringify({ code }),
      },
      userId
    ),

  createCheckoutSession: (userId: string, planName: string, successUrl: string, cancelUrl: string) =>
    fetchAPI<{ url: string; session_id: string }>(
      '/payments/create-checkout',
      {
        method: 'POST',
        body: JSON.stringify({
          plan_name: planName,
          success_url: successUrl,
          cancel_url: cancelUrl,
        }),
      },
      userId
    ),

  // Assistants
  getAssistants: (userId: string) =>
    fetchAPI<{ assistants: Assistant[] }>('/assistants', {}, userId),

  getAssistant: (userId: string, assistantId: string) =>
    fetchAPI<{ assistant: AssistantDetail }>(`/assistants/${assistantId}`, {}, userId),

  createAssistant: (userId: string, data: CreateAssistantData) =>
    fetchAPI<{ success: boolean; assistant: Assistant }>(
      '/assistants',
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
      userId
    ),

  updateAssistant: (userId: string, assistantId: string, data: Partial<CreateAssistantData> & { is_active?: boolean }) =>
    fetchAPI<{ success: boolean }>(
      `/assistants/${assistantId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(data),
      },
      userId
    ),

  deleteAssistant: (userId: string, assistantId: string) =>
    fetchAPI<{ success: boolean }>(`/assistants/${assistantId}`, { method: 'DELETE' }, userId),

  // Call Logs
  getCalls: (userId: string, limit: number = 50, offset: number = 0, assistantId?: string) =>
    fetchAPI<{ calls: CallLog[]; total: number; limit: number; offset: number }>(
      `/calls?limit=${limit}&offset=${offset}${assistantId ? `&assistant_id=${assistantId}` : ''}`,
      {},
      userId
    ),

  getCall: (userId: string, callId: string) =>
    fetchAPI<{ call: CallDetail }>(`/calls/${callId}`, {}, userId),

  getCallStats: (userId: string) =>
    fetchAPI<{ stats: CallStats }>('/calls/stats/summary', {}, userId),
};

export interface Subscription {
  plan_name: string;
  display_name: string;
  price_cents: number;
  status: string;
  current_period_start: string;
  current_period_end: string;
}

export interface Usage {
  minutes_used: number;
  bonus_minutes?: number;
  conversations_count: number;
  voice_clones_count: number;
  assistants_count: number;
}

export interface FeatureLimits {
  plan: string;
  display_name: string;
  limits: {
    max_minutes: number;
    max_assistants: number;
    max_voice_clones: number;
    custom_voices: boolean;
    api_access: boolean;
    priority_support: boolean;
  };
  current_usage: {
    minutes_used: number;
    assistants_count: number;
    voice_clones_count: number;
  };
}

export interface RedeemResult {
  success: boolean;
  message: string;
  minutes_added?: number;
}

export interface Assistant {
  id: string;
  name: string;
  description: string | null;
  voice_id: string;
  model: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  call_count: number;
}

export interface AssistantDetail extends Assistant {
  system_prompt: string;
  temperature: number;
  max_tokens: number;
  first_message: string | null;
  vad_sensitivity: number;
  endpointing_ms: number;
  enable_bargein: boolean;
  streaming_chunks: boolean;
  first_message_latency_ms: number;
  turn_detection_mode: string;
  metadata: Record<string, unknown>;
}

export interface CreateAssistantData {
  name: string;
  system_prompt: string;
  description?: string;
  voice_id?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  first_message?: string;
  vad_sensitivity?: number;
  endpointing_ms?: number;
  enable_bargein?: boolean;
  streaming_chunks?: boolean;
  first_message_latency_ms?: number;
  turn_detection_mode?: string;
}

export interface CallLog {
  id: string;
  assistant_id: string | null;
  assistant_name: string;
  call_type: string;
  phone_number: string | null;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  cost_cents: number;
  summary: string | null;
  sentiment: string | null;
  ended_reason: string | null;
}

export interface CallDetail extends CallLog {
  minutes_used: number;
  transcript: Array<{ role: string; content: string; timestamp?: string }>;
  recording_url: string | null;
  metadata: Record<string, unknown>;
}

export interface CallStats {
  total_calls: number;
  total_duration_seconds: number;
  total_cost_cents: number;
  avg_duration_seconds: number;
  completed_calls: number;
  failed_calls: number;
  calls_today: number;
  calls_this_week: number;
  calls_this_month: number;
}
