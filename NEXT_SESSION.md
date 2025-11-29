# HIVE215 - Next Session Instructions

**Last Updated:** November 29, 2025
**Previous Session:** Implemented Lightning Stack Phase 1 (Sub-150ms Voice AI)

---

## What Was Completed (Phase 1: Lightning Stack)

### New Files Created
```
backend/
├── groq_client.py        # Groq LPU streaming LLM (40ms TTFT)
├── cartesia_client.py    # Cartesia Sonic-3 TTS (42 languages, voice cloning)
├── deepgram_client.py    # Deepgram Nova-3 STT (36+ languages)
├── sentence_detector.py  # Real-time sentence boundary detection
└── lightning_pipeline.py # Unified orchestrator
```

### API Endpoints Added to main.py
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/lightning/status` | GET | Pipeline status & config |
| `/lightning/languages` | GET | Supported languages |
| `/lightning/chat` | POST | Fast LLM chat (Groq) |
| `/lightning/tts` | POST | Ultra-fast TTS (Cartesia) |
| `/lightning/voice-clone` | POST | Clone voice from audio |
| `/lightning/localize` | POST | Localize voice to other languages |
| `/ws/lightning/{assistant_id}` | WS | Full voice streaming pipeline |

### Configuration Updated
- `requirements.txt` - Added `groq>=0.11.0`
- `.env.example` - Added Groq, Deepgram, Cartesia settings
- `config/settings.py` - Updated latency targets to 200ms
- `README.md` - Added Lightning Stack documentation

---

## How to Test

### 1. Set API Keys

Get free API keys:
- **Groq**: https://console.groq.com (FREE tier!)
- **Deepgram**: https://console.deepgram.com ($200 free credit)
- **Cartesia**: https://play.cartesia.ai (trial available)

Add to `.env`:
```bash
GROQ_API_KEY=gsk_...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...  # Fallback
```

### 2. Install Dependencies
```bash
pip install groq
```

### 3. Test Lightning Pipeline Directly
```bash
python backend/lightning_pipeline.py
```

### 4. Run Backend
```bash
uvicorn backend.main:app --reload
```

### 5. Test API Endpoints
```bash
# Check status
curl http://localhost:8000/lightning/status

# Test LLM (requires GROQ_API_KEY or ANTHROPIC_API_KEY)
curl -X POST http://localhost:8000/lightning/chat \
  -H "Content-Type: application/json" \
  -H "X-User-ID: test" \
  -d '{"message": "Hello!"}'

# Test TTS (requires CARTESIA_API_KEY)
curl -X POST http://localhost:8000/lightning/tts \
  -H "Content-Type: application/json" \
  -H "X-User-ID: test" \
  -d '{"text": "Hello world!"}'
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  LIGHTNING STACK - Sub-150ms Voice AI                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Audio In                                                   │
│      ↓                                                      │
│  Deepgram Nova-3 (STT)  ─────────────────────> ~30ms       │
│      ↓                                                      │
│  Groq Llama 3.3 70B (LLM) ───────────────────> ~40ms TTFT  │
│      ↓                                                      │
│  Sentence Detector ──────────────────────────> ~0.1ms      │
│      ↓                                                      │
│  Cartesia Sonic-3 (TTS) ─────────────────────> ~30ms TTFB  │
│      ↓                                                      │
│  Audio Out                                                  │
│                                                             │
│  SECRET: TTS starts on FIRST SENTENCE, not full response!  │
│                                                             │
│  Total perceived latency: ~150ms                            │
│  (Human conversation threshold: 500ms)                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app with all endpoints |
| `backend/lightning_pipeline.py` | Main orchestrator |
| `backend/groq_client.py` | Groq LLM with Claude fallback |
| `backend/cartesia_client.py` | TTS + voice cloning |
| `backend/deepgram_client.py` | STT + multi-language |
| `backend/sentence_detector.py` | Sentence boundary detection |
| `.env.example` | All environment variables |
| `config/settings.py` | Configuration settings |

---

## Next Steps (Priority Order)

### Phase 2: Edge Network (Optional)
Add LiveKit or Daily.co for:
- WebRTC (better than WebSocket for audio)
- Global edge POPs (lower latency worldwide)
- VAD/AEC at edge (noise suppression, echo cancellation)

### Phase 3: Bilingual Translation
- Real-time translation with voice cloning
- User A speaks English → User B hears Spanish (in User A's voice!)
- Uses Cartesia Localize for cross-lingual voice

### Phase 4: Global Deployment
- Configure all 42 TTS languages
- Set up regional voices
- Multi-language pricing tiers

### Phase 5: Frontend Integration
- Update web frontend to use `/ws/lightning/{assistant_id}`
- Add latency metrics display
- Add voice cloning UI

---

## Cost Estimates

At 10,000 calls/month (2 min avg):
```
Deepgram STT:  $86/mo
Groq LLM:      $12/mo  (mostly free tier!)
Cartesia TTS:  $120/mo
─────────────────────
Total:         ~$220/mo ($0.022/call)
```

At $99/customer × 100 customers = $9,900 revenue
**Gross margin: ~97%**

---

## Questions for Next Session

1. Do you want to add LiveKit/Daily.co edge network?
2. Should we implement bilingual translation?
3. Any specific languages to prioritize?
4. Do you want to update the web frontend to use `/ws/lightning/`?
