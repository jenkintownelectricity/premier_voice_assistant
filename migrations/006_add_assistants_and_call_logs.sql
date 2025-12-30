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
