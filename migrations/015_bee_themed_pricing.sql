-- Migration 015: Update to Bee-Themed Pricing Tiers
-- Date: January 3, 2026
-- Description: Replace old pricing tiers with bee-themed plans

-- First, deactivate old plans
UPDATE va_subscription_plans
SET is_active = false
WHERE plan_name IN ('free', 'starter', 'pro', 'business', 'enterprise');

-- Insert new bee-themed plans (or update if they exist)
INSERT INTO va_subscription_plans (plan_name, display_name, price_cents, billing_interval, is_active)
VALUES
  ('worker_bee', 'The Worker Bee', 9700, 'monthly', true),
  ('swarm', 'The Swarm', 29700, 'monthly', true),
  ('queen_bee', 'The Queen Bee', 69700, 'monthly', true),
  ('hive_mind', 'The Hive Mind', 250000, 'monthly', true)
ON CONFLICT (plan_name) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  price_cents = EXCLUDED.price_cents,
  is_active = EXCLUDED.is_active;

-- Add minutes_included column if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'va_subscription_plans' AND column_name = 'minutes_included'
  ) THEN
    ALTER TABLE va_subscription_plans ADD COLUMN minutes_included INTEGER DEFAULT 0;
  END IF;
END $$;

-- Add phone_numbers column if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'va_subscription_plans' AND column_name = 'phone_numbers'
  ) THEN
    ALTER TABLE va_subscription_plans ADD COLUMN phone_numbers INTEGER DEFAULT 1;
  END IF;
END $$;

-- Add voice_clones column if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'va_subscription_plans' AND column_name = 'voice_clones'
  ) THEN
    ALTER TABLE va_subscription_plans ADD COLUMN voice_clones INTEGER DEFAULT 1;
  END IF;
END $$;

-- Add team_members column if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'va_subscription_plans' AND column_name = 'team_members'
  ) THEN
    ALTER TABLE va_subscription_plans ADD COLUMN team_members INTEGER DEFAULT 1;
  END IF;
END $$;

-- Update plan features
-- Worker Bee: $97/mo, 400 mins, 1 phone, 1 voice, 1 team
UPDATE va_subscription_plans SET
  minutes_included = 400,
  phone_numbers = 1,
  voice_clones = 1,
  team_members = 1
WHERE plan_name = 'worker_bee';

-- Swarm: $297/mo, 1350 mins, 3 phones, 3 voices, 3 team
UPDATE va_subscription_plans SET
  minutes_included = 1350,
  phone_numbers = 3,
  voice_clones = 3,
  team_members = 3
WHERE plan_name = 'swarm';

-- Queen Bee: $697/mo, 3500 mins, 10 phones, 10 voices, 10 team
UPDATE va_subscription_plans SET
  minutes_included = 3500,
  phone_numbers = 10,
  voice_clones = 10,
  team_members = 10
WHERE plan_name = 'queen_bee';

-- Hive Mind: Custom, 10000 mins, unlimited (-1)
UPDATE va_subscription_plans SET
  minutes_included = 10000,
  phone_numbers = -1,
  voice_clones = -1,
  team_members = -1
WHERE plan_name = 'hive_mind';
