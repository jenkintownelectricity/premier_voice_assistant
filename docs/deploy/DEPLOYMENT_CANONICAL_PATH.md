# Deployment Canonical Path

## Canonical: Dockerfile + Railway

The canonical deployment path is:

1. **Build:** `Dockerfile` (python:3.11-slim, system deps, pip install, ONNX model download)
2. **Route:** `start.sh` checks `SERVICE_TYPE` env var
3. **Web:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. **Worker:** `python backend/livekit_worker.py start`
5. **Platform:** Railway with `railway.toml` (restart on failure, max 3 retries)
6. **Custom Start Command:** MUST BE EMPTY in Railway UI

## Auxiliary: Modal for STT/TTS

Modal services are auxiliary -- they provide alternative STT/TTS backends. The primary voice runtime runs on Railway.

| Service | Module | Deploy Command |
|---------|--------|----------------|
| Whisper STT | `modal_deployment/whisper_stt.py` | `modal deploy` |
| Coqui TTS | `modal_deployment/coqui_tts.py` | `modal deploy` |
| Kokoro TTS | `modal_deployment/kokoro_tts.py` | `modal deploy` |
| Voice Cloner | `modal_deployment/voice_cloner.py` | `modal deploy` |

## Non-Canonical Paths (Legacy)

| Path | Status | Notes |
|------|--------|-------|
| `Procfile` | Legacy | Overridden by Dockerfile CMD |
| `nixpacks.toml` | Legacy | Superseded by Dockerfile |
| `runtime.txt` | Legacy | Python version for Nixpacks |

## Verification

After deployment, run `scripts/deploy_verify.py` to validate all services.
