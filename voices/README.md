# Voice Samples

This directory contains voice samples for cloning with Coqui XTTS-v2. Custom voice cloning is a premium feature available on Starter plan and above.

## 🎤 Recording Guidelines

For best voice cloning results:

### Audio Quality
- **Duration**: 6-30 seconds (10-15 seconds is ideal)
- **Format**: WAV or MP3 (will be converted to WAV 22050Hz mono)
- **Quality**: Clear audio, minimal background noise
- **Mic**: Any decent microphone works (phone mic is fine)

### Content
- **Speech**: Natural, conversational tone
- **Variation**: Include varied intonation and pacing
- **Content**: Read a short paragraph or natural speech
  - ✓ Good: "Hi, thanks for calling Jenkintown Electricity. How can I help you today? We offer a full range of electrical services..."
  - ✗ Avoid: "Testing one two three" or monotone reading

### Recording Methods

**Option 1: Phone Voice Recorder**
1. Use your phone's voice recorder app
2. Record in a quiet room
3. Hold phone at normal speaking distance
4. Speak naturally, as if talking to someone
5. Export and transfer to this folder

**Option 2: Computer/Audacity**
1. Download Audacity (free)
2. Set to 22050Hz, mono
3. Record your sample
4. Export as WAV
5. Save to this folder

**Option 3: Online Recorder**
- Use online-voice-recorder.com
- Record, download as WAV
- Save here

## 🎯 Required Voices

### Fabio (Primary Receptionist)
- File: `fabio_sample.wav`
- Tone: Professional, friendly, clear
- Use case: Main receptionist voice

### Jake (Secondary)
- File: `jake_sample.wav`
- Tone: [TBD based on use case]
- Use case: Alternative voice for specific scenarios

## 🔐 Subscription Requirements

Voice cloning is a **premium feature**:

| Plan | Custom Voices | Limit |
|------|---------------|-------|
| Free | ❌ Not available | 0 |
| Starter | ✅ Available | 2 clones |
| Pro | ✅ Available | Unlimited |
| Enterprise | ✅ Available | Unlimited |

### Free Plan Users

If you're on the Free plan, you can:
- ✅ Use pre-existing public voices (e.g., Fabio, Jake)
- ❌ Cannot create custom voices

To create custom voices, upgrade to Starter ($99/mo) or higher.

## 🚀 Cloning Voices

### Using API Endpoint

```bash
# Clone a voice via API
curl -X POST http://localhost:8000/clone-voice \
  -H "X-User-ID: your-user-id" \
  -F "voice_name=fabio" \
  -F "display_name=Fabio - Professional" \
  -F "audio=@voices/fabio_sample.wav" \
  -F "is_public=false"

# Response (if successful):
{
  "success": true,
  "voice_clone": {
    "id": "...",
    "voice_name": "fabio",
    "display_name": "Fabio - Professional",
    "sample_duration": 12.5
  }
}

# Response (if limit reached):
{
  "detail": "Voice clone limit reached. You have 2 of 2 custom voices. Upgrade to Pro for unlimited."
}

# Response (if Free plan):
{
  "detail": "Custom voices not available on your plan. Upgrade to Starter or higher."
}
```

### Using Modal CLI (Development)

```bash
# Clone Fabio's voice directly
modal run modal_deployment/voice_cloner.py --voice-name fabio --audio-path voices/fabio_sample.wav

# Clone Jake's voice
modal run modal_deployment/voice_cloner.py --voice-name jake --audio-path voices/jake_sample.wav

# List available voices
modal run modal_deployment/voice_cloner.py::list_voices
```

## 📊 Voice Clone Management

### List Your Voice Clones

```bash
curl http://localhost:8000/voice-clones \
  -H "X-User-ID: your-user-id"
```

Response:
```json
{
  "voice_clones": [
    {
      "id": "...",
      "voice_name": "fabio",
      "display_name": "Fabio - Professional",
      "is_public": false,
      "created_at": "2025-11-18T10:30:00Z"
    },
    {
      "id": "...",
      "voice_name": "custom_voice",
      "display_name": "My Custom Voice",
      "is_public": false,
      "created_at": "2025-11-18T11:45:00Z"
    }
  ]
}
```

### Check Your Voice Clone Limit

```bash
curl http://localhost:8000/feature-limits \
  -H "X-User-ID: your-user-id"
```

Response:
```json
{
  "plan": "starter",
  "features": {
    "max_voice_clones": {
      "current": 1,
      "limit": 2,
      "remaining": 1
    }
  },
  "capabilities": {
    "custom_voices": true
  }
}
```

## 🎨 Using Custom Voices

Once you've cloned a voice, use it in conversations:

```bash
# Use custom voice in chat
curl -X POST http://localhost:8000/chat \
  -H "X-User-ID: your-user-id" \
  -F "audio=@test.wav" \
  -F "voice=fabio"  # Use your cloned voice
```

Or set as default in user preferences:

