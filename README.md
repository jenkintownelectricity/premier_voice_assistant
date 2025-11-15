# Premier Voice Assistant

Production-ready voice AI phone receptionist system for Jenkintown Electricity, built with open-source models and serverless infrastructure.

## Target Cost: <$0.005/minute

## Tech Stack
- **STT**: Whisper (faster-whisper on Modal)
- **TTS**: Coqui XTTS-v2 (voice cloning on Modal)
- **LLM**: Claude API with aggressive caching
- **Framework**: Pipecat for voice orchestration
- **Telephony**: VoIP.ms SIP trunk

## Quick Start

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure secrets**:
```bash
cp config/secrets.example.py config/secrets.py
# Edit config/secrets.py with your API keys
```

3. **Deploy to Modal**:
```bash
modal deploy modal_deployment/whisper_stt.py
modal deploy modal_deployment/coqui_tts.py
```

4. **Run locally**:
```bash
python main.py
```

## Project Structure
```
premier_voice_assistant/
├── main.py                      # Flask app orchestrator
├── modal_deployment/            # Modal serverless functions
│   ├── whisper_stt.py          # Whisper STT endpoint
│   ├── coqui_tts.py            # Coqui TTS with voice cloning
│   └── voice_cloner.py         # Voice model training
├── agent/                       # Voice agent logic
├── telephony/                   # SIP & WebRTC handlers
├── knowledge/                   # Business logic & prompts
├── voices/                      # Voice samples & cache
└── config/                      # Configuration
```

## Development Phases

### Phase 1: Core Voice Pipeline (Current)
- [x] Modal environment setup
- [ ] Whisper STT deployment
- [ ] Coqui TTS deployment
- [ ] Basic integration test

### Phase 2: Pipecat Integration
- [ ] Real-time voice agent
- [ ] Context management
- [ ] Response caching

### Phase 3: Telephony
- [ ] VoIP.ms SIP integration
- [ ] Call routing
- [ ] Emergency detection

### Phase 4: Business Logic
- [ ] Scheduling system
- [ ] Knowledge base
- [ ] Cost optimization

## License
Proprietary - BuildingSystems.ai
