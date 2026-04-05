# DEPLOYMENT POSTURE -- HIVE215

**Frozen:** 2026-04-05
**Classification:** Immutable Doctrine

## Primary Deployment Path

**Platform:** Railway
**Mechanism:** Dockerfile + start.sh with SERVICE_TYPE routing

### Web Service
- **SERVICE_TYPE:** `web` (or unset -- defaults to web)
- **Command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Entrypoint:** `backend/main.py`
- **Role:** FastAPI server, REST API, WebSocket, token generation, health checks

### Worker Service
- **SERVICE_TYPE:** `worker`
- **Command:** `python backend/livekit_worker.py start`
- **Entrypoint:** `backend/livekit_worker.py`
- **Role:** LiveKit voice agent, STT/TTS/LLM pipeline, Iron Ear filtering

### Container
- **Base:** `python:3.11-slim`
- **System deps:** build-essential, gcc, ffmpeg, libopus0
- **Python deps:** requirements.txt + livekit-agents[deepgram,cartesia,openai,silero]==1.3.8
- **Build step:** Downloads turn detector ONNX model
- **CMD:** `bash start.sh`

### Railway Configuration
- **railway.toml:** Restart on failure, max 3 retries
- **Custom Start Command:** Must be EMPTY in Railway UI (Dockerfile CMD handles routing)

## Auxiliary Deployment Path

**Platform:** Modal
**Role:** STT/TTS services (not the main runtime)

### Modal Services
- `modal_deployment/whisper_stt.py` -- Whisper STT service
- `modal_deployment/coqui_tts.py` -- Coqui TTS service
- `modal_deployment/kokoro_tts.py` -- Kokoro TTS service
- `modal_deployment/voice_cloner.py` -- Voice cloning service

### Modal Deployment Scripts
- `QUICK_DEPLOY.sh` -- Quick deployment
- `deploy_modal.sh` -- Full deployment
- `deploy_modal_endpoints.sh` -- Endpoint deployment

## Deployment Rules

1. The Dockerfile is the canonical build definition. Nixpacks is legacy.
2. SERVICE_TYPE is the only routing mechanism. No other environment variable changes which service starts.
3. Railway Custom Start Command must be empty. Setting it overrides the Dockerfile CMD.
4. All environment variables must be set before deployment. Missing critical vars should cause startup failure.
5. Modal services are auxiliary. The primary voice runtime runs on Railway.
