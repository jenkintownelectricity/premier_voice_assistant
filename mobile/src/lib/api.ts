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
