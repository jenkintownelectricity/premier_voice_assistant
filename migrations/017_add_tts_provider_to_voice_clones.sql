-- Migration 017: Add tts_provider column to va_voice_clones
-- Date: January 3, 2026
-- Description: Add tts_provider column to differentiate between Coqui and Fish Speech voice clones

-- Add tts_provider column if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'va_voice_clones' AND column_name = 'tts_provider'
  ) THEN
    ALTER TABLE public.va_voice_clones ADD COLUMN tts_provider VARCHAR(50) DEFAULT 'coqui';
  END IF;
END $$;

-- Update existing voice clones to have 'coqui' as default provider (if null)
UPDATE public.va_voice_clones
SET tts_provider = 'coqui'
WHERE tts_provider IS NULL;

-- Add comment explaining the column
COMMENT ON COLUMN public.va_voice_clones.tts_provider IS 'TTS provider: coqui (legacy), fish_speech (recommended)';

-- Create index for faster queries by provider
CREATE INDEX IF NOT EXISTS idx_voice_clones_tts_provider ON public.va_voice_clones(tts_provider);

-- Update va_client_get_voice_clones function to optionally filter by provider
DROP FUNCTION IF EXISTS va_client_get_voice_clones(UUID, VARCHAR);
DROP FUNCTION IF EXISTS va_client_get_voice_clones(UUID);

CREATE OR REPLACE FUNCTION va_client_get_voice_clones(
    p_user_id UUID,
    p_tts_provider VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    voice_name VARCHAR,
    display_name VARCHAR,
    reference_audio_url TEXT,
    sample_duration FLOAT,
    modal_voice_id VARCHAR,
    is_public BOOLEAN,
    tts_provider VARCHAR,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    IF p_tts_provider IS NULL THEN
        -- Return all voice clones for the user
        RETURN QUERY
        SELECT
            vc.id, vc.voice_name, vc.display_name, vc.reference_audio_url,
            vc.sample_duration, vc.modal_voice_id, vc.is_public,
            vc.tts_provider, vc.created_at
        FROM public.va_voice_clones vc
        WHERE vc.user_id = p_user_id
        ORDER BY vc.created_at DESC;
    ELSE
        -- Return voice clones for the specific provider
        RETURN QUERY
        SELECT
            vc.id, vc.voice_name, vc.display_name, vc.reference_audio_url,
            vc.sample_duration, vc.modal_voice_id, vc.is_public,
            vc.tts_provider, vc.created_at
        FROM public.va_voice_clones vc
        WHERE vc.user_id = p_user_id
        AND vc.tts_provider = p_tts_provider
        ORDER BY vc.created_at DESC;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION va_client_get_voice_clones(UUID, VARCHAR) TO authenticated;
GRANT EXECUTE ON FUNCTION va_client_get_voice_clones(UUID, VARCHAR) TO service_role;
