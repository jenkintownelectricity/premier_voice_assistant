# Deployment Guide - Premier Voice Assistant

Complete deployment guide for the Premier Voice Assistant mobile backend.

## Architecture Overview

```
┌──────────────────┐
│  iOS/Android App │
│  (Your mobile)   │
└────────┬─────────┘
         │ HTTPS
         ▼
┌─────────────────────┐
│  Railway            │ FastAPI Backend
│  - User auth        │ (This repo)
│  - Orchestration    │
│  - Supabase client  │
└─┬──────┬────────┬───┘
  │      │        │
  ▼      ▼        ▼
Modal  Claude  Supabase
(GPU)   API     (DB)
```

## Prerequisites

1. ✅ **Modal account** - https://modal.com (free $30/month credit)
2. ✅ **Anthropic API key** - https://console.anthropic.com
3. ✅ **Supabase Pro account** - https://supabase.com (you have this!)
4. ✅ **Railway account** - https://railway.app (free $5 credit)
5. ✅ **GitHub account** - For deploying from git

## Step 1: Setup Supabase

### 1.1 Run Database Schema

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Copy and paste the contents of `supabase/schema.sql`
4. Click **Run** to create all tables and policies

### 1.2 Create Storage Buckets

1. Go to **Storage** in your Supabase dashboard
2. Create bucket: `voice-recordings` (Private)
3. Create bucket: `voice-clones` (Private)

### 1.3 Enable Authentication

1. Go to **Authentication > Providers**
2. Enable the following:
   - ✅ Email (for passwordless magic links)
   - ✅ Phone (recommended - configure with Twilio)
   - ✅ Apple Sign-In (for iOS)
   - ✅ Google Sign-In (for Android)

### 1.4 Get API Keys

1. Go to **Settings > API**
2. Copy:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY` (keep this secret!)

## Step 2: Setup Modal

### 2.1 Install Modal CLI

```bash
pip install modal
```

### 2.2 Authenticate

```bash
modal token new
```

This will open a browser to authenticate. Copy your token ID and secret.

### 2.3 Deploy Modal Services

Deploy Whisper STT:
```bash
modal deploy modal_deployment/whisper_stt.py
```

Deploy Coqui TTS:
```bash
modal deploy modal_deployment/coqui_tts.py
```

First deployment takes ~5-10 minutes as it downloads models.

### 2.4 Get Modal Tokens

Go to https://modal.com/settings and copy:
- `MODAL_TOKEN_ID`
- `MODAL_TOKEN_SECRET`

## Step 3: Setup Railway

### 3.1 Create New Project

1. Go to https://railway.app
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Connect your GitHub account and select this repository

### 3.2 Configure Environment Variables

In Railway dashboard, add these environment variables:

```bash
# Modal
MODAL_TOKEN_ID=your_modal_token_id
MODAL_TOKEN_SECRET=your_modal_token_secret

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Optional
CLAUDE_MODEL=claude-3-5-sonnet-20241022
MAX_TOKENS=150
TEMPERATURE=0.7
```

### 3.3 Deploy

Railway will automatically:
1. Detect Python project
2. Install dependencies from `requirements.txt`
3. Run the start command from `railway.toml`
4. Assign a public URL (e.g., `https://your-app.up.railway.app`)

Deployment takes ~3-5 minutes.

## Step 4: Verify Deployment

### 4.1 Test Health Endpoint

```bash
curl https://your-app.up.railway.app/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "Premier Voice Assistant",
  "version": "0.2.0"
}
```

### 4.2 Test STT (from command line)

```bash
curl -X POST https://your-app.up.railway.app/transcribe \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@test_audio.wav"
```

### 4.3 Test TTS

```bash
curl -X POST https://your-app.up.railway.app/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "fabio"}' \
  --output response.wav
```

## Step 5: Mobile App Integration

### iOS (Swift)

```swift
import Supabase

let supabase = SupabaseClient(
    supabaseURL: URL(string: "https://your-project.supabase.co")!,
    supabaseKey: "your-anon-key"
)

// Sign in
let user = try await supabase.auth.signIn(phone: "+1234567890")

// Call backend
let url = URL(string: "https://your-app.up.railway.app/chat")!
var request = URLRequest(url: url)
request.setValue(user.id, forHTTPHeaderField: "X-User-ID")
request.httpMethod = "POST"
request.setValue("multipart/form-data", forHTTPHeaderField: "Content-Type")
```

