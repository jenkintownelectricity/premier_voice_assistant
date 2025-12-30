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
