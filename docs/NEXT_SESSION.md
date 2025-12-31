# HIVE215 - Next Session Instructions

**Last Updated:** December 4, 2025
**Previous Session:** Fast Brain LPU Integration

---

## What Was Completed (Fast Brain Integration)

### Backend Changes (`backend/main.py`)
- Enhanced `/admin/status` with actual Fast Brain health check + latency
- Added `GET /api/skills/fast-brain` - Fetch available skills
- Added `POST /api/skills/fast-brain` - Create custom skills
- Updated voice_agent status to check Fast Brain health before selecting

### Frontend Changes (`web/src/app/dashboard/developer/page.tsx`)
- Fast Brain card shows Online/Configured/Not Set states
- Displays available skills as purple tags
- Shows health check latency

### Already Working
- `backend/brain_client.py` - Full FastBrainClient (HTTP + WebSocket)
- `backend/livekit_agent.py` - BrainLLM class integrates with LiveKit
- Voice agent fallback chain: Fast Brain → Groq → Anthropic

---

## Current Status

### What's Working
- Fast Brain detected and showing as "Primary" LLM
- Developer dashboard displays Fast Brain status
- Skills API endpoints ready
- Fallback chain configured

### Issue to Fix
**LiveKit 401 Error**: `https://your-project.livekit.cloud` is a placeholder.

Need actual LiveKit credentials in Railway:
```bash
LIVEKIT_URL=wss://your-actual-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

Get from: https://cloud.livekit.io → Settings → Keys

---

## Environment Variables (Railway Backend)

### Currently Set
```bash
FAST_BRAIN_URL=https://jenkintownelectricity--fast-brain-api-fastapi-app.modal.run
GROQ_API_KEY=...
ANTHROPIC_API_KEY=...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
```

### Need to Set
```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

---

## Fast Brain Quick Reference

### Deployed URL
```
https://jenkintownelectricity--fast-brain-api-fastapi-app.modal.run
```

### Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with skills list |
| `/v1/skills` | GET | List all skills |
| `/v1/skills` | POST | Create custom skill |
| `/v1/chat/completions` | POST | Chat (OpenAI format) |

### Skills Available
- `general` - Default assistant
- `receptionist` - Professional call handling
- `electrician` - Electrical service intake
- `plumber` - Plumbing service intake
- `lawyer` - Legal intake calls

### Test Fast Brain
```bash
# Health check
curl https://jenkintownelectricity--fast-brain-api-fastapi-app.modal.run/health

# Chat completion
curl -X POST https://jenkintownelectricity--fast-brain-api-fastapi-app.modal.run/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "skill": "receptionist"}'
```

---

## Voice Pipeline Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    HIVE215 VOICE PIPELINE                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   Caller → Twilio → LiveKit Worker → Fast Brain LPU → Response   │
│                          │                  │                     │
│                    [Deepgram STT]    ┌──────┴──────┐              │
│                       ~100ms         │   Groq      │              │
│                          │           │ Llama 3.3   │              │
│                    [Cartesia TTS]    │   70B       │              │
│                       ~40ms          └─────────────┘              │
│                          │                  │                     │
│                   [Audio Response]   [Skills Database]            │
│                                                                   │
│   Latency: Deepgram ~100ms + Fast Brain ~80ms + Cartesia ~40ms   │
│   Total: ~220ms (target <500ms ✓)                                │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Next Steps (Priority Order)

### 1. Fix LiveKit Connection
Set actual LiveKit credentials in Railway to enable voice calls.

### 2. Test Full Voice Flow
1. Call Twilio number
2. Verify Fast Brain responds (~80ms TTFB)
3. Check fallback works if Fast Brain down

### 3. Add Skill Selection UI
Allow users to select which skill their assistant uses from dashboard.

### 4. Custom Skills
Enable creating business-specific skills through the dashboard.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/main.py` | API endpoints including `/api/skills/fast-brain` |
| `backend/brain_client.py` | FastBrainClient for HTTP/WebSocket |
| `backend/livekit_agent.py` | Voice agent with BrainLLM integration |
| `web/src/app/dashboard/developer/page.tsx` | Fast Brain status display |
| `screenshots/HIVE215_INTEGRATION.md` | Full integration guide |

---

## Branch Information

**Current Branch:** `claude/integrate-fast-brain-lpu-01UtorJFkpFmGieoY5J2yCFZ`

All Fast Brain integration changes are committed and pushed.

---

## Claude Code Session Prompt

```
I'm continuing work on HIVE215 voice assistant. Last session we integrated Fast Brain LPU.

Current status:
- Fast Brain is configured and detected as primary LLM
- Need to fix LiveKit credentials (currently shows 401 error)
- Skills API is ready at /api/skills/fast-brain

Fast Brain URL: https://jenkintownelectricity--fast-brain-api-fastapi-app.modal.run

Please help me [fix LiveKit / add skill selection UI / test voice flow].
```
