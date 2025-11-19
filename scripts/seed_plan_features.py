#!/usr/bin/env python3
"""
Seed script for plan features in Premier Voice Assistant.
Populates the va_plan_features table with limits for each subscription plan.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.supabase_client import get_supabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_plan_features():
    """Seed plan features for all subscription plans."""
    try:
        supabase = get_supabase()

        # Get all plans
        plans_result = supabase.client.table("va_subscription_plans").select("*").execute()
        plans = {plan["plan_name"]: plan["id"] for plan in plans_result.data}

        logger.info(f"Found {len(plans)} plans: {list(plans.keys())}")

        # Define features for each plan
        # -1 means unlimited
        plan_features = {
            "free": {
                "max_minutes": 100,  # 100 minutes per month
                "max_assistants": 1,  # 1 assistant
                "max_voice_clones": 0,  # No custom voices
                "custom_voices": False,  # Cannot create custom voices
                "api_access": False,  # No API access
                "priority_support": False,  # Community support only
                "analytics": False,  # No analytics dashboard
                "overage_allowed": False,  # Hard limit, no overages
                "overage_rate_cents": 0,  # No overage billing
            },
            "starter": {
                "max_minutes": 2000,  # 2,000 minutes per month
                "max_assistants": 3,  # 3 assistants
                "max_voice_clones": 2,  # 2 custom voices
                "custom_voices": True,  # Can create custom voices
                "api_access": True,  # Basic API access
                "priority_support": False,  # Email support
                "analytics": True,  # Basic analytics
                "overage_allowed": True,  # Allow overages
                "overage_rate_cents": 10,  # $0.10 per minute overage
            },
            "pro": {
                "max_minutes": 10000,  # 10,000 minutes per month
                "max_assistants": -1,  # Unlimited assistants
                "max_voice_clones": -1,  # Unlimited custom voices
                "custom_voices": True,  # Can create custom voices
                "api_access": True,  # Full API access
                "priority_support": True,  # Priority support
                "analytics": True,  # Advanced analytics
                "overage_allowed": True,  # Allow overages
                "overage_rate_cents": 8,  # $0.08 per minute overage (discounted)
            },
            "enterprise": {
                "max_minutes": -1,  # Unlimited minutes
                "max_assistants": -1,  # Unlimited assistants
                "max_voice_clones": -1,  # Unlimited custom voices
                "custom_voices": True,  # Can create custom voices
                "api_access": True,  # Full API access with higher rate limits
                "priority_support": True,  # Dedicated support
                "analytics": True,  # Enterprise analytics
                "overage_allowed": True,  # Allow overages (shouldn't happen)
                "overage_rate_cents": 0,  # No overage charges (included)
            },
        }

        # Delete existing features (for re-seeding)
        logger.info("Clearing existing plan features...")
        supabase.client.table("va_plan_features").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

        # Insert features for each plan
        features_to_insert = []

        for plan_name, features in plan_features.items():
            if plan_name not in plans:
                logger.warning(f"Plan '{plan_name}' not found in database, skipping...")
                continue

            plan_id = plans[plan_name]

            for feature_key, feature_value in features.items():
                # Determine description based on feature
                descriptions = {
                    "max_minutes": "Maximum conversation minutes per billing period",
                    "max_assistants": "Maximum number of voice assistants (-1 = unlimited)",
                    "max_voice_clones": "Maximum number of custom voice clones (-1 = unlimited)",
                    "custom_voices": "Ability to create custom voice clones",
                    "api_access": "Access to REST API",
                    "priority_support": "Priority customer support",
                    "analytics": "Access to analytics dashboard",
                    "overage_allowed": "Allow usage beyond plan limits",
                    "overage_rate_cents": "Cost per minute for overage usage (in cents)",
                }

                features_to_insert.append({
                    "plan_id": plan_id,
                    "feature_key": feature_key,
                    "feature_value": feature_value,
                    "description": descriptions.get(feature_key, ""),
                })

        # Batch insert all features
        logger.info(f"Inserting {len(features_to_insert)} plan features...")
        result = supabase.client.table("va_plan_features").insert(features_to_insert).execute()

        logger.info(f"✅ Successfully seeded {len(result.data)} plan features!")

        # Display summary
        print("\n" + "="*80)
        print("PLAN FEATURES SUMMARY")
        print("="*80)

        for plan_name in ["free", "starter", "pro", "enterprise"]:
            if plan_name not in plans:
                continue

            plan_id = plans[plan_name]
            features_result = supabase.client.table("va_plan_features").select("*").eq("plan_id", plan_id).execute()

            print(f"\n📋 {plan_name.upper()} Plan:")
            for feature in features_result.data:
                value = feature["feature_value"]
                if value == -1:
                    value_str = "Unlimited"
                elif isinstance(value, bool):
                    value_str = "✅ Yes" if value else "❌ No"
                else:
                    value_str = str(value)

                print(f"  • {feature['feature_key']}: {value_str}")

        print("\n" + "="*80)
        print("✅ Seed completed successfully!")
        print("="*80 + "\n")

        return True

    except Exception as e:
        logger.error(f"❌ Error seeding plan features: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = seed_plan_features()
    sys.exit(0 if success else 1)
