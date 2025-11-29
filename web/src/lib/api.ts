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
    // Handle error.detail being an array (validation errors) or object
    let errorMessage = 'Request failed';
    if (typeof error.detail === 'string') {
      errorMessage = error.detail;
    } else if (Array.isArray(error.detail)) {
      errorMessage = error.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
    } else if (error.detail && typeof error.detail === 'object') {
      errorMessage = error.detail.message || error.detail.msg || JSON.stringify(error.detail);
    }
    throw new Error(errorMessage || `API Error: ${response.status}`);
  }

  return response.json();
}

// Anthropic Claude API call
export const claudeApi = {
  chat: async (message: string, systemPrompt?: string): Promise<{ response: string }> => {
    const response = await fetch(`${API_URL}/chat/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        system_prompt: systemPrompt || 'You are a helpful AI assistant for HIVE215, a premier voice assistant platform. Be concise, friendly, and helpful.',
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Chat request failed' }));
      // Handle error.detail being an array (validation errors) or object
      let errorMessage = 'Chat request failed';
      if (typeof error.detail === 'string') {
        errorMessage = error.detail;
      } else if (Array.isArray(error.detail)) {
        errorMessage = error.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
      } else if (error.detail && typeof error.detail === 'object') {
        errorMessage = error.detail.message || error.detail.msg || JSON.stringify(error.detail);
      }
      throw new Error(errorMessage || `Chat Error: ${response.status}`);
    }

    return response.json();
  },
};

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

  // Assistants
  getAssistants: (userId: string) =>
    fetchAPI<{
      assistants: Array<{
        id: string;
        name: string;
        description: string | null;
        voice_id: string;
        model: string;
        is_active: boolean;
        created_at: string;
        updated_at: string;
        call_count: number;
      }>;
    }>('/assistants', {}, userId),

  getAssistant: (userId: string, assistantId: string) =>
    fetchAPI<{
      assistant: {
        id: string;
        name: string;
        description: string | null;
        system_prompt: string;
        voice_id: string;
        llm_provider?: string;
        model: string;
        temperature: number;
        max_tokens: number;
        first_message: string | null;
        is_active: boolean;
        // Advanced settings
        vad_sensitivity?: number;
        endpointing_ms?: number;
        enable_bargein?: boolean;
        streaming_chunks?: boolean;
        first_message_latency_ms?: number;
        turn_detection_mode?: string;
        // Voice control settings
        speech_speed?: number;
        response_delay_ms?: number;
        punctuation_pause_ms?: number;
        no_punctuation_pause_ms?: number;
        turn_eagerness?: string;
        metadata: Record<string, unknown>;
        created_at: string;
        updated_at: string;
      };
    }>(`/assistants/${assistantId}`, {}, userId),

  createAssistant: (
    userId: string,
    data: {
      name: string;
      system_prompt: string;
      description?: string;
      voice_id?: string;
      llm_provider?: string;  // Provider: groq, anthropic, openai, google, etc.
      model?: string;
      temperature?: number;
      max_tokens?: number;
      first_message?: string;
      // Advanced latency optimization settings
      vad_sensitivity?: number;
      endpointing_ms?: number;
      enable_bargein?: boolean;
      streaming_chunks?: boolean;
      first_message_latency_ms?: number;
      turn_detection_mode?: string;
      // Voice control settings
      speech_speed?: number;
      response_delay_ms?: number;
      punctuation_pause_ms?: number;
      no_punctuation_pause_ms?: number;
      turn_eagerness?: string;
    }
  ) =>
    fetchAPI<{
      success: boolean;
      assistant: {
        id: string;
        name: string;
        description: string | null;
        system_prompt: string;
        voice_id: string;
        model: string;
        temperature: number;
        max_tokens: number;
        first_message: string | null;
        is_active: boolean;
        created_at: string;
      };
    }>(
      '/assistants',
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
      userId
    ),

  updateAssistant: (
    userId: string,
    assistantId: string,
    data: {
      name?: string;
      description?: string;
      system_prompt?: string;
      voice_id?: string;
      llm_provider?: string;  // Provider: groq, anthropic, openai, google, etc.
      model?: string;
      temperature?: number;
      max_tokens?: number;
      first_message?: string;
      is_active?: boolean;
      // Advanced latency optimization settings
      vad_sensitivity?: number;
      endpointing_ms?: number;
      enable_bargein?: boolean;
      streaming_chunks?: boolean;
      first_message_latency_ms?: number;
      turn_detection_mode?: string;
      // Voice control settings
      speech_speed?: number;
      response_delay_ms?: number;
      punctuation_pause_ms?: number;
      no_punctuation_pause_ms?: number;
      turn_eagerness?: string;
    }
  ) =>
    fetchAPI<{
      success: boolean;
      assistant: {
        id: string;
        name: string;
        is_active: boolean;
      } | null;
    }>(
      `/assistants/${assistantId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(data),
      },
      userId
    ),

  deleteAssistant: (userId: string, assistantId: string) =>
    fetchAPI<{
      success: boolean;
      message: string;
    }>(`/assistants/${assistantId}`, { method: 'DELETE' }, userId),

  // Call Logs
  getCalls: (userId: string, limit: number = 50, offset: number = 0, assistantId?: string) =>
    fetchAPI<{
      calls: Array<{
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
      }>;
      total: number;
      limit: number;
      offset: number;
    }>(
      `/calls?limit=${limit}&offset=${offset}${assistantId ? `&assistant_id=${assistantId}` : ''}`,
      {},
      userId
    ),

  getCall: (userId: string, callId: string) =>
    fetchAPI<{
      call: {
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
        minutes_used: number;
        transcript: Array<{ role: string; content: string; timestamp?: string }>;
        summary: string | null;
        recording_url: string | null;
        sentiment: string | null;
        ended_reason: string | null;
        metadata: Record<string, unknown>;
      };
    }>(`/calls/${callId}`, {}, userId),

  getCallStats: (userId: string) =>
    fetchAPI<{
      stats: {
        total_calls: number;
        total_duration_seconds: number;
        total_cost_cents: number;
        avg_duration_seconds: number;
        completed_calls: number;
        failed_calls: number;
        calls_today: number;
        calls_this_week: number;
        calls_this_month: number;
      };
    }>('/calls/stats/summary', {}, userId),

  // Budget Management
  getBudget: (userId: string) =>
    fetchAPI<{
      budget: {
        monthly_budget_cents: number;
        monthly_budget_dollars: number;
        alert_thresholds: number[];
        is_active: boolean;
        last_alert_sent_at?: string;
        last_alert_threshold?: number;
      };
      current_month: {
        cost_cents: number;
        cost_dollars: number;
        percentage_used: number;
        remaining_cents: number;
        remaining_dollars: number;
        status: 'healthy' | 'warning' | 'over_budget';
      };
    }>('/budget', {}, userId),

  setBudget: (userId: string, monthlyBudgetDollars: number, alertThresholds: number[] = [80, 90, 100]) =>
    fetchAPI<{
      success: boolean;
      budget: {
        monthly_budget_cents: number;
        monthly_budget_dollars: number;
        alert_thresholds: number[];
      };
    }>(
      '/budget',
      {
        method: 'POST',
        body: JSON.stringify({
          monthly_budget_dollars: monthlyBudgetDollars,
          alert_thresholds: alertThresholds,
        }),
      },
      userId
    ),

  // Usage Analytics
  getUsageAnalytics: (userId: string, days: number = 30) =>
    fetchAPI<{
      period: {
        start_date: string;
        end_date: string;
        days: number;
      };
      totals: {
        input_tokens: number;
        output_tokens: number;
        total_tokens: number;
        cost_cents: number;
        cost_dollars: number;
        total_requests: number;
        total_errors: number;
        success_rate: number;
      };
      averages: {
        tokens_per_request: number;
        cost_per_request_cents: number;
        requests_per_day: number;
        error_rate: number;
      };
      errors: {
        total: number;
        rate: number;
        by_type: Record<string, number>;
      };
      by_event_type: Record<string, {
        count: number;
        input_tokens: number;
        output_tokens: number;
        cost_cents: number;
      }>;
      daily_usage: Array<{
        date: string;
        input_tokens: number;
        output_tokens: number;
        cost_cents: number;
        requests: number;
        errors: number;
      }>;
    }>(`/usage/analytics?days=${days}`, {}, userId),

  // AI Usage Coach endpoints
  getWeeklyInsights: (userId: string) =>
    fetchAPI<any>('/insights/weekly', { method: 'GET' }, userId),

  getCostOptimizer: (userId: string) =>
    fetchAPI<any>('/insights/cost-optimizer', { method: 'GET' }, userId),

  // Advanced Observability endpoints
  getLatencyPercentiles: (userId: string, days: number = 7) =>
    fetchAPI<any>(`/observability/latency?days=${days}`, { method: 'GET' }, userId),

  getErrorCorrelation: (userId: string, days: number = 7) =>
    fetchAPI<any>(`/observability/error-correlation?days=${days}`, { method: 'GET' }, userId),

  // Team Collaboration endpoints
  listTeams: (userId: string) =>
    fetchAPI<{ teams: any[] }>('/teams', { method: 'GET' }, userId),

  createTeam: (userId: string, name: string, description?: string) =>
    fetchAPI<{ team: any; message: string }>(
      '/teams',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description }),
      },
      userId
    ),

  getTeamDetails: (userId: string, teamId: string) =>
    fetchAPI<{ team: any; members: any[]; user_role: string }>(
      `/teams/${teamId}`,
      { method: 'GET' },
      userId
    ),

  addTeamMember: (userId: string, teamId: string, memberUserId: string, role: string = 'member') =>
    fetchAPI<{ member: any; message: string }>(
      `/teams/${teamId}/members`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ member_user_id: memberUserId, role }),
      },
      userId
    ),

  removeTeamMember: (userId: string, teamId: string, memberUserId: string) =>
    fetchAPI<{ message: string }>(
      `/teams/${teamId}/members/${memberUserId}`,
      { method: 'DELETE' },
      userId
    ),

  getTeamAnalytics: (userId: string, teamId: string, days: number = 30) =>
    fetchAPI<any>(
      `/teams/${teamId}/analytics?days=${days}`,
      { method: 'GET' },
      userId
    ),

  listTeamDashboards: (userId: string, teamId: string) =>
    fetchAPI<{ dashboards: any[] }>(
      `/teams/${teamId}/dashboards`,
      { method: 'GET' },
      userId
    ),

  createTeamDashboard: (userId: string, teamId: string, name: string, description?: string, config?: any) =>
    fetchAPI<{ dashboard: any; message: string }>(
      `/teams/${teamId}/dashboards`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, config }),
      },
      userId
    ),
};

