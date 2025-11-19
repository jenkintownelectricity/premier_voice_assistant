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
