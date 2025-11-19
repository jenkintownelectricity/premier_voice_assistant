const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app';

// Helper for API calls
async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {},
  userId?: string,
  adminKey?: string
): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (userId) {
    (headers as Record<string, string>)['X-User-ID'] = userId;
  }

  if (adminKey) {
    (headers as Record<string, string>)['X-Admin-Key'] = adminKey;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  return response.json();
}

// User API calls
export const api = {
  // Subscription & Usage
  getSubscription: (userId: string) =>
    fetchAPI<{ subscription: {
      plan_name: string;
      display_name: string;
      price_cents: number;
      status: string;
      current_period_start: string;
      current_period_end: string;
    } | null }>('/subscription', {}, userId),

  getUsage: (userId: string) =>
    fetchAPI<{ usage: {
      minutes_used: number;
      bonus_minutes?: number;
      conversations_count: number;
      voice_clones_count: number;
      assistants_count: number;
    } }>('/usage', {}, userId),

  getFeatureLimits: (userId: string) =>
    fetchAPI<{
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
    }>('/feature-limits', {}, userId),

  // Payments
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

  createPortalSession: (userId: string, returnUrl: string) =>
    fetchAPI<{ url: string }>(
      '/payments/create-portal',
      {
        method: 'POST',
        body: JSON.stringify({ return_url: returnUrl }),
      },
      userId
    ),

  // Discount Codes
  redeemCode: (userId: string, code: string) =>
    fetchAPI<{
      success: boolean;
      message: string;
      minutes_added?: number;
    }>(
      '/codes/redeem',
      {
        method: 'POST',
        body: JSON.stringify({ code }),
      },
      userId
    ),
};

// Admin API calls
export const adminApi = {
  // User management
  getUsers: async (adminKey: string, search?: string) => {
    // Note: Backend needs a search endpoint - for now fetch all and filter client-side
    // This would need to be implemented on the backend
    return { users: [] };
  },

  getUserSubscription: (adminKey: string, userId: string) =>
    fetchAPI<{
      user_id: string;
      subscription: {
        plan_name: string;
        display_name: string;
        status: string;
        current_period_start: string;
        current_period_end: string;
      } | null;
    }>(`/admin/user-subscription/${userId}`, {}, undefined, adminKey),

  upgradeUser: (adminKey: string, userId: string, planName: string) =>
    fetchAPI<{
      success: boolean;
      user_id: string;
      plan: string;
      display_name: string;
      message: string;
    }>(
      '/admin/upgrade-user',
      {
        method: 'POST',
        body: JSON.stringify({
          user_id: userId,
          plan_name: planName,
        }),
      },
      undefined,
      adminKey
    ),

  addBonusMinutes: (adminKey: string, userId: string, minutes: number, reason?: string) =>
    fetchAPI<{
      success: boolean;
      user_id: string;
      minutes_added: number;
      total_bonus_minutes: number;
      reason?: string;
      message: string;
    }>(
      '/admin/add-minutes',
      {
        method: 'POST',
        body: JSON.stringify({
          user_id: userId,
          minutes,
          reason,
        }),
      },
      undefined,
      adminKey
    ),

  resetUsage: (adminKey: string, userId: string) =>
    fetchAPI<{
      success: boolean;
      user_id: string;
      reset_fields: string[];
      message: string;
    }>(
      '/admin/reset-usage',
      {
        method: 'POST',
        body: JSON.stringify({
          user_id: userId,
          reset_minutes: true,
          reset_conversations: false,
          reset_voice_clones: false,
        }),
      },
      undefined,
      adminKey
    ),

  // Discount codes
  getCodes: (adminKey: string, activeOnly: boolean = true) =>
    fetchAPI<{
      codes: Array<{
        id: string;
        code: string;
        description: string;
        discount_type: string;
        discount_value: number;
        max_uses: number | null;
        current_uses: number;
        valid_until: string | null;
        is_active: boolean;
        created_at: string;
      }>;
      count: number;
    }>(`/admin/codes?active_only=${activeOnly}`, {}, undefined, adminKey),

  createCode: (
    adminKey: string,
    code: string,
    discountType: string,
    discountValue: number,
    description?: string,
    maxUses?: number,
    validUntil?: string
  ) =>
    fetchAPI<{
      success: boolean;
      code: {
        id: string;
        code: string;
        description: string;
        discount_type: string;
        discount_value: number;
        max_uses: number | null;
        is_active: boolean;
      };
    }>(
      '/admin/codes',
      {
        method: 'POST',
        body: JSON.stringify({
          code,
          discount_type: discountType,
          discount_value: discountValue,
          description,
          max_uses: maxUses,
          valid_until: validUntil,
          max_uses_per_user: 1,
        }),
      },
      undefined,
      adminKey
    ),

  deactivateCode: (adminKey: string, code: string) =>
    fetchAPI<{
      success: boolean;
      message: string;
    }>(`/admin/codes/${code}`, { method: 'DELETE' }, undefined, adminKey),
};
