from gradio_client import Client

client = Client("http://localhost:7860/")
user_id = "ea97ae74-a597-4dc8-9c6e-1c6981324ce5"

print("=" * 50)
print("HIVE215 - Full Feature Gates Test")
print("=" * 50)
print()

# 1. Initial Status
print("1. Initial Status:")
result = client.predict(user_id=user_id, api_name="/refresh_status")
print(f"   Plan: {result['plan']}")
print(f"   Minutes: {result['minutes_used']}/{result['minutes_limit']}")
print()

# 2. Test Chat
print("2. Test Chat (5 minutes):")
result = client.predict(user_id=user_id, minutes=5, api_name="/handle_chat")
print(f"   {result[0]}")
print()

# 3. Test Voice Clone (Free - should fail)
print("3. Test Voice Clone (should fail on Free):")
result = client.predict(user_id=user_id, api_name="/handle_voice_clone")
print(f"   {'BLOCKED' if 'Blocked' in result[0] else 'ALLOWED'}")
print()

# 4. Upgrade to Starter
print("4. Upgrading to Starter...")
result = client.predict(user_id=user_id, plan="starter", api_key="admin", api_name="/handle_upgrade")
print(f"   {result}")
print()

# 5. New Status
print("5. Starter Status:")
result = client.predict(user_id=user_id, api_name="/refresh_status")
print(f"   Plan: {result['plan']}")
print(f"   Minutes Limit: {result['minutes_limit']} (should be 2000)")
print()

# 6. Test Voice Clone (Starter - should work)
print("6. Test Voice Clone (should work on Starter):")
result = client.predict(user_id=user_id, api_name="/handle_voice_clone")
print(f"   {'ALLOWED' if 'successful' in result[0].lower() else 'BLOCKED'}")
print()

# 7. Upgrade to Pro
print("7. Upgrading to Pro...")
result = client.predict(user_id=user_id, plan="pro", api_key="admin", api_name="/handle_upgrade")
print(f"   {result}")
print()

# 8. Final Status
print("8. Pro Status:")
result = client.predict(user_id=user_id, api_name="/refresh_status")
print(f"   Plan: {result['plan']}")
print(f"   Minutes Limit: {result['minutes_limit']} (should be 10000)")
print()

print("=" * 50)
print("Test Complete!")
print("=" * 50)