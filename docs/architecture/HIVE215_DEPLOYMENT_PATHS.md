# HIVE215 Deployment Paths

## Primary Path: Railway via Dockerfile

### Build
- **Dockerfile:** `python:3.11-slim` base
- **System deps:** build-essential, gcc (webrtcvad compilation), ffmpeg, libopus0 (audio processing)
- **Python deps:** `requirements.txt` + `livekit-agents[deepgram,cartesia,openai,silero]==1.3.8`
- **Build step:** Downloads turn detector ONNX model (`python backend/livekit_agent.py download-files`)
- **CMD:** `bash start.sh`

### Routing
`start.sh` checks `SERVICE_TYPE` environment variable:
- `SERVICE_TYPE=worker` -> `python backend/livekit_worker.py start`
- Anything else (including unset) -> `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

### Railway Configuration
- `railway.toml`: Restart on failure, max 3 retries
- Custom Start Command in Railway UI: **MUST BE EMPTY** (Dockerfile CMD handles routing)
- Each service sets `SERVICE_TYPE` in Railway environment variables

### Services
| Service | SERVICE_TYPE | PORT | Purpose |
|---------|-------------|------|---------|
| Web | `web` | Railway-assigned | FastAPI REST/WebSocket server |
| Worker | `worker` | N/A | LiveKit voice agent |

## Auxiliary Path: Modal for STT/TTS

### Modal Services
| Module | Service | Purpose |
|--------|---------|---------|
| `modal_deployment/whisper_stt.py` | Whisper STT | Speech-to-text (alternative to Deepgram) |
| `modal_deployment/coqui_tts.py` | Coqui TTS | Text-to-speech (alternative to Cartesia) |
| `modal_deployment/kokoro_tts.py` | Kokoro TTS | Text-to-speech (alternative) |
| `modal_deployment/voice_cloner.py` | Voice Cloner | Voice cloning service |

### Modal Deployment Scripts
- `QUICK_DEPLOY.sh` -- Quick deployment of Modal services
- `deploy_modal.sh` -- Full Modal deployment
- `deploy_modal_endpoints.sh` -- Deploy specific endpoints
- `test_modal_endpoints.sh` -- Test deployed endpoints

### Fast Brain (Modal)
Deployed separately from `D:\APP_CENTRAL\fast_brain` (not in this repo).
- Groq LPU for System 1 (~80ms)
- Claude for System 2 (~2000ms)
- Skills management
- Accessed via `FAST_BRAIN_URL` environment variable

## Legacy/Alternative Paths

| Path | File | Status | Notes |
|------|------|--------|-------|
| Procfile | `Procfile` | Available | Railway alternative, overridden by Dockerfile |
| Nixpacks | `nixpacks.toml` | Legacy | Superseded by Dockerfile |
| Runtime | `runtime.txt` | Legacy | Python version specification for Nixpacks |

## Deployment Verification

After deployment, verify:
1. Web service responds to `GET /health` with 200
2. Worker connects to LiveKit Cloud (check LiveKit dashboard)
3. STT (Deepgram) processes test audio
4. TTS (Cartesia) synthesizes test text
5. Fast Brain responds to health check
