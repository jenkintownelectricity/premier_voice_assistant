-- Migration 010: Add User API Keys Table
-- Stores user's LLM provider API keys securely

-- =====================================================
-- CREATE USER API KEYS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS public.va_user_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'openai', 'anthropic', 'groq', etc.
    api_key TEXT NOT NULL,          -- Encrypted in production!
    api_key_masked VARCHAR(50),     -- For display: 'sk-...abc123'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Composite unique constraint: one key per provider per user
    CONSTRAINT va_user_api_keys_user_provider_unique UNIQUE (user_id, provider)
);

-- Create index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_va_user_api_keys_user_id
ON public.va_user_api_keys(user_id);

-- Add comments
COMMENT ON TABLE public.va_user_api_keys IS 'Stores user LLM API keys for different providers';
COMMENT ON COLUMN public.va_user_api_keys.provider IS 'LLM provider: openai, anthropic, groq, google, mistral, together, fireworks, deepseek, xai, cohere, perplexity';
COMMENT ON COLUMN public.va_user_api_keys.api_key IS 'The actual API key (should be encrypted in production)';
COMMENT ON COLUMN public.va_user_api_keys.api_key_masked IS 'Masked version for display (e.g., sk-...abc123)';

-- =====================================================
-- ROW LEVEL SECURITY
-- =====================================================

-- Enable RLS
ALTER TABLE public.va_user_api_keys ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own API keys
CREATE POLICY "Users can view own API keys"
ON public.va_user_api_keys FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own API keys"
ON public.va_user_api_keys FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own API keys"
ON public.va_user_api_keys FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own API keys"
ON public.va_user_api_keys FOR DELETE
USING (auth.uid() = user_id);

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Function to get user's API key for a specific provider
CREATE OR REPLACE FUNCTION va_get_user_api_key(p_user_id UUID, p_provider VARCHAR)
RETURNS TEXT AS $$
DECLARE
    v_api_key TEXT;
BEGIN
    SELECT api_key INTO v_api_key
    FROM public.va_user_api_keys
    WHERE user_id = p_user_id AND provider = p_provider;

    RETURN v_api_key;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user has a key for a provider
CREATE OR REPLACE FUNCTION va_user_has_api_key(p_user_id UUID, p_provider VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.va_user_api_keys
        WHERE user_id = p_user_id AND provider = p_provider
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION va_get_user_api_key IS 'Get user API key for a specific LLM provider';
COMMENT ON FUNCTION va_user_has_api_key IS 'Check if user has configured an API key for a provider';