```bash
curl -X PATCH http://localhost:8000/profile \
  -H "X-User-ID: your-user-id" \
  -H "Content-Type: application/json" \
  -d '{"preferred_voice": "fabio"}'
```

## 💡 Best Practices

### Voice Recording Tips

1. **Consistent Environment**
   - Record all samples in same location
   - Use same microphone/device
   - Minimize background noise

2. **Natural Speech**
   - Don't read robotically
   - Use natural pauses and intonation
   - Speak at normal conversational pace

3. **Sample Length**
   - Too short (<6s): May not capture voice characteristics
   - Too long (>30s): Diminishing returns, slower processing
   - Sweet spot: 10-15 seconds

4. **Content Variety**
   - Include questions and statements
   - Vary pitch and pace naturally
   - Use complete sentences

### Naming Conventions

- **voice_name**: lowercase, underscores, no spaces (e.g., `fabio_professional`)
- **display_name**: User-friendly name (e.g., "Fabio - Professional Receptionist")

### Storage & Organization

```
voices/
├── fabio_sample.wav           # Primary voice sample
├── jake_sample.wav            # Secondary voice sample
├── custom_voice_1.wav         # Additional samples
├── custom_voice_2.wav
└── cached_responses/          # Auto-generated cached audio
    ├── greeting.wav
    ├── thank_you.wav
    └── confirmation.wav
```

## 🧪 Testing Voice Clones

### Test Quality

```bash
# Generate test audio with your cloned voice
curl -X POST http://localhost:8000/speak \
  -H "X-User-ID: your-user-id" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is a test of my cloned voice. How does it sound?",
    "voice": "fabio"
  }' \
  --output test_output.wav

# Play the output
play test_output.wav  # Linux/Mac
# or open test_output.wav  # Opens in default player
```

### Compare Voices

Try different text samples to evaluate:
- Clarity and naturalness
- Emotion and tone
- Pronunciation accuracy
- Speed and pacing

If quality is poor:
1. Re-record with better audio quality
2. Try longer sample (15-20 seconds)
3. Ensure varied intonation in sample

## 📈 Upgrade for More Voices

### Starter Plan ($99/mo)
- 2 custom voices
- Perfect for small businesses
- Example: Primary + backup voice

### Pro Plan ($299/mo)
- **Unlimited** custom voices
- Great for agencies
- Multiple personalities/styles
- A/B testing different voices

### Upgrade

```bash
# Contact admin to upgrade
# Or use admin endpoint (requires admin key):
curl -X POST http://localhost:8000/admin/upgrade-user \
  -H "X-Admin-Key: admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "target_user_id": "your-user-id",
    "plan_name": "pro"
  }'
```

## 💾 Cached Responses

The `cached_responses/` subdirectory stores pre-rendered common phrases to reduce TTS costs and latency:

- Greetings ("Hello", "Good morning")
- Confirmations ("Got it", "Understood")
- Thank you messages
- Common questions

These are generated automatically by the caching system when frequently used phrases are detected.

**Benefits:**
- ⚡ Instant response (<50ms vs ~300ms for TTS)
- 💰 Reduces TTS API costs
- 🔊 Consistent quality for common phrases

## 🔧 Technical Details

### Audio Specifications

Coqui XTTS-v2 requirements:
- **Sample Rate**: 22050 Hz (auto-converted if different)
- **Channels**: Mono (auto-converted if stereo)
- **Format**: WAV (auto-converted from MP3/other)
- **Bit Depth**: 16-bit PCM

### Processing Pipeline

```
Your Recording
    ↓
Format Conversion (if needed)
    ↓
Upload to Supabase Storage
    ↓
Clone on Modal (Coqui XTTS-v2)
    ↓
Save metadata to database
    ↓
Voice ready for use!
```

### Storage Locations

- **Supabase Storage**: `va-voice-clones/{user_id}/{voice_name}.wav`
- **Modal**: Voice model stored in Modal volume
- **Database**: Metadata in `va_voice_clones` table

## 🐛 Troubleshooting

### "Custom voices not available on your plan"
- You're on Free plan
- Upgrade to Starter or higher
- Check your plan: `GET /subscription`

### "Voice clone limit reached"
- You've hit your plan's voice limit
- Starter: 2 voices max
- Upgrade to Pro for unlimited
- Or delete unused voices

### "Poor voice quality"
- Re-record with better audio quality
- Increase sample length (aim for 15s)
- Reduce background noise
- Speak more naturally with varied intonation

### "Voice not found"
- Check spelling of `voice_name`
- List your voices: `GET /voice-clones`
- Ensure voice cloning completed successfully

## 📚 Additional Resources

- **[Coqui XTTS-v2 Docs](https://docs.coqui.ai/en/latest/models/xtts.html)** - Official documentation
- **[Feature Gates Guide](../FEATURE_GATES_IMPLEMENTATION.md)** - Subscription limits
- **[API Docs](../README.md#api-endpoints)** - Complete API reference

---

**Note**: Voice cloning requires Starter plan or higher. Free plan users can use pre-existing public voices only.

**Last Updated**: 2025-11-18
