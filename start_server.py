#!/usr/bin/env python3
"""
Startup script for FastAPI backend - loads .env and starts uvicorn
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Verify critical env vars are loaded
print("=" * 60)
print("Environment Variables Loaded:")
print(f"  SUPABASE_URL: {os.getenv('SUPABASE_URL')[:30]}..." if os.getenv('SUPABASE_URL') else "  SUPABASE_URL: NOT SET")
print(f"  ANTHROPIC_API_KEY: {'SET' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET'}")
print(f"  MODAL_TOKEN_ID: {'SET' if os.getenv('MODAL_TOKEN_ID') else 'NOT SET'}")
print("=" * 60)

# Start uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,  # Disable reload to avoid multiprocessing issues
    )
