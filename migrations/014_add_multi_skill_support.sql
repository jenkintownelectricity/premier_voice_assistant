-- Migration 014: Add Multi-Skill Support
-- This migration adds support for assigning multiple skills to an assistant
-- The assistant can dynamically switch between these skills during a call

-- =====================================================
-- STEP 1: ADD MULTI-SKILL COLUMNS
-- =====================================================

-- Array of skill IDs this assistant can use
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT ARRAY['default'];

-- Primary skill (default/fallback)
-- Note: fast_brain_skill from migration 013 becomes the primary_skill
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS primary_skill VARCHAR(100);

-- Whether to auto-switch skills based on conversation context
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS auto_switch_skills BOOLEAN DEFAULT true;

-- Announce skill transitions to caller ("Let me connect you with...")
ALTER TABLE public.va_assistants
ADD COLUMN IF NOT EXISTS announce_skill_switch BOOLEAN DEFAULT true;

-- =====================================================
-- STEP 2: MIGRATE EXISTING DATA
-- =====================================================

-- Set primary_skill from fast_brain_skill
UPDATE public.va_assistants
SET primary_skill = COALESCE(fast_brain_skill, 'default')
WHERE primary_skill IS NULL;

-- Initialize skills array from fast_brain_skill
UPDATE public.va_assistants
SET skills = ARRAY[COALESCE(fast_brain_skill, 'default')]
WHERE skills = ARRAY['default'] OR skills IS NULL;

-- =====================================================
-- STEP 3: ADD COMMENTS
-- =====================================================

COMMENT ON COLUMN public.va_assistants.skills IS 'Array of skill IDs this assistant can use dynamically';
COMMENT ON COLUMN public.va_assistants.primary_skill IS 'Default/fallback skill when no match detected';
COMMENT ON COLUMN public.va_assistants.auto_switch_skills IS 'Enable automatic skill switching based on conversation';
COMMENT ON COLUMN public.va_assistants.announce_skill_switch IS 'Announce transitions like "Let me connect you with..."';

-- =====================================================
-- STEP 4: UPDATE FUNCTIONS FOR MULTI-SKILL SUPPORT
-- =====================================================

-- Drop existing functions first
DROP FUNCTION IF EXISTS public.va_client_get_assistant(UUID);
DROP FUNCTION IF EXISTS public.va_client_create_assistant(VARCHAR, TEXT, TEXT, VARCHAR, VARCHAR, VARCHAR, VARCHAR, DECIMAL, INTEGER, TEXT, VARCHAR, DECIMAL, INTEGER, BOOLEAN, BOOLEAN, INTEGER, VARCHAR, DECIMAL, INTEGER, INTEGER, INTEGER, VARCHAR);
DROP FUNCTION IF EXISTS public.va_client_update_assistant(UUID, VARCHAR, TEXT, TEXT, VARCHAR, VARCHAR, VARCHAR, VARCHAR, DECIMAL, INTEGER, TEXT, BOOLEAN, VARCHAR, DECIMAL, INTEGER, BOOLEAN, BOOLEAN, INTEGER, VARCHAR, DECIMAL, INTEGER, INTEGER, INTEGER, VARCHAR);

-- Get single assistant by ID (with multi-skill fields)
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
    skills TEXT[],
    primary_skill VARCHAR,
    auto_switch_skills BOOLEAN,
    announce_skill_switch BOOLEAN,
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
        COALESCE(a.skills, ARRAY['default']),
        COALESCE(a.primary_skill, a.fast_brain_skill, 'default')::VARCHAR,
        COALESCE(a.auto_switch_skills, true),
        COALESCE(a.announce_skill_switch, true),
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

-- Create new assistant with multi-skill support
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
    p_skills TEXT[] DEFAULT ARRAY['default'],
    p_primary_skill VARCHAR DEFAULT NULL,
    p_auto_switch_skills BOOLEAN DEFAULT true,
    p_announce_skill_switch BOOLEAN DEFAULT true,
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
    v_primary VARCHAR;
