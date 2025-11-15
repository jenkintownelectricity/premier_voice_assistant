# Voice Samples

This directory contains voice samples for cloning with Coqui XTTS-v2.

## Recording Guidelines

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

## Required Voices

### Fabio (Primary Receptionist)
- File: `fabio_sample.wav`
- Tone: Professional, friendly, clear
- Use case: Main receptionist voice

### Jake (Secondary)
- File: `jake_sample.wav`
- Tone: [TBD based on use case]
- Use case: Alternative voice for specific scenarios

## Cloning Voices

Once you have your voice samples:

```bash
# Clone Fabio's voice
modal run modal_deployment/voice_cloner.py --voice-name fabio --audio-path voices/fabio_sample.wav

# Clone Jake's voice
modal run modal_deployment/voice_cloner.py --voice-name jake --audio-path voices/jake_sample.wav

# List available voices
modal run modal_deployment/voice_cloner.py::list_voices
```

## Cached Responses

The `cached_responses/` subdirectory stores pre-rendered common phrases to reduce TTS costs:
- Greetings
- Confirmations
- Thank you messages
- Common questions

These are generated automatically by the caching system.
