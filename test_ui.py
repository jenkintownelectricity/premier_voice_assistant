#!/usr/bin/env python3
"""
Gradio Testing Interface for Premier Voice Assistant (HIVE215)
Quick UI to test subscription features and voice chat
"""
import os
import gradio as gr
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import backend components
from backend.feature_gates import FeatureGate, FeatureGateError

def get_subscription_info(user_id: str) -> dict:
    """Get subscription details for display"""
    try:
        # Get subscription via Supabase
        from supabase import create_client
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        )

        # Get subscription with plan details
        sub_result = supabase.table("va_user_subscriptions").select(
            "*, va_subscription_plans(*)"
        ).eq("user_id", user_id).eq("status", "active").execute()

        if not sub_result.data:
            return {
                "error": "No subscription found",
                "plan": "none",
                "status": "not found"
            }

        subscription = sub_result.data[0]
        plan = subscription.get("va_subscription_plans", {})

        # Get usage data
        usage_result = supabase.table("va_usage_tracking").select("*").eq(
            "user_id", user_id
        ).order("period_start", desc=True).limit(1).execute()

        usage = usage_result.data[0] if usage_result.data else {}

        minutes_used = usage.get("minutes_used", 0)

        # Get actual limit from plan features
        limit_result = supabase.rpc("va_get_feature_limit", {
            "p_user_id": user_id,
            "p_feature_key": "max_minutes"
        }).execute()

        minutes_limit = int(limit_result.data) if limit_result.data else 100
        usage_pct = (minutes_used / minutes_limit * 100) if minutes_limit > 0 else 0

        return {
            "plan": plan.get("plan_name", "unknown"),
            "display_name": plan.get("display_name", ""),
            "price": f"${plan.get('price_cents', 0) / 100:.2f}/mo",
            "status": subscription.get("status", "unknown"),
            "minutes_used": minutes_used,
            "minutes_limit": minutes_limit,
            "usage_percentage": round(usage_pct, 1),
            "days_remaining": 30,
            "assistants_count": usage.get("assistants_count", 0),
            "voice_clones_count": usage.get("voice_clones_count", 0)
        }
    except Exception as e:
        return {
            "error": str(e),
            "plan": "unknown",
            "status": "error"
        }

def check_feature_access(user_id: str, feature: str = "max_minutes", amount: int = 1) -> str:
    """Check if user can access a feature"""
    try:
        fg = FeatureGate()
        allowed, details = fg.check_feature(user_id, feature, amount)

        if allowed:
            return f"✅ Access Granted\n\nCurrent: {details['current_usage']}\nLimit: {details['limit_value']}\nRemaining: {details['remaining']}"
        else:
            return f"❌ Access Denied\n\nCurrent: {details['current_usage']}\nLimit: {details['limit_value']}\nRemaining: {details['remaining']}\n\n⚠️ Upgrade required!"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def simulate_chat(user_id: str, minutes_to_use: int = 1) -> tuple:
    """Simulate a chat request (without actual audio processing for now)"""
    try:
        fg = FeatureGate()

        # Check if user can use feature
        fg.enforce_feature(user_id, "max_minutes", minutes_to_use)

        # Simulate usage
        success = fg.increment_usage(user_id, minutes=minutes_to_use, metadata={"test": True})

        if success:
            sub_info = get_subscription_info(user_id)
            return (
                f"✅ Chat successful! Used {minutes_to_use} minute(s).",
                sub_info,
                "success"
            )
        else:
            return (
                "❌ Failed to track usage",
                get_subscription_info(user_id),
                "error"
            )

    except FeatureGateError as e:
        return (
            f"❌ Feature Gate Error:\n\n{e.message}\n\nFeature: {e.feature_key}\nCurrent: {e.current}\nLimit: {e.limit}",
            get_subscription_info(user_id),
            "error"
        )
    except Exception as e:
        return (
            f"❌ Error: {str(e)}",
            get_subscription_info(user_id),
            "error"
        )

def test_voice_clone(user_id: str) -> tuple:
    """Test voice clone feature gate"""
    try:
        fg = FeatureGate()
        fg.enforce_feature(user_id, "max_voice_clones", 1)

        return (
            "✅ Voice clone allowed!",
            get_subscription_info(user_id),
            "success"
        )
    except FeatureGateError as e:
        return (
            f"❌ Voice Clone Blocked:\n\n{e.message}\n\nCurrent: {e.current}\nLimit: {e.limit}",
            get_subscription_info(user_id),
            "error"
        )

