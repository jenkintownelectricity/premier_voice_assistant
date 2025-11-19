#!/usr/bin/env python3
"""
Quick API Test Script for Premier Voice Assistant
Tests subscription, usage, and admin upgrade endpoints directly via HTTP.

Usage:
    # Make sure FastAPI is running first:
    python -m backend.main

    # Then run this test:
    python api_test.py
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
TEST_USER_ID = "ea97ae74-a597-4dc8-9c6e-1c6981324ce5"
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "admin-secret-key")


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(success, message):
    status = "✅" if success else "❌"
    print(f"{status} {message}")


def test_health():
    """Test health endpoint"""
    print_header("1. Health Check")
    try:
        r = requests.get(f"{API_URL}/health")
        if r.status_code == 200:
            data = r.json()
            print_result(True, f"Service: {data['service']} v{data['version']}")
            return True
        else:
            print_result(False, f"Health check failed: {r.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_result(False, "Cannot connect to API. Is FastAPI running?")
        print("   Run: python -m backend.main")
        return False


def test_subscription():
    """Test subscription endpoint"""
    print_header("2. Get Subscription")
    try:
        r = requests.get(
            f"{API_URL}/subscription",
            headers={"X-User-ID": TEST_USER_ID}
        )
        if r.status_code == 200:
            data = r.json()
            sub = data.get("subscription")
            if sub:
                print_result(True, f"Plan: {sub['plan_name']} ({sub['display_name']})")
                price = sub.get('price_cents', 0) / 100
                print(f"   Price: ${price:.2f}/mo")
                print(f"   Status: {sub['status']}")
                return sub['plan_name']
            else:
                print_result(False, "No subscription found")
                return None
        else:
            print_result(False, f"Error: {r.json().get('detail', r.status_code)}")
            return None
    except Exception as e:
        print_result(False, f"Error: {e}")
        return None


def test_usage():
    """Test usage endpoint"""
    print_header("3. Get Usage")
    try:
        r = requests.get(
            f"{API_URL}/usage",
            headers={"X-User-ID": TEST_USER_ID}
        )
        if r.status_code == 200:
            data = r.json()
            usage = data.get("usage", {})
            minutes = usage.get("minutes_used", 0)
            print_result(True, f"Minutes used: {minutes}")
            print(f"   Conversations: {usage.get('conversations_count', 0)}")
            print(f"   Voice clones: {usage.get('voice_clones_count', 0)}")
            return minutes
        else:
            print_result(False, f"Error: {r.json().get('detail', r.status_code)}")
            return 0
    except Exception as e:
        print_result(False, f"Error: {e}")
        return 0


def test_feature_limits():
    """Test feature limits endpoint"""
    print_header("4. Get Feature Limits")
    try:
        r = requests.get(
            f"{API_URL}/feature-limits",
            headers={"X-User-ID": TEST_USER_ID}
        )
        if r.status_code == 200:
            data = r.json()
            plan = data.get("plan", "unknown")
            limits = data.get("limits", {})
            usage = data.get("current_usage", {})

            print_result(True, f"Plan: {plan}")

            max_minutes = limits.get("max_minutes", 0)
            used_minutes = usage.get("minutes_used", 0)
            print(f"   Minutes: {used_minutes}/{max_minutes}")
            print(f"   Assistants: {usage.get('assistants_count', 0)}/{limits.get('max_assistants', 0)}")
            print(f"   Voice clones: {usage.get('voice_clones_count', 0)}/{limits.get('max_voice_clones', 0)}")
            print(f"   Custom voices: {'✅' if limits.get('custom_voices') else '❌'}")
            print(f"   API access: {'✅' if limits.get('api_access') else '❌'}")

            return max_minutes
        else:
            print_result(False, f"Error: {r.json().get('detail', r.status_code)}")
            return 0
    except Exception as e:
        print_result(False, f"Error: {e}")
        return 0


def test_admin_upgrade(plan_name):
    """Test admin upgrade endpoint"""
    print_header(f"5. Admin Upgrade to {plan_name.upper()}")
    try:
        r = requests.post(
            f"{API_URL}/admin/upgrade-user",
            headers={
                "X-Admin-Key": ADMIN_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "user_id": TEST_USER_ID,
                "plan_name": plan_name
            }
        )
        if r.status_code == 200:
            data = r.json()
            print_result(True, data.get("message", "Upgrade successful"))
            return True
        elif r.status_code == 401:
            print_result(False, "Invalid admin API key")
            print(f"   Set ADMIN_API_KEY in .env (currently using: {ADMIN_API_KEY[:10]}...)")
            return False
        else:
            print_result(False, f"Error: {r.json().get('detail', r.status_code)}")
            return False
    except Exception as e:
        print_result(False, f"Error: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("  HIVE215 - API Test Suite")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"Test User: {TEST_USER_ID}")
    print(f"Admin Key: {ADMIN_API_KEY[:10]}...")

    # Test 1: Health check
    if not test_health():
        print("\n❌ Cannot proceed - API not running")
        return

    # Test 2: Get current subscription
    current_plan = test_subscription()

    # Test 3: Get usage
    test_usage()

    # Test 4: Get feature limits
    test_feature_limits()

    # Test 5: Upgrade cycle
    print_header("6. Upgrade Cycle Test")

    # Downgrade to free first
    if current_plan != "free":
        print("\nDowngrading to Free...")
        test_admin_upgrade("free")
        test_feature_limits()

    # Upgrade to starter
    print("\nUpgrading to Starter...")
    if test_admin_upgrade("starter"):
        limits = test_feature_limits()
        if limits == 2000:
            print_result(True, "Starter limits correct (2000 minutes)")
        else:
            print_result(False, f"Expected 2000 minutes, got {limits}")

    # Upgrade to pro
    print("\nUpgrading to Pro...")
    if test_admin_upgrade("pro"):
        limits = test_feature_limits()
        if limits == 10000:
            print_result(True, "Pro limits correct (10000 minutes)")
        else:
            print_result(False, f"Expected 10000 minutes, got {limits}")

    # Summary
    print_header("Test Complete")
    print(f"User {TEST_USER_ID[:8]}... is now on Pro plan")
    print("\nNext steps:")
    print("  - Test /chat endpoint with audio file")
    print("  - Test /clone-voice endpoint")
    print("  - Add Stripe payment integration")


if __name__ == "__main__":
    main()
