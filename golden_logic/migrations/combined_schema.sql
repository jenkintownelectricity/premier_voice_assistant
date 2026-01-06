-- Combined Database Migrations for Premier Voice Assistant
-- Generated: 2026-01-06 10:51:12 UTC


-- ============================================
-- FILE: 001_add_subscription_system.sql
-- ============================================

-- Premier Voice Assistant - Subscription and Feature Gate System
-- Migration: 001_add_subscription_system
-- Purpose: Add subscription plans, feature gates, and usage tracking

-- ============================================================================
-- SUBSCRIPTION PLANS TABLE
-- ============================================================================
CREATE TABLE public.va_subscription_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_name VARCHAR(50) UNIQUE NOT NULL, -- 'free', 'starter', 'pro', 'enterprise'
    display_name VARCHAR(100) NOT NULL,
    price_cents INTEGER NOT NULL DEFAULT 0, -- Price in cents (e.g., $99 = 9900)
    billing_interval VARCHAR(20) DEFAULT 'monthly', -- 'monthly', 'yearly'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default plans
INSERT INTO public.va_subscription_plans (plan_name, display_name, price_cents, billing_interval) VALUES
    ('free', 'Free', 0, 'monthly'),
    ('starter', 'Starter', 9900, 'monthly'),
    ('pro', 'Pro', 29900, 'monthly'),
    ('enterprise', 'Enterprise', 0, 'custom');

-- ============================================================================
-- PLAN FEATURES TABLE
-- ============================================================================
CREATE TABLE public.va_plan_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id UUID NOT NULL REFERENCES public.va_subscription_plans(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL, -- 'max_minutes', 'max_assistants', 'custom_voices', etc.
    feature_value JSONB NOT NULL, -- Flexible storage for limits (numbers, booleans, etc.)
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(plan_id, feature_key)
);

-- Create index for faster feature lookups
CREATE INDEX idx_va_plan_features_plan_id ON public.va_plan_features(plan_id);
CREATE INDEX idx_va_plan_features_key ON public.va_plan_features(feature_key);

-- ============================================================================
-- USER SUBSCRIPTIONS TABLE
-- ============================================================================
CREATE TABLE public.va_user_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES public.va_subscription_plans(id),
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'cancelled', 'expired', 'trialing'
    current_period_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    current_period_end TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '1 month',
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    stripe_customer_id VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE public.va_user_subscriptions ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own subscription
CREATE POLICY "Users can view own subscription"
    ON public.va_user_subscriptions FOR SELECT
    USING (auth.uid() = user_id);

-- Create index for faster lookups
CREATE INDEX idx_va_user_subscriptions_user_id ON public.va_user_subscriptions(user_id);
CREATE INDEX idx_va_user_subscriptions_status ON public.va_user_subscriptions(status);

-- ============================================================================
-- USAGE TRACKING TABLE
-- ============================================================================
CREATE TABLE public.va_usage_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    minutes_used INTEGER DEFAULT 0,
    minutes_limit INTEGER,
    assistants_count INTEGER DEFAULT 0,
    assistants_limit INTEGER,
    voice_clones_count INTEGER DEFAULT 0,
    voice_clones_limit INTEGER,
    api_calls_count INTEGER DEFAULT 0,
    overage_minutes INTEGER DEFAULT 0, -- Minutes beyond limit
    overage_cost_cents INTEGER DEFAULT 0, -- Cost in cents for overages
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, period_start, period_end)
);

-- Enable Row Level Security
ALTER TABLE public.va_usage_tracking ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own usage
CREATE POLICY "Users can view own usage"
    ON public.va_usage_tracking FOR SELECT
    USING (auth.uid() = user_id);

