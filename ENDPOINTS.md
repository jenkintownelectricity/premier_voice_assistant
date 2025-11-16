# Modal Web Endpoints - Premier Voice Assistant

## Your Workspace
**`jenkintownelectricity`** (workspace: main)

## Endpoint URLs (After Deployment)

### 1. Speech-to-Text (Whisper)
```
https://jenkintownelectricity--premier-whisper-stt-transcribe-web.modal.run
```

**Method**: POST
**Input**:
- `audio_bytes` (File): Audio file (WAV, MP3, etc.)
- `language` (Form): Language code (default: "en")

**Output** (JSON):
```json
{
  "text": "transcribed text here",
  "language": "en",
  "duration": 2.5,
  "segments": [...],
  "processing_time": 0.234
}
```

**Example**:
```bash
curl -X POST \
  -F "audio_bytes=@test.wav" \
  -F "language=en" \
  https://jenkintownelectricity--premier-whisper-stt-transcribe-web.modal.run
```

---

### 2. Text-to-Speech (Coqui TTS)
```
https://jenkintownelectricity--premier-coqui-tts-synthesize-web.modal.run
```

**Method**: POST
**Input**:
- `text` (Form): Text to synthesize
- `voice_name` (Form): Voice to use (default: "fabio")
- `language` (Form): Language code (default: "en")

**Output**: WAV audio file (audio/wav)

**Example**:
```bash
curl -X POST \
  -F "text=Hello, how are you today?" \
  -F "voice_name=fabio" \
  -F "language=en" \
  https://jenkintownelectricity--premier-coqui-tts-synthesize-web.modal.run \
  --output response.wav
```

---

### 3. Voice Cloning
```
https://jenkintownelectricity--premier-coqui-tts-clone-voice-web.modal.run
```

**Method**: POST
**Input**:
- `voice_name` (Form): Name for the cloned voice
- `reference_audio` (File): WAV audio sample (6-30 seconds)

**Output** (JSON):
```json
{
  "voice_name": "my_voice",
  "status": "success",
  "duration": 12.5,
  "processing_time": 1.234
}
```

**Example**:
```bash
curl -X POST \
  -F "voice_name=my_voice" \
  -F "reference_audio=@voice_sample.wav" \
  https://jenkintownelectricity--premier-coqui-tts-clone-voice-web.modal.run
```

---

## How to Deploy

### Option 1: Quick Script (Easiest)
```bash
./QUICK_DEPLOY.sh
```

### Option 2: Manual Commands
```bash
# Authenticate
modal token set --token-id ak-jt7FZ9TvShs4gLDth2QK0d --token-secret as-ds98ZNXm5fibjXkOvz0hvs

# Deploy
modal deploy modal_deployment/whisper_stt.py
modal deploy modal_deployment/coqui_tts.py
```

### Option 3: Auto-Deploy Script
```bash
./deploy_modal_endpoints.sh
```

---

## Verify Deployment

```bash
# List all apps
modal app list

# Show app details (includes endpoint URLs)
modal app show premier-whisper-stt
modal app show premier-coqui-tts

# Test endpoints
./test_modal_endpoints.sh
```

---

## Monitor

```bash
# View logs in real-time
modal app logs premier-whisper-stt --follow
modal app logs premier-coqui-tts --follow

# Check status
modal app list

# View volumes
modal volume list
```

---

## Use in Your FastAPI Backend

Add to your `.env`:
```bash
# Modal endpoints (after deployment)
WHISPER_STT_URL=https://jenkintownelectricity--premier-whisper-stt-transcribe-web.modal.run
COQUI_TTS_URL=https://jenkintownelectricity--premier-coqui-tts-synthesize-web.modal.run
VOICE_CLONE_URL=https://jenkintownelectricity--premier-coqui-tts-clone-voice-web.modal.run
```

Or use the Modal SDK directly (current approach in `backend/main.py`):
```python
from modal_deployment.whisper_stt import WhisperSTT
from modal_deployment.coqui_tts import CoquiTTS

stt = WhisperSTT()
result = stt.transcribe.remote(audio_bytes)
```

---

## Important Notes

1. **First deployment takes 5-10 minutes** (downloading AI models)
2. **Subsequent deployments take 30-60 seconds**
3. **Endpoints are HTTPS** - accessible from anywhere
4. **GPU costs**: Only charged when processing (~$0.60/hour for T4)
5. **Cold starts**: ~10 seconds (first request after idle)
6. **Warm containers**: Kept alive for 5 minutes (300s)

---

## Costs Estimate

- Free tier: $30/month credit
- Typical usage (100 conversations/day): ~$3/month
- Each request: <$0.01
- Idle time: Free

---

## Troubleshooting

### Endpoint returns 404
- Not deployed yet - run deployment
- Check: `modal app list`

### Endpoint returns 422
- Good! Endpoint exists, needs valid data
- Check input format above

### Slow first request
- Cold start (loading model) - normal
- Second request will be fast (<500ms)

### Models not found
- Wait for deployment to complete
- Check logs: `modal app logs premier-whisper-stt`

---

**All code is ready to deploy! Just run QUICK_DEPLOY.sh on your local machine.**
