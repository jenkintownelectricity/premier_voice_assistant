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
