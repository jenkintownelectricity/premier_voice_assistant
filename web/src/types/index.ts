// Subscription types
export interface Subscription {
  plan_name: string;
  display_name: string;
  price_cents: number;
  status: string;
  current_period_start: string;
  current_period_end: string;
}

// Usage types
export interface Usage {
  minutes_used: number;
  conversations_count: number;
  voice_clones_count: number;
  assistants_count: number;
  bonus_minutes?: number;
}

// Feature limits
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

// Discount code types
export interface DiscountCode {
  id: string;
  code: string;
  description?: string;
  discount_type: 'percentage' | 'fixed' | 'minutes' | 'upgrade';
  discount_value: number;
  applicable_plan?: string;
  max_uses?: number;
  current_uses: number;
  max_uses_per_user: number;
  valid_until?: string;
  is_active: boolean;
  created_at: string;
}

// User types for admin
export interface UserSubscription {
  user_id: string;
  subscription: {
    plan_name: string;
    display_name: string;
    status: string;
    current_period_start: string;
    current_period_end: string;
  } | null;
}

// Plan types
export interface Plan {
  name: string;
  display_name: string;
  price: number;
  minutes: number;
  assistants: number | string;
  voice_clones: number | string;
  custom_voices: boolean;
  api_access: boolean;
  priority_support: boolean;
}

// API Response types
export interface ApiResponse<T> {
  success?: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// Chart data types
export interface UsageChartData {
  date: string;
  minutes: number;
  conversations: number;
}

export interface RevenueChartData {
  month: string;
  revenue: number;
  users: number;
}
