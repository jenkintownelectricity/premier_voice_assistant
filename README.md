# HIVE215 Voice AI Platform

Real-time voice AI assistant platform built on LiveKit, featuring multi-tier LLM intelligence and sub-second response times.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn backend.main:app --reload --port 8000  # Web service
python backend/livekit_worker.py start          # Voice worker
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        HIVE215 Voice Pipeline                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Speech                                                    │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────┐    ┌─────────────────────────────────────┐    │
│   │   Silero    │    │         IRON EAR STACK               │    │
│   │    VAD      │───▶│  V1: Debounce (door slams, coughs)  │    │
│   │             │    │  V2: Speaker Locking (background)    │    │
│   └─────────────┘    │  V3: Identity Lock (ML fingerprint)  │    │
│                      └─────────────────────────────────────┘    │
│                                      │                           │
│                                      ▼                           │
│   ┌─────────────┐    ┌─────────────────────────────────────┐    │
│   │  Deepgram   │◀───│      Clean, Verified Audio          │    │
│   │    STT      │    └─────────────────────────────────────┘    │
│   └─────────────┘                                                │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    FAST BRAIN LPU                        │   │
│   ├──────────────────────┬──────────────────────────────────┤   │
│   │  System 1 (Fast)     │  System 2 (Deep)                 │   │
│   │  Groq + Llama 3.3    │  Claude 3.5 Sonnet               │   │
│   │  ~80ms latency       │  ~2000ms (with filler)           │   │
│   │  90% of queries      │  10% complex queries             │   │
│   └──────────────────────┴──────────────────────────────────┘   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────┐                                                │
│   │  Cartesia   │                                                │
│   │    TTS      │───▶  User Hears Response                      │
│   └─────────────┘                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Iron Ear Stack (Noise Filtering)

The "Iron Ear" is a multi-layer audio filtering system that ensures only the target caller is processed:

| Version | Feature | Problem Solved | Method |
|---------|---------|----------------|--------|
| **V1** | Debounce | Door slams, coughs | Require 300ms+ continuous speech |
| **V2** | Speaker Locking | Background TV, other people | Volume fingerprint (60% threshold) |
| **V3** | Identity Lock | Imposters, similar voices | 256-dim ML embeddings (Resemblyzer) |

### Honey Pot Flow (V3)

1. Agent asks engaging question: *"Could you tell me your name and what you're calling about?"*
2. User responds with 10-15 seconds of natural speech
3. System extracts 256-dimensional voice embedding
4. Identity LOCKED - only matching voice accepted
5. Background voices and imposters rejected

```python
# Usage
from worker.voice_agent import VoiceAgent

agent = VoiceAgent(skill_type="electrician")
agent.start_honeypot()  # Begin voice fingerprint collection

prompt = agent.get_honeypot_prompt()  # Skill-specific opening question
# "Could you describe the electrical issue you're experiencing?"

# After ~10s of speech, identity locks automatically
if agent.is_identity_calibrated:
    print(agent.get_identity_stats())
    # {'ml_enabled': True, 'avg_similarity': 0.82, 'acceptance_rate': 0.97}
```

## Voice Features

### LatencyMasker
Context-aware filler sounds while waiting for LLM:
- Acoustic (<200ms): "Hmm...", "Uh-huh..."
- Process (2s+): "Running the estimate...", "Checking the calendar..."

### TurnManager
State-of-the-art turn-taking for natural conversation:
- Semantic turn detection
- Interruption classification (backchannel, barge-in, correction)
- Prosodic cue analysis

## Project Structure

```
premier_voice_assistant/
├── backend/
│   ├── main.py              # FastAPI web server
│   └── livekit_worker.py    # Voice agent worker
├── worker/
│   ├── voice_agent.py       # VoiceAgent with latency masking
│   ├── turn_taking.py       # TurnManager with Iron Ear
│   ├── identity_manager.py  # Speaker verification (Resemblyzer)
│   └── latency_manager.py   # LatencyMasker for fillers
├── web/                     # Next.js frontend
├── mobile/                  # React Native app
├── docs/                    # Documentation
└── Dockerfile               # Railway deployment
```

## Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `LIVEKIT_URL` | Both | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | Both | LiveKit authentication |
| `LIVEKIT_API_SECRET` | Both | LiveKit authentication |
| `DEEPGRAM_API_KEY` | Worker | STT service |
| `CARTESIA_API_KEY` | Worker | TTS service |
| `GROQ_API_KEY` | Worker | LLM (Groq Llama) |
| `FAST_BRAIN_URL` | Worker | Modal-deployed Fast Brain |
| `SERVICE_TYPE` | Both | `web` or `worker` (Railway) |

## Deployment

### Railway

```bash
# Web service: SERVICE_TYPE=web
# Worker service: SERVICE_TYPE=worker
# IMPORTANT: Clear Custom Start Command in Railway settings
```

### Local Development

```bash
# Terminal 1: Web
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Worker
python backend/livekit_worker.py start
```

## Dependencies

Key packages (see `requirements.txt` for full list):
- `livekit-agents==1.3.8` - Voice agent SDK
- `resemblyzer>=0.1.3` - Speaker embeddings
- `fastapi>=0.115.0` - Web framework
- `anthropic>=0.39.0` - Claude LLM
- `groq>=0.11.0` - Groq LPU

## Documentation

- `CLAUDE.md` - AI development instructions
- `docs/ARCHITECTURE_GUIDE.md` - System architecture
- `docs/DEPLOYMENT.md` - Deployment guide
- `docs/visuals/` - Visual documentation

## Session Updates (December 31, 2025)

### Added
- Iron Ear V2: Speaker Locking (Cocktail Party Fix)
- Iron Ear V3: Identity Lock with Resemblyzer ML embeddings
- Honey pot prompts for natural voice enrollment
- Soft fail prompts for noisy environments

### Fixed
- Supabase client access (`get_supabase().client.client` → `.client`)
- LiveKit connection state check (int vs enum)
- VoiceCallWrapper defaulting to LiveKit mode
- Turn detector model download in Dockerfile

---

**Last Updated**: December 31, 2025
