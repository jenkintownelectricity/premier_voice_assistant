#!/bin/bash
# =============================================================================
# QUICK DEPLOY - Run this on your LOCAL MACHINE (not in Claude Code)
# =============================================================================

set -e

echo "=========================================="
echo "Modal Quick Deploy"
echo "=========================================="
echo ""

# Your tokens are already provided
echo "Setting up Modal authentication..."
modal token set --token-id ak-jt7FZ9TvShs4gLDth2QK0d --token-secret as-ds98ZNXm5fibjXkOvz0hvs

echo ""
echo "Verifying authentication..."
modal profile list

echo ""
echo "=========================================="
echo "Deploying Whisper STT..."
echo "=========================================="
modal deploy modal_deployment/whisper_stt.py

echo ""
echo "=========================================="
echo "Deploying Coqui TTS..."
echo "=========================================="
modal deploy modal_deployment/coqui_tts.py

echo ""
echo "=========================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Your endpoints are now live at:"
echo ""
echo "1. STT Transcription:"
echo "   https://jenkintownelectricity--premier-whisper-stt-transcribe-web.modal.run"
echo ""
echo "2. TTS Synthesis:"
echo "   https://jenkintownelectricity--premier-coqui-tts-synthesize-web.modal.run"
echo ""
echo "3. Voice Cloning:"
echo "   https://jenkintownelectricity--premier-coqui-tts-clone-voice-web.modal.run"
echo ""
echo "=========================================="
echo "Verify deployment:"
echo "=========================================="
echo ""
echo "  modal app list"
echo "  modal app show premier-whisper-stt"
echo "  modal app show premier-coqui-tts"
echo ""
