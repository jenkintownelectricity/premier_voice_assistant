#!/bin/bash
# =============================================================================
# Test Modal Web Endpoints
# =============================================================================
# Tests all 3 Modal web endpoints after deployment
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Testing Modal Web Endpoints"
echo "=========================================="
echo ""

# Get workspace name
WORKSPACE=$(modal profile list 2>/dev/null | grep "│" | awk '{print $5}' | head -1)

if [ -z "$WORKSPACE" ]; then
    echo -e "${RED}❌ Modal not authenticated${NC}"
    echo "Run: modal token new"
    exit 1
fi

echo "📍 Workspace: $WORKSPACE"
echo ""

# Define endpoint URLs
STT_URL="https://$WORKSPACE--premier-whisper-stt-transcribe-web.modal.run"
TTS_URL="https://$WORKSPACE--premier-coqui-tts-synthesize-web.modal.run"
CLONE_URL="https://$WORKSPACE--premier-coqui-tts-clone-voice-web.modal.run"

echo "=========================================="
echo "Endpoint URLs:"
echo "=========================================="
echo "STT: $STT_URL"
echo "TTS: $TTS_URL"
echo "Clone: $CLONE_URL"
echo ""

# Test 1: Check if endpoints exist
echo "=========================================="
echo "Test 1: Checking endpoint availability..."
echo "=========================================="

check_endpoint() {
    local name=$1
    local url=$2

    echo -n "Testing $name... "

    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$url" -X POST || echo "000")

    if [ "$STATUS" = "000" ]; then
        echo -e "${RED}❌ FAILED (Connection error)${NC}"
        echo "   Endpoint may not be deployed yet"
        return 1
    elif [ "$STATUS" = "422" ]; then
        echo -e "${GREEN}✅ AVAILABLE (422 = validation error, endpoint exists)${NC}"
        return 0
    elif [ "$STATUS" = "404" ]; then
        echo -e "${RED}❌ NOT FOUND${NC}"
        echo "   Run: modal deploy modal_deployment/*.py"
        return 1
    else
        echo -e "${YELLOW}⚠️  Status $STATUS${NC}"
        return 0
    fi
}

echo ""
check_endpoint "STT" "$STT_URL"
check_endpoint "TTS" "$TTS_URL"
check_endpoint "Clone" "$CLONE_URL"

echo ""
echo "=========================================="
echo "Test 2: Checking Modal apps status..."
echo "=========================================="
echo ""

modal app list

echo ""
echo "=========================================="
echo "📝 Next Steps:"
echo "=========================================="
echo ""
echo "1. If endpoints show ❌ NOT FOUND, deploy them:"
echo "   ./deploy_modal_endpoints.sh"
echo ""
echo "2. View detailed app info:"
echo "   modal app show premier-whisper-stt"
echo "   modal app show premier-coqui-tts"
echo ""
echo "3. Stream live logs:"
echo "   modal app logs premier-whisper-stt --follow"
echo ""
echo "4. Test with real audio:"
echo "   See examples in tests/ directory"
echo ""
echo "=========================================="
