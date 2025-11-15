#!/bin/bash
# Premier Voice Assistant - Setup Script
# Run this to get started quickly

set -e

echo "=========================================="
echo "Premier Voice Assistant - Setup"
echo "=========================================="
echo

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $python_version"

if [[ ! $python_version == 3.11* ]] && [[ ! $python_version == 3.12* ]]; then
    echo "⚠ Warning: Python 3.11+ recommended (you have $python_version)"
fi

echo

# Install dependencies
echo "Installing Python dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo

# Check Modal
echo "Checking Modal setup..."
if command -v modal &> /dev/null; then
    echo "✓ Modal CLI installed"

    if modal token verify &> /dev/null 2>&1; then
        echo "✓ Modal authenticated"
    else
        echo "⚠ Modal not authenticated"
        echo "  Run: modal setup"
    fi
else
    echo "✓ Modal will be available after install"
    echo "  Run after setup: modal setup"
fi

echo

# Check config
echo "Checking configuration..."
if [ -f "config/secrets.py" ]; then
    echo "✓ config/secrets.py exists"
else
    echo "⚠ config/secrets.py not found"
    echo "  Creating from template..."
    cp config/secrets.example.py config/secrets.py
    echo "  ✓ Created config/secrets.py"
    echo "  → Edit this file and add your API keys:"
    echo "     - ANTHROPIC_API_KEY"
    echo "     - Modal keys (if not in environment)"
fi

echo

# Check voice directory
echo "Checking voice samples..."
if ls voices/*.wav &> /dev/null 2>&1; then
    echo "✓ Voice samples found:"
    ls voices/*.wav | while read f; do
        echo "  - $(basename $f)"
    done
else
    echo "⚠ No voice samples found"
    echo "  → Add voice samples to voices/ directory"
    echo "  → See voices/README.md for recording instructions"
fi

echo
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
echo "Next steps:"
echo
echo "1. Configure API keys:"
echo "   nano config/secrets.py"
echo
echo "2. Authenticate with Modal (if not done):"
echo "   modal setup"
echo
echo "3. Deploy to Modal:"
echo "   ./scripts/deploy_modal.sh"
echo
echo "4. Clone voices (optional):"
echo "   modal run modal_deployment/voice_cloner.py --voice-name fabio --audio-path voices/fabio_sample.wav"
echo
echo "5. Run tests:"
echo "   python scripts/test_integration.py"
echo
echo "6. Start the app:"
echo "   python main.py"
echo
echo "For detailed instructions, see QUICKSTART.md"
echo
