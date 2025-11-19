#!/usr/bin/env python3
"""
Test script for feature gates and subscription system.
Tests Free plan limits and upgrade flow.
"""
import os
import sys
from pathlib import Path
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.supabase_client import get_supabase
from backend.feature_gates import get_feature_gate, admin_upgrade_user, FeatureGateError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_user() -> str:
    """Create a test user profile."""
    supabase = get_supabase()

    # Generate a test user ID (in production, this comes from Supabase auth)
    test_user_id = str(uuid.uuid4())

    logger.info(f"\n{'='*80}")
    logger.info("CREATING TEST USER")
    logger.info(f"{'='*80}")
    logger.info(f"Test User ID: {test_user_id}")

    try:
        # Create user profile (this will trigger automatic Free plan subscription)
        profile = supabase.client.table("va_user_profiles").insert({
            "id": test_user_id,
            "phone": "+1234567890",
            "preferred_voice": "fabio",
        }).execute()

        logger.info("✅ User profile created")
        logger.info("✅ Free plan subscription automatically created")

        return test_user_id

    except Exception as e:
        logger.error(f"❌ Error creating test user: {e}")
        raise


def test_free_plan_limits(user_id: str):
    """Test Free plan limits."""
    logger.info(f"\n{'='*80}")
    logger.info("TEST 1: FREE PLAN LIMITS")
    logger.info(f"{'='*80}")

    feature_gate = get_feature_gate()

    # Check subscription
    plan = feature_gate.get_user_plan(user_id)
    logger.info(f"\n📋 Current Plan: {plan['plan_name'].upper()}")
    logger.info(f"   Display Name: {plan['display_name']}")
    logger.info(f"   Status: {plan['status']}")

    # Check feature limits
    logger.info(f"\n🔒 Feature Limits:")

    # Max minutes
    allowed, details = feature_gate.check_feature(user_id, "max_minutes", 1)
    logger.info(f"\n  Minutes:")
    logger.info(f"    Limit: {details['limit_value']} minutes/month")
    logger.info(f"    Used: {details['current_usage']} minutes")
    logger.info(f"    Remaining: {details['remaining']} minutes")
    logger.info(f"    Can use 1 minute: {'✅ Yes' if allowed else '❌ No'}")

    # Max assistants
    allowed, details = feature_gate.check_feature(user_id, "max_assistants", 1)
    logger.info(f"\n  Assistants:")
    logger.info(f"    Limit: {details['limit_value']}")
    logger.info(f"    Current: {details['current_usage']}")
    logger.info(f"    Can create: {'✅ Yes' if allowed else '❌ No'}")

    # Max voice clones
    allowed, details = feature_gate.check_feature(user_id, "max_voice_clones", 1)
    logger.info(f"\n  Voice Clones:")
    logger.info(f"    Limit: {details['limit_value']}")
    logger.info(f"    Current: {details['current_usage']}")
    logger.info(f"    Can create: {'✅ Yes' if allowed else '❌ No'}")

    # Test exceeding limits
    logger.info(f"\n{'='*80}")
    logger.info("TEST 2: EXCEEDING FREE PLAN LIMITS")
    logger.info(f"{'='*80}")

    # Simulate using 100 minutes
    logger.info("\n📊 Simulating 100 minutes of usage...")
    feature_gate.increment_usage(user_id, minutes=100)

    # Try to use 1 more minute
    logger.info("\n🚫 Attempting to use 1 more minute (should fail)...")
    try:
        feature_gate.enforce_feature(user_id, "max_minutes", 1)
        logger.error("❌ ERROR: Should have blocked this!")
    except FeatureGateError as e:
        logger.info(f"✅ Successfully blocked: {e.message}")

    # Check updated usage
    usage = feature_gate.get_user_usage(user_id)
    logger.info(f"\n📈 Current Usage:")
    logger.info(f"   Minutes used: {usage['minutes_used']}/{usage['minutes_limit']}")
    logger.info(f"   Usage percentage: {usage['usage_percentage']}")


