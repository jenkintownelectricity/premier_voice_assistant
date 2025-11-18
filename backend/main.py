"""
Premier Voice Assistant - FastAPI Backend
Orchestrates STT → Claude → TTS with Supabase database integration
Designed for mobile apps (iOS/Android)
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
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
# SUBSCRIPTION & USAGE ENDPOINTS
# ============================================================================

@app.get("/subscription")
async def get_subscription(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """Get user's current subscription plan."""
    try:
        feature_gate = get_feature_gate()
        plan = feature_gate.get_user_plan(user_id)

        if not plan:
            return {
                "plan_name": "free",
                "display_name": "Free",
                "status": "active"
            }

        return {"subscription": plan}

    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/usage")
async def get_usage(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """Get user's current usage statistics."""
    try:
        feature_gate = get_feature_gate()
        usage = feature_gate.get_user_usage(user_id)

        if not usage:
            return {
                "minutes_used": 0,
                "minutes_limit": 100,
                "usage_percentage": "0%",
                "assistants_count": 0,
                "assistants_limit": 1,
            }

        return {"usage": usage}

    except Exception as e:
        logger.error(f"Error getting usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feature-limits")
async def get_feature_limits(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """Get user's feature limits based on their subscription."""
    try:
        feature_gate = get_feature_gate()

        # Get limits for all relevant features
        features = {}
        for feature_key in ['max_minutes', 'max_assistants', 'max_voice_clones']:
            allowed, details = feature_gate.check_feature(user_id, feature_key, 0)
            features[feature_key] = {
                "current": details.get("current_usage", 0),
                "limit": details.get("limit_value", 0),
                "remaining": details.get("remaining", 0),
            }

        # Get boolean features
        plan = feature_gate.get_user_plan(user_id)
        plan_name = plan.get("plan_name", "free") if plan else "free"

        from backend.feature_gates import get_plan_features
        plan_features = get_plan_features(plan_name)

        return {
            "plan": plan_name,
            "features": features,
            "capabilities": {
                "custom_voices": plan_features.get("custom_voices", False),
                "api_access": plan_features.get("api_access", False),
                "priority_support": plan_features.get("priority_support", False),
                "analytics": plan_features.get("analytics", False),
            }
        }

    except Exception as e:
        logger.error(f"Error getting feature limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/upgrade-user")
async def admin_upgrade_user_endpoint(
    target_user_id: str,
    plan_name: str,
    admin_key: str = Header(..., alias="X-Admin-Key"),
):
    """
    Admin endpoint to upgrade a user's subscription.

    Requires X-Admin-Key header with admin API key.
    """
    # Verify admin key
    expected_admin_key = os.getenv("ADMIN_API_KEY")
    if not expected_admin_key or admin_key != expected_admin_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    try:
        from backend.feature_gates import admin_upgrade_user

        success = admin_upgrade_user(target_user_id, plan_name)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to upgrade user")

        return {
            "success": True,
            "message": f"User {target_user_id} upgraded to {plan_name}",
        }

    except Exception as e:
        logger.error(f"Error upgrading user: {e}")
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
    print("  POST   /admin/upgrade-user            - Admin: Upgrade user (requires admin key)")
    print("\n" + "=" * 60)

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "true").lower() == "true",
    )
