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
