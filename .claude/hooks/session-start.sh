#!/bin/bash
set -euo pipefail

# Only run in remote environment (Claude Code on the web)
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Change to project directory
cd "$CLAUDE_PROJECT_DIR"

# Install Python dependencies
pip install -r requirements.txt