// Phone & SMS API
export const phoneApi = {
  getPhoneNumbers: (userId: string) =>
    fetchAPI<{ phone_numbers: Array<{
      id: string;
      phone_number: string;
      phone_type: string;
      is_verified: boolean;
      is_primary: boolean;
      created_at: string;
    }> }>('/phone-numbers', {}, userId),

  addPhoneNumber: (userId: string, phoneNumber: string, phoneType: string = 'mobile') =>
    fetchAPI<{ success: boolean; message: string; phone_number: string; dev_code?: string }>(
      '/phone-numbers',
      { method: 'POST', body: JSON.stringify({ phone_number: phoneNumber, phone_type: phoneType }) },
      userId
    ),

  verifyPhone: (userId: string, phoneNumber: string, code: string) =>
    fetchAPI<{ success: boolean; message: string }>(
      '/phone-numbers/verify',
      { method: 'POST', body: JSON.stringify({ phone_number: phoneNumber, code }) },
      userId
    ),

  deletePhone: (userId: string, phoneId: string) =>
    fetchAPI<{ success: boolean }>(`/phone-numbers/${phoneId}`, { method: 'DELETE' }, userId),

  sendSMS: (userId: string, toNumber: string, message: string) =>
    fetchAPI<{ success: boolean; message: string }>(
      '/sms/send',
      { method: 'POST', body: JSON.stringify({ to_number: toNumber, message }) },
      userId
    ),

  getSMSHistory: (userId: string, limit: number = 50, offset: number = 0) =>
    fetchAPI<{ messages: Array<any>; total: number }>(
      `/sms?limit=${limit}&offset=${offset}`,
      {},
      userId
    ),
};

