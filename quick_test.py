#!/usr/bin/env python3
"""
Quick Feature Gates Test for HIVE215
Tests subscription upgrades and feature gates via direct API calls.

Usage:
    # Start FastAPI first:
    python -m backend.main

    # Run test:
    python quick_test.py
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
USER_ID = "ea97ae74-a597-4dc8-9c6e-1c6981324ce5"
ADMIN_KEY = os.getenv("ADMIN_API_KEY", "admin-secret-key")

def api_get(endpoint, user_id=USER_ID):
    """Make GET request with user ID header"""
    return requests.get(
        f"{API_URL}{endpoint}",
        headers={"X-User-ID": user_id}
    )

def admin_upgrade(plan):
    """Upgrade user to specified plan"""
    return requests.post(
        f"{API_URL}/admin/upgrade-user",
        headers={"X-Admin-Key": ADMIN_KEY},
        json={"user_id": USER_ID, "plan_name": plan}
    )

print("=" * 50)
print("HIVE215 - Feature Gates Test (API)")
print("=" * 50)
print(f"API: {API_URL}")
print(f"User: {USER_ID[:8]}...")
print()

# Check API is running
try:
    r = requests.get(f"{API_URL}/health")
    if r.status_code != 200:
        raise Exception("Health check failed")
except:
    print("❌ Cannot connect to API!")
    print("   Run: python -m backend.main")
    exit(1)

# 1. Initial Status
print("1. Initial Status:")
r = api_get("/feature-limits")
if r.status_code == 200:
    data = r.json()
    limits = data.get("limits", {})
    usage = data.get("current_usage", {})
    print(f"   Plan: {data['plan']}")
    print(f"   Minutes: {usage.get('minutes_used', 0)}/{limits.get('max_minutes', 0)}")
else:
    print(f"   ❌ Error: {r.status_code}")
print()

# 2. Downgrade to Free first
print("2. Downgrade to Free:")
r = admin_upgrade("free")
if r.status_code == 200:
    print(f"   ✅ {r.json()['message']}")
elif r.status_code == 401:
    print(f"   ❌ Invalid admin key - set ADMIN_API_KEY in .env")
    exit(1)
else:
    print(f"   ❌ Error: {r.json().get('detail', r.status_code)}")
print()

# 3. Check Free limits
print("3. Free Plan Limits:")
r = api_get("/feature-limits")
if r.status_code == 200:
    data = r.json()
    limits = data.get("limits", {})
    max_min = limits.get("max_minutes", 0)
    print(f"   Minutes limit: {max_min} {'✅' if max_min == 100 else '❌ (expected 100)'}")
    print(f"   Custom voices: {'❌ (correct)' if not limits.get('custom_voices') else '✅ (unexpected)'}")
print()

# 4. Upgrade to Starter
print("4. Upgrade to Starter:")
r = admin_upgrade("starter")
if r.status_code == 200:
    print(f"   ✅ {r.json()['message']}")
else:
    print(f"   ❌ Error: {r.json().get('detail', r.status_code)}")
print()

# 5. Check Starter limits
print("5. Starter Plan Limits:")
r = api_get("/feature-limits")
if r.status_code == 200:
    data = r.json()
    limits = data.get("limits", {})
    max_min = limits.get("max_minutes", 0)
    print(f"   Minutes limit: {max_min} {'✅' if max_min == 2000 else '❌ (expected 2000)'}")
    print(f"   Custom voices: {'✅ (correct)' if limits.get('custom_voices') else '❌ (expected true)'}")
    print(f"   Max voice clones: {limits.get('max_voice_clones', 0)}")
print()

# 6. Upgrade to Pro
print("6. Upgrade to Pro:")
r = admin_upgrade("pro")
if r.status_code == 200:
    print(f"   ✅ {r.json()['message']}")
else:
    print(f"   ❌ Error: {r.json().get('detail', r.status_code)}")
print()

# 7. Check Pro limits
print("7. Pro Plan Limits:")
r = api_get("/feature-limits")
if r.status_code == 200:
    data = r.json()
    limits = data.get("limits", {})
    max_min = limits.get("max_minutes", 0)
    print(f"   Minutes limit: {max_min} {'✅' if max_min == 10000 else '❌ (expected 10000)'}")
    print(f"   Custom voices: {'✅' if limits.get('custom_voices') else '❌'}")
    print(f"   Max voice clones: {limits.get('max_voice_clones', 'unlimited')}")
print()

print("=" * 50)
print("✅ Test Complete!")
print("=" * 50)