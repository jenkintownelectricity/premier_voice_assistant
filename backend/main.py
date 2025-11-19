"""
Premier Voice Assistant - FastAPI Backend
Orchestrates STT → Claude → TTS with Supabase database integration
Designed for mobile apps (iOS/Android)
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import io
import time
import logging
import os
from datetime import datetime

from backend.supabase_client import get_supabase, SupabaseManager
from backend.feature_gates import get_feature_gate, FeatureGateError
from backend.stripe_payments import get_stripe_payments, handle_webhook_event

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Premier Voice Assistant API",
    description="Voice AI backend for mobile apps with STT, LLM, and TTS",
    version="0.2.0"
)

# CORS configuration for mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for your mobile app domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response validation
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    voice: Optional[str] = "fabio"
    user_id: Optional[str] = None


class SpeakRequest(BaseModel):
    text: str
    voice: Optional[str] = "fabio"


class UserPreferencesUpdate(BaseModel):
    preferred_voice: Optional[str] = None
    conversation_style: Optional[str] = None
    language: Optional[str] = None


class AdminUpgradeRequest(BaseModel):
    user_id: str
    plan_name: str  # 'free', 'starter', 'pro', 'enterprise'


class AdminResetUsageRequest(BaseModel):
    user_id: str
    reset_minutes: bool = True
    reset_conversations: bool = False
    reset_voice_clones: bool = False


class CreateCheckoutRequest(BaseModel):
    plan_name: str  # 'starter', 'pro', 'enterprise'
    success_url: str
    cancel_url: str


class CreatePortalRequest(BaseModel):
    return_url: str


class VoiceAssistant:
    """
    Main voice assistant orchestrator with Supabase integration.
    """

    def __init__(self):
        self.modal_initialized = False
        self.stt = None
        self.tts = None
        self.anthropic_client = None
        self.supabase = get_supabase()

    def initialize_modal(self):
        """Initialize Modal clients (lazy loading)"""
        if self.modal_initialized:
            return

        try:
            import modal

            # Import Modal apps
            from modal_deployment.whisper_stt import WhisperSTT
            from modal_deployment.coqui_tts import CoquiTTS

            self.stt = WhisperSTT()
            self.tts = CoquiTTS()
            self.modal_initialized = True

            logger.info("Modal services initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Modal: {e}")
            raise

    def initialize_claude(self):
        """Initialize Claude API client"""
        if self.anthropic_client:
            return

        try:
            from anthropic import Anthropic

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")

            self.anthropic_client = Anthropic(api_key=api_key)
            logger.info("Claude API initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Claude: {e}")
            raise

    def transcribe_audio(self, audio_bytes: bytes, user_id: str = None) -> dict:
        """
        Transcribe audio to text using Whisper.
        """
        self.initialize_modal()

        start = time.time()
        result = self.stt.transcribe.remote(audio_bytes)
        latency_ms = int((time.time() - start) * 1000)

        # Log metrics
        if user_id:
            self.supabase.log_usage_metric(
                user_id=user_id,
                event_type="transcribe",
                stt_latency_ms=latency_ms,
                audio_duration_seconds=result.get('duration'),
            )

        return result

    def generate_response(
        self,
        user_message: str,
        conversation_id: str = None,
        user_id: str = None,
        conversation_style: str = "professional",
    ) -> str:
        """
        Generate AI response using Claude with conversation history from Supabase.
        """
        self.initialize_claude()

        # Build system prompt
        style_prompts = {
            "professional": "You are a professional, courteous AI assistant.",
            "casual": "You are a friendly, casual AI assistant.",
            "technical": "You are a technical expert AI assistant.",
        }

        system_prompt = f"""{style_prompts.get(conversation_style, style_prompts['professional'])}

