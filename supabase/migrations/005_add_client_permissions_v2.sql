-- Migration 005: Client permissions for discount codes and bonus minutes
-- Run this AFTER migrations 003 and 004 in Supabase SQL Editor

-- ============================================================================
-- RLS POLICIES FOR DISCOUNT CODES
-- ============================================================================

-- Enable RLS on discount codes table
ALTER TABLE va_discount_codes ENABLE ROW LEVEL SECURITY;

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
