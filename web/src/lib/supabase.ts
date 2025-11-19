import { createClient } from '@supabase/supabase-js';

// Use placeholder values during build time to prevent errors
// Real values come from Vercel environment variables at runtime
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder-key';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Type definitions for database
export interface User {
  id: string;
  email: string;
  plan?: string;
  created_at?: string;
}

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
  bonus_minutes: number;
  conversations_count: number;
  voice_clones_count: number;
  assistants_count: number;
  period_start?: string;
  period_end?: string;
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

export interface DiscountCode {
  id: string;
  code: string;
  description: string;
  discount_type: string;
  discount_value: number;
  max_uses: number | null;
  current_uses: number;
  valid_until: string | null;
  is_active: boolean;
}

export interface AdminUser {
  id: string;
  email: string;
  plan: string;
  status: string;
  minutes_used: number;
  max_minutes: number;
  bonus_minutes: number;
  created_at: string;
}
