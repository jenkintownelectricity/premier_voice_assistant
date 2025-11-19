-- Migration: Add Stripe payment fields
-- Run this in Supabase SQL Editor

-- Add stripe_customer_id to user profiles
ALTER TABLE va_user_profiles
ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT UNIQUE;

-- Add stripe_subscription_id to user subscriptions
ALTER TABLE va_user_subscriptions
ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT UNIQUE;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_stripe_customer
ON va_user_profiles(stripe_customer_id);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_stripe
ON va_user_subscriptions(stripe_subscription_id);

-- Comment for documentation
COMMENT ON COLUMN va_user_profiles.stripe_customer_id IS 'Stripe customer ID for payment processing';
COMMENT ON COLUMN va_user_subscriptions.stripe_subscription_id IS 'Stripe subscription ID for recurring billing';
