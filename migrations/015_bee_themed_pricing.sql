-- Migration 015: Update to Bee-Themed Pricing Tiers
-- Date: January 3, 2026
-- Description: Replace old pricing tiers with bee-themed plans

-- First, deactivate old plans
UPDATE va_subscription_plans
SET is_active = false
WHERE plan_name IN ('starter', 'pro', 'business', 'enterprise');

-- Insert new bee-themed plans (or update if they exist)
INSERT INTO va_subscription_plans (plan_name, display_name, price_cents, billing_interval, is_active)
VALUES
  ('free', 'Free Trial', 0, 'monthly', true),
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

-- Update minutes for each plan
UPDATE va_subscription_plans SET minutes_included = 30 WHERE plan_name = 'free';
UPDATE va_subscription_plans SET minutes_included = 400 WHERE plan_name = 'worker_bee';
UPDATE va_subscription_plans SET minutes_included = 1350 WHERE plan_name = 'swarm';
UPDATE va_subscription_plans SET minutes_included = 3500 WHERE plan_name = 'queen_bee';
UPDATE va_subscription_plans SET minutes_included = -1 WHERE plan_name = 'hive_mind'; -- -1 = unlimited
