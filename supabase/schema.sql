-- Premier Voice Assistant - Supabase Schema
-- This schema supports mobile apps with user authentication, conversation history, and voice cloning
-- All tables prefixed with "va_" (voice assistant) to avoid conflicts with other projects

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (extends Supabase auth.users)
CREATE TABLE public.va_user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    phone VARCHAR(20),
    preferred_voice VARCHAR(50) DEFAULT 'fabio',
    conversation_style VARCHAR(20) DEFAULT 'professional', -- professional, casual, technical
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE public.va_user_profiles ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only read/update their own profile
CREATE POLICY "Users can view own profile"
    ON public.va_user_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.va_user_profiles FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON public.va_user_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Conversations table
CREATE TABLE public.va_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Enable Row Level Security
ALTER TABLE public.va_conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own conversations"
    ON public.va_conversations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own conversations"
    ON public.va_conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own conversations"
    ON public.va_conversations FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own conversations"
    ON public.va_conversations FOR DELETE
    USING (auth.uid() = user_id);

-- Create index for faster queries
CREATE INDEX idx_va_conversations_user_id ON public.va_conversations(user_id);
CREATE INDEX idx_va_conversations_last_message_at ON public.va_conversations(last_message_at DESC);

-- Messages table (conversation history)
CREATE TABLE public.va_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES public.va_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    audio_url TEXT, -- Optional: URL to audio in Supabase Storage
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb -- For storing latency metrics, etc.
);

-- Enable Row Level Security
ALTER TABLE public.va_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view messages from own conversations"
    ON public.va_messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.va_conversations
            WHERE va_conversations.id = va_messages.conversation_id
            AND va_conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert messages to own conversations"
    ON public.va_messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.va_conversations
            WHERE va_conversations.id = va_messages.conversation_id
            AND va_conversations.user_id = auth.uid()
        )
    );

-- Create index for faster queries
CREATE INDEX idx_va_messages_conversation_id ON public.va_messages(conversation_id);
CREATE INDEX idx_va_messages_created_at ON public.va_messages(created_at DESC);

-- Voice clones table (for custom voice models)
CREATE TABLE public.va_voice_clones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    voice_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    reference_audio_url TEXT NOT NULL, -- URL in Supabase Storage
    sample_duration FLOAT, -- Duration in seconds
    modal_voice_id VARCHAR(100), -- ID in Modal system
    is_public BOOLEAN DEFAULT FALSE, -- Allow other users to use this voice
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE(user_id, voice_name)
);

-- Enable Row Level Security
ALTER TABLE public.va_voice_clones ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own voice clones"
    ON public.va_voice_clones FOR SELECT
    USING (auth.uid() = user_id OR is_public = TRUE);

CREATE POLICY "Users can insert own voice clones"
    ON public.va_voice_clones FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own voice clones"
    ON public.va_voice_clones FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own voice clones"
    ON public.va_voice_clones FOR DELETE
    USING (auth.uid() = user_id);

-- Create index
CREATE INDEX idx_va_voice_clones_user_id ON public.va_voice_clones(user_id);
CREATE INDEX idx_va_voice_clones_public ON public.va_voice_clones(is_public) WHERE is_public = TRUE;

-- Usage metrics table (for analytics and monitoring)
CREATE TABLE public.va_usage_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES public.va_conversations(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL, -- 'transcribe', 'generate', 'synthesize', 'clone_voice'
    stt_latency_ms INTEGER,
    llm_latency_ms INTEGER,
    tts_latency_ms INTEGER,
    total_latency_ms INTEGER,
    tokens_used INTEGER,
    audio_duration_seconds FLOAT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Enable Row Level Security
ALTER TABLE public.va_usage_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own metrics"
    ON public.va_usage_metrics FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service can insert metrics"
    ON public.va_usage_metrics FOR INSERT
    WITH CHECK (TRUE); -- Backend service inserts metrics

-- Create indexes for analytics
CREATE INDEX idx_va_usage_metrics_user_id ON public.va_usage_metrics(user_id);
CREATE INDEX idx_va_usage_metrics_created_at ON public.va_usage_metrics(created_at DESC);
CREATE INDEX idx_va_usage_metrics_event_type ON public.va_usage_metrics(event_type);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION va_update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER update_va_user_profiles_updated_at
    BEFORE UPDATE ON public.va_user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION va_update_updated_at_column();

-- Function to auto-update conversation last_message_at
CREATE OR REPLACE FUNCTION va_update_conversation_on_new_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.va_conversations
    SET
        last_message_at = NEW.created_at,
        message_count = message_count + 1
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update conversation when new message is added
CREATE TRIGGER update_va_conversation_on_message
    AFTER INSERT ON public.va_messages
    FOR EACH ROW
    EXECUTE FUNCTION va_update_conversation_on_new_message();

-- Create storage buckets (run these separately in Supabase dashboard or via API)
-- INSERT INTO storage.buckets (id, name, public) VALUES ('va-voice-recordings', 'va-voice-recordings', false);
-- INSERT INTO storage.buckets (id, name, public) VALUES ('va-voice-clones', 'va-voice-clones', false);

-- Storage policies for va-voice-recordings bucket
-- CREATE POLICY "Users can upload own recordings"
--     ON storage.objects FOR INSERT
--     WITH CHECK (bucket_id = 'va-voice-recordings' AND auth.uid()::text = (storage.foldername(name))[1]);

-- CREATE POLICY "Users can read own recordings"
--     ON storage.objects FOR SELECT
--     USING (bucket_id = 'va-voice-recordings' AND auth.uid()::text = (storage.foldername(name))[1]);

-- Storage policies for va-voice-clones bucket
-- CREATE POLICY "Users can upload own voice clones"
--     ON storage.objects FOR INSERT
--     WITH CHECK (bucket_id = 'va-voice-clones' AND auth.uid()::text = (storage.foldername(name))[1]);

-- CREATE POLICY "Users can read own voice clones"
--     ON storage.objects FOR SELECT
--     USING (bucket_id = 'va-voice-clones' AND auth.uid()::text = (storage.foldername(name))[1]);

-- CREATE POLICY "Public can read public voice clones"
--     ON storage.objects FOR SELECT
--     USING (bucket_id = 'va-voice-clones' AND (storage.foldername(name))[1] = 'public');
