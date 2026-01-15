-- Migration 016: Early Risers Contest
-- Date: January 15, 2026
-- Description: Free 90-day premium trial with points-based engagement system

-- Contest definitions
CREATE TABLE IF NOT EXISTS va_contests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contest_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('pending', 'active', 'paused', 'ended')),
    trial_days INTEGER DEFAULT 90,
    tier VARCHAR(50) DEFAULT 'premium',
    funding_dependent BOOLEAN DEFAULT true,
    lds_entity_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Contest entries (user participation)
CREATE TABLE IF NOT EXISTS va_contest_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contest_id UUID NOT NULL REFERENCES va_contests(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    points_balance INTEGER DEFAULT 0,
    invites_sent INTEGER DEFAULT 0,
    invites_converted INTEGER DEFAULT 0,
    trial_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    trial_end TIMESTAMP WITH TIME ZONE,
    features_unlocked JSONB DEFAULT '[]'::jsonb,
    lds_entity_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(contest_id, user_id)
);

-- Points transactions
CREATE TABLE IF NOT EXISTS va_contest_points (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_id UUID NOT NULL REFERENCES va_contest_entries(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    points INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Redemptions
CREATE TABLE IF NOT EXISTS va_contest_redemptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_id UUID NOT NULL REFERENCES va_contest_entries(id) ON DELETE CASCADE,
    reward_type VARCHAR(50) NOT NULL,
    points_spent INTEGER NOT NULL,
    reward_value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contest_entries_user ON va_contest_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_contest_entries_contest ON va_contest_entries(contest_id);
CREATE INDEX IF NOT EXISTS idx_contest_points_entry ON va_contest_points(entry_id);
CREATE INDEX IF NOT EXISTS idx_contest_redemptions_entry ON va_contest_redemptions(entry_id);

-- Insert Early Risers Contest
INSERT INTO va_contests (contest_id, name, description, status, trial_days, tier, funding_dependent, lds_entity_id)
VALUES (
    'early_risers_2026',
    'EARLY RISERS',
    'Free 90-day premium access. Earn points through invites and engagement. Redeem for trial extensions and feature unlocks.',
    'active',
    90,
    'premium',
    true,
    'contest:early_risers:2026'
) ON CONFLICT (contest_id) DO NOTHING;

-- Function to add points
CREATE OR REPLACE FUNCTION va_add_contest_points(
    p_user_id UUID,
    p_action VARCHAR(50),
    p_points INTEGER,
    p_metadata JSONB DEFAULT '{}'::jsonb
) RETURNS INTEGER AS $$
DECLARE
    v_entry_id UUID;
    v_new_balance INTEGER;
BEGIN
    -- Get entry for active contest
    SELECT ce.id INTO v_entry_id
    FROM va_contest_entries ce
    JOIN va_contests c ON c.id = ce.contest_id
    WHERE ce.user_id = p_user_id AND c.status = 'active'
    LIMIT 1;

    IF v_entry_id IS NULL THEN
        RETURN -1;
    END IF;

    -- Record transaction
    INSERT INTO va_contest_points (entry_id, action, points, metadata)
    VALUES (v_entry_id, p_action, p_points, p_metadata);

    -- Update balance
    UPDATE va_contest_entries
    SET points_balance = points_balance + p_points
    WHERE id = v_entry_id
    RETURNING points_balance INTO v_new_balance;

    RETURN v_new_balance;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to redeem points
CREATE OR REPLACE FUNCTION va_redeem_contest_points(
    p_user_id UUID,
    p_reward_type VARCHAR(50),
    p_points_cost INTEGER,
    p_reward_value JSONB
) RETURNS JSONB AS $$
DECLARE
    v_entry_id UUID;
    v_current_balance INTEGER;
BEGIN
    -- Get entry and balance
    SELECT ce.id, ce.points_balance INTO v_entry_id, v_current_balance
    FROM va_contest_entries ce
    JOIN va_contests c ON c.id = ce.contest_id
    WHERE ce.user_id = p_user_id AND c.status = 'active'
    LIMIT 1;

    IF v_entry_id IS NULL THEN
        RETURN jsonb_build_object('success', false, 'error', 'no_active_entry');
    END IF;

    IF v_current_balance < p_points_cost THEN
        RETURN jsonb_build_object('success', false, 'error', 'insufficient_points', 'balance', v_current_balance);
    END IF;

    -- Deduct points
    UPDATE va_contest_entries
    SET points_balance = points_balance - p_points_cost
    WHERE id = v_entry_id;

    -- Record redemption
    INSERT INTO va_contest_redemptions (entry_id, reward_type, points_spent, reward_value)
    VALUES (v_entry_id, p_reward_type, p_points_cost, p_reward_value);

    RETURN jsonb_build_object('success', true, 'new_balance', v_current_balance - p_points_cost);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RLS policies
ALTER TABLE va_contests ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_contest_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_contest_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_contest_redemptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Contests are viewable by all" ON va_contests FOR SELECT USING (true);
CREATE POLICY "Users can view own entries" ON va_contest_entries FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can view own points" ON va_contest_points FOR SELECT
    USING (entry_id IN (SELECT id FROM va_contest_entries WHERE user_id = auth.uid()));
CREATE POLICY "Users can view own redemptions" ON va_contest_redemptions FOR SELECT
    USING (entry_id IN (SELECT id FROM va_contest_entries WHERE user_id = auth.uid()));
