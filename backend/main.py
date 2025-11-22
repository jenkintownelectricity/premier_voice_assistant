"""
Premier Voice Assistant - FastAPI Backend
Orchestrates STT → Claude → TTS with Supabase database integration
Designed for mobile apps (iOS/Android)
"""
# Load environment variables from .env file FIRST
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import io
import time
import logging
import os
import json
import asyncio
import base64
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

# Claude API Pricing (per million tokens) - as of 2025
# Source: https://www.anthropic.com/pricing
CLAUDE_PRICING = {
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,    # $3.00 per 1M input tokens
        "output": 15.00,  # $15.00 per 1M output tokens
    },
    "claude-3-5-sonnet-20240620": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
    },
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25,
    },
}

def calculate_claude_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the cost in cents for a Claude API call.

    Args:
        model: The Claude model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in cents (e.g., 0.05 = $0.0005)
    """
    # Get pricing for the model (default to Sonnet if not found)
    pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING["claude-3-5-sonnet-20241022"])

    # Calculate cost: (tokens / 1,000,000) * price_per_million
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost_dollars = input_cost + output_cost

    # Convert to cents
    return total_cost_dollars * 100

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


class RedeemCodeRequest(BaseModel):
    code: str


class CreateDiscountCodeRequest(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str  # 'percentage', 'fixed', 'minutes', 'upgrade'
    discount_value: int
    applicable_plan: Optional[str] = None
    max_uses: Optional[int] = None
    max_uses_per_user: int = 1
    valid_until: Optional[str] = None  # ISO format datetime


class AddBonusMinutesRequest(BaseModel):
    user_id: str
    minutes: int
    reason: Optional[str] = None


class CreateAssistantRequest(BaseModel):
    name: str
    system_prompt: str
    description: Optional[str] = None
    voice_id: Optional[str] = "default"
    model: Optional[str] = "claude-3-5-sonnet-20241022"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 150
    first_message: Optional[str] = None
    # Advanced latency optimization settings
    vad_sensitivity: Optional[float] = 0.5
    endpointing_ms: Optional[int] = 600
    enable_bargein: Optional[bool] = True
    streaming_chunks: Optional[bool] = True
    first_message_latency_ms: Optional[int] = 800
    turn_detection_mode: Optional[str] = "server_vad"


class UpdateAssistantRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    voice_id: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    first_message: Optional[str] = None
    is_active: Optional[bool] = None
    # Advanced latency optimization settings
    vad_sensitivity: Optional[float] = None
    endpointing_ms: Optional[int] = None
    enable_bargein: Optional[bool] = None
    streaming_chunks: Optional[bool] = None
    first_message_latency_ms: Optional[int] = None
    turn_detection_mode: Optional[str] = None


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
            model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=int(os.getenv("MAX_TOKENS", "150")),
                temperature=float(os.getenv("TEMPERATURE", "0.7")),
                system=system_prompt,
                messages=messages,
            )

            ai_text = response.content[0].text
            latency_ms = int((time.time() - start) * 1000)

            # Track token usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens

            # Calculate cost in cents
            cost_cents = calculate_claude_cost(model, input_tokens, output_tokens)

            # Log metrics with detailed token tracking
            if user_id:
                self.supabase.log_usage_metric(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    event_type="generate",
                    llm_latency_ms=latency_ms,
                    tokens_used=total_tokens,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_cents=cost_cents,
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


@app.get("/usage/analytics")
async def get_usage_analytics(
    user_id: str = Header(..., alias="X-User-ID"),
    days: int = 30,
    db: SupabaseManager = Depends(get_db),
):
    """
    Get detailed token usage and cost analytics for a user.

    Headers:
        X-User-ID: Required user ID

    Query Parameters:
        days: Number of days to analyze (default: 30)

    Returns:
        Token usage breakdown, costs, and trends
    """
    try:
        from datetime import datetime, timedelta

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Query usage metrics
        result = db.client.table("va_usage_metrics").select(
            "created_at, event_type, input_tokens, output_tokens, tokens_used, cost_cents, error"
        ).eq("user_id", user_id).gte(
            "created_at", start_date.isoformat()
        ).order("created_at", desc=False).execute()

        metrics = result.data

        # Aggregate statistics
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_cents = 0.0
        total_requests = 0
        total_errors = 0
        daily_usage = {}
        event_breakdown = {}
        error_types = {}

        for metric in metrics:
            # Track total tokens
            input_tokens = metric.get("input_tokens") or 0
            output_tokens = metric.get("output_tokens") or 0
            cost_cents = metric.get("cost_cents") or 0.0
            error = metric.get("error")

            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_cost_cents += cost_cents
            total_requests += 1

            # Track errors
            if error:
                total_errors += 1
                # Categorize error types
                error_category = error[:50] if len(error) > 50 else error  # First 50 chars
                error_types[error_category] = error_types.get(error_category, 0) + 1

            # Track by event type
            event_type = metric.get("event_type", "unknown")
            if event_type not in event_breakdown:
                event_breakdown[event_type] = {
                    "count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_cents": 0.0
                }
            event_breakdown[event_type]["count"] += 1
            event_breakdown[event_type]["input_tokens"] += input_tokens
            event_breakdown[event_type]["output_tokens"] += output_tokens
            event_breakdown[event_type]["cost_cents"] += cost_cents

            # Track daily usage for charts
            created_at = metric.get("created_at", "")
            if created_at:
                date_key = created_at[:10]  # YYYY-MM-DD
                if date_key not in daily_usage:
                    daily_usage[date_key] = {
                        "date": date_key,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost_cents": 0.0,
                        "requests": 0,
                        "errors": 0
                    }
                daily_usage[date_key]["input_tokens"] += input_tokens
                daily_usage[date_key]["output_tokens"] += output_tokens
                daily_usage[date_key]["cost_cents"] += cost_cents
                daily_usage[date_key]["requests"] += 1
                if error:
                    daily_usage[date_key]["errors"] += 1

        # Convert daily usage dict to sorted list
        daily_usage_list = sorted(daily_usage.values(), key=lambda x: x["date"])

        # Calculate error rate
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "totals": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "cost_cents": round(total_cost_cents, 4),
                "cost_dollars": round(total_cost_cents / 100, 6),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "success_rate": round(((total_requests - total_errors) / total_requests * 100), 2) if total_requests > 0 else 100
            },
            "averages": {
                "tokens_per_request": round((total_input_tokens + total_output_tokens) / total_requests, 2) if total_requests > 0 else 0,
                "cost_per_request_cents": round(total_cost_cents / total_requests, 4) if total_requests > 0 else 0,
                "requests_per_day": round(total_requests / days, 2) if days > 0 else 0,
                "error_rate": round(error_rate, 2)
            },
            "errors": {
                "total": total_errors,
                "rate": round(error_rate, 2),
                "by_type": dict(sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:10])  # Top 10 errors
            },
            "by_event_type": event_breakdown,
            "daily_usage": daily_usage_list
        }

    except Exception as e:
        logger.error(f"Error getting usage analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ASSISTANTS ROUTES
# ============================================================================

@app.get("/assistants")
async def list_assistants(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get user's AI assistants.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        result = db.client.table("va_assistants").select(
            "id, name, description, voice_id, model, is_active, created_at, updated_at"
        ).eq("user_id", user_id).order("created_at", desc=True).execute()

        # Get call counts for each assistant
        assistants = []
        for assistant in result.data:
            call_count = db.client.table("va_call_logs").select(
                "id", count="exact"
            ).eq("assistant_id", assistant["id"]).execute()

            assistant["call_count"] = call_count.count if call_count.count else 0
            assistants.append(assistant)

        return {"assistants": assistants}

    except Exception as e:
        logger.error(f"Error getting assistants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/assistants/{assistant_id}")
async def get_assistant(
    assistant_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get a single assistant's details.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        result = db.client.table("va_assistants").select("*").eq(
            "id", assistant_id
        ).eq("user_id", user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Assistant not found")

        return {"assistant": result.data[0]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assistant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/assistants")
async def create_assistant(
    request: CreateAssistantRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Create a new AI assistant.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        # Check assistant limit
        feature_gate = get_feature_gate()
        try:
            feature_gate.enforce_feature(user_id, "max_assistants", 1)
        except FeatureGateError as e:
            raise HTTPException(status_code=402, detail=e.message)

        # Create assistant
        assistant_data = {
            "user_id": user_id,
            "name": request.name,
            "description": request.description,
            "system_prompt": request.system_prompt,
            "voice_id": request.voice_id,
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "first_message": request.first_message,
            "is_active": True,
            # Advanced latency optimization settings
            "vad_sensitivity": request.vad_sensitivity,
            "endpointing_ms": request.endpointing_ms,
            "enable_bargein": request.enable_bargein,
            "streaming_chunks": request.streaming_chunks,
            "first_message_latency_ms": request.first_message_latency_ms,
            "turn_detection_mode": request.turn_detection_mode
        }

        result = db.client.table("va_assistants").insert(assistant_data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create assistant")

        logger.info(f"Created assistant {result.data[0]['id']} for user {user_id}")

        return {
            "success": True,
            "assistant": result.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating assistant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/assistants/{assistant_id}")
async def update_assistant(
    assistant_id: str,
    request: UpdateAssistantRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Update an assistant.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        # Verify ownership
        existing = db.client.table("va_assistants").select("id").eq(
            "id", assistant_id
        ).eq("user_id", user_id).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Assistant not found")

        # Build update dict
        updates = {}
        for field in ["name", "description", "system_prompt", "voice_id",
                      "model", "temperature", "max_tokens", "first_message", "is_active",
                      "vad_sensitivity", "endpointing_ms", "enable_bargein",
                      "streaming_chunks", "first_message_latency_ms", "turn_detection_mode"]:
            value = getattr(request, field)
            if value is not None:
                updates[field] = value

        if not updates:
            return {"success": True, "message": "No changes"}

        result = db.client.table("va_assistants").update(updates).eq(
            "id", assistant_id
        ).eq("user_id", user_id).execute()

        logger.info(f"Updated assistant {assistant_id}")

        return {
            "success": True,
            "assistant": result.data[0] if result.data else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assistant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/assistants/{assistant_id}")
async def delete_assistant(
    assistant_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Delete an assistant.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        result = db.client.table("va_assistants").delete().eq(
            "id", assistant_id
        ).eq("user_id", user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Assistant not found")

        logger.info(f"Deleted assistant {assistant_id}")

        return {"success": True, "message": "Assistant deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting assistant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CALL LOGS ROUTES
# ============================================================================

@app.get("/calls")
async def list_calls(
    user_id: str = Header(..., alias="X-User-ID"),
    limit: int = 50,
    offset: int = 0,
    assistant_id: Optional[str] = None,
    db: SupabaseManager = Depends(get_db),
):
    """
    Get user's call history.

    Headers:
        X-User-ID: Required user ID

    Query:
        limit: Number of calls to return (default 50)
        offset: Pagination offset (default 0)
        assistant_id: Filter by assistant (optional)
    """
    try:
        query = db.client.table("va_call_logs").select(
            "id, assistant_id, call_type, phone_number, status, started_at, "
            "ended_at, duration_seconds, cost_cents, summary, sentiment, ended_reason"
        ).eq("user_id", user_id)

        if assistant_id:
            query = query.eq("assistant_id", assistant_id)

        result = query.order("started_at", desc=True).range(
            offset, offset + limit - 1
        ).execute()

        # Get assistant names
        calls = []
        for call in result.data:
            if call.get("assistant_id"):
                assistant = db.client.table("va_assistants").select("name").eq(
                    "id", call["assistant_id"]
                ).execute()
                call["assistant_name"] = assistant.data[0]["name"] if assistant.data else "Deleted"
            else:
                call["assistant_name"] = "Unknown"
            calls.append(call)

        # Get total count
        count_query = db.client.table("va_call_logs").select(
            "id", count="exact"
        ).eq("user_id", user_id)
        if assistant_id:
            count_query = count_query.eq("assistant_id", assistant_id)
        total = count_query.execute()

        return {
            "calls": calls,
            "total": total.count if total.count else 0,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error getting calls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/calls/{call_id}")
async def get_call(
    call_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get a single call's details including transcript.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        result = db.client.table("va_call_logs").select("*").eq(
            "id", call_id
        ).eq("user_id", user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Call not found")

        call = result.data[0]

        # Get assistant name
        if call.get("assistant_id"):
            assistant = db.client.table("va_assistants").select("name").eq(
                "id", call["assistant_id"]
            ).execute()
            call["assistant_name"] = assistant.data[0]["name"] if assistant.data else "Deleted"
        else:
            call["assistant_name"] = "Unknown"

        return {"call": call}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/calls/stats/summary")
async def get_call_stats(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get call statistics summary.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        # Get all calls for stats
        result = db.client.table("va_call_logs").select(
            "duration_seconds, cost_cents, status, started_at"
        ).eq("user_id", user_id).execute()

        calls = result.data

        if not calls:
            return {
                "stats": {
                    "total_calls": 0,
                    "total_duration_seconds": 0,
                    "total_cost_cents": 0,
                    "avg_duration_seconds": 0,
                    "completed_calls": 0,
                    "failed_calls": 0,
                    "calls_today": 0,
                    "calls_this_week": 0,
                    "calls_this_month": 0
                }
            }

        from datetime import datetime, timedelta
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        total_duration = sum(c.get("duration_seconds", 0) or 0 for c in calls)
        total_cost = sum(c.get("cost_cents", 0) or 0 for c in calls)
        completed = sum(1 for c in calls if c.get("status") == "completed")
        failed = sum(1 for c in calls if c.get("status") == "failed")

        calls_today = 0
        calls_week = 0
        calls_month = 0

        for c in calls:
            started = c.get("started_at")
            if started:
                call_time = datetime.fromisoformat(started.replace("Z", "+00:00")).replace(tzinfo=None)
                if call_time >= today:
                    calls_today += 1
                if call_time >= week_ago:
                    calls_week += 1
                if call_time >= month_ago:
                    calls_month += 1

        return {
            "stats": {
                "total_calls": len(calls),
                "total_duration_seconds": total_duration,
                "total_cost_cents": total_cost,
                "avg_duration_seconds": int(total_duration / len(calls)) if calls else 0,
                "completed_calls": completed,
                "failed_calls": failed,
                "calls_today": calls_today,
                "calls_this_week": calls_week,
                "calls_this_month": calls_month
            }
        }

    except Exception as e:
        logger.error(f"Error getting call stats: {e}")
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


# ============================================================================
# DISCOUNT CODE ROUTES
# ============================================================================

@app.post("/codes/redeem")
async def redeem_discount_code(
    request: RedeemCodeRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Redeem a discount code.

    Headers:
        X-User-ID: Required user ID

    Body:
        code: Discount code to redeem
    """
    try:
        # Call the database function to redeem
        result = db.client.rpc(
            "va_redeem_discount_code",
            {
                "p_user_id": user_id,
                "p_code": request.code.upper()
            }
        ).execute()

        if not result.data:
            raise HTTPException(status_code=400, detail="Failed to process code")

        redemption_result = result.data

        if not redemption_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=redemption_result.get("error", "Invalid code")
            )

        logger.info(f"User {user_id} redeemed code {request.code}: {redemption_result.get('message')}")

        return redemption_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redeeming code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/codes")
