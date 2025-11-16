# Modal Setup Guide - Getting Your Web Endpoints

## Current Status
✅ Modal CLI installed (v1.2.2)
⚠️ **Not authenticated yet** - Need to set up tokens

## Your Modal Apps Structure

You have **2 Modal apps** with **3 web endpoints**:

### 1. `premier-whisper-stt` (Speech-to-Text)
- **Class**: `WhisperSTT` - For programmatic use via `.remote()`
- **Web Endpoint**: `transcribe_web()` - HTTP endpoint
  - URL pattern: `https://[workspace]--premier-whisper-stt-transcribe-web.modal.run`
  - Method: POST
  - Input: `audio_bytes` (file), `language` (form)
  - Output: JSON with transcription

### 2. `premier-coqui-tts` (Text-to-Speech)
- **Class**: `CoquiTTS` - For programmatic use via `.remote()`
- **Web Endpoint 1**: `synthesize_web()` - HTTP endpoint for TTS
  - URL pattern: `https://[workspace]--premier-coqui-tts-synthesize-web.modal.run`
  - Method: POST
  - Input: `text`, `voice_name`, `language` (form data)
  - Output: WAV audio file

- **Web Endpoint 2**: `clone_voice_web()` - HTTP endpoint for voice cloning
  - URL pattern: `https://[workspace]--premier-coqui-tts-clone-voice-web.modal.run`
  - Method: POST
  - Input: `voice_name` (form), `reference_audio` (file)
  - Output: JSON with clone status

---

## Authentication Options

### Option A: Interactive Browser Auth (Easiest)

```bash
modal token new
```

This will:
1. Open your browser
2. Log you into Modal
3. Automatically save credentials
4. Show you your workspace name

### Option B: Manual Token Setup (For CI/CD or non-interactive)

1. **Get your tokens**:
   - Go to: https://modal.com/settings
   - Click "Create new token" or copy existing token
   - Save your `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`

2. **Set tokens**:
   ```bash
   modal token set \
     --token-id ak-XXXXXX \
     --token-secret as-YYYYYY
   ```

3. **Verify**:
   ```bash
   modal profile list
   ```

---

## Deployment

Once authenticated, run:

```bash
./deploy_modal_endpoints.sh
```

OR manually:

```bash
# Deploy Whisper STT
modal deploy modal_deployment/whisper_stt.py

# Deploy Coqui TTS
modal deploy modal_deployment/coqui_tts.py
```

**First deployment takes ~5-10 minutes** (downloading models)
**Subsequent deployments take ~30-60 seconds**

---

## After Deployment

### 1. Find Your Endpoints

Run:
```bash
modal app list
```

This shows all deployed apps.

To see specific endpoint URLs:
```bash
modal app show premier-whisper-stt
modal app show premier-coqui-tts
```

### 2. Test Endpoints

**Test STT:**
```bash
curl -X POST \
  -F "audio_bytes=@test_audio.wav" \
  -F "language=en" \
  https://[workspace]--premier-whisper-stt-transcribe-web.modal.run
```

**Test TTS:**
```bash
curl -X POST \
  -F "text=Hello world" \
  -F "voice_name=fabio" \
  -F "language=en" \
  https://[workspace]--premier-coqui-tts-synthesize-web.modal.run \
  --output response.wav
```

### 3. Monitor Logs

```bash
# Stream live logs
modal app logs premier-whisper-stt --follow

# View recent logs
modal app logs premier-coqui-tts
```

---

## Why Endpoints Might Not Show

If you deployed but don't see web endpoints:

### Issue 1: Deployment didn't include web endpoints
**Cause**: Used `modal run` instead of `modal deploy`
**Fix**: Use `modal deploy` (not `modal run`)

### Issue 2: Not looking in the right place
**Check**:
```bash
# List all deployments
modal app list

# Show specific app details
modal app show premier-whisper-stt
```

### Issue 3: Old Modal SDK version
**Check**: `modal --version` (should be >= 1.0)
**Fix**: `pip install --upgrade modal`

### Issue 4: Web endpoint decorator issue
**Our code uses**: `@modal.asgi_app()` ✅ (Correct for Modal 1.0+)
**Old code used**: `@modal.web_endpoint()` ❌ (Deprecated)

---

## Environment Variables for Backend

Once deployed, your FastAPI backend needs these env vars:

```bash
# For calling Modal from Python
MODAL_TOKEN_ID=ak-XXXXXX
MODAL_TOKEN_SECRET=as-YYYYYY
```

Add to `.env`:
```bash
cp .env.example .env
# Then edit .env and add your Modal tokens
```

---

## Estimated Costs

- **Free tier**: $30/month credit
- **GPU usage**: ~$0.60/hour for T4 GPU
- **Web endpoints**: Free (pay only when called)
- **Cold starts**: ~10 seconds (models cached after first run)
- **Warm containers**: ~100-300ms latency

**Typical usage** (100 voice conversations/day):
- ~10 minutes GPU time/day
- ~$0.10/day = **~$3/month**

---

## Quick Reference

```bash
# Check auth status
modal profile list

# Deploy both services
modal deploy modal_deployment/whisper_stt.py
modal deploy modal_deployment/coqui_tts.py

# List deployed apps
modal app list

# View app details (includes URLs)
modal app show premier-whisper-stt

# Stream logs
modal app logs premier-whisper-stt --follow

# Stop app (to save costs)
modal app stop premier-whisper-stt

# View volumes
modal volume list

# Delete app
modal app delete premier-whisper-stt
```

---

## Need Help?

1. **Modal Docs**: https://modal.com/docs
2. **Modal Discord**: https://modal.com/discord
3. **This repo**: Check `DEPLOYMENT.md` for full setup

Your code is ready to deploy! Just need to authenticate Modal and run the deployment script.
