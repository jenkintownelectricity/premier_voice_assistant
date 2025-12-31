# Quick Start Guide - Premier Voice Assistant

Get your voice AI system running in under 10 minutes.

## Prerequisites

- ✅ Modal account (you have this!)
- ✅ Python 3.11+
- ⬜ Anthropic API key (for Claude)
- ⬜ Voice samples (optional for initial testing)

## Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- Modal SDK
- Pipecat AI framework
- Faster-Whisper for STT
- Coqui TTS for voice cloning
- Anthropic SDK for Claude
- Flask for the web API

### 2. Configure API Keys

You mentioned your Modal key is in environment settings. Great! Now add Claude API key:

**Option A: Using secrets.py** (recommended)
```bash
cp config/secrets.example.py config/secrets.py
```

Then edit `config/secrets.py` and add:
```python
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

**Option B: Using environment variables**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

### 3. Verify Modal Authentication

```bash
# Check if Modal is set up
modal token verify

# If not authenticated, run:
# modal setup
```

### 4. Deploy to Modal

Deploy the Whisper STT and Coqui TTS services:

```bash
# Make script executable
chmod +x scripts/deploy_modal.sh

# Deploy
./scripts/deploy_modal.sh
```

Or deploy manually:
```bash
modal deploy modal_deployment/whisper_stt.py
modal deploy modal_deployment/coqui_tts.py
```

### 5. Test Deployments

```bash
# Test STT
python tests/test_modal_stt.py

# Test TTS
python tests/test_modal_tts.py
```

### 6. Clone Voice (Optional but Recommended)

If you have Fabio's voice sample:

```bash
# Put voice sample in voices/ folder
cp /path/to/fabio_voice.wav voices/fabio_sample.wav

# Clone the voice to Modal
modal run modal_deployment/voice_cloner.py --voice-name fabio --audio-path voices/fabio_sample.wav

# Verify it worked
modal run modal_deployment/voice_cloner.py::list_voices
```

**Don't have a voice sample yet?** No problem! See `voices/README.md` for recording instructions, or skip this step and use a test voice initially.

### 7. Run Integration Test

Test the full pipeline (STT → Claude → TTS):

```bash
python scripts/test_integration.py
```

This will:
- Generate test audio
- Transcribe with Whisper
- Get AI response from Claude
- Synthesize speech with Coqui
- Report latency metrics

### 8. Start the Flask API

```bash
python main.py
```

The API will be available at `http://localhost:5000`

### 9. Test the API

**Health check:**
```bash
curl http://localhost:5000/health
```

**Transcribe audio:**
```bash
curl -X POST http://localhost:5000/transcribe \
  -F "audio=@your_audio.wav"
```

**Generate speech:**
```bash
curl -X POST http://localhost:5000/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from Jenkintown Electricity", "voice": "fabio"}' \
  --output response.wav
```

## What You Should See

✅ **Success indicators:**
- `modal deploy` completes without errors
- Test scripts show latency metrics
- Flask app starts on port 5000
- API endpoints respond correctly

⚠️ **Expected warnings:**
- "Voice 'fabio' not found" - if you haven't cloned a voice yet (that's OK!)
- Some deprecation warnings from libraries (safe to ignore)

## Next Steps

Now that Phase 1 is working:

1. **Record & clone voices** (if you haven't)
   - See `voices/README.md` for recording tips
   - Clone both Fabio and Jake

2. **Test with real audio**
   - Record yourself asking a question
   - Test the `/chat` endpoint

3. **Monitor costs**
   - Check Modal dashboard for GPU usage
   - Check Anthropic dashboard for API usage

4. **Move to Phase 2** when ready
   - Pipecat real-time integration
   - Response caching
   - Context management

## Troubleshooting

**"Modal not authenticated"**
- Run `modal setup` and follow prompts

**"ANTHROPIC_API_KEY not found"**
- Add to `config/secrets.py` or export as environment variable

**"Voice not found"**
- Clone a voice first, or skip TTS testing for now

**Import errors**
- Run `pip install -r requirements.txt` again
- Check Python version: `python --version` (should be 3.11+)

**GPU errors on Modal**
- First deployment might take a few minutes to provision
- Check Modal dashboard for deployment status

## Current Architecture

```
┌─────────────┐
│ User Audio  │
└──────┬──────┘
       ↓
┌──────────────────┐
│ Flask API (main) │
└──────┬───────────┘
       ↓
┌──────────────────────────────┐
│  Modal Whisper STT (GPU)     │  ← Transcribe audio
└──────┬───────────────────────┘
       ↓
┌──────────────────────────────┐
│  Claude API (Anthropic)      │  ← Generate response
└──────┬───────────────────────┘
       ↓
┌──────────────────────────────┐
│  Modal Coqui TTS (GPU)       │  ← Synthesize speech
└──────┬───────────────────────┘
       ↓
┌──────────────┐
│ Audio Output │
└──────────────┘
```

## Cost Estimate (Current Setup)

With Phase 1 configuration:
- **Whisper STT**: ~$0.0002/min (Modal GPU)
- **Claude API**: ~$0.003/min (with caching in Phase 2: ~$0.001/min)
- **Coqui TTS**: ~$0.0002/min (Modal GPU)
- **Total**: ~$0.0034/min

Target after Phase 2 optimizations: **<$0.005/min** ✅

## Need Help?

- Check the main `README.md` for full project details
- Review `voices/README.md` for voice cloning help
- Read inline code comments in `main.py` and Modal deployments
- Modal docs: https://modal.com/docs
- Anthropic docs: https://docs.anthropic.com

---

**You're all set for Phase 1!** 🚀

Once you've tested everything and it works, you can move on to:
- Phase 2: Pipecat integration for real-time voice
- Phase 3: VoIP.ms telephony
- Phase 4: Business logic and cost optimization
