from gradio_client import Client
import time

client = Client("http://localhost:7860/")
user_id = "ea97ae74-a597-4dc8-9c6e-1c6981324ce5"

print("=" * 50)
print("🐝 HIVE215 - Full Feature Gates Test")
print("=" * 50)
print()

# 1. Initial Status
print("📊 1. Initial Status (Free Plan):")
result = client.predict(user_id=user_id, api_name="/refresh_status")
print(f"   Plan: {result['plan']}")
print(f"   Minutes: {result['minutes_used']}/{result['minutes_limit']}")
print(f"   Voice Clones: {result['voice_clones_count']}")
print()

# 2. Test Chat on Free
print("🎤 2. Test Chat (5 minutes):")
result = client.predict(user_id=user_id, minutes=5, api_name="/handle_chat")
print(f"   {result[0]}")
print()

# 3. Test Voice Clone on Free (should fail)
print("🎙️ 3. Test Voice Clone (Free - should fail):")
result = client.predict(user_id=user_id, api_name="/handle_voice_clone")
status = "❌ Blocked" if "Blocked" in result[0] else "✅ Allowed"
print(f"   {status}")
print()

# 4. Upgrade to Starter
print("⬆️ 4. Upgrading to Starter Plan...")
# Note: You may need to set your admin API key here
result = client.predict(
    user_id=user_id,
    plan="starter",
    api_key="your-admin-key",  # Replace with actual key or leave as-is
    api_name="/handle_upgrade"
)
print(f"   {result}")
print()

# 5. Check new limits
print("📊 5. New Status (Starter Plan):")
result = client.predict(user_id=user_id, api_name="/refresh_status")
print(f"   Plan: {result['plan']}")
print(f"   Minutes: {result['minutes_used']}/{result['minutes_limit']}")
print(f"   Voice Clones Limit: Should be 3")
print()

# 6. Test Voice Clone on Starter (should work)
print("🎙️ 6. Test Voice Clone (Starter - should work):")
result = client.predict(user_id=user_id, api_name="/handle_voice_clone")
status = "✅ Allowed" if "successful" in result[0].lower() else "❌ Blocked"
print(f"   {status}")
print()

# 7. Test high minutes on Starter
print("🎤 7. Test 1000 minutes (Starter limit is 2000):")
result = client.predict(user_id=user_id, feature="max_minutes", amount=1000, api_name="/handle_feature_check")
print(f"   {result}")
print()

# 8. Test exceeding Starter limit
print("🎤 8. Test 3000 minutes (exceeds Starter limit):")
result = client.predict(user_id=user_id, feature="max_minutes", amount=3000, api_name="/handle_feature_check")
print(f"   {result}")
print()

# 9. Upgrade to Pro
print("⬆️ 9. Upgrading to Pro Plan...")
result = client.predict(
    user_id=user_id,
    plan="pro",
    api_key="your-admin-key",
    api_name="/handle_upgrade"
)
print(f"   {result}")
print()

# 10. Final Status
print("📊 10. Final Status (Pro Plan):")
result = client.predict(user_id=user_id, api_name="/refresh_status")
print(f"   Plan: {result['plan']}")
print(f"   Minutes Limit: {result['minutes_limit']} (should be 10000)")
print()

print("=" * 50)
print("✅ Full Test Complete!")
print("=" * 50)
