#!/usr/bin/env python3
"""
Setup Tara's Sales Assistant

This script:
1. Registers the tara-sales skill with Fast Brain
2. Provides instructions for voice cloning
3. Updates environment configuration

Usage:
    python scripts/setup_tara_agent.py

Requirements:
    - FAST_BRAIN_URL environment variable
    - CARTESIA_API_KEY environment variable (for voice cloning)
"""

import os
import sys
import asyncio
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def register_skill():
    """Register the Tara sales skill with Fast Brain."""
    from backend.brain_client import FastBrainClient
    from skills.tara_sales import TARA_SALES_SKILL, SKILL_ID

    url = os.environ.get("FAST_BRAIN_URL")
    if not url:
        print("ERROR: FAST_BRAIN_URL not set")
        print("Set it with: export FAST_BRAIN_URL=https://your-fast-brain.modal.run")
        return False

    print(f"Connecting to Fast Brain: {url[:50]}...")
    client = FastBrainClient(base_url=url, default_skill=SKILL_ID)

    # Check health
    if not await client.is_healthy():
        print("ERROR: Fast Brain is not healthy")
        return False

    print("Fast Brain is healthy!")

    # List existing skills
    skills = await client.list_skills()
    skill_ids = [s.id for s in skills]
    print(f"Existing skills: {skill_ids}")

    # Create skill if it doesn't exist
    if SKILL_ID in skill_ids:
        print(f"Skill '{SKILL_ID}' already exists. Updating...")
        # Note: Fast Brain may need a delete/recreate or update endpoint
        # For now, we'll just inform the user

    print(f"\nCreating skill: {TARA_SALES_SKILL['name']}")
    result = await client.create_skill(**TARA_SALES_SKILL)

    if result:
        print("SUCCESS: Skill created/updated!")
        print(f"  ID: {SKILL_ID}")
        print(f"  Name: {TARA_SALES_SKILL['name']}")
        return True
    else:
        print("ERROR: Failed to create skill")
        return False


def print_voice_cloning_instructions():
    """Print instructions for cloning Tara's voice."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                    VOICE CLONING INSTRUCTIONS                     ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  Step 1: Extract Audio from YouTube                               ║
║  ─────────────────────────────────────────────────────────────    ║
║  Download the audio from: https://www.youtube.com/watch?v=Ms8vUOWxghs ║
║                                                                    ║
║  Option A: Use a YouTube to MP3 converter (e.g., y2mate.com)      ║
║  Option B: Use yt-dlp: yt-dlp -x --audio-format mp3 <URL>        ║
║                                                                    ║
║  Step 2: Trim to 5-10 seconds                                     ║
║  ─────────────────────────────────────────────────────────────    ║
║  Choose a clear segment where Tara is speaking naturally.         ║
║  Avoid background music or noise.                                 ║
║  Use Audacity or any audio editor to trim.                        ║
║                                                                    ║
║  Step 3: Clone Voice on Cartesia                                  ║
║  ─────────────────────────────────────────────────────────────    ║
║  1. Go to: https://play.cartesia.ai/voices                        ║
║  2. Click "Clone Voice" or "Instant Clone"                        ║
║  3. Upload your trimmed audio file                                ║
║  4. Name it "Tara Horn" and select English                        ║
║  5. Copy the Voice ID (looks like: a0e99841-438c-4a64-b679-xxx)   ║
║                                                                    ║
║  Step 4: Update Configuration                                     ║
║  ─────────────────────────────────────────────────────────────    ║
║  Set the voice ID in Railway Worker environment:                  ║
║  CARTESIA_VOICE_ID=<your-cloned-voice-id>                        ║
║                                                                    ║
║  Also set the skill:                                              ║
║  DEFAULT_SKILL=tara-sales                                         ║
║                                                                    ║
╚══════════════════════════════════════════════════════════════════╝
""")


async def test_skill():
    """Test the Tara skill with sample questions."""
    from backend.brain_client import FastBrainClient
    from skills.tara_sales import SKILL_ID

    url = os.environ.get("FAST_BRAIN_URL")
    if not url:
        print("ERROR: FAST_BRAIN_URL not set")
        return

    print("\n=== Testing Tara Sales Skill ===\n")
    client = FastBrainClient(base_url=url, default_skill=SKILL_ID)

    test_questions = [
        "Hi, what is The Dash?",
        "How much does it cost?",
        "We already use Salesforce",
        "I'm interested, what's next?",
    ]

    for q in test_questions:
        print(f"User: {q}")
        try:
            response = await client.think(q, skill=SKILL_ID)
            print(f"Tara: {response.text}\n")
        except Exception as e:
            print(f"Error: {e}\n")

    await client.close()


async def main():
    parser = argparse.ArgumentParser(description="Setup Tara's Sales Assistant")
    parser.add_argument("--register", action="store_true", help="Register skill with Fast Brain")
    parser.add_argument("--test", action="store_true", help="Test the skill")
    parser.add_argument("--voice", action="store_true", help="Show voice cloning instructions")
    parser.add_argument("--all", action="store_true", help="Do everything")

    args = parser.parse_args()

    if args.all or args.voice or (not args.register and not args.test):
        print_voice_cloning_instructions()

    if args.all or args.register:
        success = await register_skill()
        if not success and not args.all:
            sys.exit(1)

    if args.all or args.test:
        await test_skill()


if __name__ == "__main__":
    asyncio.run(main())
