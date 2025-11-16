#!/bin/bash
# =============================================================================
# Modal Deployment Script - Premier Voice Assistant
# =============================================================================
# This script deploys your Modal services with web endpoints
# =============================================================================

set -e  # Exit on error

echo "=========================================="
echo "Modal Deployment - Premier Voice Assistant"
echo "=========================================="
echo ""

# Check if Modal is installed
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI not found. Installing..."
    pip3 install modal
fi

echo "✅ Modal CLI installed (version: $(modal --version | cut -d' ' -f4))"
echo ""

# Check if authenticated
if ! modal profile list 2>&1 | grep -q "┃"; then
    echo "⚠️  Modal not authenticated!"
    echo ""
    echo "Please authenticate Modal using ONE of these methods:"
    echo ""
    echo "METHOD 1: Interactive browser authentication"
    echo "  $ modal token new"
    echo ""
    echo "METHOD 2: Use existing tokens (non-interactive)"
    echo "  1. Get tokens from: https://modal.com/settings"
    echo "  2. Run: modal token set --token-id YOUR_TOKEN_ID --token-secret YOUR_TOKEN_SECRET"
    echo ""
    exit 1
fi

echo "✅ Modal authenticated"
echo ""

# Display current workspace
WORKSPACE=$(modal profile list | grep "│" | awk '{print $5}' | head -1)
echo "📍 Workspace: $WORKSPACE"
echo ""

# Deploy Whisper STT
echo "==========================================
"
echo "🚀 Deploying Whisper STT Service..."
echo "=========================================="
modal deploy modal_deployment/whisper_stt.py

echo ""
echo "✅ Whisper STT deployed!"
echo ""

# Deploy Coqui TTS
echo "=========================================="
echo "🚀 Deploying Coqui TTS Service..."
echo "=========================================="
modal deploy modal_deployment/coqui_tts.py

echo ""
echo "✅ Coqui TTS deployed!"
echo ""

# Show endpoints
echo "=========================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Your web endpoints are now live at:"
echo ""
echo "1. Whisper STT (Transcription):"
echo "   https://$WORKSPACE--premier-whisper-stt-transcribe-web.modal.run"
echo ""
echo "2. Coqui TTS (Text-to-Speech):"
echo "   https://$WORKSPACE--premier-coqui-tts-synthesize-web.modal.run"
echo ""
echo "3. Voice Cloning:"
echo "   https://$WORKSPACE--premier-coqui-tts-clone-voice-web.modal.run"
echo ""
echo "=========================================="
echo "📝 Next Steps:"
echo "=========================================="
echo ""
echo "1. Test the endpoints:"
echo "   curl https://$WORKSPACE--premier-whisper-stt-transcribe-web.modal.run"
echo ""
echo "2. View in Modal dashboard:"
echo "   https://modal.com/apps"
echo ""
echo "3. Monitor logs:"
echo "   modal app logs premier-whisper-stt"
echo "   modal app logs premier-coqui-tts"
echo ""
echo "=========================================="
