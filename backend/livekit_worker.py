#!/usr/bin/env python3
"""
LiveKit Agent Worker

This is the standalone worker process that runs LiveKit voice agents.
It connects to the LiveKit server and handles incoming voice sessions.

Usage:
    # Development mode (auto-reload)
    python backend/livekit_worker.py dev

    # Production mode
    python backend/livekit_worker.py start

    # With custom config
    LIVEKIT_URL=wss://... LIVEKIT_API_KEY=... python backend/livekit_worker.py start

Environment Variables:
    LIVEKIT_URL         - LiveKit server URL (wss://your-server.livekit.cloud)
    LIVEKIT_API_KEY     - LiveKit API key
    LIVEKIT_API_SECRET  - LiveKit API secret
    DEEPGRAM_API_KEY    - Deepgram API key for STT
    GROQ_API_KEY        - Groq API key for LLM
    CARTESIA_API_KEY    - Cartesia API key for TTS

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                       LIVEKIT WORKER                            │
    │                                                                 │
    │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
    │   │   Job Queue  │───▶│  Agent Pool  │───▶│ Voice Agent  │     │
    │   │  (LiveKit)   │    │  (Workers)   │    │  (Pipeline)  │     │
    │   └──────────────┘    └──────────────┘    └──────────────┘     │
    │                                                  │               │
    │                              ┌───────────────────┼──────────────┤
    │                              ▼                   ▼              │
    │                        ┌──────────┐        ┌──────────┐        │
    │                        │ Deepgram │        │ Cartesia │        │
    │                        │   STT    │        │   TTS    │        │
    │                        └──────────┘        └──────────┘        │
    │                              │                                  │
    │                              ▼                                  │
    │                        ┌──────────┐                            │
    │                        │   Groq   │                            │
    │                        │   LLM    │                            │
    │                        └──────────┘                            │
    └─────────────────────────────────────────────────────────────────┘
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger("livekit_worker")


def normalize_livekit_url():
    """
    Normalize LIVEKIT_URL to ensure it has the wss:// prefix.
    This handles common configuration mistakes where users forget the prefix.
    """
    url = os.getenv("LIVEKIT_URL", "")
    if not url:
        return url

    original_url = url

    # Remove any trailing slashes
    url = url.rstrip("/")

    # Handle various formats
    if url.startswith("wss://") or url.startswith("ws://"):
        # Already has websocket prefix
        pass
    elif url.startswith("https://"):
        # Convert HTTPS to WSS
        url = "wss://" + url[8:]
        logger.info(f"Converted LIVEKIT_URL from https:// to wss://")
    elif url.startswith("http://"):
        # Convert HTTP to WS (for local development)
        url = "ws://" + url[7:]
        logger.info(f"Converted LIVEKIT_URL from http:// to ws://")
    else:
        # No prefix, add wss://
        url = "wss://" + url
        logger.info(f"Added wss:// prefix to LIVEKIT_URL")

    # Update the environment variable so LiveKit SDK gets the correct value
    if url != original_url:
        os.environ["LIVEKIT_URL"] = url
        logger.info(f"LIVEKIT_URL normalized: {original_url} -> {url}")

    return url


def check_configuration():
    """Check that all required environment variables are set."""
    # Core required vars
    required_vars = {
        "LIVEKIT_URL": "LiveKit server URL",
        "LIVEKIT_API_KEY": "LiveKit API key",
        "LIVEKIT_API_SECRET": "LiveKit API secret",
        "DEEPGRAM_API_KEY": "Deepgram API key for STT",
        "CARTESIA_API_KEY": "Cartesia API key for TTS",
    }

    # LLM: Either Fast Brain OR Groq is required
    fast_brain_url = os.getenv("FAST_BRAIN_URL", "")
    groq_api_key = os.getenv("GROQ_API_KEY", "")

    missing = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing.append(f"  - {var}: {description}")

    # Check LLM configuration
    if not fast_brain_url and not groq_api_key:
        missing.append("  - FAST_BRAIN_URL or GROQ_API_KEY: At least one LLM backend required")

    if missing:
        logger.error("Missing required environment variables:")
        for m in missing:
            logger.error(m)
        logger.error("\nSet these variables in your .env file or environment.")
        return False

    # Log configuration (masked)
    logger.info("Configuration:")
    logger.info(f"  LIVEKIT_URL: {os.getenv('LIVEKIT_URL')}")
    logger.info(f"  LIVEKIT_API_KEY: {os.getenv('LIVEKIT_API_KEY')[:10]}...")
    logger.info(f"  DEEPGRAM_API_KEY: {os.getenv('DEEPGRAM_API_KEY')[:10]}...")
    logger.info(f"  CARTESIA_API_KEY: {os.getenv('CARTESIA_API_KEY')[:10]}...")

    # Log LLM backend
    if fast_brain_url:
        logger.info(f"  FAST_BRAIN_URL: {fast_brain_url[:40]}...")
        default_skill = os.getenv("DEFAULT_SKILL", "default")
        logger.info(f"  DEFAULT_SKILL: {default_skill}")
    if groq_api_key:
        logger.info(f"  GROQ_API_KEY: {groq_api_key[:10]}... (fallback)")

    return True


def main():
    """Main entry point for the worker."""
    logger.info("=" * 60)
    logger.info("HIVE215 LiveKit Voice Agent Worker")
    logger.info("=" * 60)

    # Normalize LIVEKIT_URL first (handle missing wss:// prefix)
    normalize_livekit_url()

    # Check configuration
    if not check_configuration():
        sys.exit(1)

    # Import and run the agent
    try:
        from livekit.agents import cli
        from backend.livekit_agent import create_worker_options

        logger.info("Starting LiveKit agent worker...")
        cli.run_app(create_worker_options())

    except ImportError as e:
        logger.error(f"Failed to import LiveKit SDK: {e}")
        logger.error("Make sure to install: pip install 'livekit-agents[deepgram,cartesia,openai,silero]'")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise


if __name__ == "__main__":
    main()
