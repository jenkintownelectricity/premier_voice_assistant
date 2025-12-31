# Premier Voice Assistant - LiveKit Integration Architecture Guide

**Last Updated:** December 3, 2025
**Status:** Worker service created in Railway, awaiting run command configuration

---

## Current Deployment Status

| Component | Status | Details |
|-----------|--------|---------|
| Railway Web Service | ✅ Deployed | FastAPI backend at `web-production-1b085.up.railway.app` |
| Railway Worker Service | ⏳ **PENDING** | Service created, env vars set, **needs Run Command** |
| LiveKit Cloud | ✅ Configured | WebRTC gateway ready |
| Supabase | ✅ Configured | PostgreSQL with all tables |
| Environment Variables | ✅ Set | All API keys configured in Railway |

---

## Visual System Architecture

```
                                    PREMIER VOICE ASSISTANT
                                  LiveKit + Brain Integration
================================================================================

                              +-------------------+
                              |   USER BROWSER    |
                              |   (Next.js 14)    |
                              +--------+----------+
                                       |
                                       | WebRTC (UDP) ~10-20ms
                                       |
                              +--------v----------+
                              |   LIVEKIT CLOUD   |
                              | (WebRTC Gateway)  |
                              +--------+----------+
                                       |
              +------------------------+------------------------+
              |                                                 |
    +---------v---------+                            +----------v----------+
    |    WEB SERVICE    |                            |   WORKER SERVICE    |
    |  (FastAPI/Railway)|                            | (LiveKit Agent)     |
    +-------------------+                            +---------------------+
    |                   |                            |                     |
    | POST /livekit/rooms                            |  entrypoint()       |
    | GET  /livekit/status                           |    |                |
    | DELETE /livekit/rooms/{id}                     |    +-> Silero VAD   |
    | POST /livekit/dispatch                         |    +-> Deepgram STT |
    |                   |                            |    +-> LLM Chain    |
    +--------+----------+                            |    +-> Cartesia TTS |
             |                                       +----------+----------+
             |                                                  |
             |                                                  |
    +--------v----------+                            +----------v----------+
    |     SUPABASE      |                            |     LLM PRIORITY    |
    |   (PostgreSQL)    |                            |       CHAIN         |
    +-------------------+                            +---------------------+
    |                   |                            |                     |
    | va_assistants     |                            | 1. Fast Brain (opt) |
    | va_call_logs      |                            | 2. Groq Llama 3.3   |
    | va_user_profiles  |                            | 3. Anthropic Claude |
    | va_usage_metrics  |                            |                     |
    +-------------------+                            +---------------------+
```

---

## Voice Pipeline Architecture

```
                         +---------------------------+
                         |     LIVEKIT AGENT         |
                         |   (livekit_agent.py)      |
                         +---------------------------+
                                      |
                    +-----------------+-----------------+
                    |                 |                 |
              +-----v-----+     +-----v-----+     +-----v-----+
              |  SILERO   |     |  DEEPGRAM |     |  CARTESIA |
              |   VAD     |     |   STT     |     |    TTS    |
              +-----------+     +-----------+     +-----------+
              |           |     |           |     |           |
              | Voice     |     | Nova-2    |     | Sonic-    |
              | Activity  |---->| Streaming |     | English   |
              | Detection |     | ~30ms     |     | ~30ms     |
              +-----------+     +-----+-----+     +-----^-----+
                                      |                 |
                                      v                 |
                         +------------+------------+    |
                         |       LLM CHAIN         |    |
                         +-------------------------+    |
                         |                         |    |
                         |  1. Fast Brain (opt)    |----+
                         |  2. Groq Llama 3.3      |
                         |  3. Anthropic Claude    |
                         +-------------------------+

    Target Latency: ~200-300ms voice-to-voice
```

---

## File Structure

