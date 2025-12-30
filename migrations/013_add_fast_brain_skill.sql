-- Migration 013: Add Fast Brain Skill Column
-- This migration adds the fast_brain_skill column to va_assistants
-- and updates all related functions with the new signature

-- =====================================================
-- STEP 1: ADD FAST BRAIN SKILL COLUMN
-- =====================================================

ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS fast_brain_skill VARCHAR(100) DEFAULT 'default';

COMMENT ON COLUMN public.va_assistants.fast_brain_skill IS 'Fast Brain skill/persona: default, receptionist, electrician, plumber, lawyer, solar, tara-sales, etc.';

-- =====================================================
-- STEP 2: DROP ALL EXISTING FUNCTION OVERLOADS
-- We use regprocedure to get exact signatures
-- =====================================================

DO $$
DECLARE
    func_sig TEXT;
BEGIN
    -- Drop all va_client_get_assistant overloads
    FOR func_sig IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname = 'va_client_get_assistant' AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_sig || ' CASCADE';
        RAISE NOTICE 'Dropped: %', func_sig;
    END LOOP;

    -- Drop all va_client_list_assistants overloads
    FOR func_sig IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname = 'va_client_list_assistants' AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_sig || ' CASCADE';
        RAISE NOTICE 'Dropped: %', func_sig;
    END LOOP;

    -- Drop all va_client_create_assistant overloads
    FOR func_sig IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname = 'va_client_create_assistant' AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_sig || ' CASCADE';
        RAISE NOTICE 'Dropped: %', func_sig;
    END LOOP;

    -- Drop all va_client_update_assistant overloads
    FOR func_sig IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE p.proname = 'va_client_update_assistant' AND n.nspname = 'public'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func_sig || ' CASCADE';
        RAISE NOTICE 'Dropped: %', func_sig;
    END LOOP;
END $$;

-- =====================================================
-- STEP 3: CREATE NEW FUNCTIONS WITH CORRECT SIGNATURES
-- =====================================================

-- Get single assistant by ID
CREATE FUNCTION public.va_client_get_assistant(p_assistant_id UUID)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    name VARCHAR,
    description TEXT,
    system_prompt TEXT,
    voice_id VARCHAR,
    tts_provider VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    temperature DECIMAL,
    max_tokens INTEGER,
    first_message TEXT,
    is_active BOOLEAN,
    fast_brain_skill VARCHAR,
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
        a.voice_id, COALESCE(a.tts_provider, 'cartesia')::VARCHAR,
        COALESCE(a.llm_provider, 'groq')::VARCHAR, a.model,
        a.temperature, a.max_tokens, a.first_message, a.is_active,
        COALESCE(a.fast_brain_skill, 'default')::VARCHAR,
        a.vad_sensitivity, a.endpointing_ms, a.enable_bargein, a.streaming_chunks,
        a.first_message_latency_ms, a.turn_detection_mode,
        COALESCE(a.speech_speed, 0.9), COALESCE(a.response_delay_ms, 400),
        COALESCE(a.punctuation_pause_ms, 300), COALESCE(a.no_punctuation_pause_ms, 1000),
        COALESCE(a.turn_eagerness, 'balanced')::VARCHAR,
        a.metadata, a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.id = p_assistant_id AND a.user_id = auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- List all assistants for user