-- Create indexes for faster queries
CREATE INDEX idx_va_usage_tracking_user_id ON public.va_usage_tracking(user_id);
CREATE INDEX idx_va_usage_tracking_period ON public.va_usage_tracking(period_start, period_end);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get current user's subscription plan
CREATE OR REPLACE FUNCTION va_get_user_plan(p_user_id UUID)
RETURNS TABLE (
    plan_name VARCHAR,
    display_name VARCHAR,
    status VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sp.plan_name,
        sp.display_name,
        us.status
    FROM public.va_user_subscriptions us
    JOIN public.va_subscription_plans sp ON us.plan_id = sp.id
    WHERE us.user_id = p_user_id
    AND us.status = 'active';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get user's feature limit
CREATE OR REPLACE FUNCTION va_get_feature_limit(p_user_id UUID, p_feature_key VARCHAR)
RETURNS JSONB AS $$
DECLARE
    v_feature_value JSONB;
BEGIN
    SELECT pf.feature_value INTO v_feature_value
    FROM public.va_user_subscriptions us
    JOIN public.va_plan_features pf ON us.plan_id = pf.plan_id
    WHERE us.user_id = p_user_id
    AND us.status = 'active'
    AND pf.feature_key = p_feature_key;

    -- If no subscription found, return free plan limit
    IF v_feature_value IS NULL THEN
        SELECT pf.feature_value INTO v_feature_value
        FROM public.va_subscription_plans sp
        JOIN public.va_plan_features pf ON sp.id = pf.plan_id
        WHERE sp.plan_name = 'free'
        AND pf.feature_key = p_feature_key;
    END IF;

    RETURN COALESCE(v_feature_value, '0'::jsonb);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user can perform action
CREATE OR REPLACE FUNCTION va_check_feature_gate(
    p_user_id UUID,
    p_feature_key VARCHAR,
    p_requested_amount INTEGER DEFAULT 1
)
RETURNS TABLE (
    allowed BOOLEAN,
    current_usage INTEGER,
    limit_value INTEGER,
    remaining INTEGER
) AS $$
DECLARE
    v_limit INTEGER;
    v_current_usage INTEGER;
    v_period_start TIMESTAMP WITH TIME ZONE;
    v_period_end TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Get current billing period
    SELECT
        current_period_start,
        current_period_end
    INTO v_period_start, v_period_end
    FROM public.va_user_subscriptions
    WHERE user_id = p_user_id
    AND status = 'active';

    -- Default to current month if no subscription
    IF v_period_start IS NULL THEN
        v_period_start := date_trunc('month', NOW());
        v_period_end := v_period_start + INTERVAL '1 month';
    END IF;

    -- Get feature limit
    v_limit := (va_get_feature_limit(p_user_id, p_feature_key))::INTEGER;

    -- Get current usage based on feature type
    IF p_feature_key = 'max_minutes' THEN
        SELECT COALESCE(minutes_used, 0) INTO v_current_usage
        FROM public.va_usage_tracking
        WHERE user_id = p_user_id
        AND period_start = v_period_start
        AND period_end = v_period_end;
    ELSIF p_feature_key = 'max_assistants' THEN
        SELECT COUNT(*) INTO v_current_usage
        FROM public.va_voice_clones
        WHERE user_id = p_user_id;
    ELSIF p_feature_key = 'max_voice_clones' THEN
        SELECT COUNT(*) INTO v_current_usage
        FROM public.va_voice_clones
        WHERE user_id = p_user_id;
    ELSE
        v_current_usage := 0;
    END IF;

    v_current_usage := COALESCE(v_current_usage, 0);

    -- Check if request would exceed limit (-1 means unlimited)
    RETURN QUERY SELECT
        (v_limit = -1 OR (v_current_usage + p_requested_amount) <= v_limit) AS allowed,
        v_current_usage AS current_usage,
        v_limit AS limit_value,
        CASE
            WHEN v_limit = -1 THEN -1
            ELSE GREATEST(0, v_limit - v_current_usage)
        END AS remaining;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to increment usage
CREATE OR REPLACE FUNCTION va_increment_usage(
    p_user_id UUID,
    p_minutes INTEGER DEFAULT 0,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS VOID AS $$
DECLARE
    v_period_start TIMESTAMP WITH TIME ZONE;
    v_period_end TIMESTAMP WITH TIME ZONE;
    v_limit INTEGER;
BEGIN
    -- Get current billing period
    SELECT
        current_period_start,
        current_period_end
    INTO v_period_start, v_period_end
    FROM public.va_user_subscriptions
    WHERE user_id = p_user_id
    AND status = 'active';

    -- Default to current month if no subscription
    IF v_period_start IS NULL THEN
        v_period_start := date_trunc('month', NOW());
        v_period_end := v_period_start + INTERVAL '1 month';
    END IF;

    -- Get minute limit
    v_limit := (va_get_feature_limit(p_user_id, 'max_minutes'))::INTEGER;

    -- Upsert usage tracking
    INSERT INTO public.va_usage_tracking (
        user_id,
        period_start,
        period_end,
        minutes_used,
        minutes_limit,
        metadata
    ) VALUES (
        p_user_id,
        v_period_start,
        v_period_end,
        p_minutes,
        v_limit,
        p_metadata
    )
    ON CONFLICT (user_id, period_start, period_end)
    DO UPDATE SET
        minutes_used = va_usage_tracking.minutes_used + p_minutes,
        updated_at = NOW(),
        metadata = va_usage_tracking.metadata || p_metadata;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Trigger to auto-update updated_at on subscriptions
CREATE TRIGGER update_va_user_subscriptions_updated_at
    BEFORE UPDATE ON public.va_user_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION va_update_updated_at_column();

-- Trigger to auto-update updated_at on usage tracking
CREATE TRIGGER update_va_usage_tracking_updated_at
    BEFORE UPDATE ON public.va_usage_tracking
    FOR EACH ROW
    EXECUTE FUNCTION va_update_updated_at_column();

-- Trigger to auto-update updated_at on subscription plans
CREATE TRIGGER update_va_subscription_plans_updated_at
    BEFORE UPDATE ON public.va_subscription_plans
    FOR EACH ROW
    EXECUTE FUNCTION va_update_updated_at_column();

-- ============================================================================
-- AUTOMATIC USER SUBSCRIPTION CREATION
-- ============================================================================

-- Function to create default subscription for new users
CREATE OR REPLACE FUNCTION va_create_default_subscription()
RETURNS TRIGGER AS $$
DECLARE
    v_free_plan_id UUID;
BEGIN
    -- Get the free plan ID
    SELECT id INTO v_free_plan_id
    FROM public.va_subscription_plans
    WHERE plan_name = 'free'
    LIMIT 1;

    -- Create subscription for new user
    INSERT INTO public.va_user_subscriptions (
        user_id,
        plan_id,
        status,
        current_period_start,
        current_period_end
    ) VALUES (
        NEW.id,
        v_free_plan_id,
        'active',
        NOW(),
        NOW() + INTERVAL '1 month'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create default subscription when user profile is created
CREATE TRIGGER create_default_subscription_on_profile
    AFTER INSERT ON public.va_user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION va_create_default_subscription();

-- ============================================================================
-- ADMIN HELPER FUNCTIONS
-- ============================================================================

-- Function to upgrade user subscription (admin only)
CREATE OR REPLACE FUNCTION va_admin_upgrade_user(
    p_user_id UUID,
    p_plan_name VARCHAR
)
RETURNS VOID AS $$
DECLARE
    v_plan_id UUID;
BEGIN
    -- Get plan ID
    SELECT id INTO v_plan_id
    FROM public.va_subscription_plans
    WHERE plan_name = p_plan_name
    AND is_active = TRUE;

    IF v_plan_id IS NULL THEN
        RAISE EXCEPTION 'Plan not found: %', p_plan_name;
    END IF;

    -- Update subscription
    UPDATE public.va_user_subscriptions
    SET
        plan_id = v_plan_id,
        current_period_start = NOW(),
        current_period_end = NOW() + INTERVAL '1 month',
        updated_at = NOW()
    WHERE user_id = p_user_id;

    -- Create if doesn't exist
    IF NOT FOUND THEN
        INSERT INTO public.va_user_subscriptions (
            user_id,
            plan_id,
            status,
            current_period_start,
            current_period_end
        ) VALUES (
            p_user_id,
            v_plan_id,
            'active',
            NOW(),
            NOW() + INTERVAL '1 month'
        );
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- VIEWS FOR EASIER QUERYING
-- ============================================================================

-- View: User subscription with plan details
CREATE OR REPLACE VIEW va_user_subscription_details AS
SELECT
    us.user_id,
    sp.plan_name,
    sp.display_name,
    sp.price_cents,
    us.status,
    us.current_period_start,
    us.current_period_end,
    us.cancel_at_period_end,
    us.created_at AS subscription_created_at
FROM public.va_user_subscriptions us
JOIN public.va_subscription_plans sp ON us.plan_id = sp.id;

-- View: Current period usage summary
CREATE OR REPLACE VIEW va_current_usage_summary AS
SELECT
    ut.user_id,
    usd.plan_name,
    usd.display_name,
    ut.minutes_used,
    ut.minutes_limit,
    CASE
        WHEN ut.minutes_limit = -1 THEN 'unlimited'
        ELSE ROUND((ut.minutes_used::NUMERIC / NULLIF(ut.minutes_limit, 0)) * 100, 2)::TEXT || '%'
    END AS usage_percentage,
    ut.assistants_count,
    ut.assistants_limit,
    ut.voice_clones_count,
    ut.voice_clones_limit,
    ut.overage_minutes,
    ut.overage_cost_cents,
    ut.period_start,
    ut.period_end
FROM public.va_usage_tracking ut
JOIN va_user_subscription_details usd ON ut.user_id = usd.user_id
WHERE ut.period_end > NOW();

-- Grant permissions
GRANT SELECT ON va_user_subscription_details TO authenticated;
GRANT SELECT ON va_current_usage_summary TO authenticated;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE public.va_subscription_plans IS 'Subscription plans (Free, Starter, Pro, Enterprise)';
COMMENT ON TABLE public.va_plan_features IS 'Feature limits for each plan';
COMMENT ON TABLE public.va_user_subscriptions IS 'User subscription status and billing info';
COMMENT ON TABLE public.va_usage_tracking IS 'Monthly usage tracking for enforcing limits';

COMMENT ON FUNCTION va_get_user_plan IS 'Get active subscription plan for a user';
COMMENT ON FUNCTION va_get_feature_limit IS 'Get feature limit value for a user';
COMMENT ON FUNCTION va_check_feature_gate IS 'Check if user can perform an action based on their plan';
COMMENT ON FUNCTION va_increment_usage IS 'Increment usage counters for a user';
COMMENT ON FUNCTION va_admin_upgrade_user IS 'Admin function to upgrade user subscription';

-- ============================================
-- FILE: 002_add_client_permissions.sql
-- ============================================

-- Migration 002: Add client permissions for mobile/web apps
-- Purpose: Allow authenticated clients to read subscription data and check limits

-- ============================================================================
-- GRANT READ PERMISSIONS TO AUTHENTICATED USERS
-- ============================================================================

-- Allow reading subscription plans (public data)
GRANT SELECT ON public.va_subscription_plans TO authenticated;
GRANT SELECT ON public.va_subscription_plans TO anon;

-- Allow reading plan features (public data - what's available in each plan)
GRANT SELECT ON public.va_plan_features TO authenticated;
GRANT SELECT ON public.va_plan_features TO anon;

-- RLS already handles users only seeing their own subscriptions
GRANT SELECT ON public.va_user_subscriptions TO authenticated;

-- RLS already handles users only seeing their own usage
GRANT SELECT ON public.va_usage_tracking TO authenticated;

-- Grant access to views (already have RLS through underlying tables)
GRANT SELECT ON va_user_subscription_details TO authenticated;
GRANT SELECT ON va_current_usage_summary TO authenticated;

-- ============================================================================
-- ADD CLIENT-FRIENDLY FUNCTION: Check Feature Access
-- ============================================================================

-- Function for clients to check if they can use a feature
-- This is safe for clients to call (doesn't bypass RLS)
CREATE OR REPLACE FUNCTION va_client_check_feature(
    p_feature_key VARCHAR,
    p_requested_amount INTEGER DEFAULT 1
)
RETURNS TABLE (
    allowed BOOLEAN,
    current_usage INTEGER,
    limit_value INTEGER,
    remaining INTEGER,
    plan_name VARCHAR,
    upgrade_required BOOLEAN
) AS $$
DECLARE
    v_user_id UUID;
BEGIN
    -- Get the authenticated user's ID
    v_user_id := auth.uid();

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User not authenticated';
    END IF;

    -- Call the existing check function with the user's ID
    RETURN QUERY
    SELECT
        cfg.allowed,
        cfg.current_usage,
        cfg.limit_value,
        cfg.remaining,
        usd.plan_name,
        NOT cfg.allowed AS upgrade_required
    FROM va_check_feature_gate(v_user_id, p_feature_key, p_requested_amount) cfg
    LEFT JOIN va_user_subscription_details usd ON usd.user_id = v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execution to authenticated users
GRANT EXECUTE ON FUNCTION va_client_check_feature TO authenticated;

-- ============================================================================
-- ADD CLIENT-FRIENDLY FUNCTION: Get My Subscription
-- ============================================================================

-- Function for clients to easily get their subscription info
CREATE OR REPLACE FUNCTION va_client_get_my_subscription()
RETURNS TABLE (
    plan_name VARCHAR,
    display_name VARCHAR,
    price_cents INTEGER,
    status VARCHAR,
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    days_remaining INTEGER
) AS $$
DECLARE
    v_user_id UUID;
BEGIN
    v_user_id := auth.uid();

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User not authenticated';
    END IF;

    RETURN QUERY
    SELECT
        usd.plan_name,
        usd.display_name,
        usd.price_cents,
        usd.status,
        usd.current_period_start,
        usd.current_period_end,
        EXTRACT(DAY FROM (usd.current_period_end - NOW()))::INTEGER AS days_remaining
    FROM va_user_subscription_details usd
    WHERE usd.user_id = v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION va_client_get_my_subscription TO authenticated;

-- ============================================================================
-- ADD CLIENT-FRIENDLY FUNCTION: Get My Usage
-- ============================================================================

-- Function for clients to get their current usage
CREATE OR REPLACE FUNCTION va_client_get_my_usage()
RETURNS TABLE (
    plan_name VARCHAR,
    minutes_used INTEGER,
    minutes_limit INTEGER,
    usage_percentage TEXT,
    assistants_count INTEGER,
    assistants_limit INTEGER,
    voice_clones_count INTEGER,
    voice_clones_limit INTEGER,
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    v_user_id UUID;
BEGIN
    v_user_id := auth.uid();

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User not authenticated';
    END IF;

    RETURN QUERY
    SELECT
        cus.plan_name,
        cus.minutes_used,
        cus.minutes_limit,
        cus.usage_percentage,
        cus.assistants_count,
        cus.assistants_limit,
        cus.voice_clones_count,
        cus.voice_clones_limit,
        cus.period_start,
        cus.period_end
    FROM va_current_usage_summary cus
    WHERE cus.user_id = v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION va_client_get_my_usage TO authenticated;

-- ============================================================================
-- ADD CLIENT-FRIENDLY FUNCTION: Get Available Plans
-- ============================================================================

-- Function to get all available plans with their features
CREATE OR REPLACE FUNCTION va_client_get_available_plans()
RETURNS TABLE (
    plan_name VARCHAR,
    display_name VARCHAR,
    price_cents INTEGER,
    billing_interval VARCHAR,
    features JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sp.plan_name,
        sp.display_name,
        sp.price_cents,
        sp.billing_interval,
        jsonb_object_agg(
            pf.feature_key,
            jsonb_build_object(
                'value', pf.feature_value,
                'description', pf.description
            )
        ) AS features
    FROM va_subscription_plans sp
    LEFT JOIN va_plan_features pf ON sp.id = pf.plan_id
    WHERE sp.is_active = TRUE
    GROUP BY sp.id, sp.plan_name, sp.display_name, sp.price_cents, sp.billing_interval
    ORDER BY sp.price_cents;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION va_client_get_available_plans TO authenticated;
GRANT EXECUTE ON FUNCTION va_client_get_available_plans TO anon;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION va_client_check_feature IS 'Client-safe function to check feature access (uses auth.uid())';
COMMENT ON FUNCTION va_client_get_my_subscription IS 'Get current user subscription info';
COMMENT ON FUNCTION va_client_get_my_usage IS 'Get current user usage statistics';
COMMENT ON FUNCTION va_client_get_available_plans IS 'Get all available subscription plans with features';

-- ============================================
-- FILE: 003_add_stripe_fields.sql
-- ============================================

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

-- ============================================
-- FILE: 004_add_discount_codes.sql
-- ============================================

-- Migration: Add Discount Codes System
-- Run this in Supabase SQL Editor

-- Discount codes table
CREATE TABLE IF NOT EXISTS va_discount_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    description TEXT,

    -- Discount type: 'percentage', 'fixed', 'minutes', 'upgrade'
    discount_type TEXT NOT NULL,

    -- Value depends on type:
    -- percentage: 0-100 (e.g., 20 = 20% off)
    -- fixed: amount in cents (e.g., 1000 = $10 off)
    -- minutes: bonus minutes to add
    -- upgrade: plan_name to upgrade to
    discount_value INTEGER NOT NULL,

    -- Optional: specific plan this applies to
    applicable_plan TEXT,

    -- Usage limits
    max_uses INTEGER DEFAULT NULL,  -- NULL = unlimited
    current_uses INTEGER DEFAULT 0,
    max_uses_per_user INTEGER DEFAULT 1,

    -- Validity period
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,

    CONSTRAINT valid_discount_type CHECK (discount_type IN ('percentage', 'fixed', 'minutes', 'upgrade'))
);

-- Track code redemptions
CREATE TABLE IF NOT EXISTS va_code_redemptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_id UUID NOT NULL REFERENCES va_discount_codes(id),
    user_id UUID NOT NULL,
    redeemed_at TIMESTAMPTZ DEFAULT NOW(),

    -- What was applied
    applied_value INTEGER,  -- Actual discount/minutes applied
    metadata JSONB DEFAULT '{}',

    UNIQUE(code_id, user_id)  -- One redemption per user per code
);

-- Bonus minutes tracking (separate from subscription minutes)
ALTER TABLE va_usage_tracking
ADD COLUMN IF NOT EXISTS bonus_minutes INTEGER DEFAULT 0;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_discount_codes_code ON va_discount_codes(code);
CREATE INDEX IF NOT EXISTS idx_discount_codes_active ON va_discount_codes(is_active, valid_until);
CREATE INDEX IF NOT EXISTS idx_code_redemptions_user ON va_code_redemptions(user_id);
CREATE INDEX IF NOT EXISTS idx_code_redemptions_code ON va_code_redemptions(code_id);

-- Function to validate and redeem a discount code
CREATE OR REPLACE FUNCTION va_redeem_discount_code(
    p_user_id UUID,
    p_code TEXT
) RETURNS JSONB AS $$
DECLARE
    v_code_record RECORD;
    v_user_redemptions INTEGER;
    v_result JSONB;
BEGIN
    -- Get code details
    SELECT * INTO v_code_record
    FROM va_discount_codes
    WHERE code = UPPER(p_code)
      AND is_active = TRUE
      AND (valid_from IS NULL OR valid_from <= NOW())
      AND (valid_until IS NULL OR valid_until > NOW());

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', FALSE,
            'error', 'Invalid or expired code'
        );
    END IF;

    -- Check max uses
    IF v_code_record.max_uses IS NOT NULL AND v_code_record.current_uses >= v_code_record.max_uses THEN
        RETURN jsonb_build_object(
            'success', FALSE,
            'error', 'Code has reached maximum uses'
        );
    END IF;

    -- Check user redemptions
    SELECT COUNT(*) INTO v_user_redemptions
    FROM va_code_redemptions
    WHERE code_id = v_code_record.id AND user_id = p_user_id;

    IF v_user_redemptions >= v_code_record.max_uses_per_user THEN
        RETURN jsonb_build_object(
            'success', FALSE,
            'error', 'You have already used this code'
        );
    END IF;

    -- Record redemption
    INSERT INTO va_code_redemptions (code_id, user_id, applied_value)
    VALUES (v_code_record.id, p_user_id, v_code_record.discount_value);

    -- Update code usage count
    UPDATE va_discount_codes
    SET current_uses = current_uses + 1
    WHERE id = v_code_record.id;

    -- Apply the discount based on type
    IF v_code_record.discount_type = 'minutes' THEN
        -- Add bonus minutes
        UPDATE va_usage_tracking
        SET bonus_minutes = COALESCE(bonus_minutes, 0) + v_code_record.discount_value
        WHERE user_id = p_user_id
          AND period_start <= NOW()
          AND period_end > NOW();

        -- If no current period, create one
        IF NOT FOUND THEN
            INSERT INTO va_usage_tracking (user_id, period_start, period_end, bonus_minutes)
            VALUES (
                p_user_id,
                NOW(),
                NOW() + INTERVAL '30 days',
                v_code_record.discount_value
            );
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'success', TRUE,
        'discount_type', v_code_record.discount_type,
        'discount_value', v_code_record.discount_value,
        'description', v_code_record.description,
        'message', CASE v_code_record.discount_type
            WHEN 'minutes' THEN format('Added %s bonus minutes!', v_code_record.discount_value)
            WHEN 'percentage' THEN format('%s%% off your next payment!', v_code_record.discount_value)
            WHEN 'fixed' THEN format('$%s off your next payment!', v_code_record.discount_value / 100.0)
            WHEN 'upgrade' THEN format('Upgraded to %s plan!', v_code_record.discount_value)
            ELSE 'Code redeemed successfully!'
        END
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update feature gate check to include bonus minutes
-- Drop old version first (had VARCHAR instead of TEXT)
DROP FUNCTION IF EXISTS va_check_feature_gate(UUID, VARCHAR, INTEGER);

CREATE OR REPLACE FUNCTION va_check_feature_gate(
    p_user_id UUID,
    p_feature_key TEXT,
    p_requested_amount INTEGER DEFAULT 1
) RETURNS TABLE (
    allowed BOOLEAN,
    current_usage INTEGER,
    limit_value INTEGER,
    remaining INTEGER
) AS $$
DECLARE
    v_plan_name TEXT;
    v_feature_value INTEGER;
    v_current_usage INTEGER;
    v_bonus_minutes INTEGER;
    v_effective_limit INTEGER;
BEGIN
    -- Get user's plan
    SELECT sp.plan_name INTO v_plan_name
    FROM va_user_subscriptions us
    JOIN va_subscription_plans sp ON us.plan_id = sp.id
    WHERE us.user_id = p_user_id AND us.status = 'active';

    IF v_plan_name IS NULL THEN
        v_plan_name := 'free';
    END IF;

    -- Get feature limit
    SELECT pf.feature_value INTO v_feature_value
    FROM va_plan_features pf
    JOIN va_subscription_plans sp ON pf.plan_id = sp.id
    WHERE sp.plan_name = v_plan_name AND pf.feature_key = p_feature_key;

    IF v_feature_value IS NULL THEN
        v_feature_value := 0;
    END IF;

    -- Get current usage and bonus minutes
    SELECT
        COALESCE(ut.minutes_used, 0),
        COALESCE(ut.bonus_minutes, 0)
    INTO v_current_usage, v_bonus_minutes
    FROM va_usage_tracking ut
    WHERE ut.user_id = p_user_id
      AND ut.period_start <= NOW()
      AND ut.period_end > NOW()
    ORDER BY ut.period_start DESC
    LIMIT 1;

    IF v_current_usage IS NULL THEN
        v_current_usage := 0;
        v_bonus_minutes := 0;
    END IF;

    -- For minutes, add bonus to effective limit
    IF p_feature_key = 'max_minutes' THEN
        v_effective_limit := v_feature_value + v_bonus_minutes;
    ELSE
        v_effective_limit := v_feature_value;
    END IF;

    RETURN QUERY SELECT
        (v_current_usage + p_requested_amount <= v_effective_limit) AS allowed,
        v_current_usage AS current_usage,
        v_effective_limit AS limit_value,
        GREATEST(0, v_effective_limit - v_current_usage) AS remaining;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissions
GRANT EXECUTE ON FUNCTION va_redeem_discount_code TO authenticated;
GRANT EXECUTE ON FUNCTION va_check_feature_gate TO authenticated;

-- ============================================
-- FILE: 005_add_client_permissions_v2.sql
-- ============================================

-- Migration 005: Client permissions for discount codes and bonus minutes
-- Run this AFTER migrations 003 and 004 in Supabase SQL Editor

-- ============================================================================
-- RLS POLICIES FOR DISCOUNT CODES
-- ============================================================================

-- Enable RLS on discount codes table
ALTER TABLE va_discount_codes ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS "Anyone can view active discount codes" ON va_discount_codes;
DROP POLICY IF EXISTS "Users can view their own redemptions" ON va_code_redemptions;
DROP POLICY IF EXISTS "Users can redeem codes" ON va_code_redemptions;

-- Public can read active discount codes (to validate before redeeming)
CREATE POLICY "Anyone can view active discount codes" ON va_discount_codes
    FOR SELECT USING (is_active = TRUE);

-- Enable RLS on code redemptions
ALTER TABLE va_code_redemptions ENABLE ROW LEVEL SECURITY;

-- Users can only see their own redemptions
CREATE POLICY "Users can view their own redemptions" ON va_code_redemptions
    FOR SELECT USING (user_id = auth.uid());

-- Users can insert their own redemptions (via function)
CREATE POLICY "Users can redeem codes" ON va_code_redemptions
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- Grant permissions
GRANT SELECT ON va_discount_codes TO authenticated;
GRANT SELECT ON va_discount_codes TO anon;
GRANT SELECT, INSERT ON va_code_redemptions TO authenticated;

-- ============================================================================
-- CLIENT FUNCTION: Redeem Discount Code
-- ============================================================================

-- Wrapper function for clients to redeem codes safely
CREATE OR REPLACE FUNCTION va_client_redeem_code(p_code TEXT)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID;
BEGIN
    v_user_id := auth.uid();

    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object(
            'success', FALSE,
            'error', 'User not authenticated'
        );
    END IF;

    -- Call the existing redemption function
    RETURN va_redeem_discount_code(v_user_id, p_code);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION va_client_redeem_code TO authenticated;

-- ============================================================================
-- UPDATE: Get My Usage with Bonus Minutes
-- ============================================================================

-- Drop and recreate to add bonus_minutes
DROP FUNCTION IF EXISTS va_client_get_my_usage();

CREATE OR REPLACE FUNCTION va_client_get_my_usage()
RETURNS TABLE (
    plan_name VARCHAR,
    minutes_used INTEGER,
    minutes_limit INTEGER,
    bonus_minutes INTEGER,
    effective_limit INTEGER,
    minutes_remaining INTEGER,
    usage_percentage TEXT,
    assistants_count INTEGER,
    assistants_limit INTEGER,
    voice_clones_count INTEGER,
    voice_clones_limit INTEGER,
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE,
    days_remaining INTEGER
) AS $$
DECLARE
    v_user_id UUID;
BEGIN
    v_user_id := auth.uid();

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User not authenticated';
    END IF;

    RETURN QUERY
    SELECT
        cus.plan_name,
        cus.minutes_used,
        cus.minutes_limit,
        COALESCE(ut.bonus_minutes, 0)::INTEGER AS bonus_minutes,
        (cus.minutes_limit + COALESCE(ut.bonus_minutes, 0))::INTEGER AS effective_limit,
        GREATEST(0, cus.minutes_limit + COALESCE(ut.bonus_minutes, 0) - cus.minutes_used)::INTEGER AS minutes_remaining,
        ROUND((cus.minutes_used::NUMERIC / NULLIF(cus.minutes_limit + COALESCE(ut.bonus_minutes, 0), 0) * 100), 1)::TEXT || '%' AS usage_percentage,
        cus.assistants_count,
        cus.assistants_limit,
        cus.voice_clones_count,
        cus.voice_clones_limit,
        cus.period_start,
        cus.period_end,
        EXTRACT(DAY FROM (cus.period_end - NOW()))::INTEGER AS days_remaining
    FROM va_current_usage_summary cus
    LEFT JOIN va_usage_tracking ut ON ut.user_id = cus.user_id
        AND ut.period_start <= NOW()
        AND ut.period_end > NOW()
    WHERE cus.user_id = v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION va_client_get_my_usage TO authenticated;

-- ============================================================================
-- CLIENT FUNCTION: Get My Redemptions
-- ============================================================================

CREATE OR REPLACE FUNCTION va_client_get_my_redemptions()
RETURNS TABLE (
    code TEXT,
    discount_type TEXT,
    discount_value INTEGER,
    description TEXT,
    redeemed_at TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    v_user_id UUID;
BEGIN
    v_user_id := auth.uid();

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User not authenticated';
    END IF;

    RETURN QUERY
    SELECT
        dc.code,
        dc.discount_type,
        dc.discount_value,
        dc.description,
        cr.redeemed_at
    FROM va_code_redemptions cr
    JOIN va_discount_codes dc ON dc.id = cr.code_id
    WHERE cr.user_id = v_user_id
    ORDER BY cr.redeemed_at DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION va_client_get_my_redemptions TO authenticated;

-- ============================================================================
-- CLIENT FUNCTION: Check if Code is Valid (without redeeming)
-- ============================================================================

CREATE OR REPLACE FUNCTION va_client_validate_code(p_code TEXT)
RETURNS JSONB AS $$
DECLARE
    v_code_record RECORD;
    v_user_id UUID;
    v_user_redemptions INTEGER;
BEGIN
    v_user_id := auth.uid();

    -- Get code details
    SELECT * INTO v_code_record
    FROM va_discount_codes
    WHERE code = UPPER(p_code)
      AND is_active = TRUE
      AND (valid_from IS NULL OR valid_from <= NOW())
      AND (valid_until IS NULL OR valid_until > NOW());

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'valid', FALSE,
            'error', 'Invalid or expired code'
        );
    END IF;

    -- Check max uses
    IF v_code_record.max_uses IS NOT NULL AND v_code_record.current_uses >= v_code_record.max_uses THEN
        RETURN jsonb_build_object(
            'valid', FALSE,
            'error', 'Code has reached maximum uses'
        );
    END IF;

    -- Check user redemptions if authenticated
    IF v_user_id IS NOT NULL THEN
        SELECT COUNT(*) INTO v_user_redemptions
        FROM va_code_redemptions
        WHERE code_id = v_code_record.id AND user_id = v_user_id;

        IF v_user_redemptions >= v_code_record.max_uses_per_user THEN
            RETURN jsonb_build_object(
                'valid', FALSE,
                'error', 'You have already used this code'
            );
        END IF;
    END IF;

    -- Code is valid
    RETURN jsonb_build_object(
        'valid', TRUE,
        'discount_type', v_code_record.discount_type,
        'discount_value', v_code_record.discount_value,
        'description', v_code_record.description,
        'message', CASE v_code_record.discount_type
            WHEN 'minutes' THEN format('%s bonus minutes', v_code_record.discount_value)
            WHEN 'percentage' THEN format('%s%% off', v_code_record.discount_value)
            WHEN 'fixed' THEN format('$%s off', v_code_record.discount_value / 100.0)
            ELSE 'Valid discount'
        END
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION va_client_validate_code TO authenticated;
GRANT EXECUTE ON FUNCTION va_client_validate_code TO anon;

-- ============================================================================
-- CLIENT FUNCTION: Get Subscription with Payment Info
-- ============================================================================

-- Update subscription function to include Stripe status
DROP FUNCTION IF EXISTS va_client_get_my_subscription();

CREATE OR REPLACE FUNCTION va_client_get_my_subscription()
RETURNS TABLE (
    plan_name VARCHAR,
    display_name VARCHAR,
    price_cents INTEGER,
    status VARCHAR,
    current_period_start TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    days_remaining INTEGER,
    has_payment_method BOOLEAN
) AS $$
DECLARE
    v_user_id UUID;
BEGIN
    v_user_id := auth.uid();

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User not authenticated';
    END IF;

    RETURN QUERY
    SELECT
        usd.plan_name,
        usd.display_name,
        usd.price_cents,
        usd.status,
        usd.current_period_start,
        usd.current_period_end,
        EXTRACT(DAY FROM (usd.current_period_end - NOW()))::INTEGER AS days_remaining,
        (up.stripe_customer_id IS NOT NULL)::BOOLEAN AS has_payment_method
    FROM va_user_subscription_details usd
    LEFT JOIN va_user_profiles up ON up.user_id = usd.user_id
    WHERE usd.user_id = v_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION va_client_get_my_subscription TO authenticated;

-- ============================================================================
-- GRANT PERMISSIONS ON NEW COLUMNS
-- ============================================================================

-- Ensure users can read bonus_minutes from usage tracking
-- (Already have SELECT on va_usage_tracking from migration 002)

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION va_client_redeem_code IS 'Client-safe function to redeem discount codes';
COMMENT ON FUNCTION va_client_get_my_redemptions IS 'Get list of codes the user has redeemed';
COMMENT ON FUNCTION va_client_validate_code IS 'Check if a code is valid without redeeming';
COMMENT ON FUNCTION va_client_get_my_usage IS 'Get usage including bonus minutes';
COMMENT ON FUNCTION va_client_get_my_subscription IS 'Get subscription with payment status';

-- ============================================
-- FILE: 006_add_assistants_and_call_logs.sql
-- ============================================

-- Migration 006: Add Assistants and Call Logs
-- This migration adds AI assistant management and call history tracking

-- =====================================================
-- ASSISTANTS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS public.va_assistants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    voice_id VARCHAR(100) DEFAULT 'default',
    model VARCHAR(100) DEFAULT 'claude-3-5-sonnet-20241022',
    temperature DECIMAL(3,2) DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 150,
    first_message TEXT,
    is_active BOOLEAN DEFAULT true,

    -- Advanced latency optimization settings
    vad_sensitivity DECIMAL(3,2) DEFAULT 0.5, -- Voice Activity Detection threshold (0-1)
    endpointing_ms INTEGER DEFAULT 600, -- Silence duration to detect end of speech
    enable_bargein BOOLEAN DEFAULT true, -- Allow user to interrupt assistant
    streaming_chunks BOOLEAN DEFAULT true, -- Stream TTS output in chunks
    first_message_latency_ms INTEGER DEFAULT 800, -- Target latency for first response
    turn_detection_mode VARCHAR(50) DEFAULT 'server_vad', -- 'server_vad', 'semantic', 'both'

    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_va_assistants_user_id ON public.va_assistants(user_id);
CREATE INDEX IF NOT EXISTS idx_va_assistants_is_active ON public.va_assistants(is_active);

-- =====================================================
-- CALL LOGS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS public.va_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    assistant_id UUID REFERENCES public.va_assistants(id) ON DELETE SET NULL,

    -- Call metadata
    call_type VARCHAR(20) NOT NULL DEFAULT 'web', -- 'web', 'phone_inbound', 'phone_outbound', 'api'
    phone_number VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'completed', -- 'completed', 'failed', 'in_progress', 'missed'

    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER DEFAULT 0,

    -- Cost tracking
    cost_cents INTEGER DEFAULT 0,
    minutes_used DECIMAL(10,2) DEFAULT 0,

    -- Content
    transcript JSONB DEFAULT '[]', -- Array of {role, content, timestamp}
    summary TEXT,

    -- Audio
    recording_url TEXT,

    -- Analysis
    sentiment VARCHAR(20), -- 'positive', 'neutral', 'negative'
    ended_reason VARCHAR(50), -- 'user_ended', 'assistant_ended', 'timeout', 'error'

    -- Additional data
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_va_call_logs_user_id ON public.va_call_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_va_call_logs_assistant_id ON public.va_call_logs(assistant_id);
CREATE INDEX IF NOT EXISTS idx_va_call_logs_started_at ON public.va_call_logs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_va_call_logs_status ON public.va_call_logs(status);

-- =====================================================
-- ROW LEVEL SECURITY
-- =====================================================

-- Enable RLS
ALTER TABLE public.va_assistants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.va_call_logs ENABLE ROW LEVEL SECURITY;

-- Assistants policies
CREATE POLICY "Users can view own assistants"
    ON public.va_assistants FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own assistants"
    ON public.va_assistants FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own assistants"
    ON public.va_assistants FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own assistants"
    ON public.va_assistants FOR DELETE
    USING (auth.uid() = user_id);

-- Call logs policies
CREATE POLICY "Users can view own call logs"
    ON public.va_call_logs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own call logs"
    ON public.va_call_logs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Service role can do everything (for backend)
CREATE POLICY "Service role full access to assistants"
    ON public.va_assistants FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to call logs"
    ON public.va_call_logs FOR ALL
    USING (auth.role() = 'service_role');

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Update timestamp on assistant modification
CREATE OR REPLACE FUNCTION update_assistant_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_va_assistants_timestamp
    BEFORE UPDATE ON public.va_assistants
    FOR EACH ROW
    EXECUTE FUNCTION update_assistant_timestamp();

-- =====================================================
-- BACKEND FUNCTIONS (Service Role)
-- =====================================================

-- Get assistant by ID
CREATE OR REPLACE FUNCTION va_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.user_id, a.name, a.description, a.system_prompt,
        a.voice_id, a.model, a.temperature, a.max_tokens,
        a.first_message, a.is_active, a.vad_sensitivity, a.endpointing_ms,
        a.enable_bargein, a.streaming_chunks, a.first_message_latency_ms,
        a.turn_detection_mode, a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create call log
CREATE OR REPLACE FUNCTION va_create_call_log(
    p_user_id UUID,
    p_assistant_id UUID,
    p_call_type VARCHAR DEFAULT 'web',
    p_phone_number VARCHAR DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_call_id UUID;
BEGIN
    INSERT INTO public.va_call_logs (
        user_id, assistant_id, call_type, phone_number, status, started_at
    ) VALUES (
        p_user_id, p_assistant_id, p_call_type, p_phone_number, 'in_progress', NOW()
    ) RETURNING id INTO v_call_id;

    RETURN v_call_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- End call and update metrics
CREATE OR REPLACE FUNCTION va_end_call(
    p_call_id UUID,
    p_transcript JSONB,
    p_summary TEXT DEFAULT NULL,
    p_ended_reason VARCHAR DEFAULT 'user_ended',
    p_recording_url TEXT DEFAULT NULL,
    p_sentiment VARCHAR DEFAULT 'neutral'
)
RETURNS VOID AS $$
DECLARE
    v_started_at TIMESTAMPTZ;
    v_duration INTEGER;
    v_minutes DECIMAL;
    v_cost INTEGER;
BEGIN
    -- Get start time
    SELECT started_at INTO v_started_at
    FROM public.va_call_logs
    WHERE id = p_call_id;

    -- Calculate duration
    v_duration := EXTRACT(EPOCH FROM (NOW() - v_started_at))::INTEGER;
    v_minutes := v_duration / 60.0;
    v_cost := CEIL(v_minutes * 1.15)::INTEGER; -- $0.0115/min in cents

    -- Update call log
    UPDATE public.va_call_logs
    SET
        ended_at = NOW(),
        duration_seconds = v_duration,
        minutes_used = v_minutes,
        cost_cents = v_cost,
        transcript = p_transcript,
        summary = p_summary,
        ended_reason = p_ended_reason,
        recording_url = p_recording_url,
        sentiment = p_sentiment,
        status = 'completed'
    WHERE id = p_call_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get call stats for user
CREATE OR REPLACE FUNCTION va_get_call_stats(p_user_id UUID)
RETURNS TABLE (
    total_calls BIGINT,
    total_duration_seconds BIGINT,
    total_cost_cents BIGINT,
    avg_duration_seconds INTEGER,
    completed_calls BIGINT,
    failed_calls BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_calls,
        COALESCE(SUM(duration_seconds), 0)::BIGINT as total_duration_seconds,
        COALESCE(SUM(cost_cents), 0)::BIGINT as total_cost_cents,
        COALESCE(AVG(duration_seconds)::INTEGER, 0) as avg_duration_seconds,
        COUNT(*) FILTER (WHERE status = 'completed')::BIGINT as completed_calls,
        COUNT(*) FILTER (WHERE status = 'failed')::BIGINT as failed_calls
    FROM public.va_call_logs
    WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- CLIENT-SAFE FUNCTIONS
-- =====================================================

-- Get authenticated user's assistants
CREATE OR REPLACE FUNCTION va_client_get_my_assistants()
RETURNS TABLE (
    id UUID,
    name VARCHAR,
    description TEXT,
    voice_id VARCHAR,
    model VARCHAR,
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    call_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.name, a.description, a.voice_id, a.model,
        a.is_active, a.created_at, a.updated_at,
        COALESCE((
            SELECT COUNT(*) FROM public.va_call_logs cl
            WHERE cl.assistant_id = a.id
        ), 0)::BIGINT as call_count
    FROM public.va_assistants a
    WHERE a.user_id = auth.uid()
    ORDER BY a.created_at DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get single assistant details
CREATE OR REPLACE FUNCTION va_client_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.name, a.description, a.system_prompt, a.voice_id,
        a.model, a.temperature, a.max_tokens, a.first_message,
        a.is_active, a.vad_sensitivity, a.endpointing_ms, a.enable_bargein,
        a.streaming_chunks, a.first_message_latency_ms, a.turn_detection_mode,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id AND a.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create assistant (with plan limit check)
CREATE OR REPLACE FUNCTION va_client_create_assistant(
    p_name VARCHAR,
    p_system_prompt TEXT,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT 'default',
    p_model VARCHAR DEFAULT 'claude-3-5-sonnet-20241022',
    p_temperature DECIMAL DEFAULT 0.7,
    p_max_tokens INTEGER DEFAULT 150,
    p_first_message TEXT DEFAULT NULL,
    p_vad_sensitivity DECIMAL DEFAULT 0.5,
    p_endpointing_ms INTEGER DEFAULT 600,
    p_enable_bargein BOOLEAN DEFAULT true,
    p_streaming_chunks BOOLEAN DEFAULT true,
    p_first_message_latency_ms INTEGER DEFAULT 800,
    p_turn_detection_mode VARCHAR DEFAULT 'server_vad'
)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
    v_current_count INTEGER;
    v_limit INTEGER;
    v_assistant_id UUID;
BEGIN
    -- Get current assistant count
    SELECT COUNT(*) INTO v_current_count
    FROM public.va_assistants
    WHERE user_id = v_user_id;

    -- Get plan limit
    SELECT COALESCE(
        (SELECT (pf.feature_value->>'value')::INTEGER
         FROM public.va_user_subscriptions us
         JOIN public.va_plan_features pf ON us.plan_id = pf.plan_id
         WHERE us.user_id = v_user_id
         AND us.status = 'active'
         AND pf.feature_key = 'max_assistants'),
        1
    ) INTO v_limit;

    -- Check limit (-1 means unlimited)
    IF v_limit != -1 AND v_current_count >= v_limit THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', format('Assistant limit reached. You have %s of %s assistants.', v_current_count, v_limit),
            'upgrade_required', true
        );
    END IF;

    -- Create assistant
    INSERT INTO public.va_assistants (
        user_id, name, description, system_prompt, voice_id,
        model, temperature, max_tokens, first_message,
        vad_sensitivity, endpointing_ms, enable_bargein,
        streaming_chunks, first_message_latency_ms, turn_detection_mode
    ) VALUES (
        v_user_id, p_name, p_description, p_system_prompt, p_voice_id,
        p_model, p_temperature, p_max_tokens, p_first_message,
        p_vad_sensitivity, p_endpointing_ms, p_enable_bargein,
        p_streaming_chunks, p_first_message_latency_ms, p_turn_detection_mode
    ) RETURNING id INTO v_assistant_id;

    RETURN jsonb_build_object(
        'success', true,
        'assistant_id', v_assistant_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update assistant
CREATE OR REPLACE FUNCTION va_client_update_assistant(
    p_assistant_id UUID,
    p_updates JSONB
)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
BEGIN
    -- Verify ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = v_user_id
    ) THEN
        RETURN jsonb_build_object('success', false, 'error', 'Assistant not found');
    END IF;

    -- Update fields
    UPDATE public.va_assistants
    SET
        name = COALESCE(p_updates->>'name', name),
        description = COALESCE(p_updates->>'description', description),
        system_prompt = COALESCE(p_updates->>'system_prompt', system_prompt),
        voice_id = COALESCE(p_updates->>'voice_id', voice_id),
        model = COALESCE(p_updates->>'model', model),
        temperature = COALESCE((p_updates->>'temperature')::DECIMAL, temperature),
        max_tokens = COALESCE((p_updates->>'max_tokens')::INTEGER, max_tokens),
        first_message = COALESCE(p_updates->>'first_message', first_message),
        is_active = COALESCE((p_updates->>'is_active')::BOOLEAN, is_active),
        vad_sensitivity = COALESCE((p_updates->>'vad_sensitivity')::DECIMAL, vad_sensitivity),
        endpointing_ms = COALESCE((p_updates->>'endpointing_ms')::INTEGER, endpointing_ms),
        enable_bargein = COALESCE((p_updates->>'enable_bargein')::BOOLEAN, enable_bargein),
        streaming_chunks = COALESCE((p_updates->>'streaming_chunks')::BOOLEAN, streaming_chunks),
        first_message_latency_ms = COALESCE((p_updates->>'first_message_latency_ms')::INTEGER, first_message_latency_ms),
        turn_detection_mode = COALESCE(p_updates->>'turn_detection_mode', turn_detection_mode)
    WHERE id = p_assistant_id AND user_id = v_user_id;

    RETURN jsonb_build_object('success', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Delete assistant
CREATE OR REPLACE FUNCTION va_client_delete_assistant(p_assistant_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
BEGIN
    DELETE FROM public.va_assistants
    WHERE id = p_assistant_id AND user_id = v_user_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error', 'Assistant not found');
    END IF;

    RETURN jsonb_build_object('success', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get authenticated user's call logs
CREATE OR REPLACE FUNCTION va_client_get_my_calls(
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0,
    p_assistant_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    assistant_id UUID,
    assistant_name VARCHAR,
    call_type VARCHAR,
    phone_number VARCHAR,
    status VARCHAR,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    cost_cents INTEGER,
    summary TEXT,
    sentiment VARCHAR,
    ended_reason VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cl.id, cl.assistant_id,
        COALESCE(a.name, 'Deleted Assistant')::VARCHAR as assistant_name,
        cl.call_type, cl.phone_number, cl.status,
        cl.started_at, cl.ended_at, cl.duration_seconds,
        cl.cost_cents, cl.summary, cl.sentiment, cl.ended_reason
    FROM public.va_call_logs cl
    LEFT JOIN public.va_assistants a ON cl.assistant_id = a.id
    WHERE cl.user_id = auth.uid()
    AND (p_assistant_id IS NULL OR cl.assistant_id = p_assistant_id)
    ORDER BY cl.started_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get single call details with transcript
CREATE OR REPLACE FUNCTION va_client_get_call(p_call_id UUID)
RETURNS TABLE (
    id UUID,
    assistant_id UUID,
    assistant_name VARCHAR,
    call_type VARCHAR,
    phone_number VARCHAR,
    status VARCHAR,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    cost_cents INTEGER,
    minutes_used DECIMAL,
    transcript JSONB,
    summary TEXT,
    recording_url TEXT,
    sentiment VARCHAR,
    ended_reason VARCHAR,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cl.id, cl.assistant_id,
        COALESCE(a.name, 'Deleted Assistant')::VARCHAR as assistant_name,
        cl.call_type, cl.phone_number, cl.status,
        cl.started_at, cl.ended_at, cl.duration_seconds,
        cl.cost_cents, cl.minutes_used, cl.transcript, cl.summary,
        cl.recording_url, cl.sentiment, cl.ended_reason, cl.metadata
    FROM public.va_call_logs cl
    LEFT JOIN public.va_assistants a ON cl.assistant_id = a.id
    WHERE cl.id = p_call_id AND cl.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get call stats for authenticated user
CREATE OR REPLACE FUNCTION va_client_get_my_call_stats()
RETURNS TABLE (
    total_calls BIGINT,
    total_duration_seconds BIGINT,
    total_cost_cents BIGINT,
    avg_duration_seconds INTEGER,
    completed_calls BIGINT,
    failed_calls BIGINT,
    calls_today BIGINT,
    calls_this_week BIGINT,
    calls_this_month BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_calls,
        COALESCE(SUM(cl.duration_seconds), 0)::BIGINT as total_duration_seconds,
        COALESCE(SUM(cl.cost_cents), 0)::BIGINT as total_cost_cents,
        COALESCE(AVG(cl.duration_seconds)::INTEGER, 0) as avg_duration_seconds,
        COUNT(*) FILTER (WHERE cl.status = 'completed')::BIGINT as completed_calls,
        COUNT(*) FILTER (WHERE cl.status = 'failed')::BIGINT as failed_calls,
        COUNT(*) FILTER (WHERE cl.started_at >= CURRENT_DATE)::BIGINT as calls_today,
        COUNT(*) FILTER (WHERE cl.started_at >= CURRENT_DATE - INTERVAL '7 days')::BIGINT as calls_this_week,
        COUNT(*) FILTER (WHERE cl.started_at >= CURRENT_DATE - INTERVAL '30 days')::BIGINT as calls_this_month
    FROM public.va_call_logs cl
    WHERE cl.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- VIEWS
-- =====================================================

-- Assistant summary view
CREATE OR REPLACE VIEW va_assistant_summary AS
SELECT
    a.id,
    a.user_id,
    a.name,
    a.description,
    a.is_active,
    a.created_at,
    COALESCE(stats.call_count, 0) as call_count,
    COALESCE(stats.total_duration, 0) as total_duration_seconds,
    COALESCE(stats.last_call, a.created_at) as last_activity
FROM public.va_assistants a
LEFT JOIN (
    SELECT
        assistant_id,
        COUNT(*) as call_count,
        SUM(duration_seconds) as total_duration,
        MAX(started_at) as last_call
    FROM public.va_call_logs
    GROUP BY assistant_id
) stats ON a.id = stats.assistant_id;

-- Daily call stats view
CREATE OR REPLACE VIEW va_daily_call_stats AS
SELECT
    user_id,
    DATE(started_at) as call_date,
    COUNT(*) as call_count,
    SUM(duration_seconds) as total_duration,
    SUM(cost_cents) as total_cost,
    AVG(duration_seconds)::INTEGER as avg_duration
FROM public.va_call_logs
GROUP BY user_id, DATE(started_at)
ORDER BY call_date DESC;

-- Grant access to views
GRANT SELECT ON va_assistant_summary TO authenticated;
GRANT SELECT ON va_daily_call_stats TO authenticated;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE public.va_assistants IS 'AI assistant configurations for voice interactions';
COMMENT ON TABLE public.va_call_logs IS 'History of all voice calls with transcripts and analytics';

COMMENT ON FUNCTION va_client_create_assistant IS 'Create a new AI assistant with plan limit checking';
COMMENT ON FUNCTION va_client_get_my_calls IS 'Get paginated call history for authenticated user';
COMMENT ON FUNCTION va_client_get_call IS 'Get full call details including transcript';

-- ============================================
-- FILE: 007_add_full_platform_features.sql
-- ============================================

-- Premier Voice Assistant - Full Platform Features Migration
-- Migration: 007_add_full_platform_features
-- Features: Twilio Integration, Profile Fields, Enhanced Call Logs, Teams, Referrals, Settings

-- ============================================================================
-- 1. PHONE NUMBERS (Twilio Integration)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.va_phone_numbers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,
    phone_type VARCHAR(20) DEFAULT 'mobile', -- 'mobile', 'landline', 'twilio'
    country_code VARCHAR(5) DEFAULT '+1',
    is_verified BOOLEAN DEFAULT FALSE,
    is_primary BOOLEAN DEFAULT FALSE,
    twilio_sid VARCHAR(100), -- Twilio phone number SID
    capabilities JSONB DEFAULT '{"voice": true, "sms": true}'::jsonb,
    forwarding_enabled BOOLEAN DEFAULT TRUE,
    forwarding_number VARCHAR(20), -- Where to forward calls when AI can't handle
    voicemail_enabled BOOLEAN DEFAULT TRUE,
    voicemail_greeting TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(phone_number)
);

CREATE INDEX idx_va_phone_numbers_user ON public.va_phone_numbers(user_id);
CREATE INDEX idx_va_phone_numbers_phone ON public.va_phone_numbers(phone_number);

-- Phone verification codes
CREATE TABLE IF NOT EXISTS public.va_phone_verifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,
    verification_code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    verified_at TIMESTAMP WITH TIME ZONE,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_phone_verifications_user ON public.va_phone_verifications(user_id);

-- ============================================================================
-- 2. USER PROFILE FIELDS (Tier-limited)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.va_user_profiles_extended (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name VARCHAR(100),
    business_name VARCHAR(200),
    -- Profile fields with tier limits (stored as JSONB for flexibility)
    profile_fields JSONB DEFAULT '[]'::jsonb,
    -- Quick access fields
    profession VARCHAR(200),
    service_area VARCHAR(200),
    greeting_name VARCHAR(100), -- How AI should greet callers
    -- AI Assistant configuration
    assistant_name VARCHAR(100) DEFAULT 'Assistant',
    assistant_personality VARCHAR(500),
    -- Contact preferences
    preferred_contact_method VARCHAR(20) DEFAULT 'phone', -- 'phone', 'sms', 'email'
    business_hours JSONB DEFAULT '{"monday": {"start": "09:00", "end": "17:00"}, "tuesday": {"start": "09:00", "end": "17:00"}, "wednesday": {"start": "09:00", "end": "17:00"}, "thursday": {"start": "09:00", "end": "17:00"}, "friday": {"start": "09:00", "end": "17:00"}}'::jsonb,
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_user_profiles_extended_user ON public.va_user_profiles_extended(user_id);

-- Profile field definitions (what fields are allowed per tier)
CREATE TABLE IF NOT EXISTS public.va_profile_field_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_name VARCHAR(50) NOT NULL,
    max_fields INTEGER NOT NULL DEFAULT 1,
    max_chars_per_field INTEGER NOT NULL DEFAULT 60,
    allowed_field_types JSONB DEFAULT '["text"]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(plan_name)
);

-- Insert tier limits
INSERT INTO public.va_profile_field_limits (plan_name, max_fields, max_chars_per_field) VALUES
    ('free', 1, 60),
    ('starter', 2, 60),
    ('pro', 5, 120),
    ('enterprise', 100, 10000)
ON CONFLICT (plan_name) DO UPDATE SET
    max_fields = EXCLUDED.max_fields,
    max_chars_per_field = EXCLUDED.max_chars_per_field;

-- ============================================================================
-- 3. ENHANCED CALL LOGS SYSTEM
-- ============================================================================
-- Add columns to existing va_call_logs if it exists, or create new table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'va_call_logs') THEN
        CREATE TABLE public.va_call_logs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            assistant_id UUID,
            contact_id UUID,
            -- Call details
            call_type VARCHAR(20) DEFAULT 'inbound', -- 'inbound', 'outbound', 'transfer'
            phone_number VARCHAR(20),
            caller_name VARCHAR(200),
            -- Twilio details
            twilio_call_sid VARCHAR(100),
            twilio_recording_url TEXT,
            -- Status and timing
            status VARCHAR(20) DEFAULT 'completed', -- 'ringing', 'in_progress', 'completed', 'failed', 'voicemail'
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            answered_at TIMESTAMP WITH TIME ZONE,
            ended_at TIMESTAMP WITH TIME ZONE,
            duration_seconds INTEGER DEFAULT 0,
            -- AI generated content
            transcript JSONB DEFAULT '[]'::jsonb,
            summary TEXT,
            key_info JSONB DEFAULT '{}'::jsonb, -- Extracted info like address, service needed, etc.
            action_items JSONB DEFAULT '[]'::jsonb,
            -- Analysis
            sentiment VARCHAR(20), -- 'positive', 'neutral', 'negative'
            urgency VARCHAR(20) DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
            category VARCHAR(100), -- 'inquiry', 'booking', 'support', 'complaint', etc.
            tags JSONB DEFAULT '[]'::jsonb,
            -- Cost tracking
            cost_cents INTEGER DEFAULT 0,
            minutes_used DECIMAL(10,2) DEFAULT 0,
            -- Metadata
            ended_reason VARCHAR(100),
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    END IF;
END $$;

-- Add new columns if they don't exist
DO $$
BEGIN
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS contact_id UUID;
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS caller_name VARCHAR(200);
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS twilio_call_sid VARCHAR(100);
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS twilio_recording_url TEXT;
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS answered_at TIMESTAMP WITH TIME ZONE;
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS key_info JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS action_items JSONB DEFAULT '[]'::jsonb;
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS urgency VARCHAR(20) DEFAULT 'normal';
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS category VARCHAR(100);
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb;
    ALTER TABLE public.va_call_logs ADD COLUMN IF NOT EXISTS shared_with JSONB DEFAULT '[]'::jsonb;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_va_call_logs_user ON public.va_call_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_va_call_logs_contact ON public.va_call_logs(contact_id);
CREATE INDEX IF NOT EXISTS idx_va_call_logs_status ON public.va_call_logs(status);
CREATE INDEX IF NOT EXISTS idx_va_call_logs_started ON public.va_call_logs(started_at DESC);

-- ============================================================================
-- 4. CONTACTS SYSTEM
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.va_contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    -- Basic info
    name VARCHAR(200),
    phone VARCHAR(20),
    email VARCHAR(255),
    company VARCHAR(200),
    -- Permissions
    permission_level VARCHAR(20) DEFAULT 'normal', -- 'blocked', 'normal', 'vip', 'team'
    -- Categorization
    contact_type VARCHAR(20) DEFAULT 'customer', -- 'customer', 'lead', 'vendor', 'team', 'personal'
    tags JSONB DEFAULT '[]'::jsonb,
    -- Additional info
    notes TEXT,
    address JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    -- Stats
    total_calls INTEGER DEFAULT 0,
    last_call_at TIMESTAMP WITH TIME ZONE,
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_contacts_user ON public.va_contacts(user_id);
CREATE INDEX idx_va_contacts_phone ON public.va_contacts(phone);
CREATE INDEX idx_va_contacts_email ON public.va_contacts(email);

-- ============================================================================
-- 5. TEAMS SYSTEM (Enhanced)
-- ============================================================================
-- Add team features if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'va_teams') THEN
        CREATE TABLE public.va_teams (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            -- Settings
            settings JSONB DEFAULT '{}'::jsonb,
            shared_phone_number VARCHAR(20),
            shared_assistant_id UUID,
            -- Timestamps
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    END IF;
END $$;

-- Team members
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'va_team_members') THEN
        CREATE TABLE public.va_team_members (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            team_id UUID NOT NULL REFERENCES public.va_teams(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            role VARCHAR(20) DEFAULT 'member', -- 'owner', 'admin', 'member', 'viewer'
            -- Permissions (granular)
            permissions JSONB DEFAULT '{"view_calls": true, "receive_transfers": true, "edit_contacts": false, "manage_settings": false}'::jsonb,
            -- Availability
            is_available BOOLEAN DEFAULT TRUE,
            availability_hours JSONB DEFAULT '{}'::jsonb,
            -- Timestamps
            joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(team_id, user_id)
        );
    END IF;
END $$;

-- Team invitations
CREATE TABLE IF NOT EXISTS public.va_team_invites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES public.va_teams(id) ON DELETE CASCADE,
    invited_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'member',
    token VARCHAR(100) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_team_invites_token ON public.va_team_invites(token);
CREATE INDEX idx_va_team_invites_email ON public.va_team_invites(email);

-- Shared call logs for teams
CREATE TABLE IF NOT EXISTS public.va_team_call_shares (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL REFERENCES public.va_call_logs(id) ON DELETE CASCADE,
    team_id UUID NOT NULL REFERENCES public.va_teams(id) ON DELETE CASCADE,
    shared_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    shared_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    UNIQUE(call_id, team_id)
);

-- ============================================================================
-- 6. REFERRAL SYSTEM
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.va_referral_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    code VARCHAR(20) UNIQUE NOT NULL,
    -- Rewards
    referrer_reward_type VARCHAR(20) DEFAULT 'minutes', -- 'minutes', 'credits', 'discount'
    referrer_reward_value INTEGER DEFAULT 50, -- e.g., 50 minutes
    referee_reward_type VARCHAR(20) DEFAULT 'minutes',
    referee_reward_value INTEGER DEFAULT 50,
    -- Milestones
    milestone_5_reward INTEGER DEFAULT 100, -- Bonus for 5 referrals
    milestone_10_reward INTEGER DEFAULT 200,
    milestone_25_reward INTEGER DEFAULT 500,
    -- Stats
    total_referrals INTEGER DEFAULT 0,
    successful_referrals INTEGER DEFAULT 0,
    total_rewards_earned INTEGER DEFAULT 0,
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_referral_codes_user ON public.va_referral_codes(user_id);
CREATE INDEX idx_va_referral_codes_code ON public.va_referral_codes(code);

-- Referral tracking
CREATE TABLE IF NOT EXISTS public.va_referrals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referral_code_id UUID NOT NULL REFERENCES public.va_referral_codes(id) ON DELETE CASCADE,
    referrer_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    referee_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    referee_email VARCHAR(255),
    -- Status
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'signed_up', 'converted', 'expired'
    -- Rewards
    referrer_reward_claimed BOOLEAN DEFAULT FALSE,
    referrer_reward_claimed_at TIMESTAMP WITH TIME ZONE,
    referee_reward_claimed BOOLEAN DEFAULT FALSE,
    referee_reward_claimed_at TIMESTAMP WITH TIME ZONE,
    -- Tracking
    signed_up_at TIMESTAMP WITH TIME ZONE,
    converted_at TIMESTAMP WITH TIME ZONE, -- When they became paying customer
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_referrals_referrer ON public.va_referrals(referrer_id);
CREATE INDEX idx_va_referrals_referee ON public.va_referrals(referee_id);
CREATE INDEX idx_va_referrals_code ON public.va_referrals(referral_code_id);

-- ============================================================================
-- 7. USER SETTINGS (Toggle everything on/off)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.va_user_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    -- AI Assistant Settings
    ai_enabled BOOLEAN DEFAULT TRUE,
    ai_greeting_enabled BOOLEAN DEFAULT TRUE,
    ai_transcription_enabled BOOLEAN DEFAULT TRUE,
    ai_summary_enabled BOOLEAN DEFAULT TRUE,
    -- Call Handling
    call_screening_enabled BOOLEAN DEFAULT TRUE,
    voicemail_enabled BOOLEAN DEFAULT TRUE,
    call_recording_enabled BOOLEAN DEFAULT TRUE,
    call_forwarding_enabled BOOLEAN DEFAULT TRUE,
    sms_enabled BOOLEAN DEFAULT TRUE,
    -- Notifications
    push_notifications_enabled BOOLEAN DEFAULT TRUE,
    email_notifications_enabled BOOLEAN DEFAULT TRUE,
    sms_notifications_enabled BOOLEAN DEFAULT FALSE,
    notify_on_missed_call BOOLEAN DEFAULT TRUE,
    notify_on_voicemail BOOLEAN DEFAULT TRUE,
    notify_on_urgent BOOLEAN DEFAULT TRUE,
    daily_summary_enabled BOOLEAN DEFAULT FALSE,
    weekly_summary_enabled BOOLEAN DEFAULT TRUE,
    -- Privacy
    share_call_logs_with_team BOOLEAN DEFAULT TRUE,
    show_phone_number BOOLEAN DEFAULT FALSE,
    -- Display preferences
    theme VARCHAR(20) DEFAULT 'dark', -- 'dark', 'light', 'system'
    language VARCHAR(10) DEFAULT 'en',
    date_format VARCHAR(20) DEFAULT 'MM/DD/YYYY',
    time_format VARCHAR(20) DEFAULT '12h', -- '12h', '24h'
    -- Advanced
    auto_categorize_calls BOOLEAN DEFAULT TRUE,
    auto_extract_info BOOLEAN DEFAULT TRUE,
    webhook_enabled BOOLEAN DEFAULT FALSE,
    webhook_url TEXT,
    webhook_events JSONB DEFAULT '["call.completed", "voicemail.received"]'::jsonb,
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_user_settings_user ON public.va_user_settings(user_id);

-- ============================================================================
-- 8. SMS MESSAGES
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.va_sms_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES public.va_contacts(id) ON DELETE SET NULL,
    phone_number_id UUID REFERENCES public.va_phone_numbers(id) ON DELETE SET NULL,
    -- Message details
    direction VARCHAR(10) NOT NULL, -- 'inbound', 'outbound'
    from_number VARCHAR(20) NOT NULL,
    to_number VARCHAR(20) NOT NULL,
    body TEXT NOT NULL,
    -- Status
    status VARCHAR(20) DEFAULT 'sent', -- 'queued', 'sent', 'delivered', 'failed', 'received'
    -- Twilio
    twilio_sid VARCHAR(100),
    twilio_status VARCHAR(50),
    -- AI processing
    ai_response TEXT,
    ai_processed BOOLEAN DEFAULT FALSE,
    -- Cost
    cost_cents INTEGER DEFAULT 0,
    -- Timestamps
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delivered_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_sms_messages_user ON public.va_sms_messages(user_id);
CREATE INDEX idx_va_sms_messages_phone ON public.va_sms_messages(from_number, to_number);

-- ============================================================================
-- 9. CALL SHARES (Share call logs via email/SMS/webhook)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.va_call_shares (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL REFERENCES public.va_call_logs(id) ON DELETE CASCADE,
    shared_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    -- Share method
    share_type VARCHAR(20) NOT NULL, -- 'email', 'sms', 'webhook', 'link'
    recipient VARCHAR(255), -- Email, phone, or webhook URL
    -- Access control
    access_token VARCHAR(100) UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE,
    view_count INTEGER DEFAULT 0,
    max_views INTEGER DEFAULT 100,
    -- Content options
    include_transcript BOOLEAN DEFAULT TRUE,
    include_summary BOOLEAN DEFAULT TRUE,
    include_recording BOOLEAN DEFAULT FALSE,
    include_key_info BOOLEAN DEFAULT TRUE,
    -- Status
    status VARCHAR(20) DEFAULT 'sent', -- 'pending', 'sent', 'viewed', 'expired'
    sent_at TIMESTAMP WITH TIME ZONE,
    first_viewed_at TIMESTAMP WITH TIME ZONE,
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_call_shares_call ON public.va_call_shares(call_id);
CREATE INDEX idx_va_call_shares_token ON public.va_call_shares(access_token);

-- ============================================================================
-- 10. WEBHOOKS LOG
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.va_webhook_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    webhook_url TEXT NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    success BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_va_webhook_logs_user ON public.va_webhook_logs(user_id);
CREATE INDEX idx_va_webhook_logs_event ON public.va_webhook_logs(event_type);

-- ============================================================================
-- 11. FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to auto-create referral code for new users
CREATE OR REPLACE FUNCTION public.create_referral_code_for_user()
RETURNS TRIGGER AS $$
DECLARE
    new_code VARCHAR(20);
BEGIN
    -- Generate unique code
    new_code := 'HIVE-' || UPPER(SUBSTRING(MD5(NEW.id::text || NOW()::text) FROM 1 FOR 6));

    INSERT INTO public.va_referral_codes (user_id, code)
    VALUES (NEW.id, new_code)
    ON CONFLICT DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create referral code on user creation
DROP TRIGGER IF EXISTS tr_create_referral_code ON auth.users;
CREATE TRIGGER tr_create_referral_code
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.create_referral_code_for_user();

-- Function to auto-create user settings
CREATE OR REPLACE FUNCTION public.create_user_settings()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.va_user_settings (user_id)
    VALUES (NEW.id)
    ON CONFLICT DO NOTHING;

    INSERT INTO public.va_user_profiles_extended (user_id)
    VALUES (NEW.id)
    ON CONFLICT DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create user settings on user creation
DROP TRIGGER IF EXISTS tr_create_user_settings ON auth.users;
CREATE TRIGGER tr_create_user_settings
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.create_user_settings();

-- Function to update contact stats on new call
CREATE OR REPLACE FUNCTION public.update_contact_on_call()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.contact_id IS NOT NULL THEN
        UPDATE public.va_contacts
        SET
            total_calls = total_calls + 1,
            last_call_at = NEW.started_at,
            updated_at = NOW()
        WHERE id = NEW.contact_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS tr_update_contact_on_call ON public.va_call_logs;
CREATE TRIGGER tr_update_contact_on_call
    AFTER INSERT ON public.va_call_logs
    FOR EACH ROW
    EXECUTE FUNCTION public.update_contact_on_call();

-- Function to claim referral reward
CREATE OR REPLACE FUNCTION public.claim_referral_reward(
    p_user_id UUID,
    p_referral_code VARCHAR
)
RETURNS JSONB AS $$
DECLARE
    v_referral_code_id UUID;
    v_referrer_id UUID;
    v_reward_value INTEGER;
    v_result JSONB;
BEGIN
    -- Find the referral code
    SELECT id, user_id, referee_reward_value
    INTO v_referral_code_id, v_referrer_id, v_reward_value
    FROM public.va_referral_codes
    WHERE code = p_referral_code AND is_active = TRUE;

    IF v_referral_code_id IS NULL THEN
        RETURN jsonb_build_object('success', false, 'message', 'Invalid referral code');
    END IF;

    IF v_referrer_id = p_user_id THEN
        RETURN jsonb_build_object('success', false, 'message', 'Cannot use your own referral code');
    END IF;

    -- Check if already used this code
    IF EXISTS (SELECT 1 FROM public.va_referrals WHERE referee_id = p_user_id AND referral_code_id = v_referral_code_id) THEN
        RETURN jsonb_build_object('success', false, 'message', 'Already used this referral code');
    END IF;

    -- Create referral record
    INSERT INTO public.va_referrals (
        referral_code_id, referrer_id, referee_id, status, signed_up_at, referee_reward_claimed, referee_reward_claimed_at
    ) VALUES (
        v_referral_code_id, v_referrer_id, p_user_id, 'signed_up', NOW(), TRUE, NOW()
    );

    -- Add bonus minutes to referee
    UPDATE public.va_usage_tracking
    SET bonus_minutes = COALESCE(bonus_minutes, 0) + v_reward_value
    WHERE user_id = p_user_id;

    -- Update referral code stats
    UPDATE public.va_referral_codes
    SET
        total_referrals = total_referrals + 1,
        successful_referrals = successful_referrals + 1,
        updated_at = NOW()
    WHERE id = v_referral_code_id;

    -- Add bonus to referrer
    UPDATE public.va_usage_tracking
    SET bonus_minutes = COALESCE(bonus_minutes, 0) + (
        SELECT referrer_reward_value FROM public.va_referral_codes WHERE id = v_referral_code_id
    )
    WHERE user_id = v_referrer_id;

    -- Mark referrer reward as claimed
    UPDATE public.va_referrals
    SET referrer_reward_claimed = TRUE, referrer_reward_claimed_at = NOW()
    WHERE referee_id = p_user_id AND referral_code_id = v_referral_code_id;

    RETURN jsonb_build_object(
        'success', true,
        'message', 'Referral code applied successfully',
        'minutes_earned', v_reward_value
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- 12. ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Phone numbers
ALTER TABLE public.va_phone_numbers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own phone numbers" ON public.va_phone_numbers
    FOR ALL USING (auth.uid() = user_id);

-- User profiles extended
ALTER TABLE public.va_user_profiles_extended ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own profile" ON public.va_user_profiles_extended
    FOR ALL USING (auth.uid() = user_id);

-- Contacts
ALTER TABLE public.va_contacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own contacts" ON public.va_contacts
    FOR ALL USING (auth.uid() = user_id);

-- User settings
ALTER TABLE public.va_user_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own settings" ON public.va_user_settings
    FOR ALL USING (auth.uid() = user_id);

-- Referral codes
ALTER TABLE public.va_referral_codes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own referral codes" ON public.va_referral_codes
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own referral codes" ON public.va_referral_codes
    FOR ALL USING (auth.uid() = user_id);

-- Referrals
ALTER TABLE public.va_referrals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view referrals they made or received" ON public.va_referrals
    FOR SELECT USING (auth.uid() = referrer_id OR auth.uid() = referee_id);

-- SMS messages
ALTER TABLE public.va_sms_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own SMS" ON public.va_sms_messages
    FOR ALL USING (auth.uid() = user_id);

-- Call shares
ALTER TABLE public.va_call_shares ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own call shares" ON public.va_call_shares
    FOR ALL USING (auth.uid() = shared_by);

-- Teams (users can see teams they own or are members of)
ALTER TABLE public.va_teams ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view teams they belong to" ON public.va_teams
    FOR SELECT USING (
        auth.uid() = owner_id OR
        EXISTS (SELECT 1 FROM public.va_team_members WHERE team_id = id AND user_id = auth.uid())
    );
CREATE POLICY "Owners can manage their teams" ON public.va_teams
    FOR ALL USING (auth.uid() = owner_id);

-- Team members
ALTER TABLE public.va_team_members ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Team members can view team membership" ON public.va_team_members
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM public.va_teams WHERE id = team_id AND owner_id = auth.uid()) OR
        user_id = auth.uid()
    );

-- Team invites
ALTER TABLE public.va_team_invites ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view invites they sent or received" ON public.va_team_invites
    FOR SELECT USING (
        auth.uid() = invited_by OR
        email = (SELECT email FROM auth.users WHERE id = auth.uid())
    );

-- ============================================================================
-- DONE
-- ============================================================================

-- ============================================
-- FILE: 008_add_voice_control_settings.sql
-- ============================================

-- Migration 008: Add Voice Control Settings
-- This migration adds voice customization settings to assistants
-- (Competitive with Vapi and ElevenLabs voice agent features)

-- =====================================================
-- ADD NEW COLUMNS TO VA_ASSISTANTS
-- =====================================================

-- Speech speed control (0.7 to 1.2x)
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS speech_speed DECIMAL(3,2) DEFAULT 0.9;

-- Response delay (ms to wait after user stops speaking before responding)
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS response_delay_ms INTEGER DEFAULT 400;

-- Punctuation pause (ms to wait after detecting punctuation)
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS punctuation_pause_ms INTEGER DEFAULT 300;

-- No punctuation pause (ms to wait when no punctuation detected)
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS no_punctuation_pause_ms INTEGER DEFAULT 1000;

-- Turn eagerness (how quickly to take conversational turns)
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS turn_eagerness VARCHAR(20) DEFAULT 'balanced';

-- Add comments explaining the columns
COMMENT ON COLUMN public.va_assistants.speech_speed IS 'TTS speaking rate (0.7-1.2x). Default 0.9 for natural pace.';
COMMENT ON COLUMN public.va_assistants.response_delay_ms IS 'Delay before responding after user stops speaking. Higher = more patient.';
COMMENT ON COLUMN public.va_assistants.punctuation_pause_ms IS 'Pause after detecting punctuation. Affects conversation flow.';
COMMENT ON COLUMN public.va_assistants.no_punctuation_pause_ms IS 'Wait when no punctuation (user may still be speaking).';
COMMENT ON COLUMN public.va_assistants.turn_eagerness IS 'Turn-taking style: low (patient), balanced, high (eager).';

-- =====================================================
-- DROP EXISTING FUNCTIONS (required to change return types)
-- =====================================================

DROP FUNCTION IF EXISTS va_get_assistant(UUID);
DROP FUNCTION IF EXISTS va_client_get_assistant(UUID);
DROP FUNCTION IF EXISTS va_client_create_assistant(VARCHAR, TEXT, TEXT, VARCHAR, VARCHAR, DECIMAL, INTEGER, TEXT, DECIMAL, INTEGER, BOOLEAN, BOOLEAN, INTEGER, VARCHAR);
DROP FUNCTION IF EXISTS va_client_update_assistant(UUID, JSONB);

-- =====================================================
-- RECREATE FUNCTIONS WITH NEW COLUMNS
-- =====================================================

-- Update va_get_assistant to return new columns
CREATE OR REPLACE FUNCTION va_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    speech_speed DECIMAL,
    response_delay_ms INTEGER,
    punctuation_pause_ms INTEGER,
    no_punctuation_pause_ms INTEGER,
    turn_eagerness VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.user_id, a.name, a.description, a.system_prompt,
        a.voice_id, a.model, a.temperature, a.max_tokens,
        a.first_message, a.is_active, a.vad_sensitivity, a.endpointing_ms,
        a.enable_bargein, a.streaming_chunks, a.first_message_latency_ms,
        a.turn_detection_mode, a.speech_speed, a.response_delay_ms,
        a.punctuation_pause_ms, a.no_punctuation_pause_ms, a.turn_eagerness,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_get_assistant to return new columns
CREATE OR REPLACE FUNCTION va_client_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    speech_speed DECIMAL,
    response_delay_ms INTEGER,
    punctuation_pause_ms INTEGER,
    no_punctuation_pause_ms INTEGER,
    turn_eagerness VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.name, a.description, a.system_prompt, a.voice_id,
        a.model, a.temperature, a.max_tokens, a.first_message,
        a.is_active, a.vad_sensitivity, a.endpointing_ms, a.enable_bargein,
        a.streaming_chunks, a.first_message_latency_ms, a.turn_detection_mode,
        a.speech_speed, a.response_delay_ms, a.punctuation_pause_ms,
        a.no_punctuation_pause_ms, a.turn_eagerness,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id AND a.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_create_assistant to accept new parameters
CREATE OR REPLACE FUNCTION va_client_create_assistant(
    p_name VARCHAR,
    p_system_prompt TEXT,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT 'default',
    p_model VARCHAR DEFAULT 'claude-sonnet-4-5-20250929',
    p_temperature DECIMAL DEFAULT 0.7,
    p_max_tokens INTEGER DEFAULT 150,
    p_first_message TEXT DEFAULT NULL,
    p_vad_sensitivity DECIMAL DEFAULT 0.5,
    p_endpointing_ms INTEGER DEFAULT 600,
    p_enable_bargein BOOLEAN DEFAULT true,
    p_streaming_chunks BOOLEAN DEFAULT true,
    p_first_message_latency_ms INTEGER DEFAULT 800,
    p_turn_detection_mode VARCHAR DEFAULT 'server_vad',
    p_speech_speed DECIMAL DEFAULT 0.9,
    p_response_delay_ms INTEGER DEFAULT 400,
    p_punctuation_pause_ms INTEGER DEFAULT 300,
    p_no_punctuation_pause_ms INTEGER DEFAULT 1000,
    p_turn_eagerness VARCHAR DEFAULT 'balanced'
)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
    v_current_count INTEGER;
    v_limit INTEGER;
    v_assistant_id UUID;
BEGIN
    -- Get current assistant count
    SELECT COUNT(*) INTO v_current_count
    FROM public.va_assistants
    WHERE user_id = v_user_id;

    -- Get plan limit
    SELECT COALESCE(
        (SELECT (pf.feature_value->>'value')::INTEGER
         FROM public.va_user_subscriptions us
         JOIN public.va_plan_features pf ON us.plan_id = pf.plan_id
         WHERE us.user_id = v_user_id
         AND us.status = 'active'
         AND pf.feature_key = 'max_assistants'),
        1
    ) INTO v_limit;

    -- Check limit (-1 means unlimited)
    IF v_limit != -1 AND v_current_count >= v_limit THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', format('Assistant limit reached. You have %s of %s assistants.', v_current_count, v_limit),
            'upgrade_required', true
        );
    END IF;

    -- Create assistant with all settings including voice control
    INSERT INTO public.va_assistants (
        user_id, name, description, system_prompt, voice_id,
        model, temperature, max_tokens, first_message,
        vad_sensitivity, endpointing_ms, enable_bargein,
        streaming_chunks, first_message_latency_ms, turn_detection_mode,
        speech_speed, response_delay_ms, punctuation_pause_ms,
        no_punctuation_pause_ms, turn_eagerness
    ) VALUES (
        v_user_id, p_name, p_description, p_system_prompt, p_voice_id,
        p_model, p_temperature, p_max_tokens, p_first_message,
        p_vad_sensitivity, p_endpointing_ms, p_enable_bargein,
        p_streaming_chunks, p_first_message_latency_ms, p_turn_detection_mode,
        p_speech_speed, p_response_delay_ms, p_punctuation_pause_ms,
        p_no_punctuation_pause_ms, p_turn_eagerness
    ) RETURNING id INTO v_assistant_id;

    RETURN jsonb_build_object(
        'success', true,
        'assistant_id', v_assistant_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_update_assistant to handle new columns
CREATE OR REPLACE FUNCTION va_client_update_assistant(
    p_assistant_id UUID,
    p_updates JSONB
)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
BEGIN
    -- Verify ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = v_user_id
    ) THEN
        RETURN jsonb_build_object('success', false, 'error', 'Assistant not found');
    END IF;

    -- Update fields including new voice control settings
    UPDATE public.va_assistants
    SET
        name = COALESCE(p_updates->>'name', name),
        description = COALESCE(p_updates->>'description', description),
        system_prompt = COALESCE(p_updates->>'system_prompt', system_prompt),
        voice_id = COALESCE(p_updates->>'voice_id', voice_id),
        model = COALESCE(p_updates->>'model', model),
        temperature = COALESCE((p_updates->>'temperature')::DECIMAL, temperature),
        max_tokens = COALESCE((p_updates->>'max_tokens')::INTEGER, max_tokens),
        first_message = COALESCE(p_updates->>'first_message', first_message),
        is_active = COALESCE((p_updates->>'is_active')::BOOLEAN, is_active),
        vad_sensitivity = COALESCE((p_updates->>'vad_sensitivity')::DECIMAL, vad_sensitivity),
        endpointing_ms = COALESCE((p_updates->>'endpointing_ms')::INTEGER, endpointing_ms),
        enable_bargein = COALESCE((p_updates->>'enable_bargein')::BOOLEAN, enable_bargein),
        streaming_chunks = COALESCE((p_updates->>'streaming_chunks')::BOOLEAN, streaming_chunks),
        first_message_latency_ms = COALESCE((p_updates->>'first_message_latency_ms')::INTEGER, first_message_latency_ms),
        turn_detection_mode = COALESCE(p_updates->>'turn_detection_mode', turn_detection_mode),
        -- Voice control settings
        speech_speed = COALESCE((p_updates->>'speech_speed')::DECIMAL, speech_speed),
        response_delay_ms = COALESCE((p_updates->>'response_delay_ms')::INTEGER, response_delay_ms),
        punctuation_pause_ms = COALESCE((p_updates->>'punctuation_pause_ms')::INTEGER, punctuation_pause_ms),
        no_punctuation_pause_ms = COALESCE((p_updates->>'no_punctuation_pause_ms')::INTEGER, no_punctuation_pause_ms),
        turn_eagerness = COALESCE(p_updates->>'turn_eagerness', turn_eagerness)
    WHERE id = p_assistant_id AND user_id = v_user_id;

    RETURN jsonb_build_object('success', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON FUNCTION va_client_create_assistant IS 'Create a new AI assistant with voice control settings and plan limit checking';
COMMENT ON FUNCTION va_client_update_assistant IS 'Update assistant including voice control settings (speech_speed, response_delay_ms, etc.)';

-- ============================================
-- FILE: 009_add_llm_provider.sql
-- ============================================

-- Migration 009: Add LLM Provider Selection
-- This migration adds per-agent LLM provider selection

-- =====================================================
-- ADD NEW COLUMN TO VA_ASSISTANTS
-- =====================================================

-- LLM provider selection (groq, anthropic, openai, google, mistral, etc.)
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(50) DEFAULT 'groq';

-- Add comment explaining the column
COMMENT ON COLUMN public.va_assistants.llm_provider IS 'LLM provider: groq, anthropic, openai, google, mistral, together, fireworks, deepseek, xai, cohere, perplexity';

-- Update default model to match groq provider
-- (only for new assistants, existing ones keep their model)
ALTER TABLE public.va_assistants
ALTER COLUMN model SET DEFAULT 'llama-3.3-70b-versatile';

-- =====================================================
-- DROP EXISTING FUNCTIONS (required to change signatures)
-- =====================================================

DROP FUNCTION IF EXISTS va_get_assistant(UUID);
DROP FUNCTION IF EXISTS va_client_get_assistant(UUID);
DROP FUNCTION IF EXISTS va_client_create_assistant(VARCHAR, TEXT, TEXT, VARCHAR, VARCHAR, DECIMAL, INTEGER, TEXT, DECIMAL, INTEGER, BOOLEAN, BOOLEAN, INTEGER, VARCHAR, DECIMAL, INTEGER, INTEGER, INTEGER, VARCHAR);
DROP FUNCTION IF EXISTS va_client_update_assistant(UUID, JSONB);

-- =====================================================
-- RECREATE FUNCTIONS WITH LLM_PROVIDER COLUMN
-- =====================================================

-- Update va_get_assistant to return llm_provider
CREATE OR REPLACE FUNCTION va_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    speech_speed DECIMAL,
    response_delay_ms INTEGER,
    punctuation_pause_ms INTEGER,
    no_punctuation_pause_ms INTEGER,
    turn_eagerness VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.user_id, a.name, a.description, a.system_prompt,
        a.voice_id, a.llm_provider, a.model, a.temperature, a.max_tokens,
        a.first_message, a.is_active, a.vad_sensitivity, a.endpointing_ms,
        a.enable_bargein, a.streaming_chunks, a.first_message_latency_ms,
        a.turn_detection_mode, a.speech_speed, a.response_delay_ms,
        a.punctuation_pause_ms, a.no_punctuation_pause_ms, a.turn_eagerness,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_get_assistant to return llm_provider
CREATE OR REPLACE FUNCTION va_client_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    speech_speed DECIMAL,
    response_delay_ms INTEGER,
    punctuation_pause_ms INTEGER,
    no_punctuation_pause_ms INTEGER,
    turn_eagerness VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.name, a.description, a.system_prompt, a.voice_id,
        a.llm_provider, a.model, a.temperature, a.max_tokens, a.first_message,
        a.is_active, a.vad_sensitivity, a.endpointing_ms, a.enable_bargein,
        a.streaming_chunks, a.first_message_latency_ms, a.turn_detection_mode,
        a.speech_speed, a.response_delay_ms, a.punctuation_pause_ms,
        a.no_punctuation_pause_ms, a.turn_eagerness,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id AND a.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_create_assistant to accept llm_provider
CREATE OR REPLACE FUNCTION va_client_create_assistant(
    p_name VARCHAR,
    p_system_prompt TEXT,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT 'default',
    p_llm_provider VARCHAR DEFAULT 'groq',
    p_model VARCHAR DEFAULT 'llama-3.3-70b-versatile',
    p_temperature DECIMAL DEFAULT 0.7,
    p_max_tokens INTEGER DEFAULT 150,
    p_first_message TEXT DEFAULT NULL,
    p_vad_sensitivity DECIMAL DEFAULT 0.5,
    p_endpointing_ms INTEGER DEFAULT 600,
    p_enable_bargein BOOLEAN DEFAULT true,
    p_streaming_chunks BOOLEAN DEFAULT true,
    p_first_message_latency_ms INTEGER DEFAULT 800,
    p_turn_detection_mode VARCHAR DEFAULT 'server_vad',
    p_speech_speed DECIMAL DEFAULT 0.9,
    p_response_delay_ms INTEGER DEFAULT 400,
    p_punctuation_pause_ms INTEGER DEFAULT 300,
    p_no_punctuation_pause_ms INTEGER DEFAULT 1000,
    p_turn_eagerness VARCHAR DEFAULT 'balanced'
)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
    v_current_count INTEGER;
    v_limit INTEGER;
    v_assistant_id UUID;
BEGIN
    -- Get current assistant count
    SELECT COUNT(*) INTO v_current_count
    FROM public.va_assistants
    WHERE user_id = v_user_id;

    -- Get plan limit
    SELECT COALESCE(
        (SELECT (pf.feature_value->>'value')::INTEGER
         FROM public.va_user_subscriptions us
         JOIN public.va_plan_features pf ON us.plan_id = pf.plan_id
         WHERE us.user_id = v_user_id
         AND us.status = 'active'
         AND pf.feature_key = 'max_assistants'),
        1
    ) INTO v_limit;

    -- Check limit (-1 means unlimited)
    IF v_limit != -1 AND v_current_count >= v_limit THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', format('Assistant limit reached. You have %s of %s assistants.', v_current_count, v_limit),
            'upgrade_required', true
        );
    END IF;

    -- Create assistant with llm_provider
    INSERT INTO public.va_assistants (
        user_id, name, description, system_prompt, voice_id,
        llm_provider, model, temperature, max_tokens, first_message,
        vad_sensitivity, endpointing_ms, enable_bargein,
        streaming_chunks, first_message_latency_ms, turn_detection_mode,
        speech_speed, response_delay_ms, punctuation_pause_ms,
        no_punctuation_pause_ms, turn_eagerness
    ) VALUES (
        v_user_id, p_name, p_description, p_system_prompt, p_voice_id,
        p_llm_provider, p_model, p_temperature, p_max_tokens, p_first_message,
        p_vad_sensitivity, p_endpointing_ms, p_enable_bargein,
        p_streaming_chunks, p_first_message_latency_ms, p_turn_detection_mode,
        p_speech_speed, p_response_delay_ms, p_punctuation_pause_ms,
        p_no_punctuation_pause_ms, p_turn_eagerness
    ) RETURNING id INTO v_assistant_id;

    RETURN jsonb_build_object(
        'success', true,
        'assistant_id', v_assistant_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_update_assistant to handle llm_provider
CREATE OR REPLACE FUNCTION va_client_update_assistant(
    p_assistant_id UUID,
    p_updates JSONB
)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
BEGIN
    -- Verify ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = v_user_id
    ) THEN
        RETURN jsonb_build_object('success', false, 'error', 'Assistant not found');
    END IF;

    -- Update fields including llm_provider
    UPDATE public.va_assistants
    SET
        name = COALESCE(p_updates->>'name', name),
        description = COALESCE(p_updates->>'description', description),
        system_prompt = COALESCE(p_updates->>'system_prompt', system_prompt),
        voice_id = COALESCE(p_updates->>'voice_id', voice_id),
        llm_provider = COALESCE(p_updates->>'llm_provider', llm_provider),
        model = COALESCE(p_updates->>'model', model),
        temperature = COALESCE((p_updates->>'temperature')::DECIMAL, temperature),
        max_tokens = COALESCE((p_updates->>'max_tokens')::INTEGER, max_tokens),
        first_message = COALESCE(p_updates->>'first_message', first_message),
        is_active = COALESCE((p_updates->>'is_active')::BOOLEAN, is_active),
        vad_sensitivity = COALESCE((p_updates->>'vad_sensitivity')::DECIMAL, vad_sensitivity),
        endpointing_ms = COALESCE((p_updates->>'endpointing_ms')::INTEGER, endpointing_ms),
        enable_bargein = COALESCE((p_updates->>'enable_bargein')::BOOLEAN, enable_bargein),
        streaming_chunks = COALESCE((p_updates->>'streaming_chunks')::BOOLEAN, streaming_chunks),
        first_message_latency_ms = COALESCE((p_updates->>'first_message_latency_ms')::INTEGER, first_message_latency_ms),
        turn_detection_mode = COALESCE(p_updates->>'turn_detection_mode', turn_detection_mode),
        speech_speed = COALESCE((p_updates->>'speech_speed')::DECIMAL, speech_speed),
        response_delay_ms = COALESCE((p_updates->>'response_delay_ms')::INTEGER, response_delay_ms),
        punctuation_pause_ms = COALESCE((p_updates->>'punctuation_pause_ms')::INTEGER, punctuation_pause_ms),
        no_punctuation_pause_ms = COALESCE((p_updates->>'no_punctuation_pause_ms')::INTEGER, no_punctuation_pause_ms),
        turn_eagerness = COALESCE(p_updates->>'turn_eagerness', turn_eagerness),
        updated_at = NOW()
    WHERE id = p_assistant_id AND user_id = v_user_id;

    RETURN jsonb_build_object('success', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON FUNCTION va_client_create_assistant IS 'Create a new AI assistant with LLM provider selection and plan limit checking';
COMMENT ON FUNCTION va_client_update_assistant IS 'Update assistant including LLM provider (groq, anthropic, openai, etc.)';

-- ============================================
-- FILE: 010_add_user_api_keys.sql
-- ============================================

-- Migration 010: Add User API Keys Table
-- Stores user's LLM provider API keys securely

-- =====================================================
-- CREATE USER API KEYS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS public.va_user_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'openai', 'anthropic', 'groq', etc.
    api_key TEXT NOT NULL,          -- Encrypted in production!
    api_key_masked VARCHAR(50),     -- For display: 'sk-...abc123'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Composite unique constraint: one key per provider per user
    CONSTRAINT va_user_api_keys_user_provider_unique UNIQUE (user_id, provider)
);

-- Create index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_va_user_api_keys_user_id
ON public.va_user_api_keys(user_id);

-- Add comments
COMMENT ON TABLE public.va_user_api_keys IS 'Stores user LLM API keys for different providers';
COMMENT ON COLUMN public.va_user_api_keys.provider IS 'LLM provider: openai, anthropic, groq, google, mistral, together, fireworks, deepseek, xai, cohere, perplexity';
COMMENT ON COLUMN public.va_user_api_keys.api_key IS 'The actual API key (should be encrypted in production)';
COMMENT ON COLUMN public.va_user_api_keys.api_key_masked IS 'Masked version for display (e.g., sk-...abc123)';

-- =====================================================
-- ROW LEVEL SECURITY
-- =====================================================

-- Enable RLS
ALTER TABLE public.va_user_api_keys ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own API keys
CREATE POLICY "Users can view own API keys"
ON public.va_user_api_keys FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own API keys"
ON public.va_user_api_keys FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own API keys"
ON public.va_user_api_keys FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own API keys"
ON public.va_user_api_keys FOR DELETE
USING (auth.uid() = user_id);

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Function to get user's API key for a specific provider
CREATE OR REPLACE FUNCTION va_get_user_api_key(p_user_id UUID, p_provider VARCHAR)
RETURNS TEXT AS $$
DECLARE
    v_api_key TEXT;
BEGIN
    SELECT api_key INTO v_api_key
    FROM public.va_user_api_keys
    WHERE user_id = p_user_id AND provider = p_provider;

    RETURN v_api_key;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user has a key for a provider
CREATE OR REPLACE FUNCTION va_user_has_api_key(p_user_id UUID, p_provider VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.va_user_api_keys
        WHERE user_id = p_user_id AND provider = p_provider
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION va_get_user_api_key IS 'Get user API key for a specific LLM provider';
COMMENT ON FUNCTION va_user_has_api_key IS 'Check if user has configured an API key for a provider';

-- ============================================
-- FILE: 011_add_tts_provider.sql
-- ============================================

-- Migration 011: Add TTS Provider Selection
-- This migration adds per-assistant TTS (Text-to-Speech) provider selection
-- Supports: cartesia, elevenlabs, deepgram, openai, playht, rime

-- =====================================================
-- ADD NEW COLUMN TO VA_ASSISTANTS
-- =====================================================

-- TTS provider selection (cartesia, elevenlabs, deepgram, openai, playht, rime)
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS tts_provider VARCHAR(50) DEFAULT 'cartesia';

-- Add comment explaining the column
COMMENT ON COLUMN public.va_assistants.tts_provider IS 'TTS provider: cartesia (recommended), elevenlabs, deepgram, openai, playht, rime';

-- Update voice_id default to Cartesia Katie voice
ALTER TABLE public.va_assistants
ALTER COLUMN voice_id SET DEFAULT 'f786b574-daa5-4673-aa0c-cbe3e8534c02';

-- =====================================================
-- DROP EXISTING FUNCTIONS (required to change signatures)
-- =====================================================

DROP FUNCTION IF EXISTS va_get_assistant(UUID);
DROP FUNCTION IF EXISTS va_client_get_assistant(UUID);
DROP FUNCTION IF EXISTS va_client_create_assistant(VARCHAR, TEXT, TEXT, VARCHAR, VARCHAR, VARCHAR, DECIMAL, INTEGER, TEXT, DECIMAL, INTEGER, BOOLEAN, BOOLEAN, INTEGER, VARCHAR, DECIMAL, INTEGER, INTEGER, INTEGER, VARCHAR);
DROP FUNCTION IF EXISTS va_client_update_assistant(UUID, JSONB);

-- =====================================================
-- RECREATE FUNCTIONS WITH TTS_PROVIDER COLUMN
-- =====================================================

-- Update va_get_assistant to return tts_provider
CREATE OR REPLACE FUNCTION va_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    tts_provider VARCHAR,
    voice_id VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    speech_speed DECIMAL,
    response_delay_ms INTEGER,
    punctuation_pause_ms INTEGER,
    no_punctuation_pause_ms INTEGER,
    turn_eagerness VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.user_id, a.name, a.description, a.system_prompt,
        a.tts_provider, a.voice_id, a.llm_provider, a.model, a.temperature,
        a.max_tokens, a.first_message, a.is_active, a.vad_sensitivity,
        a.endpointing_ms, a.enable_bargein, a.streaming_chunks,
        a.first_message_latency_ms, a.turn_detection_mode, a.speech_speed,
        a.response_delay_ms, a.punctuation_pause_ms, a.no_punctuation_pause_ms,
        a.turn_eagerness, a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_get_assistant to return tts_provider
CREATE OR REPLACE FUNCTION va_client_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    tts_provider VARCHAR,
    voice_id VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    speech_speed DECIMAL,
    response_delay_ms INTEGER,
    punctuation_pause_ms INTEGER,
    no_punctuation_pause_ms INTEGER,
    turn_eagerness VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.name, a.description, a.system_prompt, a.tts_provider,
        a.voice_id, a.llm_provider, a.model, a.temperature, a.max_tokens,
        a.first_message, a.is_active, a.vad_sensitivity, a.endpointing_ms,
        a.enable_bargein, a.streaming_chunks, a.first_message_latency_ms,
        a.turn_detection_mode, a.speech_speed, a.response_delay_ms,
        a.punctuation_pause_ms, a.no_punctuation_pause_ms, a.turn_eagerness,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id AND a.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_create_assistant to accept tts_provider
CREATE OR REPLACE FUNCTION va_client_create_assistant(
    p_name VARCHAR,
    p_system_prompt TEXT,
    p_description TEXT DEFAULT NULL,
    p_tts_provider VARCHAR DEFAULT 'cartesia',
    p_voice_id VARCHAR DEFAULT 'f786b574-daa5-4673-aa0c-cbe3e8534c02',
    p_llm_provider VARCHAR DEFAULT 'groq',
    p_model VARCHAR DEFAULT 'llama-3.3-70b-versatile',
    p_temperature DECIMAL DEFAULT 0.7,
    p_max_tokens INTEGER DEFAULT 150,
    p_first_message TEXT DEFAULT NULL,
    p_vad_sensitivity DECIMAL DEFAULT 0.5,
    p_endpointing_ms INTEGER DEFAULT 600,
    p_enable_bargein BOOLEAN DEFAULT true,
    p_streaming_chunks BOOLEAN DEFAULT true,
    p_first_message_latency_ms INTEGER DEFAULT 800,
    p_turn_detection_mode VARCHAR DEFAULT 'server_vad',
    p_speech_speed DECIMAL DEFAULT 0.9,
    p_response_delay_ms INTEGER DEFAULT 400,
    p_punctuation_pause_ms INTEGER DEFAULT 300,
    p_no_punctuation_pause_ms INTEGER DEFAULT 1000,
    p_turn_eagerness VARCHAR DEFAULT 'balanced'
)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
    v_current_count INTEGER;
    v_limit INTEGER;
    v_assistant_id UUID;
BEGIN
    -- Get current assistant count
    SELECT COUNT(*) INTO v_current_count
    FROM public.va_assistants
    WHERE user_id = v_user_id;

    -- Get plan limit
    SELECT COALESCE(
        (SELECT (pf.feature_value->>'value')::INTEGER
         FROM public.va_user_subscriptions us
         JOIN public.va_plan_features pf ON us.plan_id = pf.plan_id
         WHERE us.user_id = v_user_id
         AND us.status = 'active'
         AND pf.feature_key = 'max_assistants'),
        1
    ) INTO v_limit;

    -- Check limit (-1 means unlimited)
    IF v_limit != -1 AND v_current_count >= v_limit THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', format('Assistant limit reached. You have %s of %s assistants.', v_current_count, v_limit),
            'upgrade_required', true
        );
    END IF;

    -- Create assistant with tts_provider
    INSERT INTO public.va_assistants (
        user_id, name, description, system_prompt, tts_provider, voice_id,
        llm_provider, model, temperature, max_tokens, first_message,
        vad_sensitivity, endpointing_ms, enable_bargein,
        streaming_chunks, first_message_latency_ms, turn_detection_mode,
        speech_speed, response_delay_ms, punctuation_pause_ms,
        no_punctuation_pause_ms, turn_eagerness
    ) VALUES (
        v_user_id, p_name, p_description, p_system_prompt, p_tts_provider, p_voice_id,
        p_llm_provider, p_model, p_temperature, p_max_tokens, p_first_message,
        p_vad_sensitivity, p_endpointing_ms, p_enable_bargein,
        p_streaming_chunks, p_first_message_latency_ms, p_turn_detection_mode,
        p_speech_speed, p_response_delay_ms, p_punctuation_pause_ms,
        p_no_punctuation_pause_ms, p_turn_eagerness
    ) RETURNING id INTO v_assistant_id;

    RETURN jsonb_build_object(
        'success', true,
        'assistant_id', v_assistant_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update va_client_update_assistant to handle tts_provider
CREATE OR REPLACE FUNCTION va_client_update_assistant(
    p_assistant_id UUID,
    p_updates JSONB
)
RETURNS JSONB AS $$
DECLARE
    v_user_id UUID := auth.uid();
BEGIN
    -- Verify ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = v_user_id
    ) THEN
        RETURN jsonb_build_object('success', false, 'error', 'Assistant not found');
    END IF;

    -- Update fields including tts_provider
    UPDATE public.va_assistants
    SET
        name = COALESCE(p_updates->>'name', name),
        description = COALESCE(p_updates->>'description', description),
        system_prompt = COALESCE(p_updates->>'system_prompt', system_prompt),
        tts_provider = COALESCE(p_updates->>'tts_provider', tts_provider),
        voice_id = COALESCE(p_updates->>'voice_id', voice_id),
        llm_provider = COALESCE(p_updates->>'llm_provider', llm_provider),
        model = COALESCE(p_updates->>'model', model),
        temperature = COALESCE((p_updates->>'temperature')::DECIMAL, temperature),
        max_tokens = COALESCE((p_updates->>'max_tokens')::INTEGER, max_tokens),
        first_message = COALESCE(p_updates->>'first_message', first_message),
        is_active = COALESCE((p_updates->>'is_active')::BOOLEAN, is_active),
        vad_sensitivity = COALESCE((p_updates->>'vad_sensitivity')::DECIMAL, vad_sensitivity),
        endpointing_ms = COALESCE((p_updates->>'endpointing_ms')::INTEGER, endpointing_ms),
        enable_bargein = COALESCE((p_updates->>'enable_bargein')::BOOLEAN, enable_bargein),
        streaming_chunks = COALESCE((p_updates->>'streaming_chunks')::BOOLEAN, streaming_chunks),
        first_message_latency_ms = COALESCE((p_updates->>'first_message_latency_ms')::INTEGER, first_message_latency_ms),
        turn_detection_mode = COALESCE(p_updates->>'turn_detection_mode', turn_detection_mode),
        speech_speed = COALESCE((p_updates->>'speech_speed')::DECIMAL, speech_speed),
        response_delay_ms = COALESCE((p_updates->>'response_delay_ms')::INTEGER, response_delay_ms),
        punctuation_pause_ms = COALESCE((p_updates->>'punctuation_pause_ms')::INTEGER, punctuation_pause_ms),
        no_punctuation_pause_ms = COALESCE((p_updates->>'no_punctuation_pause_ms')::INTEGER, no_punctuation_pause_ms),
        turn_eagerness = COALESCE(p_updates->>'turn_eagerness', turn_eagerness),
        updated_at = NOW()
    WHERE id = p_assistant_id AND user_id = v_user_id;

    RETURN jsonb_build_object('success', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON FUNCTION va_client_create_assistant IS 'Create a new AI assistant with TTS provider selection (cartesia, elevenlabs, deepgram, openai, playht, rime)';
COMMENT ON FUNCTION va_client_update_assistant IS 'Update assistant including TTS provider for voice synthesis';

-- ============================================
-- FILE: 012_call_messages_and_data_lifecycle.sql
-- ============================================

-- Migration 012: Call Messages Table and Data Lifecycle Management
-- This migration adds individual message storage for call transcripts
-- and data lifecycle management for storage optimization

-- =====================================================
-- CALL MESSAGES TABLE (Real-time individual message storage)
-- =====================================================

CREATE TABLE IF NOT EXISTS public.va_call_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES public.va_call_logs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Message content
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,

    -- Timing
    message_timestamp TIMESTAMPTZ DEFAULT NOW(),
    sequence_number INTEGER NOT NULL, -- Order within the call

    -- Analysis (optional, populated asynchronously)
    sentiment_score DECIMAL(3,2), -- -1 to 1
    contains_pii BOOLEAN DEFAULT false, -- For compliance

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_va_call_messages_call_id ON public.va_call_messages(call_id);
CREATE INDEX IF NOT EXISTS idx_va_call_messages_user_id ON public.va_call_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_va_call_messages_timestamp ON public.va_call_messages(message_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_va_call_messages_role ON public.va_call_messages(role);

-- =====================================================
-- DATA LIFECYCLE / STORAGE MANAGEMENT TABLE
-- =====================================================

-- Standalone retention policies (not tied to plans for now)
CREATE TABLE IF NOT EXISTS public.va_data_retention_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE, -- 'free', 'pro', 'business', 'enterprise'

    -- Retention periods (in days, -1 = unlimited)
    call_log_retention_days INTEGER DEFAULT 90,
    call_message_retention_days INTEGER DEFAULT 30,
    recording_retention_days INTEGER DEFAULT 7,
    analytics_retention_days INTEGER DEFAULT 365,

    -- Storage limits (in MB, -1 = unlimited)
    max_recording_storage_mb INTEGER DEFAULT 500,
    max_transcript_storage_mb INTEGER DEFAULT 100,

    -- Auto-cleanup settings
    auto_delete_old_recordings BOOLEAN DEFAULT true,
    auto_archive_old_calls BOOLEAN DEFAULT true,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User storage usage tracking
CREATE TABLE IF NOT EXISTS public.va_storage_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- User's retention tier
    retention_tier VARCHAR(50) DEFAULT 'free',

    -- Current usage (in bytes)
    recording_bytes BIGINT DEFAULT 0,
    transcript_bytes BIGINT DEFAULT 0,
    voice_clone_bytes BIGINT DEFAULT 0,
    total_bytes BIGINT DEFAULT 0,

    -- Counts
    call_count INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    recording_count INTEGER DEFAULT 0,

    -- Last calculated
    last_calculated_at TIMESTAMPTZ DEFAULT NOW(),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id)
);

-- =====================================================
-- ROW LEVEL SECURITY
-- =====================================================

ALTER TABLE public.va_call_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.va_data_retention_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.va_storage_usage ENABLE ROW LEVEL SECURITY;

-- Call messages policies
DROP POLICY IF EXISTS "Users can view own call messages" ON public.va_call_messages;
CREATE POLICY "Users can view own call messages"
    ON public.va_call_messages FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access to call messages" ON public.va_call_messages;
CREATE POLICY "Service role full access to call messages"
    ON public.va_call_messages FOR ALL
    USING (auth.role() = 'service_role');

-- Storage usage policies
DROP POLICY IF EXISTS "Users can view own storage usage" ON public.va_storage_usage;
CREATE POLICY "Users can view own storage usage"
    ON public.va_storage_usage FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access to storage usage" ON public.va_storage_usage;
CREATE POLICY "Service role full access to storage usage"
    ON public.va_storage_usage FOR ALL
    USING (auth.role() = 'service_role');

-- Retention policies are readable by all authenticated users
DROP POLICY IF EXISTS "Authenticated users can view retention policies" ON public.va_data_retention_policies;
CREATE POLICY "Authenticated users can view retention policies"
    ON public.va_data_retention_policies FOR SELECT
    USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- =====================================================
-- FUNCTIONS FOR MESSAGE HANDLING
-- =====================================================

-- Insert a single call message (called during call)
CREATE OR REPLACE FUNCTION va_add_call_message(
    p_call_id UUID,
    p_user_id UUID,
    p_role VARCHAR,
    p_content TEXT,
    p_sequence_number INTEGER,
    p_metadata JSONB DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    v_message_id UUID;
BEGIN
    INSERT INTO public.va_call_messages (
        call_id, user_id, role, content, sequence_number, metadata
    ) VALUES (
        p_call_id, p_user_id, p_role, p_content, p_sequence_number, p_metadata
    ) RETURNING id INTO v_message_id;

    -- Also update the call log transcript array for backwards compatibility
    UPDATE public.va_call_logs
    SET transcript = COALESCE(transcript, '[]'::jsonb) || jsonb_build_array(jsonb_build_object(
        'role', p_role,
        'content', p_content,
        'timestamp', NOW()::TEXT
    ))
    WHERE id = p_call_id;

    RETURN v_message_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get call messages for a specific call
CREATE OR REPLACE FUNCTION va_client_get_call_messages(p_call_id UUID)
RETURNS TABLE (
    id UUID,
    role VARCHAR,
    content TEXT,
    message_timestamp TIMESTAMPTZ,
    sequence_number INTEGER,
    sentiment_score DECIMAL,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id, m.role, m.content, m.message_timestamp,
        m.sequence_number, m.sentiment_score, m.metadata
    FROM public.va_call_messages m
    JOIN public.va_call_logs cl ON m.call_id = cl.id
    WHERE m.call_id = p_call_id AND cl.user_id = auth.uid()
    ORDER BY m.sequence_number ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get storage usage for authenticated user
CREATE OR REPLACE FUNCTION va_client_get_storage_usage()
RETURNS TABLE (
    recording_bytes BIGINT,
    transcript_bytes BIGINT,
    voice_clone_bytes BIGINT,
    total_bytes BIGINT,
    call_count INTEGER,
    message_count INTEGER,
    recording_count INTEGER,
    storage_limit_bytes BIGINT,
    usage_percentage DECIMAL
) AS $$
DECLARE
    v_limit BIGINT;
    v_tier VARCHAR;
BEGIN
    -- Get user's tier
    SELECT COALESCE(su.retention_tier, 'free') INTO v_tier
    FROM public.va_storage_usage su
    WHERE su.user_id = auth.uid();

    -- Get storage limit from retention policy (default 500MB = 524288000 bytes)
    SELECT COALESCE(
        (SELECT (drp.max_recording_storage_mb + drp.max_transcript_storage_mb) * 1024 * 1024
         FROM public.va_data_retention_policies drp
         WHERE drp.name = COALESCE(v_tier, 'free')),
        524288000  -- Default 500MB
    ) INTO v_limit;

    RETURN QUERY
    SELECT
        COALESCE(su.recording_bytes, 0)::BIGINT,
        COALESCE(su.transcript_bytes, 0)::BIGINT,
        COALESCE(su.voice_clone_bytes, 0)::BIGINT,
        COALESCE(su.total_bytes, 0)::BIGINT,
        COALESCE(su.call_count, 0),
        COALESCE(su.message_count, 0),
        COALESCE(su.recording_count, 0),
        v_limit,
        CASE WHEN v_limit > 0 THEN
            ROUND((COALESCE(su.total_bytes, 0)::DECIMAL / v_limit) * 100, 2)
        ELSE 0 END
    FROM public.va_storage_usage su
    WHERE su.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- DATA CLEANUP FUNCTIONS
-- =====================================================

-- Clean up old data based on retention policies
CREATE OR REPLACE FUNCTION va_cleanup_old_data()
RETURNS TABLE (
    deleted_call_messages INTEGER,
    deleted_recordings INTEGER,
    archived_calls INTEGER
) AS $$
DECLARE
    v_deleted_messages INTEGER := 0;
    v_deleted_recordings INTEGER := 0;
    v_archived_calls INTEGER := 0;
BEGIN
    -- Delete old call messages beyond default retention (30 days for now)
    WITH deleted AS (
        DELETE FROM public.va_call_messages m
        WHERE m.created_at < NOW() - INTERVAL '30 days'
        RETURNING m.id
    )
    SELECT COUNT(*) INTO v_deleted_messages FROM deleted;

    -- Clear recording URLs for old recordings (7 days default)
    WITH updated AS (
        UPDATE public.va_call_logs cl
        SET recording_url = NULL
        WHERE cl.recording_url IS NOT NULL
        AND cl.created_at < NOW() - INTERVAL '7 days'
        RETURNING cl.id
    )
    SELECT COUNT(*) INTO v_deleted_recordings FROM updated;

    RETURN QUERY SELECT v_deleted_messages, v_deleted_recordings, v_archived_calls;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update storage usage for a user
CREATE OR REPLACE FUNCTION va_update_storage_usage(p_user_id UUID)
RETURNS VOID AS $$
BEGIN
    INSERT INTO public.va_storage_usage (
        user_id,
        recording_bytes,
        transcript_bytes,
        call_count,
        message_count,
        recording_count,
        total_bytes,
        last_calculated_at
    )
    SELECT
        p_user_id,
        0, -- Recording bytes (would need actual file size tracking)
        COALESCE(SUM(LENGTH(m.content)), 0),
        (SELECT COUNT(*) FROM public.va_call_logs WHERE user_id = p_user_id),
        COUNT(*),
        (SELECT COUNT(*) FROM public.va_call_logs WHERE user_id = p_user_id AND recording_url IS NOT NULL),
        COALESCE(SUM(LENGTH(m.content)), 0),
        NOW()
    FROM public.va_call_messages m
    WHERE m.user_id = p_user_id
    ON CONFLICT (user_id) DO UPDATE SET
        transcript_bytes = EXCLUDED.transcript_bytes,
        call_count = EXCLUDED.call_count,
        message_count = EXCLUDED.message_count,
        recording_count = EXCLUDED.recording_count,
        total_bytes = EXCLUDED.total_bytes,
        last_calculated_at = NOW(),
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- EXPORT FUNCTIONS
-- =====================================================

-- Export call data as JSON
CREATE OR REPLACE FUNCTION va_client_export_calls_json(
    p_start_date TIMESTAMPTZ DEFAULT NULL,
    p_end_date TIMESTAMPTZ DEFAULT NULL,
    p_assistant_id UUID DEFAULT NULL
)
RETURNS JSONB AS $$
BEGIN
    RETURN (
        SELECT jsonb_agg(call_data)
        FROM (
            SELECT jsonb_build_object(
                'id', cl.id,
                'assistant_name', COALESCE(a.name, 'Unknown'),
                'call_type', cl.call_type,
                'phone_number', cl.phone_number,
                'status', cl.status,
                'started_at', cl.started_at,
                'ended_at', cl.ended_at,
                'duration_seconds', cl.duration_seconds,
                'cost_cents', cl.cost_cents,
                'sentiment', cl.sentiment,
                'summary', cl.summary,
                'messages', (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'role', m.role,
                            'content', m.content,
                            'timestamp', m.message_timestamp
                        ) ORDER BY m.sequence_number
                    )
                    FROM public.va_call_messages m
                    WHERE m.call_id = cl.id
                )
            ) as call_data
            FROM public.va_call_logs cl
            LEFT JOIN public.va_assistants a ON cl.assistant_id = a.id
            WHERE cl.user_id = auth.uid()
            AND (p_start_date IS NULL OR cl.started_at >= p_start_date)
            AND (p_end_date IS NULL OR cl.started_at <= p_end_date)
            AND (p_assistant_id IS NULL OR cl.assistant_id = p_assistant_id)
            ORDER BY cl.started_at DESC
        ) sub
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- DEFAULT RETENTION POLICIES
-- =====================================================

-- Insert default retention policies for each tier
INSERT INTO public.va_data_retention_policies (name, call_log_retention_days, call_message_retention_days, recording_retention_days, analytics_retention_days, max_recording_storage_mb, max_transcript_storage_mb)
VALUES
    ('free', 30, 14, 3, 30, 100, 25),
    ('pro', 90, 60, 14, 180, 500, 100),
    ('business', 365, 180, 30, 365, 2000, 500),
    ('enterprise', -1, -1, -1, -1, -1, -1)
ON CONFLICT (name) DO NOTHING;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE public.va_call_messages IS 'Individual messages from calls, stored in real-time for robust transcript tracking';
COMMENT ON TABLE public.va_data_retention_policies IS 'Data retention policies per subscription tier';
COMMENT ON TABLE public.va_storage_usage IS 'Per-user storage usage tracking for quota enforcement';

COMMENT ON FUNCTION va_add_call_message IS 'Add a single message during a call (real-time storage)';
COMMENT ON FUNCTION va_cleanup_old_data IS 'Automated cleanup of data beyond retention periods';
COMMENT ON FUNCTION va_client_export_calls_json IS 'Export call data with messages as JSON';

-- ============================================
-- FILE: 013_add_fast_brain_skill.sql
-- ============================================

-- Migration 013: Add Fast Brain Skill Column
-- This migration adds the fast_brain_skill column to va_assistants
-- and updates all related functions with the new signature

-- =====================================================
-- STEP 1: ADD FAST BRAIN SKILL COLUMN
-- =====================================================

ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS fast_brain_skill VARCHAR(100) DEFAULT 'default';

COMMENT ON COLUMN public.va_assistants.fast_brain_skill IS 'Fast Brain skill/persona: default, receptionist, electrician, plumber, lawyer, solar, tara-sales, etc.';

-- =====================================================
-- STEP 2: DROP ALL EXISTING FUNCTION OVERLOADS
-- We use regprocedure to get exact signatures
-- =====================================================

DO $$
DECLARE
    func_sig TEXT;
BEGIN
    -- Drop all va_client_get_assistant overloads
    FOR func_sig IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname = 'va_client_get_assistant' AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_sig || ' CASCADE';
        RAISE NOTICE 'Dropped: %', func_sig;
    END LOOP;

    -- Drop all va_client_list_assistants overloads
    FOR func_sig IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname = 'va_client_list_assistants' AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_sig || ' CASCADE';
        RAISE NOTICE 'Dropped: %', func_sig;
    END LOOP;

    -- Drop all va_client_create_assistant overloads
    FOR func_sig IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname = 'va_client_create_assistant' AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_sig || ' CASCADE';
        RAISE NOTICE 'Dropped: %', func_sig;
    END LOOP;

    -- Drop all va_client_update_assistant overloads
    FOR func_sig IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname = 'va_client_update_assistant' AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_sig || ' CASCADE';
        RAISE NOTICE 'Dropped: %', func_sig;
    END LOOP;
END $$;

-- =====================================================
-- STEP 3: CREATE NEW FUNCTIONS WITH CORRECT SIGNATURES
-- =====================================================

-- Get single assistant by ID
CREATE FUNCTION public.va_client_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    tts_provider VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    fast_brain_skill VARCHAR,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    speech_speed DECIMAL,
    response_delay_ms INTEGER,
    punctuation_pause_ms INTEGER,
    no_punctuation_pause_ms INTEGER,
    turn_eagerness VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.user_id, a.name, a.description, a.system_prompt,
        a.voice_id, COALESCE(a.tts_provider, 'cartesia')::VARCHAR,
        COALESCE(a.llm_provider, 'groq')::VARCHAR, a.model,
        a.temperature, a.max_tokens, a.first_message, a.is_active,
        COALESCE(a.fast_brain_skill, 'default')::VARCHAR,
        a.vad_sensitivity, a.endpointing_ms, a.enable_bargein, a.streaming_chunks,
        a.first_message_latency_ms, a.turn_detection_mode,
        COALESCE(a.speech_speed, 0.9), COALESCE(a.response_delay_ms, 400),
        COALESCE(a.punctuation_pause_ms, 300), COALESCE(a.no_punctuation_pause_ms, 1000),
        COALESCE(a.turn_eagerness, 'balanced')::VARCHAR,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id AND a.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- List all assistants for user
CREATE FUNCTION public.va_client_list_assistants()
RETURNS TABLE (
    id UUID,
    name VARCHAR,
    description TEXT,
    voice_id VARCHAR,
    tts_provider VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    is_active BOOLEAN,
    fast_brain_skill VARCHAR,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.name, a.description, a.voice_id,
        COALESCE(a.tts_provider, 'cartesia')::VARCHAR,
        COALESCE(a.llm_provider, 'groq')::VARCHAR,
        a.model, a.is_active,
        COALESCE(a.fast_brain_skill, 'default')::VARCHAR,
        a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.user_id = auth.uid()
    ORDER BY a.created_at DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create new assistant
CREATE FUNCTION public.va_client_create_assistant(
    p_name VARCHAR,
    p_system_prompt TEXT,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT 'default',
    p_tts_provider VARCHAR DEFAULT 'cartesia',
    p_llm_provider VARCHAR DEFAULT 'groq',
    p_model VARCHAR DEFAULT 'llama-3.3-70b-versatile',
    p_temperature DECIMAL DEFAULT 0.7,
    p_max_tokens INTEGER DEFAULT 150,
    p_first_message TEXT DEFAULT NULL,
    p_fast_brain_skill VARCHAR DEFAULT 'default',
    p_vad_sensitivity DECIMAL DEFAULT 0.5,
    p_endpointing_ms INTEGER DEFAULT 600,
    p_enable_bargein BOOLEAN DEFAULT true,
    p_streaming_chunks BOOLEAN DEFAULT true,
    p_first_message_latency_ms INTEGER DEFAULT 800,
    p_turn_detection_mode VARCHAR DEFAULT 'server_vad',
    p_speech_speed DECIMAL DEFAULT 0.9,
    p_response_delay_ms INTEGER DEFAULT 400,
    p_punctuation_pause_ms INTEGER DEFAULT 300,
    p_no_punctuation_pause_ms INTEGER DEFAULT 1000,
    p_turn_eagerness VARCHAR DEFAULT 'balanced'
)
RETURNS UUID AS $$
DECLARE
    v_assistant_id UUID;
BEGIN
    INSERT INTO public.va_assistants (
        user_id, name, system_prompt, description, voice_id,
        tts_provider, llm_provider, model, temperature, max_tokens, first_message,
        fast_brain_skill,
        vad_sensitivity, endpointing_ms, enable_bargein, streaming_chunks,
        first_message_latency_ms, turn_detection_mode,
        speech_speed, response_delay_ms, punctuation_pause_ms, no_punctuation_pause_ms, turn_eagerness
    ) VALUES (
        auth.uid(), p_name, p_system_prompt, p_description, p_voice_id,
        p_tts_provider, p_llm_provider, p_model, p_temperature, p_max_tokens, p_first_message,
        p_fast_brain_skill,
        p_vad_sensitivity, p_endpointing_ms, p_enable_bargein, p_streaming_chunks,
        p_first_message_latency_ms, p_turn_detection_mode,
        p_speech_speed, p_response_delay_ms, p_punctuation_pause_ms, p_no_punctuation_pause_ms, p_turn_eagerness
    ) RETURNING id INTO v_assistant_id;

    RETURN v_assistant_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update existing assistant
CREATE FUNCTION public.va_client_update_assistant(
    p_assistant_id UUID,
    p_name VARCHAR DEFAULT NULL,
    p_system_prompt TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT NULL,
    p_tts_provider VARCHAR DEFAULT NULL,
    p_llm_provider VARCHAR DEFAULT NULL,
    p_model VARCHAR DEFAULT NULL,
    p_temperature DECIMAL DEFAULT NULL,
    p_max_tokens INTEGER DEFAULT NULL,
    p_first_message TEXT DEFAULT NULL,
    p_is_active BOOLEAN DEFAULT NULL,
    p_fast_brain_skill VARCHAR DEFAULT NULL,
    p_vad_sensitivity DECIMAL DEFAULT NULL,
    p_endpointing_ms INTEGER DEFAULT NULL,
    p_enable_bargein BOOLEAN DEFAULT NULL,
    p_streaming_chunks BOOLEAN DEFAULT NULL,
    p_first_message_latency_ms INTEGER DEFAULT NULL,
    p_turn_detection_mode VARCHAR DEFAULT NULL,
    p_speech_speed DECIMAL DEFAULT NULL,
    p_response_delay_ms INTEGER DEFAULT NULL,
    p_punctuation_pause_ms INTEGER DEFAULT NULL,
    p_no_punctuation_pause_ms INTEGER DEFAULT NULL,
    p_turn_eagerness VARCHAR DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = auth.uid()
    ) THEN
        RETURN false;
    END IF;

    UPDATE public.va_assistants SET
        name = COALESCE(p_name, name),
        system_prompt = COALESCE(p_system_prompt, system_prompt),
        description = COALESCE(p_description, description),
        voice_id = COALESCE(p_voice_id, voice_id),
        tts_provider = COALESCE(p_tts_provider, tts_provider),
        llm_provider = COALESCE(p_llm_provider, llm_provider),
        model = COALESCE(p_model, model),
        temperature = COALESCE(p_temperature, temperature),
        max_tokens = COALESCE(p_max_tokens, max_tokens),
        first_message = COALESCE(p_first_message, first_message),
        is_active = COALESCE(p_is_active, is_active),
        fast_brain_skill = COALESCE(p_fast_brain_skill, fast_brain_skill),
        vad_sensitivity = COALESCE(p_vad_sensitivity, vad_sensitivity),
        endpointing_ms = COALESCE(p_endpointing_ms, endpointing_ms),
        enable_bargein = COALESCE(p_enable_bargein, enable_bargein),
        streaming_chunks = COALESCE(p_streaming_chunks, streaming_chunks),
        first_message_latency_ms = COALESCE(p_first_message_latency_ms, first_message_latency_ms),
        turn_detection_mode = COALESCE(p_turn_detection_mode, turn_detection_mode),
        speech_speed = COALESCE(p_speech_speed, speech_speed),
        response_delay_ms = COALESCE(p_response_delay_ms, response_delay_ms),
        punctuation_pause_ms = COALESCE(p_punctuation_pause_ms, punctuation_pause_ms),
        no_punctuation_pause_ms = COALESCE(p_no_punctuation_pause_ms, no_punctuation_pause_ms),
        turn_eagerness = COALESCE(p_turn_eagerness, turn_eagerness),
        updated_at = NOW()
    WHERE id = p_assistant_id;

    RETURN true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- FILE: 014_add_multi_skill_support.sql
-- ============================================

-- Migration 014: Add Multi-Skill Support
-- This migration adds support for assigning multiple skills to an assistant
-- The assistant can dynamically switch between these skills during a call

-- =====================================================
-- STEP 1: ADD MULTI-SKILL COLUMNS
-- =====================================================

-- Array of skill IDs this assistant can use
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT ARRAY['default'];

-- Primary skill (default/fallback)
-- Note: fast_brain_skill from migration 013 becomes the primary_skill
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS primary_skill VARCHAR(100);

-- Whether to auto-switch skills based on conversation context
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS auto_switch_skills BOOLEAN DEFAULT true;

-- Announce skill transitions to caller ("Let me connect you with...")
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS announce_skill_switch BOOLEAN DEFAULT true;

-- =====================================================
-- STEP 2: MIGRATE EXISTING DATA
-- =====================================================

-- Set primary_skill from fast_brain_skill
UPDATE public.va_assistants
SET primary_skill = COALESCE(fast_brain_skill, 'default')
WHERE primary_skill IS NULL;

-- Initialize skills array from fast_brain_skill
UPDATE public.va_assistants
SET skills = ARRAY[COALESCE(fast_brain_skill, 'default')]
WHERE skills = ARRAY['default'] OR skills IS NULL;

-- =====================================================
-- STEP 3: ADD COMMENTS
-- =====================================================

COMMENT ON COLUMN public.va_assistants.skills IS 'Array of skill IDs this assistant can use dynamically';
COMMENT ON COLUMN public.va_assistants.primary_skill IS 'Default/fallback skill when no match detected';
COMMENT ON COLUMN public.va_assistants.auto_switch_skills IS 'Enable automatic skill switching based on conversation';
COMMENT ON COLUMN public.va_assistants.announce_skill_switch IS 'Announce transitions like "Let me connect you with..."';

-- =====================================================
-- STEP 4: UPDATE FUNCTIONS FOR MULTI-SKILL SUPPORT
-- =====================================================

-- Drop existing functions first
DROP FUNCTION IF EXISTS public.va_client_get_assistant(UUID);
DROP FUNCTION IF EXISTS public.va_client_create_assistant(VARCHAR, TEXT, TEXT, VARCHAR, VARCHAR, VARCHAR, VARCHAR, DECIMAL, INTEGER, TEXT, VARCHAR, DECIMAL, INTEGER, BOOLEAN, BOOLEAN, INTEGER, VARCHAR, DECIMAL, INTEGER, INTEGER, INTEGER, VARCHAR);
DROP FUNCTION IF EXISTS public.va_client_update_assistant(UUID, VARCHAR, TEXT, TEXT, VARCHAR, VARCHAR, VARCHAR, VARCHAR, DECIMAL, INTEGER, TEXT, BOOLEAN, VARCHAR, DECIMAL, INTEGER, BOOLEAN, BOOLEAN, INTEGER, VARCHAR, DECIMAL, INTEGER, INTEGER, INTEGER, VARCHAR);

-- Get single assistant by ID (with multi-skill fields)
CREATE FUNCTION public.va_client_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    tts_provider VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    fast_brain_skill VARCHAR,
    skills TEXT[],
    primary_skill VARCHAR,
    auto_switch_skills BOOLEAN,
    announce_skill_switch BOOLEAN,
    vad_sensitivity DECIMAL,
    endpointing_ms INTEGER,
    enable_bargein BOOLEAN,
    streaming_chunks BOOLEAN,
    first_message_latency_ms INTEGER,
    turn_detection_mode VARCHAR,
    speech_speed DECIMAL,
    response_delay_ms INTEGER,
    punctuation_pause_ms INTEGER,
    no_punctuation_pause_ms INTEGER,
    turn_eagerness VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.user_id, a.name, a.description, a.system_prompt,
        a.voice_id, COALESCE(a.tts_provider, 'cartesia')::VARCHAR,
        COALESCE(a.llm_provider, 'groq')::VARCHAR, a.model,
        a.temperature, a.max_tokens, a.first_message, a.is_active,
        COALESCE(a.fast_brain_skill, 'default')::VARCHAR,
        COALESCE(a.skills, ARRAY['default']),
        COALESCE(a.primary_skill, a.fast_brain_skill, 'default')::VARCHAR,
        COALESCE(a.auto_switch_skills, true),
        COALESCE(a.announce_skill_switch, true),
        a.vad_sensitivity, a.endpointing_ms, a.enable_bargein, a.streaming_chunks,
        a.first_message_latency_ms, a.turn_detection_mode,
        COALESCE(a.speech_speed, 0.9), COALESCE(a.response_delay_ms, 400),
        COALESCE(a.punctuation_pause_ms, 300), COALESCE(a.no_punctuation_pause_ms, 1000),
        COALESCE(a.turn_eagerness, 'balanced')::VARCHAR,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id AND a.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create new assistant with multi-skill support
CREATE FUNCTION public.va_client_create_assistant(
    p_name VARCHAR,
    p_system_prompt TEXT,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT 'default',
    p_tts_provider VARCHAR DEFAULT 'cartesia',
    p_llm_provider VARCHAR DEFAULT 'groq',
    p_model VARCHAR DEFAULT 'llama-3.3-70b-versatile',
    p_temperature DECIMAL DEFAULT 0.7,
    p_max_tokens INTEGER DEFAULT 150,
    p_first_message TEXT DEFAULT NULL,
    p_fast_brain_skill VARCHAR DEFAULT 'default',
    p_skills TEXT[] DEFAULT ARRAY['default'],
    p_primary_skill VARCHAR DEFAULT NULL,
    p_auto_switch_skills BOOLEAN DEFAULT true,
    p_announce_skill_switch BOOLEAN DEFAULT true,
    p_vad_sensitivity DECIMAL DEFAULT 0.5,
    p_endpointing_ms INTEGER DEFAULT 600,
    p_enable_bargein BOOLEAN DEFAULT true,
    p_streaming_chunks BOOLEAN DEFAULT true,
    p_first_message_latency_ms INTEGER DEFAULT 800,
    p_turn_detection_mode VARCHAR DEFAULT 'server_vad',
    p_speech_speed DECIMAL DEFAULT 0.9,
    p_response_delay_ms INTEGER DEFAULT 400,
    p_punctuation_pause_ms INTEGER DEFAULT 300,
    p_no_punctuation_pause_ms INTEGER DEFAULT 1000,
    p_turn_eagerness VARCHAR DEFAULT 'balanced'
)
RETURNS UUID AS $$
DECLARE
    v_assistant_id UUID;
    v_primary VARCHAR;
BEGIN
    -- Use first skill as primary if not specified
    v_primary := COALESCE(p_primary_skill, p_skills[1], p_fast_brain_skill, 'default');

    INSERT INTO public.va_assistants (
        user_id, name, system_prompt, description, voice_id,
        tts_provider, llm_provider, model, temperature, max_tokens, first_message,
        fast_brain_skill, skills, primary_skill, auto_switch_skills, announce_skill_switch,
        vad_sensitivity, endpointing_ms, enable_bargein, streaming_chunks,
        first_message_latency_ms, turn_detection_mode,
        speech_speed, response_delay_ms, punctuation_pause_ms, no_punctuation_pause_ms, turn_eagerness
    ) VALUES (
        auth.uid(), p_name, p_system_prompt, p_description, p_voice_id,
        p_tts_provider, p_llm_provider, p_model, p_temperature, p_max_tokens, p_first_message,
        v_primary, p_skills, v_primary, p_auto_switch_skills, p_announce_skill_switch,
        p_vad_sensitivity, p_endpointing_ms, p_enable_bargein, p_streaming_chunks,
        p_first_message_latency_ms, p_turn_detection_mode,
        p_speech_speed, p_response_delay_ms, p_punctuation_pause_ms, p_no_punctuation_pause_ms, p_turn_eagerness
    ) RETURNING id INTO v_assistant_id;

    RETURN v_assistant_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update existing assistant with multi-skill support
CREATE FUNCTION public.va_client_update_assistant(
    p_assistant_id UUID,
    p_name VARCHAR DEFAULT NULL,
    p_system_prompt TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT NULL,
    p_tts_provider VARCHAR DEFAULT NULL,
    p_llm_provider VARCHAR DEFAULT NULL,
    p_model VARCHAR DEFAULT NULL,
    p_temperature DECIMAL DEFAULT NULL,
    p_max_tokens INTEGER DEFAULT NULL,
    p_first_message TEXT DEFAULT NULL,
    p_is_active BOOLEAN DEFAULT NULL,
    p_fast_brain_skill VARCHAR DEFAULT NULL,
    p_skills TEXT[] DEFAULT NULL,
    p_primary_skill VARCHAR DEFAULT NULL,
    p_auto_switch_skills BOOLEAN DEFAULT NULL,
    p_announce_skill_switch BOOLEAN DEFAULT NULL,
    p_vad_sensitivity DECIMAL DEFAULT NULL,
    p_endpointing_ms INTEGER DEFAULT NULL,
    p_enable_bargein BOOLEAN DEFAULT NULL,
    p_streaming_chunks BOOLEAN DEFAULT NULL,
    p_first_message_latency_ms INTEGER DEFAULT NULL,
    p_turn_detection_mode VARCHAR DEFAULT NULL,
    p_speech_speed DECIMAL DEFAULT NULL,
    p_response_delay_ms INTEGER DEFAULT NULL,
    p_punctuation_pause_ms INTEGER DEFAULT NULL,
    p_no_punctuation_pause_ms INTEGER DEFAULT NULL,
    p_turn_eagerness VARCHAR DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = auth.uid()
    ) THEN
        RETURN false;
    END IF;

    UPDATE public.va_assistants SET
        name = COALESCE(p_name, name),
        system_prompt = COALESCE(p_system_prompt, system_prompt),
        description = COALESCE(p_description, description),
        voice_id = COALESCE(p_voice_id, voice_id),
        tts_provider = COALESCE(p_tts_provider, tts_provider),
        llm_provider = COALESCE(p_llm_provider, llm_provider),
        model = COALESCE(p_model, model),
        temperature = COALESCE(p_temperature, temperature),
        max_tokens = COALESCE(p_max_tokens, max_tokens),
        first_message = COALESCE(p_first_message, first_message),
        is_active = COALESCE(p_is_active, is_active),
        fast_brain_skill = COALESCE(p_fast_brain_skill, fast_brain_skill),
        skills = COALESCE(p_skills, skills),
        primary_skill = COALESCE(p_primary_skill, primary_skill),
        auto_switch_skills = COALESCE(p_auto_switch_skills, auto_switch_skills),
        announce_skill_switch = COALESCE(p_announce_skill_switch, announce_skill_switch),
        vad_sensitivity = COALESCE(p_vad_sensitivity, vad_sensitivity),
        endpointing_ms = COALESCE(p_endpointing_ms, endpointing_ms),
        enable_bargein = COALESCE(p_enable_bargein, enable_bargein),
        streaming_chunks = COALESCE(p_streaming_chunks, streaming_chunks),
        first_message_latency_ms = COALESCE(p_first_message_latency_ms, first_message_latency_ms),
        turn_detection_mode = COALESCE(p_turn_detection_mode, turn_detection_mode),
        speech_speed = COALESCE(p_speech_speed, speech_speed),
        response_delay_ms = COALESCE(p_response_delay_ms, response_delay_ms),
        punctuation_pause_ms = COALESCE(p_punctuation_pause_ms, punctuation_pause_ms),
        no_punctuation_pause_ms = COALESCE(p_no_punctuation_pause_ms, no_punctuation_pause_ms),
        turn_eagerness = COALESCE(p_turn_eagerness, turn_eagerness),
        updated_at = NOW()
    WHERE id = p_assistant_id;

    RETURN true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- STEP 5: CREATE HELPER FUNCTION FOR SKILL ARRAY UPDATES
-- =====================================================

-- Add a skill to an assistant's skill list
CREATE OR REPLACE FUNCTION public.va_add_skill_to_assistant(
    p_assistant_id UUID,
    p_skill_id VARCHAR
)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = auth.uid()
    ) THEN
        RETURN false;
    END IF;

    -- Add skill if not already present
    UPDATE public.va_assistants
    SET skills = array_append(skills, p_skill_id),
        updated_at = NOW()
    WHERE id = p_assistant_id
      AND NOT (p_skill_id = ANY(skills));

    RETURN true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Remove a skill from an assistant's skill list
CREATE OR REPLACE FUNCTION public.va_remove_skill_from_assistant(
    p_assistant_id UUID,
    p_skill_id VARCHAR
)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = auth.uid()
    ) THEN
        RETURN false;
    END IF;

    -- Remove skill (but don't allow removing if it's the only one)
    UPDATE public.va_assistants
    SET skills = array_remove(skills, p_skill_id),
        updated_at = NOW()
    WHERE id = p_assistant_id
      AND array_length(skills, 1) > 1;

    RETURN true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================
--
-- New columns:
--   - skills: TEXT[] - Array of skill IDs
--   - primary_skill: VARCHAR - Default/fallback skill
--   - auto_switch_skills: BOOLEAN - Enable auto-switching
--   - announce_skill_switch: BOOLEAN - Announce transitions
--
-- Example usage:
--   -- Create assistant with 3 skills
--   SELECT va_client_create_assistant(
--     'Trade Receptionist',
--     'You are a receptionist...',
--     p_skills := ARRAY['receptionist', 'electrician', 'plumber'],
--     p_primary_skill := 'receptionist',
--     p_auto_switch_skills := true
--   );
--
--   -- Add a skill to existing assistant
--   SELECT va_add_skill_to_assistant('uuid-here', 'solar');

-- ============================================
-- FILE: 015_bee_themed_pricing.sql
-- ============================================

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

-- ============================================
-- FILE: 20250122_add_budget_tracking.sql
-- ============================================

-- Add user budgets table for budget tracking and alerts
-- Migration: Create user_budgets table

CREATE TABLE IF NOT EXISTS va_user_budgets (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  monthly_budget_cents INTEGER NOT NULL DEFAULT 5000, -- $50 default budget
  alert_thresholds INTEGER[] DEFAULT ARRAY[80, 90, 100], -- Alert at 80%, 90%, 100%
  last_alert_sent_at TIMESTAMP WITH TIME ZONE,
  last_alert_threshold INTEGER,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  UNIQUE(user_id)
);

-- Add index for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_budgets_user_id ON va_user_budgets(user_id);
CREATE INDEX IF NOT EXISTS idx_user_budgets_active ON va_user_budgets(is_active) WHERE is_active = true;

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_va_user_budgets_updated_at BEFORE UPDATE
  ON va_user_budgets FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- Add comments
COMMENT ON TABLE va_user_budgets IS 'User budget settings and alert thresholds for cost management';
COMMENT ON COLUMN va_user_budgets.monthly_budget_cents IS 'Monthly budget in cents (e.g., 5000 = $50)';
COMMENT ON COLUMN va_user_budgets.alert_thresholds IS 'Array of percentage thresholds to trigger alerts (e.g., [80, 90, 100])';
COMMENT ON COLUMN va_user_budgets.last_alert_sent_at IS 'Timestamp of last budget alert sent to prevent spam';
COMMENT ON COLUMN va_user_budgets.last_alert_threshold IS 'The threshold percentage that triggered the last alert';

-- ============================================
-- FILE: 20250122_add_token_tracking.sql
-- ============================================

-- Add token tracking and cost columns to usage metrics
-- Migration: Add input_tokens, output_tokens, and cost_cents columns

ALTER TABLE va_usage_metrics
ADD COLUMN IF NOT EXISTS input_tokens INTEGER,
ADD COLUMN IF NOT EXISTS output_tokens INTEGER,
ADD COLUMN IF NOT EXISTS cost_cents DECIMAL(10, 4);

-- Add index for efficient analytics queries
CREATE INDEX IF NOT EXISTS idx_usage_metrics_user_created
ON va_usage_metrics(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_usage_metrics_cost
ON va_usage_metrics(user_id, cost_cents)
WHERE cost_cents IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN va_usage_metrics.input_tokens IS 'Number of input tokens sent to the LLM';
COMMENT ON COLUMN va_usage_metrics.output_tokens IS 'Number of output tokens generated by the LLM';
COMMENT ON COLUMN va_usage_metrics.cost_cents IS 'Cost of this API call in cents (e.g., 0.05 = $0.0005)';

-- ============================================
-- FILE: 20250123_add_team_collaboration.sql
-- ============================================

-- Migration: Add Team Collaboration Features
-- Created: 2025-01-23
-- Description: Adds tables for team management and shared dashboards

-- ============================================================================
-- TEAMS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS va_teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookup by owner
CREATE INDEX idx_va_teams_owner_id ON va_teams(owner_id);

-- ============================================================================
-- TEAM MEMBERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS va_team_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES va_teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    invited_by UUID REFERENCES auth.users(id),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(team_id, user_id)
);

-- Indexes for fast lookup
CREATE INDEX idx_va_team_members_team_id ON va_team_members(team_id);
CREATE INDEX idx_va_team_members_user_id ON va_team_members(user_id);

-- ============================================================================
-- SHARED DASHBOARDS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS va_team_dashboards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES va_teams(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB DEFAULT '{}',
    shared_by UUID NOT NULL REFERENCES auth.users(id),
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookup by team
CREATE INDEX idx_va_team_dashboards_team_id ON va_team_dashboards(team_id);

-- ============================================================================
-- DASHBOARD WIDGETS TABLE (Optional - for customizable dashboards)
-- ============================================================================
CREATE TABLE IF NOT EXISTS va_dashboard_widgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dashboard_id UUID NOT NULL REFERENCES va_team_dashboards(id) ON DELETE CASCADE,
    widget_type VARCHAR(100) NOT NULL,
    widget_config JSONB DEFAULT '{}',
    position_x INT DEFAULT 0,
    position_y INT DEFAULT 0,
    width INT DEFAULT 1,
    height INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookup by dashboard
CREATE INDEX idx_va_dashboard_widgets_dashboard_id ON va_dashboard_widgets(dashboard_id);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all team tables
ALTER TABLE va_teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_team_dashboards ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_dashboard_widgets ENABLE ROW LEVEL SECURITY;

-- Teams: Users can see teams they own or are members of
CREATE POLICY "Users can view their teams"
    ON va_teams FOR SELECT
    USING (
        owner_id = auth.uid() OR
        id IN (SELECT team_id FROM va_team_members WHERE user_id = auth.uid())
    );

-- Teams: Only owners can create teams
CREATE POLICY "Users can create teams"
    ON va_teams FOR INSERT
    WITH CHECK (owner_id = auth.uid());

-- Teams: Only owners can update teams
CREATE POLICY "Owners can update teams"
    ON va_teams FOR UPDATE
    USING (owner_id = auth.uid());

-- Teams: Only owners can delete teams
CREATE POLICY "Owners can delete teams"
    ON va_teams FOR DELETE
    USING (owner_id = auth.uid());

-- Team Members: Users can view members of teams they belong to
CREATE POLICY "Users can view team members"
    ON va_team_members FOR SELECT
    USING (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members WHERE user_id = auth.uid()
        )
    );

-- Team Members: Owners and admins can add members
CREATE POLICY "Owners and admins can add members"
    ON va_team_members FOR INSERT
    WITH CHECK (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Team Members: Owners and admins can update member roles
CREATE POLICY "Owners and admins can update members"
    ON va_team_members FOR UPDATE
    USING (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Team Members: Owners and admins can remove members
CREATE POLICY "Owners and admins can remove members"
    ON va_team_members FOR DELETE
    USING (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Team Dashboards: Team members can view dashboards
CREATE POLICY "Team members can view dashboards"
    ON va_team_dashboards FOR SELECT
    USING (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members WHERE user_id = auth.uid()
        )
        OR is_public = TRUE
    );

-- Team Dashboards: Owners, admins, and members can create dashboards
CREATE POLICY "Team members can create dashboards"
    ON va_team_dashboards FOR INSERT
    WITH CHECK (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin', 'member')
        )
    );

-- Team Dashboards: Creators and admins can update dashboards
CREATE POLICY "Creators and admins can update dashboards"
    ON va_team_dashboards FOR UPDATE
    USING (
        shared_by = auth.uid() OR
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Team Dashboards: Creators and admins can delete dashboards
CREATE POLICY "Creators and admins can delete dashboards"
    ON va_team_dashboards FOR DELETE
    USING (
        shared_by = auth.uid() OR
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Dashboard Widgets: Inherit permissions from parent dashboard
CREATE POLICY "Users can view dashboard widgets"
    ON va_dashboard_widgets FOR SELECT
    USING (
        dashboard_id IN (SELECT id FROM va_team_dashboards)
    );

CREATE POLICY "Users can manage dashboard widgets"
    ON va_dashboard_widgets FOR ALL
    USING (
        dashboard_id IN (
            SELECT id FROM va_team_dashboards
            WHERE shared_by = auth.uid() OR
            team_id IN (
                SELECT id FROM va_teams WHERE owner_id = auth.uid()
                UNION
                SELECT team_id FROM va_team_members
                WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
            )
        )
    );

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_team_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for teams table
CREATE TRIGGER update_va_teams_updated_at
    BEFORE UPDATE ON va_teams
    FOR EACH ROW
    EXECUTE FUNCTION update_team_updated_at();

-- Trigger for dashboards table
CREATE TRIGGER update_va_team_dashboards_updated_at
    BEFORE UPDATE ON va_team_dashboards
    FOR EACH ROW
    EXECUTE FUNCTION update_team_updated_at();

-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================

-- Note: This migration is safe to run multiple times due to IF NOT EXISTS checks
-- The tables will only be created if they don't already exist
