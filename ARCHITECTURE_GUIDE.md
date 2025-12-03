# Premier Voice Assistant - LiveKit Integration Architecture Guide

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


================================================================================
                              CONNECTION FLOW DIAGRAM
================================================================================

    User Opens Voice Call
           |
           v
    +------+------+
    | Frontend    |  POST /livekit/rooms
    | LiveKit-    +------------------------+
    | VoiceCall   |                        |
    +------+------+                        |
           |                               |
           v                               v
    +------+------+                 +------+------+
    | Create Room |                 | Validate    |
    | (get token) |                 | Assistant   |
    +------+------+                 +------+------+
           |                               |
           v                               v
    +------+------+                 +------+------+
    | Connect to  |                 | Create      |
    | LiveKit     |<================+ Call Log    |
    | (WebRTC)    |                 | (Supabase)  |
    +------+------+                 +-------------+
           |
           | Room Created Event
           v
    +------+------+
    | Agent Worker|
    | joins room  |
    +------+------+
           |
           v
    +------+------+
    | Voice       |
    | Pipeline    |
    | Starts      |
    +-------------+


================================================================================
                            VOICE PIPELINE ARCHITECTURE
================================================================================

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
                         |  +-------------------+  |    |
                         |  |   FAST BRAIN      |  |----+
                         |  |  (if configured)  |  |
                         |  | - BitNet LPU      |  |
                         |  | - Skill Adapters  |  |
                         |  | - Turn-Taking     |  |
                         |  +--------+----------+  |
                         |           |             |
                         |  +--------v----------+  |
                         |  |      GROQ         |  |
                         |  |  (fallback #1)    |  |
                         |  | Llama 3.3 70B     |  |
                         |  | ~40ms TTFT        |  |
                         |  +--------+----------+  |
                         |           |             |
                         |  +--------v----------+  |
                         |  |   ANTHROPIC       |  |
                         |  |  (fallback #2)    |  |
                         |  | Claude Sonnet     |  |
                         |  +-------------------+  |
                         +-------------------------+


================================================================================
                         LATENCY BREAKDOWN (Target)
================================================================================

    +----------------+----------+--------+
    | Component      | Latency  | Status |
    +----------------+----------+--------+
    | WebRTC (UDP)   | ~10-20ms |   OK   |
    | Silero VAD     | ~5ms     |   OK   |
    | Deepgram STT   | ~30ms    |   OK   |
    | LLM (Groq)     | ~40ms    |   OK   |
    | Cartesia TTS   | ~30ms    |   OK   |
    +----------------+----------+--------+
    | TOTAL          | ~150ms   |        |
    +----------------+----------+--------+

    Human conversation threshold: ~500ms
    Voice-to-Voice target: ~200-300ms


================================================================================
                             FILE STRUCTURE
================================================================================

    /backend/
    ├── main.py               # FastAPI app (63 endpoints)
    ├── livekit_api.py        # LiveKit REST endpoints
    ├── livekit_agent.py      # Voice agent (STT->LLM->TTS)
    ├── livekit_worker.py     # Worker process entry
    ├── brain_client.py       # Fast Brain API client
    └── supabase_client.py    # Database operations

    /web/src/
    ├── components/
    │   └── LiveKitVoiceCall.tsx  # WebRTC voice UI
    └── lib/
        └── api.ts               # API client

    /config/
    ├── railway.toml          # Railway deployment
    └── Procfile              # Worker configuration
```

## Connection Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Railway Backend | **DOWN** | Connection timeout - needs restart |
| Supabase | **CONFIGURED** | Schema ready, migrations applied |
| LiveKit Cloud | **CONFIGURED** | Credentials in .env.example |
| Deepgram STT | **CONFIGURED** | API key placeholder ready |
| Groq LLM | **CONFIGURED** | API key placeholder ready |
| Cartesia TTS | **CONFIGURED** | API key & voice ID ready |
| Fast Brain | **OPTIONAL** | URL in .env.example if deployed |
| Worker Process | **READY** | Procfile configured |

## What's Working

1. **Code Architecture** - All files are properly structured and connected
2. **LiveKit Integration** - Using v1.x API with AgentSession correctly
3. **Brain Client** - Full implementation with HTTP & WebSocket support
4. **Frontend Component** - LiveKitVoiceCall.tsx with full WebRTC handling
5. **Database Schema** - All tables created via migrations
6. **Fallback Chain** - Fast Brain -> Groq -> Anthropic

## What Needs Attention

1. **Railway Backend DOWN** - The production API is not responding
2. **Worker Not Running** - LiveKit worker needs separate Railway service
3. **Environment Variables** - Need real API keys configured in Railway

## Procfile Worker Configuration

```
web: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: python backend/livekit_worker.py start
```

## Required Environment Variables for Worker

```bash
# LiveKit Server (REQUIRED)
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxx
LIVEKIT_API_SECRET=xxxxx

# Voice Providers (REQUIRED)
DEEPGRAM_API_KEY=xxxxx
CARTESIA_API_KEY=xxxxx
CARTESIA_VOICE_ID=a0e99841-438c-4a64-b679-ae501e7d6091

# LLM - At least one required
GROQ_API_KEY=gsk_xxxxx        # Primary
ANTHROPIC_API_KEY=sk-ant-xxx  # Fallback

# Fast Brain (Optional)
FAST_BRAIN_URL=https://...modal.run
DEFAULT_SKILL=default
```

---
*Generated by Claude Code Architecture Analysis*
