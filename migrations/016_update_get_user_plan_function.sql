-- Migration 016: Update va_get_user_plan function for bee-themed plans
-- Date: January 3, 2026
-- Description: Update the function to return bee-themed plan columns

-- Drop and recreate the function with new columns
DROP FUNCTION IF EXISTS va_get_user_plan(UUID);

CREATE OR REPLACE FUNCTION va_get_user_plan(p_user_id UUID)
RETURNS TABLE (
    plan_name VARCHAR,
    display_name VARCHAR,
    status VARCHAR,
    minutes_included INTEGER,
    phone_numbers INTEGER,
    voice_clones INTEGER,
    team_members INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sp.plan_name,
        sp.display_name,
        us.status,
        COALESCE(sp.minutes_included, 0)::INTEGER,
        COALESCE(sp.phone_numbers, 1)::INTEGER,
        COALESCE(sp.voice_clones, 0)::INTEGER,
        COALESCE(sp.team_members, 1)::INTEGER
    FROM public.va_user_subscriptions us
    JOIN public.va_subscription_plans sp ON us.plan_id = sp.id
    WHERE us.user_id = p_user_id
    AND us.status = 'active';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION va_get_user_plan(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION va_get_user_plan(UUID) TO service_role;
