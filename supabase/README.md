# Supabase Setup for Premier Voice Assistant

This directory contains the database schema and setup instructions for integrating Supabase with your voice assistant mobile app.

## Quick Setup

### 1. Create Storage Buckets

In your Supabase dashboard, go to **Storage** and create two buckets:

**Bucket 1: `va-voice-recordings`** (Private)
- For temporary voice recordings from users
- Auto-delete after 24 hours (optional)

**Bucket 2: `va-voice-clones`** (Private with public folder)
- For storing reference audio for voice cloning
- Users can only access their own clones

### 2. Run the Schema SQL

In your Supabase dashboard, go to **SQL Editor** and run the contents of `schema.sql`.

This will create:
- ✅ `user_profiles` - Extended user info (phone, preferences)
- ✅ `conversations` - Conversation sessions
- ✅ `messages` - Message history with audio URLs
- ✅ `voice_clones` - Custom voice models
- ✅ `usage_metrics` - Analytics and monitoring
- ✅ Row Level Security policies (users can only access their own data)

### 3. Enable Authentication Providers

Go to **Authentication > Providers** and enable:

**For Mobile Apps:**
- ✅ Email (passwordless magic links)
- ✅ Phone (SMS OTP) - Recommended for voice app
- ✅ Apple Sign-In (iOS)
- ✅ Google Sign-In (Android)

**Configure Phone Auth (Recommended):**
1. Enable "Phone" provider
2. Choose an SMS provider (Twilio recommended)
3. Add your Twilio credentials
4. Configure phone number verification

### 4. Get Your API Keys

Go to **Settings > API** and copy:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key  # For backend only!
```

Add these to your `.env` file (backend) and mobile app config.

## Database Schema Overview

```
┌─────────────────┐
│  auth.users     │ (Supabase managed)
│  - id           │
│  - email/phone  │
└────────┬────────┘
         │
         ├─────► user_profiles (preferences)
         │
         ├─────► conversations
         │           │
         │           └─────► messages (with audio URLs)
         │
         ├─────► voice_clones (custom voices)
         │
         └─────► usage_metrics (analytics)
```

## Storage Buckets

### va-voice-recordings/
```
{user_id}/
  ├── recording_123.wav
  ├── recording_124.wav
  └── ...
```

### va-voice-clones/
```
{user_id}/
  ├── fabio.wav
  ├── custom_voice.wav
public/
  ├── default_male.wav
  └── default_female.wav
```

## Row Level Security (RLS)

All tables have RLS enabled to ensure users can only:
- ✅ Read their own data
- ✅ Write to their own records
- ✅ Access public voice clones
- ❌ Cannot access other users' data

## Using from Mobile App

### iOS (Swift)
```swift
import Supabase

let supabase = SupabaseClient(
    supabaseURL: URL(string: "https://your-project.supabase.co")!,
    supabaseKey: "your-anon-key"
)

// Sign in with phone
await supabase.auth.signIn(phone: "+1234567890")
```

### Android (Kotlin)
```kotlin
val supabase = createSupabaseClient(
    supabaseUrl = "https://your-project.supabase.co",
    supabaseKey = "your-anon-key"
)
```

### React Native
```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://your-project.supabase.co',
  'your-anon-key'
)
```

## Backend Integration

The FastAPI backend uses the **service role key** (keep secret!) to:
- Create conversations and messages
- Log usage metrics
- Manage voice clones on Modal

See `backend/supabase_client.py` for implementation.

## Next Steps

1. ✅ Run `schema.sql` in Supabase SQL Editor
2. ✅ Create storage buckets
3. ✅ Enable phone authentication
4. ✅ Add API keys to `.env`
5. ✅ Deploy backend to Railway
6. ✅ Integrate Supabase SDK in mobile app

## Useful Supabase Queries

**Get conversation history:**
```sql
SELECT m.*, c.title
FROM messages m
JOIN conversations c ON m.conversation_id = c.id
WHERE c.user_id = auth.uid()
ORDER BY m.created_at DESC
LIMIT 50;
```

**Get user's average latency:**
```sql
SELECT
  AVG(total_latency_ms) as avg_latency,
  COUNT(*) as total_requests
FROM usage_metrics
WHERE user_id = auth.uid()
AND created_at > NOW() - INTERVAL '7 days';
```

## Support

- [Supabase Docs](https://supabase.com/docs)
- [RLS Guide](https://supabase.com/docs/guides/auth/row-level-security)
- [Storage Guide](https://supabase.com/docs/guides/storage)