### Android (Kotlin)

```kotlin
val supabase = createSupabaseClient(
    supabaseUrl = "https://your-project.supabase.co",
    supabaseKey = "your-anon-key"
)

// Sign in
val user = supabase.auth.signInWith(Phone) {
    phoneNumber = "+1234567890"
}

// Call backend
val client = OkHttpClient()
val request = Request.Builder()
    .url("https://your-app.up.railway.app/chat")
    .addHeader("X-User-ID", user.id)
    .post(audioFile.asRequestBody())
    .build()
```

### React Native

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://your-project.supabase.co',
  'your-anon-key'
)

// Sign in
const { user } = await supabase.auth.signIn({ phone: '+1234567890' })

// Call backend
const formData = new FormData()
formData.append('audio', audioBlob, 'recording.wav')

const response = await fetch('https://your-app.up.railway.app/chat', {
  method: 'POST',
  headers: {
    'X-User-ID': user.id,
  },
  body: formData,
})
```

## API Endpoints

### POST /chat
Full voice conversation pipeline (audio → text → AI → audio)

**Headers:**
- `X-User-ID` (required): User ID from Supabase auth
- `X-Conversation-ID` (optional): Continue existing conversation

**Body:** multipart/form-data with audio file

**Response:** Audio stream (WAV) with headers:
- `X-Conversation-ID`: Conversation ID (use for follow-ups)
- `X-User-Text`: What the user said
- `X-AI-Text`: AI response text
- `X-Total-Latency`: Total latency in milliseconds

### POST /transcribe
Audio to text only

### POST /speak
Text to speech only

### POST /clone-voice
Clone a new voice from reference audio

### GET /conversations
Get user's conversation history

### GET /profile
Get user profile and preferences

### PATCH /profile
Update user preferences

See `backend/main.py` for full API documentation.

## Monitoring & Costs

### Estimated Monthly Costs (Low-Medium Traffic)

| Service | Free Tier | Paid Tier | Notes |
|---------|-----------|-----------|-------|
| Modal | $30 credit/month | ~$20-50/month | GPU usage (STT+TTS) |
| Anthropic | None | ~$10-30/month | Pay per token |
| Supabase | FREE | $25/month (Pro) | Database + Storage + Auth |
| Railway | $5 credit | ~$5-20/month | API hosting |
| **Total** | ~$45-75 (with credits) | ~$60-125/month | Production ready |

### Monitoring

- **Railway**: Check logs in dashboard
- **Modal**: View usage at https://modal.com/usage
- **Supabase**: Database > Logs shows queries
- **Anthropic**: https://console.anthropic.com/usage

## Scaling

### For Higher Traffic:

1. **Railway**: Upgrade to higher tier, add Redis caching
2. **Modal**: Increase `scaledown_window` for warm instances
3. **Supabase**: Upgrade to Team tier for better performance
4. **Consider**: Adding CDN (Cloudflare) for static assets

## Troubleshooting

### Railway deployment fails
- Check logs in Railway dashboard
- Verify all environment variables are set
- Ensure `requirements.txt` is up to date

### Modal functions not responding
- Check Modal dashboard for errors
- Verify `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` are correct
- Re-deploy Modal functions

### Supabase connection errors
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- Check Supabase dashboard for API status
- Ensure Row Level Security policies are correct

### High latency
- Check Modal logs for cold starts
- Increase `scaledown_window` to keep containers warm
- Consider using Modal's "keep warm" feature for critical functions

## Security Checklist

- ✅ Never commit `.env` to git
- ✅ Use Supabase Row Level Security (already configured in schema)
- ✅ Only use `SUPABASE_SERVICE_ROLE_KEY` in backend (never in mobile app)
- ✅ Mobile apps should use `SUPABASE_ANON_KEY` only
- ✅ Enable Railway IP allowlisting in production
- ✅ Set up proper CORS origins for your mobile app domains

## Next Steps

1. ✅ Deploy to Railway
2. ✅ Test all endpoints
3. ✅ Integrate with mobile app
4. Add error tracking (Sentry)
5. Set up monitoring/alerting
6. Configure CI/CD pipeline
7. Add rate limiting
8. Set up staging environment

## Support

- Railway: https://railway.app/help
- Modal: https://modal.com/docs
- Supabase: https://supabase.com/docs
- Anthropic: https://docs.anthropic.com
