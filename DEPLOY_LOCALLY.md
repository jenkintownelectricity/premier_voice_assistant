# Deploy Modal Services from Your Local Machine

Since the Modal CLI can't connect from this environment, deploy from your local machine instead.

## Quick Setup (5 minutes)

### 1. Clone the repository (if not already)
```bash
git clone https://github.com/jenkintownelectricity/premier_voice_assistant.git
cd premier_voice_assistant
git checkout claude/review-all-branches-015Lqsv5sYDL6WyHYGpzF9JN
```

### 2. Install Modal CLI
```bash
pip install modal
```

### 3. Authenticate Modal
```bash
modal token set --token-id ak-jt7FZ9TvShs4gLDth2QK0d --token-secret as-ds98ZNXm5fibjXkOvz0hvs
```

Verify:
```bash
modal profile list
```

You should see your workspace name.

### 4. Deploy Both Services
```bash
# Deploy Whisper STT (creates transcription endpoint)
modal deploy modal_deployment/whisper_stt.py

# Deploy Coqui TTS (creates synthesis + cloning endpoints)
modal deploy modal_deployment/coqui_tts.py
```

**First deployment takes ~5-10 minutes** (downloading AI models)
**Subsequent deployments take ~30-60 seconds**

### 5. Get Your Endpoint URLs

After deployment completes, run:
```bash
modal app list
```

This shows all deployed apps. Then:
```bash
modal app show premier-whisper-stt
modal app show premier-coqui-tts
```

This will display the web endpoint URLs like:
- `https://[workspace]--premier-whisper-stt-transcribe-web.modal.run`
- `https://[workspace]--premier-coqui-tts-synthesize-web.modal.run`
- `https://[workspace]--premier-coqui-tts-clone-voice-web.modal.run`

---

## Option 2: Use the Helper Script

Or simply run the deployment script we created:
```bash
./deploy_modal_endpoints.sh
```

This will deploy both services and show you the endpoint URLs.

---

## Verify Endpoints Are Working

Test the endpoints:
```bash
./test_modal_endpoints.sh
```

Or manually:
```bash
# Get your workspace name
WORKSPACE=$(modal profile list | grep "│" | awk '{print $5}' | head -1)

# Test STT endpoint (should return 422 = endpoint exists, needs valid data)
curl -X POST https://$WORKSPACE--premier-whisper-stt-transcribe-web.modal.run

# Test TTS endpoint
curl -X POST https://$WORKSPACE--premier-coqui-tts-synthesize-web.modal.run

# Test clone endpoint
curl -X POST https://$WORKSPACE--premier-coqui-tts-clone-voice-web.modal.run
```

If you get `422` status codes, that's good! It means the endpoints exist and are waiting for proper data.

---

## What Gets Deployed

### Whisper STT Service (`premier-whisper-stt`)
- **Endpoint**: `transcribe_web()` - POST endpoint for audio transcription
- **Model**: Faster-Whisper base.en (downloaded during build)
- **GPU**: T4 (cost-effective)
- **Input**: audio file + language code
- **Output**: JSON with transcription text

### Coqui TTS Service (`premier-coqui-tts`)
- **Endpoint 1**: `synthesize_web()` - POST endpoint for text-to-speech
  - Input: text + voice_name + language
  - Output: WAV audio file

- **Endpoint 2**: `clone_voice_web()` - POST endpoint for voice cloning
  - Input: voice_name + reference audio file
  - Output: JSON with clone status

- **Volume**: `premier-voice-models` - Persistent storage for cloned voices

---

## Monitoring & Logs

### View live logs:
```bash
modal app logs premier-whisper-stt --follow
modal app logs premier-coqui-tts --follow
```

### Check app status:
```bash
modal app list
```

### View volumes:
```bash
modal volume list
```

---

## Troubleshooting

### "Could not connect to Modal server"
- Check your internet connection
- Verify tokens: `modal profile list`
- Try: `modal token new` for browser-based auth

### "App not found"
- Make sure deployment completed successfully
- Check: `modal app list`

### "Endpoint returns 404"
- Redeploy: `modal deploy modal_deployment/whisper_stt.py`
- Check logs: `modal app logs premier-whisper-stt`

### Models downloading slowly
- First deployment downloads ~2GB of AI models
- Be patient - subsequent deployments are much faster

---

## Next Steps After Deployment

1. **Copy the endpoint URLs** - You'll need these for your FastAPI backend

2. **Test with real audio**:
   ```bash
   # Create test audio file
   echo "Testing speech recognition" | say -o test.aiff
   ffmpeg -i test.aiff -ar 16000 test.wav

   # Test STT
   curl -X POST -F "audio_bytes=@test.wav" \
     https://[workspace]--premier-whisper-stt-transcribe-web.modal.run
   ```

3. **Update your .env file** with the endpoint URLs if needed

4. **Monitor costs** at https://modal.com/billing

---

## Estimated Costs

- **Free tier**: $30/month credit
- **T4 GPU**: ~$0.60/hour (only when actually processing)
- **Cold starts**: Free (just slower ~10s)
- **Typical usage** (100 voice conversations/day): ~$3/month

Your endpoints stay live 24/7 but only charge when actually processing requests!

---

Your code is ready to deploy - just run it from your local machine! 🚀