# Create Gradio Interface
with gr.Blocks(
    title="HIVE215 Testing Interface",
    theme=gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="amber",
    )
) as demo:

    gr.Markdown("""
    # 🐝 HIVE215 - Premier Voice Assistant
    ### Testing Interface for Subscription & Feature Gates
    """)

    with gr.Row():
        user_id_input = gr.Textbox(
            label="Test User ID (UUID format)",
            value="00000000-0000-0000-0000-000000000001",
            placeholder="Enter user UUID to test"
        )
        refresh_btn = gr.Button("🔄 Refresh Status", size="sm")

    # Subscription Status Card
    with gr.Group():
        gr.Markdown("### 📊 Subscription Status")
        subscription_display = gr.JSON(label="Current Subscription & Usage")

    gr.Markdown("---")

    # Feature Testing Section
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🎤 Test Chat (Minutes)")
            minutes_input = gr.Slider(
                minimum=1,
                maximum=100,
                value=1,
                step=1,
                label="Minutes to Simulate"
            )
            chat_btn = gr.Button("Test Chat Request", variant="primary")
            chat_result = gr.Textbox(label="Result", lines=5)

        with gr.Column():
            gr.Markdown("### 🎙️ Test Voice Clone")
            clone_btn = gr.Button("Test Voice Clone", variant="secondary")
            clone_result = gr.Textbox(label="Result", lines=5)

    gr.Markdown("---")

    # Feature Check Section
    with gr.Group():
        gr.Markdown("### 🔍 Check Feature Access")
        with gr.Row():
            feature_select = gr.Dropdown(
                choices=["max_minutes", "max_assistants", "max_voice_clones", "custom_voices", "api_access"],
                value="max_minutes",
                label="Feature to Check"
            )
            amount_input = gr.Number(value=1, label="Amount Requested")
            check_btn = gr.Button("Check Access")

        feature_result = gr.Textbox(label="Access Check Result", lines=4)

    gr.Markdown("---")

    # Admin Section
    with gr.Accordion("⚙️ Admin Functions", open=False):
        gr.Markdown("### Admin Upgrade User")
        with gr.Row():
            admin_user_id = gr.Textbox(label="User ID", value="00000000-0000-0000-0000-000000000001")
            admin_plan = gr.Dropdown(
                choices=["free", "starter", "pro", "enterprise"],
                value="starter",
                label="New Plan"
            )
            admin_key = gr.Textbox(label="Admin API Key", type="password", placeholder="Required for upgrade")
        upgrade_btn = gr.Button("Upgrade User Plan")
        upgrade_result = gr.Textbox(label="Upgrade Result", lines=3)

    # Event Handlers
    def refresh_status(user_id):
        return get_subscription_info(user_id)

    def handle_chat(user_id, minutes):
        result_text, sub_info, status = simulate_chat(user_id, int(minutes))
        return result_text, sub_info

    def handle_voice_clone(user_id):
        result_text, sub_info, status = test_voice_clone(user_id)
        return result_text, sub_info

    def handle_feature_check(user_id, feature, amount):
        return check_feature_access(user_id, feature, int(amount))

    def handle_upgrade(user_id, plan, api_key):
        try:
            if not api_key:
                return "❌ Admin API key required"

            import requests

            # Call the admin upgrade API endpoint
            api_url = os.getenv("API_URL", "http://localhost:8000")
            response = requests.post(
                f"{api_url}/admin/upgrade-user",
                headers={"X-Admin-Key": api_key},
                json={"user_id": user_id, "plan_name": plan}
            )

            if response.status_code == 200:
                result = response.json()
                return f"✅ {result['message']}\n\nPlan: {result['display_name']}"
            elif response.status_code == 401:
                return "❌ Invalid admin API key"
            else:
                error = response.json().get("detail", "Unknown error")
                return f"❌ Error: {error}"

        except requests.exceptions.ConnectionError:
            return "❌ Cannot connect to API server. Make sure FastAPI is running on port 8000."
        except Exception as e:
            return f"❌ Error: {str(e)}"

    # Wire up events
    refresh_btn.click(refresh_status, inputs=[user_id_input], outputs=[subscription_display])
    chat_btn.click(handle_chat, inputs=[user_id_input, minutes_input], outputs=[chat_result, subscription_display])
    clone_btn.click(handle_voice_clone, inputs=[user_id_input], outputs=[clone_result, subscription_display])
    check_btn.click(handle_feature_check, inputs=[user_id_input, feature_select, amount_input], outputs=[feature_result])
    upgrade_btn.click(handle_upgrade, inputs=[admin_user_id, admin_plan, admin_key], outputs=[upgrade_result])

    # Load initial subscription on page load
    demo.load(refresh_status, inputs=[user_id_input], outputs=[subscription_display])

if __name__ == "__main__":
    print("=" * 60)
    print("🐝 HIVE215 Testing Interface")
    print("=" * 60)
    print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL', 'NOT SET')[:40]}...")
    print(f"Service Role Key: {'SET' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else 'NOT SET'}")
    print("=" * 60)

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,  # Create public shareable link
        show_error=True
    )
