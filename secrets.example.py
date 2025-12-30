"""
Configuration template for API keys and secrets.
Copy this file to secrets.py and fill in your actual values.
"""

# Modal Configuration
MODAL_TOKEN_ID = "your-modal-token-id"
MODAL_TOKEN_SECRET = "your-modal-token-secret"

# Anthropic Claude API
ANTHROPIC_API_KEY = "sk-ant-your-key-here"

# VoIP.ms (for Phase 3)
VOIPMS_USERNAME = "your-voipms-username"
VOIPMS_PASSWORD = "your-voipms-password"
VOIPMS_API_KEY = "your-voipms-api-key"

# Twilio (optional fallback)
TWILIO_ACCOUNT_SID = "your-twilio-sid"
TWILIO_AUTH_TOKEN = "your-twilio-token"

# Redis (for caching - optional, can use local dict initially)
REDIS_URL = "redis://localhost:6379"

# Flask Configuration
FLASK_SECRET_KEY = "your-secret-key-for-sessions"
DEBUG = True