BEGIN
    -- Use first skill as primary if not specified
    v_primary := COALESCE(p_primary_skill, p_skills[1], p_fast_brain_skill, 'default');

    INSERT INTO public.va_assistants (
        user_id, name, system_prompt, description, voice_id,
        tts_provider, llm_provider, model, temperature, max_tokens, first_message,
        fast_brain_skill, skills, primary_skill, auto_switch_skills, announce_skill_switch,
        vad_sensitivity, endpointing_ms, enable_bargein, streaming_chunks,
        first_message_latency_ms, turn_detection_mode,
        speech_speed, response_delay_ms, punctuation_pause_ms, no_punctuation_pause_ms, turn_eagerness
    ) VALUES (
        auth.uid(), p_name, p_system_prompt, p_description, p_voice_id,
        p_tts_provider, p_llm_provider, p_model, p_temperature, p_max_tokens, p_first_message,
        v_primary, p_skills, v_primary, p_auto_switch_skills, p_announce_skill_switch,
        p_vad_sensitivity, p_endpointing_ms, p_enable_bargein, p_streaming_chunks,
        p_first_message_latency_ms, p_turn_detection_mode,
        p_speech_speed, p_response_delay_ms, p_punctuation_pause_ms, p_no_punctuation_pause_ms, p_turn_eagerness
    ) RETURNING id INTO v_assistant_id;

    RETURN v_assistant_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update existing assistant with multi-skill support
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
    p_skills TEXT[] DEFAULT NULL,
    p_primary_skill VARCHAR DEFAULT NULL,
    p_auto_switch_skills BOOLEAN DEFAULT NULL,
    p_announce_skill_switch BOOLEAN DEFAULT NULL,
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
        skills = COALESCE(p_skills, skills),
        primary_skill = COALESCE(p_primary_skill, primary_skill),
        auto_switch_skills = COALESCE(p_auto_switch_skills, auto_switch_skills),
        announce_skill_switch = COALESCE(p_announce_skill_switch, announce_skill_switch),
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

-- =====================================================
-- STEP 5: CREATE HELPER FUNCTION FOR SKILL ARRAY UPDATES
-- =====================================================

-- Add a skill to an assistant's skill list
CREATE OR REPLACE FUNCTION public.va_add_skill_to_assistant(
    p_assistant_id UUID,
    p_skill_id VARCHAR
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

    -- Add skill if not already present
    UPDATE public.va_assistants
    SET skills = array_append(skills, p_skill_id),
        updated_at = NOW()
    WHERE id = p_assistant_id
      AND NOT (p_skill_id = ANY(skills));

    RETURN true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Remove a skill from an assistant's skill list
CREATE OR REPLACE FUNCTION public.va_remove_skill_from_assistant(
    p_assistant_id UUID,
    p_skill_id VARCHAR
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

    -- Remove skill (but don't allow removing if it's the only one)
    UPDATE public.va_assistants
    SET skills = array_remove(skills, p_skill_id),
        updated_at = NOW()
    WHERE id = p_assistant_id
      AND array_length(skills, 1) > 1;

    RETURN true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================
--
-- New columns:
--   - skills: TEXT[] - Array of skill IDs
--   - primary_skill: VARCHAR - Default/fallback skill
--   - auto_switch_skills: BOOLEAN - Enable auto-switching
--   - announce_skill_switch: BOOLEAN - Announce transitions
--
-- Example usage:
--   -- Create assistant with 3 skills
--   SELECT va_client_create_assistant(
--     'Trade Receptionist',
--     'You are a receptionist...',
--     p_skills := ARRAY['receptionist', 'electrician', 'plumber'],
--     p_primary_skill := 'receptionist',
--     p_auto_switch_skills := true
--   );
--
--   -- Add a skill to existing assistant
--   SELECT va_add_skill_to_assistant('uuid-here', 'solar');