Your role:
- Provide helpful, accurate responses
- Keep responses SHORT - 1-2 sentences maximum (this is voice conversation)
- Be natural and conversational
- If you don't know something, say so honestly
"""

        # Get conversation history from Supabase if conversation_id provided
        messages = []
        if conversation_id:
            history = self.supabase.get_conversation_messages(conversation_id, limit=10)
            for msg in history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message,
        })

        try:
            start = time.time()

            # Call Claude API
            response = self.anthropic_client.messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=int(os.getenv("MAX_TOKENS", "150")),
                temperature=float(os.getenv("TEMPERATURE", "0.7")),
                system=system_prompt,
                messages=messages,
            )

            ai_text = response.content[0].text
            latency_ms = int((time.time() - start) * 1000)
            tokens = response.usage.output_tokens

            # Log metrics
            if user_id:
                self.supabase.log_usage_metric(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    event_type="generate",
                    llm_latency_ms=latency_ms,
                    tokens_used=tokens,
                )

            # Save message to conversation
            if conversation_id:
                self.supabase.add_message(conversation_id, "user", user_message)
                self.supabase.add_message(conversation_id, "assistant", ai_text)

            return ai_text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            if user_id:
                self.supabase.log_usage_metric(
                    user_id=user_id,
                    event_type="generate",
                    error=str(e),
                )
            return "I apologize, I'm having trouble processing that right now."

    def synthesize_speech(
        self, text: str, voice: str = "fabio", user_id: str = None
    ) -> bytes:
        """
        Synthesize text to speech using Coqui TTS.
        """
        self.initialize_modal()

        start = time.time()
        audio = self.tts.synthesize.remote(text, voice)
        latency_ms = int((time.time() - start) * 1000)

        # Log metrics
        if user_id:
            self.supabase.log_usage_metric(
                user_id=user_id,
                event_type="synthesize",
                tts_latency_ms=latency_ms,
            )

        return audio

    def process_voice_input(
        self,
        audio_bytes: bytes,
        user_id: str,
        conversation_id: str = None,
        voice: str = "fabio",
    ) -> dict:
        """
        End-to-end voice processing pipeline with Supabase logging.
        """
        start_time = time.time()

        # Get user profile for preferences
        profile = self.supabase.get_or_create_user_profile(user_id)
        voice = voice or profile.get("preferred_voice", "fabio")
        conversation_style = profile.get("conversation_style", "professional")

        # Create conversation if needed
        if not conversation_id:
            conversation = self.supabase.create_conversation(
                user_id, title=f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            conversation_id = conversation["id"]

        # Step 1: STT
        stt_start = time.time()
        transcription = self.transcribe_audio(audio_bytes, user_id)
        stt_latency = int((time.time() - stt_start) * 1000)
        user_text = transcription['text']

        logger.info(f"User said: {user_text}")

        # Step 2: LLM
        llm_start = time.time()
        ai_response = self.generate_response(
            user_text, conversation_id, user_id, conversation_style
        )
        llm_latency = int((time.time() - llm_start) * 1000)

        logger.info(f"AI responding: {ai_response}")

        # Step 3: TTS
        tts_start = time.time()
        audio_response = self.synthesize_speech(ai_response, voice, user_id)
        tts_latency = int((time.time() - tts_start) * 1000)

        # Total metrics
        total_latency = int((time.time() - start_time) * 1000)

        # Log complete pipeline metrics
        self.supabase.log_usage_metric(
            user_id=user_id,
            conversation_id=conversation_id,
            event_type="chat_complete",
            stt_latency_ms=stt_latency,
            llm_latency_ms=llm_latency,
            tts_latency_ms=tts_latency,
            total_latency_ms=total_latency,
        )

        logger.info(
            f"Pipeline complete - STT: {stt_latency}ms, "
            f"LLM: {llm_latency}ms, TTS: {tts_latency}ms, "
            f"Total: {total_latency}ms"
        )

        return {
            "conversation_id": conversation_id,
            "user_text": user_text,
            "ai_text": ai_response,
            "audio_response": audio_response,
            "metrics": {
                "stt_latency_ms": stt_latency,
                "llm_latency_ms": llm_latency,
                "tts_latency_ms": tts_latency,
                "total_latency_ms": total_latency,
            },
        }


# Global assistant instance
assistant = VoiceAssistant()


# Dependency for getting Supabase client
def get_db() -> SupabaseManager:
    return get_supabase()


# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Premier Voice Assistant",
        "version": "0.2.0",
    }


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Transcribe audio to text.

    Headers:
        X-User-ID: Optional user ID for metrics
    """
    try:
        audio_bytes = await audio.read()
        result = assistant.transcribe_audio(audio_bytes, user_id)

        return {
            "success": True,
            "text": result['text'],
            "duration": result.get('duration'),
            "processing_time": result.get('processing_time'),
        }

    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/speak")