// Profile & Settings API
export const profileApi = {
  getExtendedProfile: (userId: string) =>
    fetchAPI<{
      profile: {
        display_name?: string;
        business_name?: string;
        profession?: string;
        service_area?: string;
        greeting_name?: string;
        assistant_name?: string;
        assistant_personality?: string;
        profile_fields?: Array<{ label: string; value: string }>;
        business_hours?: Record<string, { start: string; end: string }>;
        timezone?: string;
      };
      field_limits: {
        max_fields: number;
        max_chars_per_field: number;
      };
      plan: string;
    }>('/profile/extended', {}, userId),

  updateProfile: (userId: string, data: {
    display_name?: string;
    business_name?: string;
    profession?: string;
    service_area?: string;
    greeting_name?: string;
    assistant_name?: string;
    assistant_personality?: string;
    profile_fields?: Array<{ label: string; value: string }>;
    business_hours?: Record<string, { start: string; end: string }>;
    timezone?: string;
  }) =>
    fetchAPI<{ success: boolean; profile: any }>(
      '/profile/extended',
      { method: 'PATCH', body: JSON.stringify(data) },
      userId
    ),

  getSettings: (userId: string) =>
    fetchAPI<{
      settings: {
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
        language: string;
        webhook_enabled: boolean;
        webhook_url?: string;
      };
    }>('/settings', {}, userId),

  updateSettings: (userId: string, data: Partial<{
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
    language: string;
    webhook_enabled: boolean;
    webhook_url: string;
  }>) =>
    fetchAPI<{ success: boolean; settings: any }>(
      '/settings',
      { method: 'PATCH', body: JSON.stringify(data) },
      userId
    ),
};