```
/backend/
├── main.py               # FastAPI app (63 endpoints)
├── livekit_api.py        # LiveKit REST endpoints (/livekit/*)
├── livekit_agent.py      # Voice agent pipeline (STT->LLM->TTS)
├── livekit_worker.py     # Worker process entry point
├── brain_client.py       # Fast Brain API client
└── supabase_client.py    # Database operations

/web/src/components/
└── LiveKitVoiceCall.tsx  # WebRTC voice call UI component

/root/
├── railway.toml          # Railway web service config
└── Procfile              # Process definitions
```

---

## Railway Worker Run Command

The worker service needs this **Run Command** in Railway settings:

```bash
python backend/livekit_worker.py start
```

### Alternative (if using Procfile):
```bash
worker
```

---

## Required Environment Variables (Already Set)

```bash
# LiveKit Server
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxx
LIVEKIT_API_SECRET=xxxxx

# Voice Providers
DEEPGRAM_API_KEY=xxxxx
CARTESIA_API_KEY=xxxxx
CARTESIA_VOICE_ID=a0e99841-438c-4a64-b679-ae501e7d6091

# LLM Providers
GROQ_API_KEY=gsk_xxxxx
ANTHROPIC_API_KEY=sk-ant-xxx

# Database
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxxx

# Optional: Fast Brain
FAST_BRAIN_URL=https://...modal.run
DEFAULT_SKILL=default
```

---

## Connection Flow

1. **User clicks "Start Call"** in frontend
2. **Frontend** calls `POST /livekit/rooms` with assistant_id
3. **Web Service** validates user, creates call_log in Supabase, creates LiveKit room
4. **Web Service** returns room token to frontend
5. **Frontend** connects to LiveKit Cloud via WebRTC
6. **LiveKit Cloud** notifies Worker of new room
7. **Worker** joins room and starts voice pipeline
8. **Voice conversation** flows: User audio → STT → LLM → TTS → Agent audio

---

## What's Complete

- [x] LiveKit Agent code (v1.x API with AgentSession)
- [x] Brain Client with HTTP + WebSocket streaming
- [x] Frontend LiveKitVoiceCall component
- [x] Database schema and migrations
- [x] LLM fallback chain (Brain → Groq → Claude)
- [x] Railway web service deployed
- [x] Railway worker service created
- [x] Environment variables configured

## What's Pending

- [ ] **Set Run Command for worker service in Railway**
- [ ] Test end-to-end voice call
- [ ] Verify agent joins rooms automatically

---

# NEXT SESSION INSTRUCTIONS

## For Claude Code: Configure Railway Worker Run Command

### Context
The Premier Voice Assistant uses LiveKit for WebRTC-based voice AI. The architecture requires two Railway services:
1. **Web Service** - FastAPI backend (already running)
2. **Worker Service** - LiveKit agent that handles voice calls (created, needs run command)

### Current State
- Worker service is created in Railway
- All environment variables are set
- Just needs the **Run Command** to be configured

### Task
Help the user configure the Railway worker service run command:

**Run Command to set:**
```bash
python backend/livekit_worker.py start
```

### Steps to Complete
1. Go to Railway dashboard → Worker service → Settings
2. Find "Deploy" or "Start Command" section
3. Set the run command to: `python backend/livekit_worker.py start`
4. Deploy the service
5. Check logs to verify worker starts and connects to LiveKit

### Verification
After deployment, the worker logs should show:
```
HIVE215 LiveKit Voice Agent Worker
Configuration:
  LIVEKIT_URL: wss://...
  LIVEKIT_API_KEY: APIxxx...
Starting LiveKit agent worker...
```

### Test the Integration
Once worker is running:
1. Call `GET /livekit/status` - should return `enabled: true`
2. Create a room via frontend or API
3. Check worker logs for "Agent job started for room: ..."

### Files Reference
- `backend/livekit_worker.py` - Worker entry point
- `backend/livekit_agent.py` - Voice pipeline implementation
- `Procfile` - Contains `worker: python backend/livekit_worker.py start`

---

*Generated by Claude Code Architecture Analysis - December 3, 2025*
