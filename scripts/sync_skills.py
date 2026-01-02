#!/usr/bin/env python3
"""
Sync All Skills to Fast Brain

This script registers all locally defined skills with the Fast Brain API.
Run this whenever you add or update skills.

Usage:
    python scripts/sync_skills.py [options]

Options:
    --verify    Only verify which skills exist (don't sync)
    --list      List all local skills
    --test      Test skills after syncing
    --skill ID  Only sync a specific skill

Requirements:
    FAST_BRAIN_URL environment variable must be set

Examples:
    # Sync all skills
    python scripts/sync_skills.py

    # Verify which skills exist on Fast Brain
    python scripts/sync_skills.py --verify

    # Sync and test
    python scripts/sync_skills.py --test

    # Sync only electrician skill
    python scripts/sync_skills.py --skill electrician
"""

import os
import sys
import asyncio
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.registry import registry, get_skill_ids, get_skill


async def verify_skills():
    """Check which skills exist on Fast Brain."""
    from backend.brain_client import FastBrainClient

    url = os.environ.get("FAST_BRAIN_URL")
    if not url:
        print("ERROR: FAST_BRAIN_URL not set")
        return False

    print(f"Connecting to Fast Brain: {url[:50]}...")
    client = FastBrainClient(base_url=url)

    if not await client.is_healthy():
        print("ERROR: Fast Brain is not healthy")
        return False

    print("Fast Brain is healthy!\n")

    # Get skills from Fast Brain
    remote_skills = await client.list_skills()
    remote_ids = {s.id for s in remote_skills}

    # Compare with local skills
    local_ids = set(get_skill_ids())

    print("=" * 60)
    print("SKILL VERIFICATION REPORT")
    print("=" * 60)

    print(f"\nLocal skills ({len(local_ids)}):")
    for skill_id in sorted(local_ids):
        skill = get_skill(skill_id)
        status = "✓" if skill_id in remote_ids else "✗"
        print(f"  {status} {skill_id}: {skill.name}")

    print(f"\nRemote skills ({len(remote_ids)}):")
    for skill in sorted(remote_skills, key=lambda s: s.id):
        status = "✓" if skill.id in local_ids else "?"
        print(f"  {status} {skill.id}: {skill.name}")

    # Summary
    missing = local_ids - remote_ids
    extra = remote_ids - local_ids

    print("\n" + "-" * 60)
    if missing:
        print(f"⚠️  Missing on Fast Brain: {', '.join(missing)}")
        print("   Run 'python scripts/sync_skills.py' to sync")
    else:
        print("✓ All local skills exist on Fast Brain")

    if extra:
        print(f"ℹ️  Extra on Fast Brain (not defined locally): {', '.join(extra)}")

    await client.close()
    return len(missing) == 0


async def sync_skills(skill_id: str = None):
    """Sync skills with Fast Brain."""
    from backend.brain_client import FastBrainClient

    url = os.environ.get("FAST_BRAIN_URL")
    if not url:
        print("ERROR: FAST_BRAIN_URL not set")
        print("Set it with: export FAST_BRAIN_URL=https://your-fast-brain.modal.run")
        return False

    print(f"Connecting to Fast Brain: {url[:50]}...")
    client = FastBrainClient(base_url=url)

    if not await client.is_healthy():
        print("ERROR: Fast Brain is not healthy")
        return False

    print("Fast Brain is healthy!\n")

    # Determine which skills to sync
    if skill_id:
        skill = get_skill(skill_id)
        if not skill:
            print(f"ERROR: Skill '{skill_id}' not found")
            print(f"Available skills: {', '.join(get_skill_ids())}")
            return False
        skills_to_sync = {skill_id: skill}
    else:
        skills_to_sync = {sid: get_skill(sid) for sid in get_skill_ids()}

    print("=" * 60)
    print(f"SYNCING {len(skills_to_sync)} SKILL(S)")
    print("=" * 60)

    results = {}
    for sid, skill in skills_to_sync.items():
        print(f"\nSyncing: {sid} ({skill.name})")
        try:
            result = await client.create_skill(**skill.to_dict())
            results[sid] = result is not None
            if result:
                print(f"  ✓ Success")
            else:
                print(f"  ✗ Failed (no result)")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results[sid] = False

    # Summary
    print("\n" + "=" * 60)
    print("SYNC SUMMARY")
    print("=" * 60)

    success = sum(1 for v in results.values() if v)
    failed = len(results) - success

    print(f"\n✓ Succeeded: {success}")
    print(f"✗ Failed: {failed}")

    if failed > 0:
        print(f"\nFailed skills: {', '.join(k for k, v in results.items() if not v)}")

    await client.close()
    return failed == 0


async def test_skills():
    """Test skills with sample queries."""
    from backend.brain_client import FastBrainClient

    url = os.environ.get("FAST_BRAIN_URL")
    if not url:
        print("ERROR: FAST_BRAIN_URL not set")
        return

    client = FastBrainClient(base_url=url)

    test_cases = {
        "receptionist": "What are your business hours?",
        "electrician": "I need to install an EV charger",
        "plumber": "I have a leaky faucet",
        "lawyer": "I was in a car accident",
        "solar": "How much can I save with solar panels?",
        "tara-sales": "What is The Dash?",
    }

    print("\n" + "=" * 60)
    print("TESTING SKILLS")
    print("=" * 60)

    for skill_id, question in test_cases.items():
        if skill_id not in get_skill_ids():
            continue

        print(f"\n[{skill_id}]")
        print(f"  Q: {question}")

        try:
            response = await client.think(question, skill=skill_id)
            # Truncate response if too long
            text = response.text
            if len(text) > 200:
                text = text[:200] + "..."
            print(f"  A: {text}")
        except Exception as e:
            print(f"  ERROR: {e}")

    await client.close()


def list_skills():
    """List all local skills."""
    print("=" * 60)
    print("LOCAL SKILLS")
    print("=" * 60)

    for skill_id in sorted(get_skill_ids()):
        skill = get_skill(skill_id)
        print(f"\n{skill_id}")
        print(f"  Name: {skill.name}")
        print(f"  Description: {skill.description}")
        if skill.knowledge:
            print(f"  Knowledge items: {len(skill.knowledge)}")


async def main():
    parser = argparse.ArgumentParser(
        description="Sync HIVE215 skills with Fast Brain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/sync_skills.py              # Sync all skills
    python scripts/sync_skills.py --verify     # Check what exists
    python scripts/sync_skills.py --test       # Sync and test
    python scripts/sync_skills.py --skill electrician  # Sync one skill
        """
    )
    parser.add_argument("--verify", action="store_true",
                        help="Only verify which skills exist")
    parser.add_argument("--list", action="store_true",
                        help="List all local skills")
    parser.add_argument("--test", action="store_true",
                        help="Test skills after syncing")
    parser.add_argument("--skill", type=str,
                        help="Only sync a specific skill ID")

    args = parser.parse_args()

    if args.list:
        list_skills()
        return

    if args.verify:
        await verify_skills()
        return

    # Sync skills
    success = await sync_skills(args.skill)

    # Test if requested
    if args.test and success:
        await test_skills()


if __name__ == "__main__":
    asyncio.run(main())
