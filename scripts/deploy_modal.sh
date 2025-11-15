#!/bin/bash
# Deploy all Modal services

set -e  # Exit on error

echo "=========================================="
echo "Deploying Premier Voice Assistant to Modal"
echo "=========================================="
echo

# Check if modal is installed
if ! command -v modal &> /dev/null; then
    echo "Error: Modal CLI not found"
    echo "Install with: pip install modal"
    exit 1
fi

# Check if authenticated
if ! modal token verify &> /dev/null; then
    echo "Error: Not authenticated with Modal"
    echo "Run: modal setup"
    exit 1
fi

echo "✓ Modal CLI ready"
echo

# Deploy Whisper STT
echo "Deploying Whisper STT..."
modal deploy modal_deployment/whisper_stt.py
echo "✓ Whisper STT deployed"
echo

# Deploy Coqui TTS
echo "Deploying Coqui TTS..."
modal deploy modal_deployment/coqui_tts.py
echo "✓ Coqui TTS deployed"
echo

echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "1. Clone voices: modal run modal_deployment/voice_cloner.py --voice-name fabio --audio-path voices/fabio_sample.wav"
echo "2. Test deployment: python tests/test_modal_stt.py"
echo "3. Start Flask app: python main.py"
echo
