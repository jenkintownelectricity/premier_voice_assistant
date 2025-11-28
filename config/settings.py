"""
Application settings and configuration management.
"""
import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
VOICES_DIR = PROJECT_ROOT / "voices"
CACHE_DIR = VOICES_DIR / "cached_responses"

# Ensure directories exist
VOICES_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# Try to import secrets, fall back to environment variables
try:
    from config.secrets import *
except ImportError:
    print("Warning: secrets.py not found, using environment variables")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    MODAL_TOKEN_ID = os.getenv("MODAL_TOKEN_ID", "")
    MODAL_TOKEN_SECRET = os.getenv("MODAL_TOKEN_SECRET", "")
    DEBUG = os.getenv("DEBUG", "True") == "True"

# Voice Processing Settings
WHISPER_MODEL = "base.en"  # Options: tiny.en, base.en, small.en, medium.en, large-v3
WHISPER_DEVICE = "cuda"  # Modal will use GPU
WHISPER_COMPUTE_TYPE = "float16"  # Optimize for speed

# TTS Settings
TTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
TTS_LANGUAGE = "en"
TTS_SAMPLE_RATE = 22050

# Voice Cloning
DEFAULT_VOICE = "fabio"  # Default voice to use
VOICE_SAMPLES = {
    "fabio": str(VOICES_DIR / "fabio_sample.wav"),
    "jake": str(VOICES_DIR / "jake_sample.wav"),
}

# LLM Settings
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"  # Stable Sonnet version
MAX_TOKENS = 150  # Keep responses concise for voice
TEMPERATURE = 0.7

# Cache Settings
ENABLE_RESPONSE_CACHE = True
CACHE_TTL = 3600  # 1 hour
SEMANTIC_SIMILARITY_THRESHOLD = 0.85

# Latency Targets (milliseconds)
TARGET_STT_LATENCY = 200
TARGET_LLM_LATENCY = 150
TARGET_TTS_LATENCY = 150
TARGET_TOTAL_LATENCY = 500

# Cost Tracking
TARGET_COST_PER_MINUTE = 0.005  # $0.005/min target
