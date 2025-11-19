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
