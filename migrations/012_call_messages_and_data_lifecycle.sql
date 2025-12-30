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