CREATE FUNCTION public.va_client_list_assistants()
RETURNS TABLE (
    id UUID,
    name VARCHAR,
    description TEXT,
    voice_id VARCHAR,
    tts_provider VARCHAR,
    llm_provider VARCHAR,
    model VARCHAR,
    is_active BOOLEAN,
    fast_brain_skill VARCHAR,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.name, a.description, a.voice_id,
        COALESCE(a.tts_provider, 'cartesia')::VARCHAR,
        COALESCE(a.llm_provider, 'groq')::VARCHAR,
        a.model, a.is_active,
        COALESCE(a.fast_brain_skill, 'default')::VARCHAR,
        a.created_at, a.updated_at
    FROM public.va_assistants a
    WHERE a.user_id = auth.uid()
    ORDER BY a.created_at DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create new assistant
CREATE FUNCTION public.va_client_create_assistant(
    p_name VARCHAR,
    p_system_prompt TEXT,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT 'default',
    p_tts_provider VARCHAR DEFAULT 'cartesia',
    p_llm_provider VARCHAR DEFAULT 'groq',
    p_model VARCHAR DEFAULT 'llama-3.3-70b-versatile',
    p_temperature DECIMAL DEFAULT 0.7,
    p_max_tokens INTEGER DEFAULT 150,
    p_first_message TEXT DEFAULT NULL,
    p_fast_brain_skill VARCHAR DEFAULT 'default',
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
RETURNS UUID AS $$
DECLARE
    v_assistant_id UUID;
BEGIN
    INSERT INTO public.va_assistants (
        user_id, name, system_prompt, description, voice_id,
        tts_provider, llm_provider, model, temperature, max_tokens, first_message,
        fast_brain_skill,
        vad_sensitivity, endpointing_ms, enable_bargein, streaming_chunks,
        first_message_latency_ms, turn_detection_mode,
        speech_speed, response_delay_ms, punctuation_pause_ms, no_punctuation_pause_ms, turn_eagerness
    ) VALUES (
        auth.uid(), p_name, p_system_prompt, p_description, p_voice_id,
        p_tts_provider, p_llm_provider, p_model, p_temperature, p_max_tokens, p_first_message,
        p_fast_brain_skill,
        p_vad_sensitivity, p_endpointing_ms, p_enable_bargein, p_streaming_chunks,
        p_first_message_latency_ms, p_turn_detection_mode,
        p_speech_speed, p_response_delay_ms, p_punctuation_pause_ms, p_no_punctuation_pause_ms, p_turn_eagerness
    ) RETURNING id INTO v_assistant_id;

    RETURN v_assistant_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update existing assistant
CREATE FUNCTION public.va_client_update_assistant(
    p_assistant_id UUID,
    p_name VARCHAR DEFAULT NULL,
    p_system_prompt TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_voice_id VARCHAR DEFAULT NULL,
    p_tts_provider VARCHAR DEFAULT NULL,
    p_llm_provider VARCHAR DEFAULT NULL,
    p_model VARCHAR DEFAULT NULL,
    p_temperature DECIMAL DEFAULT NULL,
    p_max_tokens INTEGER DEFAULT NULL,
    p_first_message TEXT DEFAULT NULL,
    p_is_active BOOLEAN DEFAULT NULL,
    p_fast_brain_skill VARCHAR DEFAULT NULL,
    p_vad_sensitivity DECIMAL DEFAULT NULL,
    p_endpointing_ms INTEGER DEFAULT NULL,
    p_enable_bargein BOOLEAN DEFAULT NULL,
    p_streaming_chunks BOOLEAN DEFAULT NULL,
    p_first_message_latency_ms INTEGER DEFAULT NULL,
    p_turn_detection_mode VARCHAR DEFAULT NULL,
    p_speech_speed DECIMAL DEFAULT NULL,
    p_response_delay_ms INTEGER DEFAULT NULL,
    p_punctuation_pause_ms INTEGER DEFAULT NULL,
    p_no_punctuation_pause_ms INTEGER DEFAULT NULL,
    p_turn_eagerness VARCHAR DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check ownership
    IF NOT EXISTS (
        SELECT 1 FROM public.va_assistants
        WHERE id = p_assistant_id AND user_id = auth.uid()
    ) THEN
        RETURN false;
    END IF;

    UPDATE public.va_assistants SET
        name = COALESCE(p_name, name),
        system_prompt = COALESCE(p_system_prompt, system_prompt),
        description = COALESCE(p_description, description),
        voice_id = COALESCE(p_voice_id, voice_id),
        tts_provider = COALESCE(p_tts_provider, tts_provider),
        llm_provider = COALESCE(p_llm_provider, llm_provider),
        model = COALESCE(p_model, model),
        temperature = COALESCE(p_temperature, temperature),
        max_tokens = COALESCE(p_max_tokens, max_tokens),
        first_message = COALESCE(p_first_message, first_message),
        is_active = COALESCE(p_is_active, is_active),
        fast_brain_skill = COALESCE(p_fast_brain_skill, fast_brain_skill),
        vad_sensitivity = COALESCE(p_vad_sensitivity, vad_sensitivity),
        endpointing_ms = COALESCE(p_endpointing_ms, endpointing_ms),
        enable_bargein = COALESCE(p_enable_bargein, enable_bargein),
        streaming_chunks = COALESCE(p_streaming_chunks, streaming_chunks),
        first_message_latency_ms = COALESCE(p_first_message_latency_ms, first_message_latency_ms),
        turn_detection_mode = COALESCE(p_turn_detection_mode, turn_detection_mode),
        speech_speed = COALESCE(p_speech_speed, speech_speed),
        response_delay_ms = COALESCE(p_response_delay_ms, response_delay_ms),
        punctuation_pause_ms = COALESCE(p_punctuation_pause_ms, punctuation_pause_ms),
        no_punctuation_pause_ms = COALESCE(p_no_punctuation_pause_ms, no_punctuation_pause_ms),
        turn_eagerness = COALESCE(p_turn_eagerness, turn_eagerness),
        updated_at = NOW()
    WHERE id = p_assistant_id;

    RETURN true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