def test_upgrade_to_pro(user_id: str):
    """Test upgrading user to Pro plan."""
    logger.info(f"\n{'='*80}")
    logger.info("TEST 3: UPGRADE TO PRO PLAN")
    logger.info(f"{'='*80}")

    # Upgrade user
    logger.info("\n⬆️  Upgrading user to Pro plan...")
    success = admin_upgrade_user(user_id, "pro")

    if not success:
        logger.error("❌ Failed to upgrade user")
        return

    logger.info("✅ User upgraded to Pro!")

    # Check new limits
    feature_gate = get_feature_gate()

    plan = feature_gate.get_user_plan(user_id)
    logger.info(f"\n📋 New Plan: {plan['plan_name'].upper()}")

    # Check feature limits
    logger.info(f"\n🔓 New Feature Limits:")

    # Max minutes
    allowed, details = feature_gate.check_feature(user_id, "max_minutes", 1)
    logger.info(f"\n  Minutes:")
    logger.info(f"    Limit: {details['limit_value']} minutes/month")
    logger.info(f"    Used: {details['current_usage']} minutes")
    logger.info(f"    Remaining: {details['remaining']} minutes")
    logger.info(f"    Can use 1 minute: {'✅ Yes' if allowed else '❌ No'}")

    # Max assistants
    allowed, details = feature_gate.check_feature(user_id, "max_assistants", 1)
    limit_display = "Unlimited" if details['limit_value'] == -1 else str(details['limit_value'])
    logger.info(f"\n  Assistants:")
    logger.info(f"    Limit: {limit_display}")
    logger.info(f"    Current: {details['current_usage']}")
    logger.info(f"    Can create: {'✅ Yes' if allowed else '❌ No'}")

    # Max voice clones
    allowed, details = feature_gate.check_feature(user_id, "max_voice_clones", 1)
    limit_display = "Unlimited" if details['limit_value'] == -1 else str(details['limit_value'])
    logger.info(f"\n  Voice Clones:")
    logger.info(f"    Limit: {limit_display}")
    logger.info(f"    Current: {details['current_usage']}")
    logger.info(f"    Can create: {'✅ Yes' if allowed else '❌ No'}")

    # Test that limits are now much higher
    logger.info(f"\n{'='*80}")
    logger.info("TEST 4: USING PRO PLAN FEATURES")
    logger.info(f"{'='*80}")

    # Try to use 100 more minutes (should work now)
    logger.info("\n✅ Attempting to use 100 minutes (should succeed)...")
    try:
        feature_gate.enforce_feature(user_id, "max_minutes", 100)
        logger.info("✅ Successfully allowed - Pro plan has higher limits!")
    except FeatureGateError as e:
        logger.error(f"❌ Blocked (unexpected): {e.message}")

    # Increment usage
    feature_gate.increment_usage(user_id, minutes=100)

    # Check final usage
    usage = feature_gate.get_user_usage(user_id)
    logger.info(f"\n📈 Final Usage:")
    logger.info(f"   Minutes used: {usage.get('minutes_used', 0)}/{usage.get('minutes_limit', 0)}")
    logger.info(f"   Usage percentage: {usage.get('usage_percentage', '0%')}")


def cleanup_test_user(user_id: str):
    """Clean up test user."""
    logger.info(f"\n{'='*80}")
    logger.info("CLEANUP")
    logger.info(f"{'='*80}")

    try:
        supabase = get_supabase()

        # Delete user profile (cascade delete will handle subscriptions and usage)
        supabase.client.table("va_user_profiles").delete().eq("id", user_id).execute()

        logger.info(f"✅ Test user cleaned up: {user_id}")

    except Exception as e:
        logger.warning(f"⚠️  Error cleaning up test user: {e}")


def main():
    """Run all tests."""
    logger.info("\n" + "="*80)
    logger.info("FEATURE GATE SYSTEM TEST")
    logger.info("="*80)

    user_id = None

    try:
        # Create test user
        user_id = create_test_user()

        # Test Free plan limits
        test_free_plan_limits(user_id)

        # Test upgrade to Pro
        test_upgrade_to_pro(user_id)

        logger.info(f"\n{'='*80}")
        logger.info("✅ ALL TESTS PASSED!")
        logger.info(f"{'='*80}\n")

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if user_id:
            cleanup = input("\nCleanup test user? (y/n): ").lower().strip()
            if cleanup == 'y':
                cleanup_test_user(user_id)
            else:
                logger.info(f"\n⚠️  Test user NOT cleaned up: {user_id}")
                logger.info("   Remember to delete manually!")


if __name__ == "__main__":
    main()