async def create_discount_code(
    request: CreateDiscountCodeRequest,
    admin_key: str = Header(..., alias="X-Admin-Key"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Create a new discount code.

    Headers:
        X-Admin-Key: Required admin API key

    Body:
        code: Unique code string
        description: Optional description
        discount_type: 'percentage', 'fixed', 'minutes', 'upgrade'
        discount_value: Value based on type
        applicable_plan: Optional plan restriction
        max_uses: Optional max total uses
        max_uses_per_user: Max uses per user (default 1)
        valid_until: Optional expiry datetime (ISO format)
    """
    try:
        # Validate admin key
        expected_key = os.getenv("ADMIN_API_KEY", "admin-secret-key")
        if admin_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        # Validate discount type
        valid_types = ['percentage', 'fixed', 'minutes', 'upgrade']
        if request.discount_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid discount_type. Must be one of: {', '.join(valid_types)}"
            )

        # Create the code
        code_data = {
            "code": request.code.upper(),
            "description": request.description,
            "discount_type": request.discount_type,
            "discount_value": request.discount_value,
            "applicable_plan": request.applicable_plan,
            "max_uses": request.max_uses,
            "max_uses_per_user": request.max_uses_per_user,
            "valid_until": request.valid_until,
            "is_active": True
        }

        result = db.client.table("va_discount_codes").insert(code_data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create code")

        logger.info(f"Created discount code: {request.code}")

        return {
            "success": True,
            "code": result.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating discount code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/codes")
async def list_discount_codes(
    admin_key: str = Header(..., alias="X-Admin-Key"),
    active_only: bool = True,
    db: SupabaseManager = Depends(get_db),
):
    """
    List all discount codes.

    Headers:
        X-Admin-Key: Required admin API key

    Query:
        active_only: Only show active codes (default True)
    """
    try:
        # Validate admin key
        expected_key = os.getenv("ADMIN_API_KEY", "admin-secret-key")
        if admin_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        query = db.client.table("va_discount_codes").select("*")

        if active_only:
            query = query.eq("is_active", True)

        result = query.order("created_at", desc=True).execute()

        return {
            "codes": result.data,
            "count": len(result.data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing codes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/add-minutes")
async def add_bonus_minutes(
    request: AddBonusMinutesRequest,
    admin_key: str = Header(..., alias="X-Admin-Key"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Add bonus minutes to a user's account.

    Headers:
        X-Admin-Key: Required admin API key

    Body:
        user_id: User UUID
        minutes: Number of bonus minutes to add
        reason: Optional reason for the bonus
    """
    try:
        # Validate admin key
        expected_key = os.getenv("ADMIN_API_KEY", "admin-secret-key")
        if admin_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        if request.minutes <= 0:
            raise HTTPException(status_code=400, detail="Minutes must be positive")

        # Get current usage record
        usage_result = db.client.table("va_usage_tracking").select("*").eq(
            "user_id", request.user_id
        ).order("period_start", desc=True).limit(1).execute()

        if usage_result.data:
            # Update existing record
            current_bonus = usage_result.data[0].get("bonus_minutes", 0) or 0
            new_bonus = current_bonus + request.minutes

            db.client.table("va_usage_tracking").update({
                "bonus_minutes": new_bonus
            }).eq("id", usage_result.data[0]["id"]).execute()

            logger.info(f"Added {request.minutes} bonus minutes to user {request.user_id} (total: {new_bonus})")

            return {
                "success": True,
                "user_id": request.user_id,
                "minutes_added": request.minutes,
                "total_bonus_minutes": new_bonus,
                "reason": request.reason,
                "message": f"Added {request.minutes} bonus minutes"
            }
        else:
            # Create new usage record with bonus minutes
            from datetime import datetime, timedelta
            now = datetime.utcnow()

            db.client.table("va_usage_tracking").insert({
                "user_id": request.user_id,
                "period_start": now.isoformat(),
                "period_end": (now + timedelta(days=30)).isoformat(),
                "minutes_used": 0,
                "bonus_minutes": request.minutes
            }).execute()

            logger.info(f"Created usage record with {request.minutes} bonus minutes for user {request.user_id}")

            return {
                "success": True,
                "user_id": request.user_id,
                "minutes_added": request.minutes,
                "total_bonus_minutes": request.minutes,
                "reason": request.reason,
                "message": f"Added {request.minutes} bonus minutes"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding bonus minutes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/codes/{code}")
async def delete_discount_code(
    code: str,
    admin_key: str = Header(..., alias="X-Admin-Key"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Deactivate a discount code.

    Headers:
        X-Admin-Key: Required admin API key
    """
    try:
        # Validate admin key
        expected_key = os.getenv("ADMIN_API_KEY", "admin-secret-key")
        if admin_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        # Deactivate the code (soft delete)
        result = db.client.table("va_discount_codes").update({
            "is_active": False
        }).eq("code", code.upper()).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Code not found")

        logger.info(f"Deactivated discount code: {code}")

        return {
            "success": True,
            "message": f"Code {code} deactivated"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# WEBSOCKET VOICE STREAMING
# =====================================================

class VoiceCallSession:
    """Manages a single WebSocket voice call session."""

    def __init__(self, websocket: WebSocket, user_id: str, assistant_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.assistant_id = assistant_id
        self.call_id = None
        self.transcript = []
        self.is_speaking = False
        self.should_stop_tts = False
        self.audio_buffer = bytearray()
        self.db = get_supabase()

    async def start_call(self):
        """Initialize call log in database."""
        try:
            result = self.db.client.rpc(
                'va_create_call_log',
                {
                    'p_user_id': self.user_id,
                    'p_assistant_id': self.assistant_id,
                    'p_call_type': 'web'
                }
            ).execute()
            self.call_id = result.data
            logger.info(f"Started call {self.call_id} for user {self.user_id}")
            return self.call_id
        except Exception as e:
            logger.error(f"Failed to create call log: {e}")
            return None

    async def end_call(self, ended_reason: str = 'user_ended'):
        """End call and save final transcript."""
        if not self.call_id:
            return

        try:
            # Determine sentiment from transcript (simple heuristic)
            sentiment = 'neutral'
            if self.transcript:
                text = ' '.join([t['content'] for t in self.transcript])
                positive_words = ['thank', 'great', 'good', 'excellent', 'happy', 'love']
                negative_words = ['bad', 'terrible', 'hate', 'angry', 'frustrated', 'wrong']
                pos_count = sum(1 for w in positive_words if w in text.lower())
                neg_count = sum(1 for w in negative_words if w in text.lower())
                if pos_count > neg_count:
                    sentiment = 'positive'
                elif neg_count > pos_count:
                    sentiment = 'negative'

            self.db.client.rpc(
                'va_end_call',
                {
                    'p_call_id': self.call_id,
                    'p_transcript': json.dumps(self.transcript),
                    'p_summary': None,
                    'p_ended_reason': ended_reason,
                    'p_recording_url': None,
                    'p_sentiment': sentiment
                }
            ).execute()
            logger.info(f"Ended call {self.call_id}")
        except Exception as e:
            logger.error(f"Failed to end call: {e}")

    def add_to_transcript(self, role: str, content: str):
        """Add message to transcript."""
        self.transcript.append({
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        })


@app.websocket("/ws/voice/{assistant_id}")
async def websocket_voice_endpoint(
    websocket: WebSocket,
    assistant_id: str,
):
    """
    WebSocket endpoint for real-time voice streaming.

    Protocol:
    - Client sends: {"type": "auth", "user_id": "..."}
    - Client sends: {"type": "audio", "data": "<base64 audio>"}
    - Client sends: {"type": "end_call"}
    - Server sends: {"type": "ready", "call_id": "..."}
    - Server sends: {"type": "transcript", "role": "user"|"assistant", "content": "..."}
    - Server sends: {"type": "audio", "data": "<base64 audio>"}
    - Server sends: {"type": "speaking", "is_speaking": true|false}
    - Server sends: {"type": "error", "message": "..."}
    - Server sends: {"type": "call_ended", "reason": "..."}
    """
    await websocket.accept()
    session = None
    assistant = None

    try:
        # Wait for authentication
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        if auth_data.get('type') != 'auth' or not auth_data.get('user_id'):
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close()
            return

        user_id = auth_data['user_id']
        logger.info(f"WebSocket authenticated for user {user_id}")

        # Get assistant configuration
        db = get_supabase()
        assistant_result = db.client.table("va_assistants").select("*").eq(
            "id", assistant_id
        ).eq("user_id", user_id).eq("is_active", True).execute()

        if not assistant_result.data:
            await websocket.send_json({"type": "error", "message": "Assistant not found or inactive"})
            await websocket.close()
            return

        assistant = assistant_result.data[0]

        # Check feature gate for minutes
        feature_gate = get_feature_gate()
        try:
            feature_gate.check_feature_available(user_id, "max_minutes")
        except FeatureGateError as e:
            await websocket.send_json({"type": "error", "message": e.message})
            await websocket.close()
            return

        # Create session and start call
        session = VoiceCallSession(websocket, user_id, assistant_id)
        call_id = await session.start_call()

        if not call_id:
            await websocket.send_json({"type": "error", "message": "Failed to start call"})
            await websocket.close()
            return

        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "call_id": call_id,
            "assistant_name": assistant['name']
        })

        # Initialize voice assistant for processing
        voice_assistant = VoiceAssistant()
        voice_assistant.initialize_modal()

        # Send first message if configured
        if assistant.get('first_message'):
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "content": assistant['first_message']
            })
            session.add_to_transcript("assistant", assistant['first_message'])

            # Synthesize and send first message audio
            try:
                audio_bytes = voice_assistant.tts.synthesize.remote(
                    assistant['first_message'],
                    assistant.get('voice_id', 'default')
                )
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                await websocket.send_json({
                    "type": "audio",
                    "data": audio_b64
                })
            except Exception as e:
                logger.error(f"Error synthesizing first message: {e}")

        # Main message loop
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get('type')

                if msg_type == 'end_call':
                    break

                elif msg_type == 'barge_in':
                    # User interrupted - stop current TTS
                    session.should_stop_tts = True
                    session.is_speaking = False
                    await websocket.send_json({"type": "speaking", "is_speaking": False})

                elif msg_type == 'audio':
                    # Receive audio chunk
                    audio_b64 = message.get('data', '')
                    if not audio_b64:
                        continue

                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                    except Exception:
                        continue

                    # Process audio through pipeline
                    session.should_stop_tts = False

                    # 1. STT - Transcribe audio
                    stt_start = time.time()
                    try:
                        stt_result = voice_assistant.stt.transcribe.remote(audio_bytes)
                        user_text = stt_result.get('text', '').strip()
                        stt_latency = int((time.time() - stt_start) * 1000)
                    except Exception as e:
                        logger.error(f"STT error: {e}")
                        continue

                    if not user_text:
                        continue

                    # Send user transcript
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "user",
                        "content": user_text
                    })
                    session.add_to_transcript("user", user_text)

                    # 2. LLM - Generate response
                    llm_start = time.time()
                    try:
                        # Build conversation history
                        messages = []
                        for t in session.transcript[-10:]:  # Last 10 messages for context
                            messages.append({
                                "role": t['role'],
                                "content": t['content']
                            })

                        response = voice_assistant.anthropic_client.messages.create(
                            model=assistant.get('model', 'claude-3-5-sonnet-20241022'),
                            max_tokens=assistant.get('max_tokens', 150),
                            temperature=float(assistant.get('temperature', 0.7)),
                            system=assistant['system_prompt'],
                            messages=messages
                        )

                        assistant_text = response.content[0].text
                        llm_latency = int((time.time() - llm_start) * 1000)
                    except Exception as e:
                        logger.error(f"LLM error: {e}")
                        assistant_text = "I'm sorry, I encountered an error. Please try again."

                    # Check for barge-in before sending response
                    if session.should_stop_tts:
                        continue

                    # Send assistant transcript
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "assistant",
                        "content": assistant_text
                    })
                    session.add_to_transcript("assistant", assistant_text)

                    # 3. TTS - Synthesize audio
                    if not session.should_stop_tts:
                        tts_start = time.time()
                        try:
                            session.is_speaking = True
                            await websocket.send_json({"type": "speaking", "is_speaking": True})

                            audio_bytes = voice_assistant.tts.synthesize.remote(
                                assistant_text,
                                assistant.get('voice_id', 'default')
                            )
                            tts_latency = int((time.time() - tts_start) * 1000)

                            # Send audio if not interrupted
                            if not session.should_stop_tts:
                                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                                await websocket.send_json({
                                    "type": "audio",
                                    "data": audio_b64
                                })

                            session.is_speaking = False
                            await websocket.send_json({"type": "speaking", "is_speaking": False})

                            # Log latencies
                            total_latency = stt_latency + llm_latency + tts_latency
                            logger.info(f"Call {call_id} - STT: {stt_latency}ms, LLM: {llm_latency}ms, TTS: {tts_latency}ms, Total: {total_latency}ms")

                        except Exception as e:
                            logger.error(f"TTS error: {e}")
                            session.is_speaking = False
                            await websocket.send_json({"type": "speaking", "is_speaking": False})

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for call {session.call_id if session else 'unknown'}")
                break
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                await websocket.send_json({"type": "error", "message": str(e)})

        # End call normally
        if session:
            await session.end_call('user_ended')
            await websocket.send_json({"type": "call_ended", "reason": "user_ended"})

    except WebSocketDisconnect:
        if session:
            await session.end_call('disconnected')
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "Authentication timeout"})
        await websocket.close()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if session:
            await session.end_call('error')
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


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
    print("\nDiscount Codes:")
    print("  POST   /codes/redeem                  - Redeem a discount code")
    print("  POST   /admin/codes                   - Create discount code")
    print("  GET    /admin/codes                   - List all codes")
    print("  DELETE /admin/codes/{code}            - Deactivate code")
    print("  POST   /admin/add-minutes             - Add bonus minutes to user")
    print("\n" + "=" * 60)

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "true").lower() == "true",
    )