// Contacts API
export const contactsApi = {
  getContacts: (userId: string, limit: number = 50, offset: number = 0, contactType?: string) =>
    fetchAPI<{
      contacts: Array<{
        id: string;
        name: string;
        phone?: string;
        email?: string;
        company?: string;
        contact_type: string;
        permission_level: string;
        notes?: string;
        tags?: string[];
        total_calls: number;
        last_call_at?: string;
      }>;
      total: number;
    }>(`/contacts?limit=${limit}&offset=${offset}${contactType ? `&contact_type=${contactType}` : ''}`, {}, userId),

  createContact: (userId: string, data: {
    name: string;
    phone?: string;
    email?: string;
    company?: string;
    contact_type?: string;
    permission_level?: string;
    notes?: string;
    tags?: string[];
  }) =>
    fetchAPI<{ success: boolean; contact: any }>(
      '/contacts',
      { method: 'POST', body: JSON.stringify(data) },
      userId
    ),

  getContact: (userId: string, contactId: string) =>
    fetchAPI<{ contact: any }>(`/contacts/${contactId}`, {}, userId),

  updateContact: (userId: string, contactId: string, data: any) =>
    fetchAPI<{ success: boolean; contact: any }>(
      `/contacts/${contactId}`,
      { method: 'PATCH', body: JSON.stringify(data) },
      userId
    ),

  deleteContact: (userId: string, contactId: string) =>
    fetchAPI<{ success: boolean }>(`/contacts/${contactId}`, { method: 'DELETE' }, userId),
};

// Call Sharing API
export const callShareApi = {
  shareCall: (userId: string, callId: string, options: {
    share_type: 'email' | 'sms' | 'webhook' | 'link';
    recipient?: string;
    include_transcript?: boolean;
    include_summary?: boolean;
    include_recording?: boolean;
    include_key_info?: boolean;
  }) =>
    fetchAPI<{ success: boolean; share: any; share_url: string }>(
      `/calls/${callId}/share`,
      { method: 'POST', body: JSON.stringify(options) },
      userId
    ),

  shareWithTeam: (userId: string, callId: string, teamId: string) =>
    fetchAPI<{ success: boolean; message: string }>(
      `/calls/${callId}/share-team/${teamId}`,
      { method: 'POST' },
      userId
    ),
};

// Referral API
export const referralApi = {
  getReferralInfo: (userId: string) =>
    fetchAPI<{
      referral_code: {
        id: string;
        code: string;
        referrer_reward_value: number;
        referee_reward_value: number;
        total_referrals: number;
        successful_referrals: number;
        total_rewards_earned: number;
      };
      referrals: Array<{
        id: string;
        referee_id: string;
        status: string;
        signed_up_at?: string;
        converted_at?: string;
      }>;
      share_url: string;
    }>('/referral', {}, userId),

  redeemReferral: (userId: string, code: string) =>
    fetchAPI<{ success: boolean; message: string; minutes_earned: number }>(
      '/referral/redeem',
      { method: 'POST', body: JSON.stringify({ code }) },
      userId
    ),
};

// Team Enhancements
export const teamApi = {
  ...api,

  inviteMember: (userId: string, teamId: string, email: string, role: string = 'member') =>
    fetchAPI<{ success: boolean; message: string; invite_url: string }>(
      `/teams/${teamId}/invite`,
      { method: 'POST', body: JSON.stringify({ email, role }) },
      userId
    ),

  joinTeam: (userId: string, token: string) =>
    fetchAPI<{ success: boolean; message: string }>(
      `/teams/join/${token}`,
      { method: 'POST' },
      userId
    ),

  getTeamCalls: (userId: string, teamId: string, limit: number = 50, offset: number = 0) =>
    fetchAPI<{ calls: Array<any>; total: number }>(
      `/teams/${teamId}/calls?limit=${limit}&offset=${offset}`,
      {},
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