async def speak(
    request: SpeakRequest,
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Convert text to speech.

    Returns WAV audio stream.
    """
    try:
        audio_bytes = assistant.synthesize_speech(
            request.text, request.voice, user_id
        )

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=response.wav"},
        )

    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(
    audio: UploadFile = File(...),
    user_id: str = Header(..., alias="X-User-ID"),
    conversation_id: Optional[str] = Header(None, alias="X-Conversation-ID"),
    voice: Optional[str] = "fabio",
):
    """
    Full voice conversation turn: audio → text → AI → audio.

    Headers:
        X-User-ID: Required user ID
        X-Conversation-ID: Optional conversation to continue
    """
    try:
        # Check feature gate - assume ~1 minute per conversation
        feature_gate = get_feature_gate()
        try:
            feature_gate.enforce_feature(user_id, "max_minutes", 1)
        except FeatureGateError as e:
            raise HTTPException(status_code=402, detail=e.message)

        audio_bytes = await audio.read()

        result = assistant.process_voice_input(
            audio_bytes=audio_bytes,
            user_id=user_id,
            conversation_id=conversation_id,
            voice=voice,
        )

        # Track actual usage (based on audio duration)
        # Estimate: ~60 seconds = 1 minute
        duration_seconds = result.get('audio_duration_seconds', 60)
        minutes_used = max(1, int(duration_seconds / 60))

        feature_gate.increment_usage(
            user_id=user_id,
            minutes=minutes_used,
            metadata={
                "conversation_id": result['conversation_id'],
                "total_latency_ms": result['metrics']['total_latency_ms'],
            }
        )

        # Return audio response directly
        return StreamingResponse(
            io.BytesIO(result['audio_response']),
            media_type="audio/wav",
            headers={
                "X-Conversation-ID": result['conversation_id'],
                "X-User-Text": result['user_text'],
                "X-AI-Text": result['ai_text'],
                "X-STT-Latency": str(result['metrics']['stt_latency_ms']),
                "X-LLM-Latency": str(result['metrics']['llm_latency_ms']),
                "X-TTS-Latency": str(result['metrics']['tts_latency_ms']),
                "X-Total-Latency": str(result['metrics']['total_latency_ms']),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clone-voice")
async def clone_voice(
    voice_name: str,
    display_name: str,
    audio: UploadFile = File(...),
    user_id: str = Header(..., alias="X-User-ID"),
    is_public: bool = False,
    db: SupabaseManager = Depends(get_db),
):
    """
    Clone a new voice from reference audio.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        # Check if user's plan allows custom voices
        feature_gate = get_feature_gate()
        from backend.feature_gates import get_plan_features

        plan = feature_gate.get_user_plan(user_id)
        plan_name = plan.get("plan_name", "free") if plan else "free"
        plan_features = get_plan_features(plan_name)

        if not plan_features.get("custom_voices", False):
            raise HTTPException(
                status_code=402,
                detail="Custom voices not available on your plan. Upgrade to Starter or higher."
            )

        # Check voice clone limit
        try:
            feature_gate.enforce_feature(user_id, "max_voice_clones", 1)
        except FeatureGateError as e:
            raise HTTPException(status_code=402, detail=e.message)

        audio_bytes = await audio.read()

        # Upload to Supabase Storage
        file_path = f"{user_id}/{voice_name}.wav"
        audio_url = db.upload_audio("voice-clones", file_path, audio_bytes)

        # Clone voice on Modal
        assistant.initialize_modal()
        clone_result = assistant.tts.clone_voice.remote(voice_name, audio_bytes)

        # Save to database
        voice_clone = db.create_voice_clone(
            user_id=user_id,
            voice_name=voice_name,
            display_name=display_name,
            reference_audio_url=audio_url,
            sample_duration=clone_result.get('duration'),
            modal_voice_id=voice_name,
            is_public=is_public,
        )

        return {
            "success": True,
            "voice_clone": voice_clone,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice cloning error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations")
async def get_conversations(
    user_id: str = Header(..., alias="X-User-ID"),
    limit: int = 20,
    db: SupabaseManager = Depends(get_db),
):
    """
    Get user's conversation history.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        conversations = db.get_user_conversations(user_id, limit)
        return {"conversations": conversations}

    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    limit: int = 50,
    db: SupabaseManager = Depends(get_db),
):
    """Get messages for a conversation."""
    try:
        # Verify user owns this conversation
        conversation = db.get_conversation(conversation_id)
        if not conversation or conversation['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        messages = db.get_conversation_messages(conversation_id, limit)
        return {"messages": messages}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profile")
async def get_profile(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Get user profile."""
    try:
        profile = db.get_or_create_user_profile(user_id)
        return {"profile": profile}

    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/profile")
async def update_profile(
    updates: UserPreferencesUpdate,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Update user preferences."""
    try:
        profile = db.update_user_preferences(
            user_id=user_id,
            preferred_voice=updates.preferred_voice,
            conversation_style=updates.conversation_style,
            language=updates.language,
        )
        return {"profile": profile}

    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voice-clones")
async def get_voice_clones(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Get user's voice clones."""
    try:
        clones = db.get_user_voice_clones(user_id)
        return {"voice_clones": clones}

    except Exception as e:
        logger.error(f"Error getting voice clones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUBSCRIPTION & USAGE ROUTES
# ============================================================================

@app.get("/subscription")
async def get_subscription(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get user's current subscription plan.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        # Get subscription with plan details
        result = db.client.table("va_user_subscriptions").select(
            "*, va_subscription_plans(*)"
        ).eq("user_id", user_id).eq("status", "active").execute()

        if not result.data:
            return {
                "subscription": None,
                "message": "No active subscription found"
            }

        subscription = result.data[0]
        plan = subscription.get("va_subscription_plans", {})

        return {
            "subscription": {
                "plan_name": plan.get("plan_name"),
                "display_name": plan.get("display_name"),
                "price_cents": plan.get("price_cents", 0),
                "status": subscription.get("status"),
                "current_period_start": subscription.get("current_period_start"),
                "current_period_end": subscription.get("current_period_end")
            }
        }

    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/usage")
async def get_usage(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get user's current usage statistics.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        feature_gate = get_feature_gate()
        usage = feature_gate.get_user_usage(user_id)

        if not usage:
            return {
                "usage": {
                    "minutes_used": 0,
                    "conversations_count": 0,
                    "voice_clones_count": 0,
                    "assistants_count": 0
                }
            }

        return {"usage": usage}

    except Exception as e:
        logger.error(f"Error getting usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feature-limits")
async def get_feature_limits(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get all feature limits for user's current plan.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        feature_gate = get_feature_gate()
        plan = feature_gate.get_user_plan(user_id)

        if not plan:
            return {
                "plan": "none",
                "limits": {}
            }

        plan_name = plan.get("plan_name", "free")

        # Get all features for this plan
        from backend.feature_gates import get_plan_features
        features = get_plan_features(plan_name)

        # Get current usage
        usage = feature_gate.get_user_usage(user_id) or {}

        return {
            "plan": plan_name,
            "display_name": plan.get("display_name", plan_name.title()),
            "limits": features,
            "current_usage": {
                "minutes_used": usage.get("minutes_used", 0),
                "assistants_count": usage.get("assistants_count", 0),
                "voice_clones_count": usage.get("voice_clones_count", 0)
            }
        }

    except Exception as e:
        logger.error(f"Error getting feature limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.post("/admin/upgrade-user")
async def admin_upgrade_user(
    request: AdminUpgradeRequest,
    admin_key: str = Header(..., alias="X-Admin-Key"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Upgrade a user to a different subscription plan.

    Headers:
        X-Admin-Key: Required admin API key

    Body:
        user_id: User UUID to upgrade
        plan_name: Target plan ('free', 'starter', 'pro', 'enterprise')
    """
    try:
        # Validate admin key
        expected_key = os.getenv("ADMIN_API_KEY", "admin-secret-key")
        if admin_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        # Validate plan name
        valid_plans = ['free', 'starter', 'pro', 'enterprise']
        if request.plan_name not in valid_plans:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid plan. Must be one of: {', '.join(valid_plans)}"
            )

        # Get plan ID
        plan_result = db.client.table("va_subscription_plans").select("id, display_name").eq(
            "plan_name", request.plan_name
        ).execute()

        if not plan_result.data:
            raise HTTPException(status_code=404, detail=f"Plan '{request.plan_name}' not found")

        plan = plan_result.data[0]

        # Check if user has existing subscription
        sub_result = db.client.table("va_user_subscriptions").select("id").eq(
            "user_id", request.user_id
        ).eq("status", "active").execute()

        if sub_result.data:
            # Update existing subscription
            db.client.table("va_user_subscriptions").update({
                "plan_id": plan["id"],
                "updated_at": "now()"
            }).eq("user_id", request.user_id).eq("status", "active").execute()

            logger.info(f"Upgraded user {request.user_id} to {request.plan_name}")
        else:
            # Create new subscription
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            period_end = now + timedelta(days=30)

            db.client.table("va_user_subscriptions").insert({
                "user_id": request.user_id,
                "plan_id": plan["id"],
                "status": "active",
                "current_period_start": now.isoformat(),
                "current_period_end": period_end.isoformat()
            }).execute()

            logger.info(f"Created new {request.plan_name} subscription for user {request.user_id}")

        return {
            "success": True,
            "user_id": request.user_id,
            "plan": request.plan_name,
            "display_name": plan["display_name"],
            "message": f"User upgraded to {plan['display_name']} plan"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upgrading user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/user-subscription/{user_id}")
async def admin_get_user_subscription(
    user_id: str,
    admin_key: str = Header(..., alias="X-Admin-Key"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get a user's current subscription details.

    Headers:
        X-Admin-Key: Required admin API key
    """
    try:
        # Validate admin key
        expected_key = os.getenv("ADMIN_API_KEY", "admin-secret-key")
        if admin_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        # Get subscription with plan details
        result = db.client.table("va_user_subscriptions").select(
            "*, va_subscription_plans(*)"
        ).eq("user_id", user_id).eq("status", "active").execute()

        if not result.data:
            return {
                "user_id": user_id,
                "subscription": None,
                "message": "No active subscription found"
            }

        subscription = result.data[0]
        plan = subscription.get("va_subscription_plans", {})

        return {
            "user_id": user_id,
            "subscription": {
                "plan_name": plan.get("plan_name"),
                "display_name": plan.get("display_name"),
                "status": subscription.get("status"),
                "current_period_start": subscription.get("current_period_start"),
                "current_period_end": subscription.get("current_period_end")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/reset-usage")
async def admin_reset_usage(
    request: AdminResetUsageRequest,
    admin_key: str = Header(..., alias="X-Admin-Key"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Reset usage counters for a user (for new billing period).

    Headers:
        X-Admin-Key: Required admin API key

    Body:
        user_id: User UUID
        reset_minutes: Reset minutes_used to 0 (default: True)
        reset_conversations: Reset conversations_count to 0 (default: False)
        reset_voice_clones: Reset voice_clones_count to 0 (default: False)
    """
    try:
        # Validate admin key
        expected_key = os.getenv("ADMIN_API_KEY", "admin-secret-key")
        if admin_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        # Build update dict
        updates = {}
        reset_fields = []

        if request.reset_minutes:
            updates["minutes_used"] = 0
            reset_fields.append("minutes")

        if request.reset_conversations:
            updates["conversations_count"] = 0
            reset_fields.append("conversations")

        if request.reset_voice_clones:
            updates["voice_clones_count"] = 0
            reset_fields.append("voice_clones")

        if not updates:
            return {
                "success": False,
                "message": "No fields selected for reset"
            }

        # Get current billing period
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Update or create usage record for current period
        existing = db.client.table("va_usage_tracking").select("id").eq(
            "user_id", request.user_id
        ).gte("period_start", period_start.isoformat()).execute()

        if existing.data:
            # Update existing record
            db.client.table("va_usage_tracking").update(updates).eq(
                "id", existing.data[0]["id"]
            ).execute()
        else:
            # Create new record with reset values
            updates["user_id"] = request.user_id
            updates["period_start"] = period_start.isoformat()
            updates["period_end"] = (period_start + timedelta(days=30)).isoformat()
            db.client.table("va_usage_tracking").insert(updates).execute()

        logger.info(f"Reset usage for user {request.user_id}: {', '.join(reset_fields)}")

        return {
            "success": True,
            "user_id": request.user_id,
            "reset_fields": reset_fields,
            "message": f"Reset {', '.join(reset_fields)} for user"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/start-billing-period")
async def admin_start_billing_period(
    user_id: str,
    admin_key: str = Header(..., alias="X-Admin-Key"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Start a new billing period for a user (resets all usage).

    Headers:
        X-Admin-Key: Required admin API key

    Query:
        user_id: User UUID
    """
    try:
        # Validate admin key
        expected_key = os.getenv("ADMIN_API_KEY", "admin-secret-key")
        if admin_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        from datetime import datetime, timedelta
        now = datetime.utcnow()
        period_end = now + timedelta(days=30)

        # Create new usage tracking record
        new_usage = db.client.table("va_usage_tracking").insert({
            "user_id": user_id,
            "period_start": now.isoformat(),
            "period_end": period_end.isoformat(),
            "minutes_used": 0,
            "conversations_count": 0,
            "voice_clones_count": 0,
            "assistants_count": 0
        }).execute()

        # Update subscription period
        db.client.table("va_user_subscriptions").update({
            "current_period_start": now.isoformat(),
            "current_period_end": period_end.isoformat()
        }).eq("user_id", user_id).eq("status", "active").execute()

        logger.info(f"Started new billing period for user {user_id}")

        return {
            "success": True,
            "user_id": user_id,
            "period_start": now.isoformat(),
            "period_end": period_end.isoformat(),
            "message": "New billing period started with reset usage"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting billing period: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STRIPE PAYMENT ROUTES
# ============================================================================

@app.post("/payments/create-checkout")
async def create_checkout_session(
    request: CreateCheckoutRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Create a Stripe Checkout session for subscription upgrade.

    Headers:
        X-User-ID: Required user ID

    Body:
        plan_name: Plan to subscribe to ('starter', 'pro', 'enterprise')
        success_url: URL to redirect on success
        cancel_url: URL to redirect on cancel
    """
    try:
        stripe = get_stripe_payments()

        # Get user profile for email
        profile = db.get_or_create_user_profile(user_id)
        email = profile.get("email", f"{user_id}@placeholder.com")

        # Get or create Stripe customer
        customer_id = profile.get("stripe_customer_id")
        if not customer_id:
            customer_id = stripe.create_customer(
                user_id=user_id,
                email=email,
                name=profile.get("display_name")
            )
            if customer_id:
                # Save customer ID to profile
                db.client.table("va_user_profiles").update({
                    "stripe_customer_id": customer_id
                }).eq("user_id", user_id).execute()

        if not customer_id:
            raise HTTPException(status_code=500, detail="Failed to create Stripe customer")

        # Create checkout session
        session = stripe.create_checkout_session(
            user_id=user_id,
            customer_id=customer_id,
            plan_name=request.plan_name,
            success_url=request.success_url,
            cancel_url=request.cancel_url
        )

        if not session:
            raise HTTPException(status_code=500, detail="Failed to create checkout session")

        return session

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/payments/create-portal")
async def create_portal_session(
    request: CreatePortalRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session for managing subscription.

    Headers:
        X-User-ID: Required user ID

    Body:
        return_url: URL to return to after portal
    """
    try:
        stripe = get_stripe_payments()

        # Get user's Stripe customer ID
        profile = db.get_or_create_user_profile(user_id)
        customer_id = profile.get("stripe_customer_id")

        if not customer_id:
            raise HTTPException(
                status_code=400,
                detail="No payment method on file. Please subscribe first."
            )

        # Create portal session
        portal_url = stripe.create_portal_session(
            customer_id=customer_id,
            return_url=request.return_url
        )

        if not portal_url:
            raise HTTPException(status_code=500, detail="Failed to create portal session")

        return {"url": portal_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/payments/webhook")
async def stripe_webhook(
    request: Request,
):
    """
    Handle Stripe webhook events.

    This endpoint receives events from Stripe for subscription updates,
    payment success/failure, etc.
    """
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")

        result = handle_webhook_event(payload, sig_header)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        # Process the event result
        event = result.get("event")
        db = get_supabase()

        if event == "checkout_completed":
            # Upgrade user to new plan
            user_id = result.get("user_id")
            plan_name = result.get("plan_name")
            subscription_id = result.get("subscription_id")

            if user_id and plan_name:
                # Get plan ID
                plan_result = db.client.table("va_subscription_plans").select("id").eq(
                    "plan_name", plan_name
                ).execute()

                if plan_result.data:
                    plan_id = plan_result.data[0]["id"]

                    # Update or create subscription
                    db.client.table("va_user_subscriptions").upsert({
                        "user_id": user_id,
                        "plan_id": plan_id,
                        "status": "active",
                        "stripe_subscription_id": subscription_id,
                        "updated_at": datetime.utcnow().isoformat()
                    }, on_conflict="user_id").execute()

                    logger.info(f"Activated {plan_name} subscription for user {user_id}")

        elif event == "payment_succeeded":
            # Update billing period and reset usage
            subscription_id = result.get("subscription_id")
            period_start = result.get("period_start")
            period_end = result.get("period_end")

            if subscription_id:
                # Find user by subscription ID
                sub_result = db.client.table("va_user_subscriptions").select("user_id").eq(
                    "stripe_subscription_id", subscription_id
                ).execute()

                if sub_result.data:
                    user_id = sub_result.data[0]["user_id"]

                    # Update subscription period
                    db.client.table("va_user_subscriptions").update({
                        "current_period_start": period_start,
                        "current_period_end": period_end
                    }).eq("stripe_subscription_id", subscription_id).execute()

                    # Create new usage tracking record (reset usage)
                    db.client.table("va_usage_tracking").insert({
                        "user_id": user_id,
                        "period_start": period_start,
                        "period_end": period_end,
                        "minutes_used": 0,
                        "conversations_count": 0,
                        "voice_clones_count": 0,
                        "assistants_count": 0
                    }).execute()

                    logger.info(f"Reset usage for new billing period: user {user_id}")

        elif event == "subscription_cancelled":
            # Downgrade to free plan
            subscription_id = result.get("subscription_id")

            if subscription_id:
                # Find and downgrade user
                sub_result = db.client.table("va_user_subscriptions").select("user_id").eq(
                    "stripe_subscription_id", subscription_id
                ).execute()

                if sub_result.data:
                    user_id = sub_result.data[0]["user_id"]

                    # Get free plan ID
                    free_plan = db.client.table("va_subscription_plans").select("id").eq(
                        "plan_name", "free"
                    ).execute()

                    if free_plan.data:
                        db.client.table("va_user_subscriptions").update({
                            "plan_id": free_plan.data[0]["id"],
                            "stripe_subscription_id": None,
                            "status": "active"
                        }).eq("user_id", user_id).execute()

                        logger.info(f"Downgraded user {user_id} to free plan")

        return {"received": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("Premier Voice Assistant - Starting FastAPI Server...")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET    /health                        - Health check")
    print("  POST   /transcribe                    - Audio → Text")
    print("  POST   /speak                         - Text → Audio")
    print("  POST   /chat                          - Full voice conversation (PROTECTED)")
    print("  POST   /clone-voice                   - Clone a new voice (PROTECTED)")
    print("  GET    /conversations                 - Get user conversations")
    print("  GET    /conversations/{id}/messages   - Get conversation messages")
    print("  GET    /profile                       - Get user profile")
    print("  PATCH  /profile                       - Update user profile")
    print("  GET    /voice-clones                  - Get user's voice clones")
    print("\nSubscription & Usage:")
    print("  GET    /subscription                  - Get user's subscription plan")
    print("  GET    /usage                         - Get user's usage statistics")
    print("  GET    /feature-limits                - Get user's feature limits")
    print("\nAdmin:")
    print("  POST   /admin/upgrade-user            - Upgrade user plan")
    print("  POST   /admin/reset-usage             - Reset usage counters")
    print("  POST   /admin/start-billing-period    - Start new billing period")
    print("  GET    /admin/user-subscription/{id}  - Get user subscription")
    print("\nPayments (Stripe):")
    print("  POST   /payments/create-checkout      - Create checkout session")
    print("  POST   /payments/create-portal        - Create customer portal")
    print("  POST   /payments/webhook              - Stripe webhook handler")
    print("\n" + "=" * 60)

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "true").lower() == "true",
    )
