import { createClient, SupabaseClient } from '@supabase/supabase-js';

// Get URL with validation
function getSupabaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  if (url && url.startsWith('http')) {
    return url;
  }
  // Return a valid placeholder URL that won't be used at runtime
  return 'https://placeholder-project.supabase.co';
}

// Get anon key with fallback
function getSupabaseAnonKey(): string {
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (key && key.length > 10) {
    return key;
  }
  // Return a valid JWT format placeholder
  return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBsYWNlaG9sZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE2NDAwMDAwMDAsImV4cCI6MTk1NTYwMDAwMH0.placeholder-signature';
}

// Create client with validated values
export const supabase = createClient(getSupabaseUrl(), getSupabaseAnonKey());

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
