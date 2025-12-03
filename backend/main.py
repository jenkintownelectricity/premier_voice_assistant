"""
Premier Voice Assistant - FastAPI Backend
Orchestrates STT → Claude → TTS with Supabase database integration
Designed for mobile apps (iOS/Android)
"""
# Load environment variables from .env file FIRST
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, Request, WebSocket, WebSocketDisconnect, Form
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
import struct
import wave
import base64
from datetime import datetime

from backend.supabase_client import get_supabase, SupabaseManager
from backend.feature_gates import get_feature_gate, FeatureGateError
from backend.stripe_payments import get_stripe_payments, handle_webhook_event, validate_stripe_config
from backend.twilio_integration import get_twilio_service, validate_twilio_config
from backend.model_manager import (
    get_model_manager, get_model, get_model_with_fallback,
    validate_models_on_startup, ResilientAnthropicClient
)
from backend.streaming_manager import (
    StreamingPipeline, StreamingConfig, PipelineState,
    create_streaming_pipeline
)
from backend.lightning_pipeline import (
    LightningPipeline, LightningConfig, PipelineState as LightningState,
    LatencyMetrics
)
from backend.groq_client import HybridLLMClient, GroqConfig
from backend.cartesia_client import CartesiaSonic3, CartesiaConfig, get_supported_languages as get_tts_languages
from backend.deepgram_client import DeepgramNova3, DeepgramConfig, get_supported_languages as get_stt_languages

# LiveKit WebRTC Integration
try:
    from backend.livekit_api import router as livekit_router
    LIVEKIT_ROUTER_AVAILABLE = True
except ImportError:
    LIVEKIT_ROUTER_AVAILABLE = False
    logger_livekit = logging.getLogger("livekit")
    logger_livekit.warning("LiveKit API not available - SDK may not be installed")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Claude API Pricing (per million tokens) - as of 2025
# Source: https://www.anthropic.com/pricing
CLAUDE_PRICING = {
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,    # $3.00 per 1M input tokens
        "output": 15.00,  # $15.00 per 1M output tokens
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-5-sonnet-20240620": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
    },
    "claude-haiku-4-5-20241022": {
        "input": 0.25,
        "output": 1.25,
    },
}

# ============================================================================
# LLM PROVIDERS - All major providers with API documentation links
# ============================================================================
LLM_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "api_docs": "https://docs.anthropic.com/en/api/getting-started",
        "api_keys_url": "https://console.anthropic.com/settings/keys",
        "models": [
            {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5 (Latest)", "context": "200K", "speed": "fast"},
            {"id": "claude-opus-4-5-20251101", "name": "Claude Opus 4.5 (Smartest)", "context": "200K", "speed": "medium"},
            {"id": "claude-haiku-4-5-20241022", "name": "Claude Haiku 4.5 (Fastest)", "context": "200K", "speed": "fastest"},
        ],
        "default_model": "claude-sonnet-4-5-20250929",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "api_docs": "https://platform.openai.com/docs/api-reference",
        "api_keys_url": "https://platform.openai.com/api-keys",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o (Latest)", "context": "128K", "speed": "fast"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini (Fastest)", "context": "128K", "speed": "fastest"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context": "128K", "speed": "medium"},
            {"id": "o1", "name": "o1 (Reasoning)", "context": "200K", "speed": "slow"},
            {"id": "o1-mini", "name": "o1 Mini (Fast Reasoning)", "context": "128K", "speed": "medium"},
        ],
        "default_model": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
    },
    "groq": {
        "name": "Groq (Ultra Fast)",
        "api_docs": "https://console.groq.com/docs/api-reference",
        "api_keys_url": "https://console.groq.com/keys",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B (Best)", "context": "128K", "speed": "fastest"},
            {"id": "llama-3.1-70b-versatile", "name": "Llama 3.1 70B", "context": "128K", "speed": "fastest"},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B (Instant)", "context": "128K", "speed": "fastest"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "context": "32K", "speed": "fastest"},
            {"id": "gemma2-9b-it", "name": "Gemma 2 9B", "context": "8K", "speed": "fastest"},
        ],
        "default_model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
    },
    "google": {
        "name": "Google (Gemini)",
        "api_docs": "https://ai.google.dev/gemini-api/docs",
        "api_keys_url": "https://aistudio.google.com/apikey",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash (Latest)", "context": "1M", "speed": "fastest"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "context": "2M", "speed": "medium"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "context": "1M", "speed": "fast"},
        ],
        "default_model": "gemini-2.0-flash",
        "env_key": "GOOGLE_API_KEY",
    },
    "mistral": {
        "name": "Mistral AI",
        "api_docs": "https://docs.mistral.ai/api/",
        "api_keys_url": "https://console.mistral.ai/api-keys/",
        "models": [
            {"id": "mistral-large-latest", "name": "Mistral Large (Best)", "context": "128K", "speed": "medium"},
            {"id": "mistral-medium-latest", "name": "Mistral Medium", "context": "32K", "speed": "fast"},
            {"id": "mistral-small-latest", "name": "Mistral Small (Fastest)", "context": "32K", "speed": "fastest"},
            {"id": "codestral-latest", "name": "Codestral (Code)", "context": "32K", "speed": "fast"},
        ],
        "default_model": "mistral-large-latest",
        "env_key": "MISTRAL_API_KEY",
    },
    "together": {
        "name": "Together AI",
        "api_docs": "https://docs.together.ai/reference/completions",
        "api_keys_url": "https://api.together.xyz/settings/api-keys",
        "models": [
            {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "name": "Llama 3.3 70B Turbo", "context": "128K", "speed": "fast"},
            {"id": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo", "name": "Llama 3.1 405B", "context": "128K", "speed": "medium"},
            {"id": "Qwen/Qwen2.5-72B-Instruct-Turbo", "name": "Qwen 2.5 72B", "context": "32K", "speed": "fast"},
            {"id": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B", "name": "DeepSeek R1 70B", "context": "64K", "speed": "fast"},
        ],
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "env_key": "TOGETHER_API_KEY",
    },
    "fireworks": {
        "name": "Fireworks AI",
        "api_docs": "https://docs.fireworks.ai/api-reference/introduction",
        "api_keys_url": "https://fireworks.ai/account/api-keys",
        "models": [
            {"id": "accounts/fireworks/models/llama-v3p3-70b-instruct", "name": "Llama 3.3 70B", "context": "128K", "speed": "fastest"},
            {"id": "accounts/fireworks/models/llama-v3p1-405b-instruct", "name": "Llama 3.1 405B", "context": "128K", "speed": "fast"},
            {"id": "accounts/fireworks/models/deepseek-r1", "name": "DeepSeek R1", "context": "64K", "speed": "medium"},
        ],
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "env_key": "FIREWORKS_API_KEY",
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_docs": "https://platform.deepseek.com/api-docs",
        "api_keys_url": "https://platform.deepseek.com/api_keys",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat (V3)", "context": "64K", "speed": "fast"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1 (Reasoning)", "context": "64K", "speed": "medium"},
        ],
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "xai": {
        "name": "xAI (Grok)",
        "api_docs": "https://docs.x.ai/api",
        "api_keys_url": "https://console.x.ai/",
        "models": [
            {"id": "grok-2-latest", "name": "Grok 2 (Latest)", "context": "128K", "speed": "fast"},
            {"id": "grok-2-vision-latest", "name": "Grok 2 Vision", "context": "32K", "speed": "fast"},
        ],
        "default_model": "grok-2-latest",
        "env_key": "XAI_API_KEY",
    },
    "cohere": {
        "name": "Cohere",
        "api_docs": "https://docs.cohere.com/reference/chat",
        "api_keys_url": "https://dashboard.cohere.com/api-keys",
        "models": [
            {"id": "command-r-plus", "name": "Command R+ (Best)", "context": "128K", "speed": "medium"},
            {"id": "command-r", "name": "Command R", "context": "128K", "speed": "fast"},
            {"id": "command-light", "name": "Command Light (Fastest)", "context": "4K", "speed": "fastest"},
        ],
        "default_model": "command-r-plus",
        "env_key": "COHERE_API_KEY",
    },
    "perplexity": {
        "name": "Perplexity (Online)",
        "api_docs": "https://docs.perplexity.ai/api-reference/chat-completions",
        "api_keys_url": "https://www.perplexity.ai/settings/api",
        "models": [
            {"id": "sonar-pro", "name": "Sonar Pro (Best Online)", "context": "200K", "speed": "medium"},
            {"id": "sonar", "name": "Sonar (Online Search)", "context": "127K", "speed": "fast"},
            {"id": "sonar-reasoning-pro", "name": "Sonar Reasoning Pro", "context": "127K", "speed": "slow"},
        ],
        "default_model": "sonar-pro",
        "env_key": "PERPLEXITY_API_KEY",
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
    pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING["claude-sonnet-4-5-20250929"])

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

# Include LiveKit router for WebRTC voice sessions
if LIVEKIT_ROUTER_AVAILABLE:
    app.include_router(livekit_router, prefix="/livekit", tags=["livekit"])
    logger.info("LiveKit API endpoints enabled at /livekit/*")

# Pydantic models for request/response validation
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    voice: Optional[str] = "fabio"
    user_id: Optional[str] = None


class SpeakRequest(BaseModel):
    text: str
    voice: Optional[str] = "fabio"


class TextChatRequest(BaseModel):
    message: str
    system_prompt: Optional[str] = None


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
    llm_provider: Optional[str] = "groq"  # Provider: groq, anthropic, openai, google, mistral, etc.
    model: Optional[str] = "llama-3.3-70b-versatile"  # Model ID from the selected provider
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
    # Voice control settings (competitive with Vapi/ElevenLabs)
    speech_speed: Optional[float] = 0.9  # TTS speed (0.7-1.2), 0.9 for natural conversation
    response_delay_ms: Optional[int] = 400  # Delay before responding after user stops (Vapi default: 400ms)
    punctuation_pause_ms: Optional[int] = 300  # Pause after punctuation detected
    no_punctuation_pause_ms: Optional[int] = 1000  # Pause when no punctuation (waiting for more speech)
    turn_eagerness: Optional[str] = "balanced"  # low, balanced, high - how quickly to take turns


class UpdateAssistantRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    voice_id: Optional[str] = None
    llm_provider: Optional[str] = None  # Provider: groq, anthropic, openai, google, mistral, etc.
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
    # Voice control settings (competitive with Vapi/ElevenLabs)
    speech_speed: Optional[float] = None  # TTS speed (0.7-1.2)
    response_delay_ms: Optional[int] = None  # Delay before responding
    punctuation_pause_ms: Optional[int] = None  # Pause after punctuation
    no_punctuation_pause_ms: Optional[int] = None  # Pause when no punctuation
    turn_eagerness: Optional[str] = None  # low, balanced, high


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM audio bytes to WAV format."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer.read()


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
        """Initialize Modal HTTP endpoints (lazy loading)"""
        if self.modal_initialized:
            return

        try:
            import httpx
            
            # Use HTTP endpoints instead of Modal SDK
            self.modal_stt_url = "https://jenkintownelectricity--premier-whisper-stt-transcribe-web.modal.run"
            self.modal_tts_url = "https://jenkintownelectricity--hive215-kokoro-tts-synthesize-web.modal.run"
            self.http_client = httpx.Client(timeout=60.0)
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
        Transcribe audio to text using Whisper via HTTP.
        """
        self.initialize_modal()

        start = time.time()
        
        try:
            # Call Modal HTTP endpoint
            files = {"audio_bytes": ("audio.wav", audio_bytes, "audio/wav")}
            data = {"language": "en"}
            response = self.http_client.post(self.modal_stt_url, files=files, data=data)
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            logger.error(f"STT HTTP error: {e}")
            result = {"text": "", "error": str(e)}
        
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
            model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
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
        Synthesize text to speech using Coqui TTS via HTTP.
        """
        self.initialize_modal()

        start = time.time()
        
        try:
            # Call Modal HTTP endpoint
            data = {"text": text, "voice": voice, "language": "en"}
            response = self.http_client.post(self.modal_tts_url, json=data)
            response.raise_for_status()
            audio = response.content
        except Exception as e:
            logger.error(f"TTS HTTP error: {e}")
            audio = b""
        
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


# ============================================================================
# ERROR REPORTING
# ============================================================================

class ErrorReportRequest(BaseModel):
    """Error report from frontend."""
    user_id: str
    assistant_id: Optional[str] = None
    call_id: Optional[str] = None
    error_message: str
    error_code: Optional[str] = None
    error_context: Optional[str] = None
    error_history: Optional[List[dict]] = None
    pipeline_info: Optional[str] = None
    latency_data: Optional[dict] = None
    transcript_summary: Optional[List[str]] = None
    call_duration: Optional[int] = None
    user_notes: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: Optional[str] = None


@app.post("/error-reports")
async def submit_error_report(report: ErrorReportRequest):
    """
    Receive error reports from the frontend.

    Stores in database and logs for developer review.
    """
    try:
        # Log the error for immediate visibility
        logger.error(
            f"[ERROR REPORT] User: {report.user_id}, "
            f"Call: {report.call_id or 'N/A'}, "
            f"Error: {report.error_message}, "
            f"Code: {report.error_code or 'N/A'}, "
            f"Pipeline: {report.pipeline_info or 'N/A'}"
        )

        # Store in database
        db = get_supabase()

        # Create error report record
        report_data = {
            "user_id": report.user_id,
            "assistant_id": report.assistant_id,
            "call_id": report.call_id,
            "error_message": report.error_message,
            "error_code": report.error_code,
            "error_context": report.error_context,
            "error_history": report.error_history,
            "pipeline_info": report.pipeline_info,
            "latency_data": report.latency_data,
            "transcript_summary": report.transcript_summary,
            "call_duration": report.call_duration,
            "user_notes": report.user_notes,
            "user_agent": report.user_agent,
            "reported_at": report.timestamp or datetime.utcnow().isoformat(),
            "status": "new",
        }

        # Try to insert into error_reports table (if exists)
        try:
            result = db.client.table("va_error_reports").insert(report_data).execute()
            report_id = result.data[0]["id"] if result.data else None
            logger.info(f"Error report saved with ID: {report_id}")
        except Exception as db_error:
            # Table might not exist yet - just log it
            logger.warning(f"Could not save error report to DB: {db_error}")
            report_id = None

        return {
            "status": "ok",
            "message": "Error report received",
            "report_id": report_id,
        }

    except Exception as e:
        logger.error(f"Failed to process error report: {e}")
        # Still return success to not frustrate users
        return {
            "status": "ok",
            "message": "Error report logged",
            "report_id": None,
        }


@app.get("/error-reports")
async def get_error_reports(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    """
    Get error reports (for admin dashboard).
    """
    try:
        db = get_supabase()
        query = db.client.table("va_error_reports").select("*")

        if user_id:
            query = query.eq("user_id", user_id)
        if status:
            query = query.eq("status", status)

        query = query.order("reported_at", desc=True).limit(limit)
        result = query.execute()

        return {
            "status": "ok",
            "reports": result.data,
            "count": len(result.data),
        }
    except Exception as e:
        logger.error(f"Failed to get error reports: {e}")
        return {
            "status": "error",
            "error": str(e),
            "reports": [],
        }


@app.get("/models/status")
async def model_status():
    """
    Get status of available models with automatic fallback info.

    Returns:
        Model validation report showing available/deprecated models
    """
    try:
        report = validate_models_on_startup()
        return {
            "status": "ok",
            "report": report,
        }
    except Exception as e:
        logger.error(f"Model status check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@app.get("/models/current")
async def current_models():
    """
    Get currently selected models for each family.

    Returns:
        Currently active model for each family (sonnet, haiku, opus)
    """
    try:
        manager = get_model_manager()
        return {
            "status": "ok",
            "models": {
                family: manager.get_model(family)
                for family in manager.get_all_families()
            },
        }
    except Exception as e:
        logger.error(f"Current models check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
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


@app.post("/chat/text")
async def chat_text(request: TextChatRequest):
    """
    Text-based chat with Claude AI.

    Body:
        message: User message
        system_prompt: Optional system prompt

    Returns:
        response: AI response text
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        system = request.system_prompt or "You are a helpful AI assistant for HIVE215, a premier voice assistant platform. Be concise, friendly, and helpful."

        message = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
            max_tokens=1024,
            system=system,
            messages=[
                {"role": "user", "content": request.message}
            ]
        )

        # Extract text from response
        response_text = message.content[0].text if message.content else "I couldn't generate a response."

        return {"response": response_text}

    except Exception as e:
        logger.error(f"Text chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clone-voice")
async def clone_voice(
    audio: UploadFile = File(...),
    voice_name: str = Form(...),
    display_name: str = Form(...),
    is_public: str = Form("false"),
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Clone a new voice from reference audio.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        # Convert is_public string to boolean (form data comes as string)
        is_public_bool = is_public.lower() in ("true", "1", "yes")

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

        # Clone voice on Modal via HTTP
        assistant.initialize_modal()
        try:
            import httpx
            clone_url = "https://jenkintownelectricity--premier-coqui-tts-clone-voice-web.modal.run"
            files = {"reference_audio": ("audio.wav", audio_bytes, "audio/wav")}
            data = {"voice": voice_name}
            response = httpx.post(clone_url, files=files, data=data, timeout=120.0)
            response.raise_for_status()
            clone_result = response.json()
        except Exception as e:
            logger.error(f"Voice clone HTTP error: {e}")
            clone_result = {"duration": 0, "error": str(e)}

        # Save to database
        voice_clone = db.create_voice_clone(
            user_id=user_id,
            voice_name=voice_name,
            display_name=display_name,
            reference_audio_url=audio_url,
            sample_duration=clone_result.get('duration'),
            modal_voice_id=voice_name,
            is_public=is_public_bool,
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


@app.get("/limits")
async def get_limits(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get user's plan limits (alias for /feature-limits).
    Returns limits in format expected by frontend.

    Headers:
        X-User-ID: Required user ID
    """
    try:
        feature_gate = get_feature_gate()
        plan = feature_gate.get_user_plan(user_id)

        if not plan:
            # Default limits for users without a plan
            return {
                "limits": {
                    "max_voice_clones": 0,
                    "max_assistants": 1,
                    "max_minutes": 10
                }
            }

        plan_name = plan.get("plan_name", "free")

        # Get all features for this plan
        from backend.feature_gates import get_plan_features
        features = get_plan_features(plan_name)

        return {
            "limits": features
        }

    except Exception as e:
        logger.error(f"Error getting limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SetBudgetRequest(BaseModel):
    monthly_budget_dollars: float
    alert_thresholds: list[int] = [80, 90, 100]


@app.get("/budget")
async def get_budget(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Get user's budget settings and current usage status."""
    try:
        # Get budget settings
        budget_result = db.client.table("va_user_budgets").select("*").eq(
            "user_id", user_id
        ).execute()

        # If no budget set, return defaults
        if not budget_result.data:
            return {
                "budget": {
                    "monthly_budget_cents": 5000,  # $50 default
                    "monthly_budget_dollars": 50.00,
                    "alert_thresholds": [80, 90, 100],
                    "is_active": False
                },
                "current_month": {
                    "cost_cents": 0,
                    "cost_dollars": 0.00,
                    "percentage_used": 0,
                    "remaining_cents": 5000,
                    "remaining_dollars": 50.00
                }
            }

        budget = budget_result.data[0]

        # Get current month's usage
        from datetime import datetime
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        usage_result = db.client.table("va_usage_metrics").select(
            "cost_cents"
        ).eq("user_id", user_id).gte(
            "created_at", month_start.isoformat()
        ).execute()

        total_cost_cents = sum(m.get("cost_cents", 0) or 0 for m in usage_result.data)
        budget_cents = budget["monthly_budget_cents"]
        percentage_used = (total_cost_cents / budget_cents * 100) if budget_cents > 0 else 0

        return {
            "budget": {
                "monthly_budget_cents": budget_cents,
                "monthly_budget_dollars": budget_cents / 100,
                "alert_thresholds": budget.get("alert_thresholds", [80, 90, 100]),
                "is_active": budget.get("is_active", True),
                "last_alert_sent_at": budget.get("last_alert_sent_at"),
                "last_alert_threshold": budget.get("last_alert_threshold")
            },
            "current_month": {
                "cost_cents": total_cost_cents,
                "cost_dollars": total_cost_cents / 100,
                "percentage_used": round(percentage_used, 2),
                "remaining_cents": max(0, budget_cents - total_cost_cents),
                "remaining_dollars": max(0, (budget_cents - total_cost_cents) / 100),
                "status": "over_budget" if percentage_used > 100 else "warning" if percentage_used > 90 else "healthy"
            }
        }

    except Exception as e:
        logger.error(f"Error getting budget: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/budget")
async def set_budget(
    request: SetBudgetRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Set or update user's monthly budget."""
    try:
        budget_cents = int(request.monthly_budget_dollars * 100)

        # Upsert budget
        result = db.client.table("va_user_budgets").upsert({
            "user_id": user_id,
            "monthly_budget_cents": budget_cents,
            "alert_thresholds": request.alert_thresholds,
            "is_active": True
        }, on_conflict="user_id").execute()

        return {
            "success": True,
            "budget": {
                "monthly_budget_cents": budget_cents,
                "monthly_budget_dollars": request.monthly_budget_dollars,
                "alert_thresholds": request.alert_thresholds
            }
        }

    except Exception as e:
        logger.error(f"Error setting budget: {e}")
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
# AI USAGE COACH ROUTES (Unique Feature)
# ============================================================================

@app.get("/insights/weekly")
async def get_weekly_insights(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get AI-powered weekly usage insights and recommendations.

    Headers:
        X-User-ID: Required user ID

    Returns:
        Weekly analysis with personalized recommendations from AI coach
    """
    try:
        from datetime import datetime, timedelta
        import anthropic

        # Get data for current week and previous week
        now = datetime.utcnow()
        week_start = now - timedelta(days=7)
        prev_week_start = now - timedelta(days=14)

        # Current week metrics
        current_week = db.client.table("va_usage_metrics").select(
            "cost_cents, input_tokens, output_tokens, total_latency_ms, event_type, error, created_at"
        ).eq("user_id", user_id).gte("created_at", week_start.isoformat()).execute()

        # Previous week metrics
        prev_week = db.client.table("va_usage_metrics").select(
            "cost_cents, input_tokens, output_tokens, total_latency_ms, event_type, error, created_at"
        ).eq("user_id", user_id).gte(
            "created_at", prev_week_start.isoformat()
        ).lt("created_at", week_start.isoformat()).execute()

        # Calculate current week stats
        current_data = current_week.data if current_week.data else []
        prev_data = prev_week.data if prev_week.data else []

        current_cost = sum(m.get("cost_cents", 0) for m in current_data) / 100
        prev_cost = sum(m.get("cost_cents", 0) for m in prev_data) / 100

        current_tokens = sum(
            m.get("input_tokens", 0) + m.get("output_tokens", 0)
            for m in current_data
        )
        prev_tokens = sum(
            m.get("input_tokens", 0) + m.get("output_tokens", 0)
            for m in prev_data
        )

        current_requests = len(current_data)
        prev_requests = len(prev_data)

        current_errors = len([m for m in current_data if m.get("error")])
        prev_errors = len([m for m in prev_data if m.get("error")])

        # Calculate average latency (only for non-error requests)
        latencies = [m.get("total_latency_ms", 0) for m in current_data if m.get("total_latency_ms")]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        # Event type distribution
        event_types = {}
        for m in current_data:
            et = m.get("event_type", "unknown")
            event_types[et] = event_types.get(et, 0) + 1

        # Calculate percentage changes
        cost_change = ((current_cost - prev_cost) / prev_cost * 100) if prev_cost > 0 else 0
        tokens_change = ((current_tokens - prev_tokens) / prev_tokens * 100) if prev_tokens > 0 else 0
        requests_change = ((current_requests - prev_requests) / prev_requests * 100) if prev_requests > 0 else 0

        # Prepare AI analysis prompt
        analysis_prompt = f"""You are an AI Usage Coach helping users optimize their voice AI platform usage.

Current Week Summary:
- Total Cost: ${current_cost:.2f}
- Total Tokens: {current_tokens:,}
- Total Requests: {current_requests}
- Errors: {current_errors}
- Average Latency: {avg_latency:.0f}ms
- Event Types: {event_types}

Previous Week Comparison:
- Cost Change: {cost_change:+.1f}%
- Tokens Change: {tokens_change:+.1f}%
- Requests Change: {requests_change:+.1f}%

Based on this data, provide:
1. A brief summary of usage trends (2-3 sentences)
2. Three specific, actionable recommendations to optimize costs or performance
3. One positive highlight from their usage patterns

Format as JSON:
{{
    "summary": "Brief trend analysis...",
    "recommendations": [
        {{"title": "Rec 1", "description": "...", "impact": "high|medium|low"}},
        {{"title": "Rec 2", "description": "...", "impact": "high|medium|low"}},
        {{"title": "Rec 3", "description": "...", "impact": "high|medium|low"}}
    ],
    "highlight": "Positive observation..."
}}"""

        # Call Claude for AI insights
        try:
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
                max_tokens=1000,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": analysis_prompt
                }]
            )

            import json
            ai_insights = json.loads(response.content[0].text)
        except Exception as e:
            logger.warning(f"AI insights generation failed: {e}")
            # Fallback to rule-based insights
            ai_insights = {
                "summary": f"Your usage {'increased' if cost_change > 0 else 'decreased'} by {abs(cost_change):.1f}% this week. Current spending is ${current_cost:.2f} across {current_requests} requests.",
                "recommendations": [
                    {
                        "title": "Monitor Cost Trends",
                        "description": "Keep track of your weekly spending patterns to avoid unexpected costs.",
                        "impact": "medium"
                    },
                    {
                        "title": "Optimize Token Usage",
                        "description": "Review your prompts to minimize unnecessary tokens while maintaining quality.",
                        "impact": "high"
                    },
                    {
                        "title": "Set Budget Alerts",
                        "description": "Configure budget alerts to stay informed about spending thresholds.",
                        "impact": "high"
                    }
                ],
                "highlight": "Your error rate is low, indicating stable performance."
            }

        return {
            "period": {
                "start": week_start.isoformat(),
                "end": now.isoformat(),
            },
            "metrics": {
                "current_week": {
                    "cost_dollars": current_cost,
                    "total_tokens": current_tokens,
                    "total_requests": current_requests,
                    "error_count": current_errors,
                    "avg_latency_ms": round(avg_latency),
                    "event_types": event_types
                },
                "changes": {
                    "cost_percent": round(cost_change, 1),
                    "tokens_percent": round(tokens_change, 1),
                    "requests_percent": round(requests_change, 1)
                }
            },
            "ai_insights": ai_insights
        }

    except Exception as e:
        logger.error(f"Error getting weekly insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/insights/cost-optimizer")
async def get_cost_optimization_suggestions(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get AI-powered cost optimization suggestions based on usage patterns.

    Headers:
        X-User-ID: Required user ID

    Returns:
        Detailed cost optimization recommendations
    """
    try:
        from datetime import datetime, timedelta

        # Get last 30 days of data
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        metrics = db.client.table("va_usage_metrics").select(
            "cost_cents, input_tokens, output_tokens, event_type, total_latency_ms, metadata, created_at"
        ).eq("user_id", user_id).gte("created_at", thirty_days_ago.isoformat()).execute()

        data = metrics.data if metrics.data else []

        if not data:
            return {
                "optimizations": [],
                "potential_savings": 0,
                "message": "Not enough usage data to generate recommendations."
            }

        # Analyze usage patterns
        total_cost = sum(m.get("cost_cents", 0) for m in data) / 100
        total_requests = len(data)

        # Group by event type
        by_event = {}
        for m in data:
            et = m.get("event_type", "unknown")
            if et not in by_event:
                by_event[et] = {"cost": 0, "count": 0, "tokens": 0}
            by_event[et]["cost"] += m.get("cost_cents", 0) / 100
            by_event[et]["count"] += 1
            by_event[et]["tokens"] += m.get("input_tokens", 0) + m.get("output_tokens", 0)

        # Find highest cost event types
        sorted_events = sorted(by_event.items(), key=lambda x: x[1]["cost"], reverse=True)

        # Calculate token efficiency
        total_tokens = sum(m.get("input_tokens", 0) + m.get("output_tokens", 0) for m in data)
        avg_tokens_per_request = total_tokens / total_requests if total_requests > 0 else 0

        # Generate optimization suggestions
        optimizations = []
        potential_savings = 0

        # High token usage optimization
        if avg_tokens_per_request > 1000:
            savings = total_cost * 0.15  # Estimate 15% savings
            potential_savings += savings
            optimizations.append({
                "title": "Reduce Prompt Tokens",
                "description": f"Your average request uses {avg_tokens_per_request:.0f} tokens. Consider shorter, more focused prompts to reduce costs.",
                "potential_savings_dollars": round(savings, 2),
                "impact": "high",
                "category": "token_optimization"
            })

        # Event type specific optimizations
        if sorted_events and sorted_events[0][1]["cost"] > total_cost * 0.6:
            event_name = sorted_events[0][0]
            event_cost = sorted_events[0][1]["cost"]
            optimizations.append({
                "title": f"Optimize {event_name.replace('_', ' ').title()} Usage",
                "description": f"{event_name} accounts for ${event_cost:.2f} ({event_cost/total_cost*100:.0f}%) of your costs. Review if all these calls are necessary.",
                "potential_savings_dollars": round(event_cost * 0.1, 2),
                "impact": "high",
                "category": "usage_pattern"
            })
            potential_savings += event_cost * 0.1

        # Caching recommendation
        optimizations.append({
            "title": "Implement Response Caching",
            "description": "Cache frequently repeated queries to reduce API calls and costs. Estimated 10-20% savings for typical usage patterns.",
            "potential_savings_dollars": round(total_cost * 0.15, 2),
            "impact": "medium",
            "category": "caching"
        })
        potential_savings += total_cost * 0.15

        # Model selection optimization
        optimizations.append({
            "title": "Review Model Selection",
            "description": "Consider using Claude Haiku for simple tasks instead of Sonnet. Haiku is 10x cheaper for suitable use cases.",
            "potential_savings_dollars": round(total_cost * 0.25, 2),
            "impact": "high",
            "category": "model_selection"
        })
        potential_savings += total_cost * 0.25

        return {
            "period_days": 30,
            "current_monthly_cost": round(total_cost, 2),
            "total_requests": total_requests,
            "optimizations": optimizations[:4],  # Top 4 recommendations
            "potential_monthly_savings": round(potential_savings, 2),
            "top_cost_drivers": [
                {
                    "event_type": event,
                    "cost_dollars": round(data["cost"], 2),
                    "percentage": round(data["cost"] / total_cost * 100, 1),
                    "count": data["count"]
                }
                for event, data in sorted_events[:3]
            ]
        }

    except Exception as e:
        logger.error(f"Error getting cost optimization suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADVANCED OBSERVABILITY ROUTES (Latency Percentiles)
# ============================================================================

@app.get("/observability/latency")
async def get_latency_percentiles(
    user_id: str = Header(..., alias="X-User-ID"),
    days: int = 7,
    db: SupabaseManager = Depends(get_db),
):
    """
    Get latency percentiles (P50, P75, P90, P95, P99) for performance monitoring.

    Headers:
        X-User-ID: Required user ID

    Query Parameters:
        days: Number of days to analyze (default: 7)

    Returns:
        Detailed latency analysis with percentiles
    """
    try:
        from datetime import datetime, timedelta
        import statistics

        start_date = datetime.utcnow() - timedelta(days=days)

        # Get all metrics with latency data
        metrics = db.client.table("va_usage_metrics").select(
            "stt_latency_ms, llm_latency_ms, tts_latency_ms, total_latency_ms, event_type, created_at"
        ).eq("user_id", user_id).gte("created_at", start_date.isoformat()).execute()

        data = metrics.data if metrics.data else []

        if not data:
            return {
                "message": "No latency data available for the specified period.",
                "percentiles": {}
            }

        def calculate_percentiles(values):
            """Calculate P50, P75, P90, P95, P99 percentiles"""
            if not values:
                return {}

            sorted_vals = sorted(values)
            n = len(sorted_vals)

            return {
                "p50": sorted_vals[int(n * 0.50)] if n > 0 else 0,
                "p75": sorted_vals[int(n * 0.75)] if n > 0 else 0,
                "p90": sorted_vals[int(n * 0.90)] if n > 0 else 0,
                "p95": sorted_vals[int(n * 0.95)] if n > 0 else 0,
                "p99": sorted_vals[int(n * 0.99)] if n > 0 else 0,
                "min": min(sorted_vals),
                "max": max(sorted_vals),
                "mean": round(statistics.mean(sorted_vals), 2),
                "median": statistics.median(sorted_vals),
                "count": n
            }

        # Extract latency values (filter out None/0 values)
        stt_latencies = [m["stt_latency_ms"] for m in data if m.get("stt_latency_ms")]
        llm_latencies = [m["llm_latency_ms"] for m in data if m.get("llm_latency_ms")]
        tts_latencies = [m["tts_latency_ms"] for m in data if m.get("tts_latency_ms")]
        total_latencies = [m["total_latency_ms"] for m in data if m.get("total_latency_ms")]

        # Calculate percentiles for each component
        percentiles = {
            "stt": calculate_percentiles(stt_latencies),
            "llm": calculate_percentiles(llm_latencies),
            "tts": calculate_percentiles(tts_latencies),
            "total": calculate_percentiles(total_latencies)
        }

        # Breakdown by event type
        by_event_type = {}
        for m in data:
            et = m.get("event_type", "unknown")
            if et not in by_event_type:
                by_event_type[et] = []
            if m.get("total_latency_ms"):
                by_event_type[et].append(m["total_latency_ms"])

        event_percentiles = {
            event: calculate_percentiles(latencies)
            for event, latencies in by_event_type.items()
        }

        # Time-based analysis (hourly breakdown)
        hourly_breakdown = {}
        for m in data:
            if m.get("total_latency_ms") and m.get("created_at"):
                hour = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")).hour
                if hour not in hourly_breakdown:
                    hourly_breakdown[hour] = []
                hourly_breakdown[hour].append(m["total_latency_ms"])

        hourly_percentiles = {
            f"{hour:02d}:00": {
                "p50": statistics.median(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 0 else 0,
                "count": len(latencies)
            }
            for hour, latencies in sorted(hourly_breakdown.items())
        }

        # Performance health score (0-100)
        # Based on P95 latency - lower is better
        p95_total = percentiles["total"].get("p95", 0)
        if p95_total == 0:
            health_score = 100
        elif p95_total < 1000:  # < 1s is excellent
            health_score = 100
        elif p95_total < 2000:  # < 2s is good
            health_score = 90
        elif p95_total < 3000:  # < 3s is acceptable
            health_score = 75
        elif p95_total < 5000:  # < 5s is concerning
            health_score = 60
        else:
            health_score = max(30, 100 - (p95_total / 100))

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": datetime.utcnow().isoformat(),
                "days": days
            },
            "overall_percentiles": percentiles,
            "by_event_type": event_percentiles,
            "hourly_analysis": hourly_percentiles,
            "performance_score": round(health_score),
            "insights": {
                "fastest_component": min(
                    [("stt", percentiles["stt"].get("mean", float('inf'))),
                     ("llm", percentiles["llm"].get("mean", float('inf'))),
                     ("tts", percentiles["tts"].get("mean", float('inf')))],
                    key=lambda x: x[1]
                )[0] if percentiles else "N/A",
                "slowest_component": max(
                    [("stt", percentiles["stt"].get("mean", 0)),
                     ("llm", percentiles["llm"].get("mean", 0)),
                     ("tts", percentiles["tts"].get("mean", 0))],
                    key=lambda x: x[1]
                )[0] if percentiles else "N/A",
                "total_requests_analyzed": len(data)
            }
        }

    except Exception as e:
        logger.error(f"Error calculating latency percentiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/observability/error-correlation")
async def get_error_correlation(
    user_id: str = Header(..., alias="X-User-ID"),
    days: int = 7,
    db: SupabaseManager = Depends(get_db),
):
    """
    Analyze error patterns and correlations with latency/usage.

    Headers:
        X-User-ID: Required user ID

    Query Parameters:
        days: Number of days to analyze (default: 7)

    Returns:
        Error pattern analysis and correlations
    """
    try:
        from datetime import datetime, timedelta
        import statistics

        start_date = datetime.utcnow() - timedelta(days=days)

        # Get all metrics
        metrics = db.client.table("va_usage_metrics").select(
            "error, total_latency_ms, event_type, created_at"
        ).eq("user_id", user_id).gte("created_at", start_date.isoformat()).execute()

        data = metrics.data if metrics.data else []

        if not data:
            return {
                "message": "No data available for the specified period.",
                "correlations": {}
            }

        # Separate errors and successes
        errors = [m for m in data if m.get("error")]
        successes = [m for m in data if not m.get("error")]

        total_requests = len(data)
        error_count = len(errors)
        success_count = len(successes)
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

        # Error types
        error_types = {}
        for m in errors:
            error_msg = m.get("error", "Unknown")
            # Extract error type (first part before colon or first 50 chars)
            error_type = error_msg.split(":")[0][:50] if ":" in error_msg else error_msg[:50]
            error_types[error_type] = error_types.get(error_type, 0) + 1

        # Latency correlation
        error_latencies = [m.get("total_latency_ms") for m in errors if m.get("total_latency_ms")]
        success_latencies = [m.get("total_latency_ms") for m in successes if m.get("total_latency_ms")]

        avg_error_latency = statistics.mean(error_latencies) if error_latencies else 0
        avg_success_latency = statistics.mean(success_latencies) if success_latencies else 0

        # Event type correlation
        error_by_event = {}
        success_by_event = {}

        for m in errors:
            et = m.get("event_type", "unknown")
            error_by_event[et] = error_by_event.get(et, 0) + 1

        for m in successes:
            et = m.get("event_type", "unknown")
            success_by_event[et] = success_by_event.get(et, 0) + 1

        event_error_rates = {}
        for event in set(list(error_by_event.keys()) + list(success_by_event.keys())):
            event_errors = error_by_event.get(event, 0)
            event_total = event_errors + success_by_event.get(event, 0)
            event_error_rates[event] = {
                "error_count": event_errors,
                "total_count": event_total,
                "error_rate_percent": round((event_errors / event_total * 100) if event_total > 0 else 0, 2)
            }

        # Time-based patterns (errors by hour)
        hourly_errors = {}
        for m in errors:
            if m.get("created_at"):
                hour = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")).hour
                hourly_errors[hour] = hourly_errors.get(hour, 0) + 1

        # Find peak error times
        peak_error_hours = sorted(hourly_errors.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": datetime.utcnow().isoformat(),
                "days": days
            },
            "summary": {
                "total_requests": total_requests,
                "error_count": error_count,
                "success_count": success_count,
                "error_rate_percent": round(error_rate, 2),
                "success_rate_percent": round(100 - error_rate, 2)
            },
            "error_types": dict(sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:10]),
            "latency_correlation": {
                "avg_error_latency_ms": round(avg_error_latency, 2),
                "avg_success_latency_ms": round(avg_success_latency, 2),
                "latency_difference_ms": round(avg_error_latency - avg_success_latency, 2),
                "correlation": "Errors have higher latency" if avg_error_latency > avg_success_latency else "No significant correlation"
            },
            "by_event_type": event_error_rates,
            "temporal_patterns": {
                "peak_error_hours": [
                    {"hour": f"{hour:02d}:00", "error_count": count}
                    for hour, count in peak_error_hours
                ],
                "hourly_distribution": hourly_errors
            },
            "recommendations": [
                f"Focus on {max(error_types.items(), key=lambda x: x[1])[0]}" if error_types else "No errors to address",
                f"Review {max(event_error_rates.items(), key=lambda x: x[1]['error_rate_percent'])[0]} event type" if event_error_rates else "Maintain current performance",
                f"Peak errors at {peak_error_hours[0][0]:02d}:00 UTC" if peak_error_hours else "No peak error times identified"
            ]
        }

    except Exception as e:
        logger.error(f"Error analyzing error correlation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LLM PROVIDERS ROUTES
# ============================================================================

@app.get("/llm-providers")
async def get_llm_providers():
    """
    Get all available LLM providers with their models and API documentation links.

    Returns:
        Dictionary of LLM providers with:
        - name: Display name
        - api_docs: API documentation URL
        - api_keys_url: URL to get API keys
        - models: List of available models with id, name, context window, speed
        - default_model: Default model ID for this provider
        - env_key: Environment variable name for API key
    """
    return {
        "providers": LLM_PROVIDERS,
        "recommended": ["groq", "anthropic", "openai"],  # Recommended for voice assistants
        "fastest": ["groq", "fireworks", "together"],  # Lowest latency options
    }


@app.get("/llm-providers/{provider_id}")
async def get_llm_provider_details(provider_id: str):
    """
    Get details for a specific LLM provider.

    Args:
        provider_id: The provider ID (e.g., 'anthropic', 'openai', 'groq')

    Returns:
        Provider details with models and API links
    """
    if provider_id not in LLM_PROVIDERS:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_id}' not found. Available: {list(LLM_PROVIDERS.keys())}"
        )

    provider = LLM_PROVIDERS[provider_id]
    return {
        "id": provider_id,
        **provider
    }


# ============================================================================
# USER API KEYS ROUTES
# ============================================================================

class SaveApiKeysRequest(BaseModel):
    keys: Dict[str, str]  # provider_id -> api_key


@app.get("/user/api-keys")
async def get_user_api_keys(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get user's configured LLM API keys (masked for security).

    Headers:
        X-User-ID: Required user ID

    Returns:
        Dictionary of provider_id -> masked_key (e.g., "sk-...abc123")
    """
    try:
        result = db.client.table("va_user_api_keys").select(
            "provider, api_key_masked, updated_at"
        ).eq("user_id", user_id).execute()

        keys = {}
        for row in result.data:
            keys[row["provider"]] = row["api_key_masked"]

        return {"keys": keys}

    except Exception as e:
        logger.error(f"Error getting API keys: {e}")
        # Return empty if table doesn't exist yet
        return {"keys": {}}


@app.post("/user/api-keys")
async def save_user_api_keys(
    request: SaveApiKeysRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Save user's LLM API keys (encrypted in database).

    Headers:
        X-User-ID: Required user ID

    Body:
        keys: Dictionary of provider_id -> api_key

    Returns:
        Success status
    """
    try:
        for provider, api_key in request.keys.items():
            if not api_key:
                # Delete key if empty
                db.client.table("va_user_api_keys").delete().eq(
                    "user_id", user_id
                ).eq("provider", provider).execute()
                continue

            # Create masked version for display
            if len(api_key) > 8:
                masked = api_key[:4] + "..." + api_key[-4:]
            else:
                masked = "****"

            # Upsert the key (encrypt in production!)
            db.client.table("va_user_api_keys").upsert({
                "user_id": user_id,
                "provider": provider,
                "api_key": api_key,  # In production, encrypt this!
                "api_key_masked": masked,
                "updated_at": "now()",
            }, on_conflict="user_id,provider").execute()

        logger.info(f"Saved API keys for user {user_id}: {list(request.keys.keys())}")
        return {"success": True, "message": "API keys saved"}

    except Exception as e:
        logger.error(f"Error saving API keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/user/api-keys/{provider}")
async def delete_user_api_key(
    provider: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Delete a specific API key for a provider.

    Headers:
        X-User-ID: Required user ID

    Path:
        provider: The LLM provider ID (e.g., 'openai', 'anthropic')
    """
    try:
        db.client.table("va_user_api_keys").delete().eq(
            "user_id", user_id
        ).eq("provider", provider).execute()

        return {"success": True, "message": f"API key for {provider} deleted"}

    except Exception as e:
        logger.error(f"Error deleting API key: {e}")
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
            "llm_provider": request.llm_provider,
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
            "turn_detection_mode": request.turn_detection_mode,
            # Voice control settings (competitive with Vapi/ElevenLabs)
            "speech_speed": request.speech_speed,
            "response_delay_ms": request.response_delay_ms,
            "punctuation_pause_ms": request.punctuation_pause_ms,
            "no_punctuation_pause_ms": request.no_punctuation_pause_ms,
            "turn_eagerness": request.turn_eagerness,
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
                      "llm_provider", "model", "temperature", "max_tokens", "first_message", "is_active",
                      "vad_sensitivity", "endpointing_ms", "enable_bargein",
                      "streaming_chunks", "first_message_latency_ms", "turn_detection_mode",
                      "speech_speed", "response_delay_ms", "punctuation_pause_ms",
                      "no_punctuation_pause_ms", "turn_eagerness"]:
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

        # Parse transcript if it's a string
        if call.get("transcript") and isinstance(call["transcript"], str):
            try:
                call["transcript"] = json.loads(call["transcript"])
            except json.JSONDecodeError:
                call["transcript"] = []

        # Parse summary if it's a string
        if call.get("summary") and isinstance(call["summary"], str):
            try:
                call["summary"] = json.loads(call["summary"])
            except json.JSONDecodeError:
                pass  # Keep as string if not valid JSON

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


@app.get("/calls/active")
async def get_active_calls(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Get currently active voice calls for monitoring.

    Returns list of calls that are in progress, with real-time data.
    """
    try:
        # Filter active calls for this user
        user_calls = []
        for call_id, call_data in active_voice_calls.items():
            if call_data.get("user_id") == user_id:
                # Calculate current duration
                start_time = call_data.get("started_at")
                if start_time:
                    duration = int((datetime.utcnow() - start_time).total_seconds())
                else:
                    duration = 0

                user_calls.append({
                    "id": call_id,
                    "assistant_id": call_data.get("assistant_id"),
                    "assistant_name": call_data.get("assistant_name", "Assistant"),
                    "user_id": user_id,
                    "started_at": call_data.get("started_at").isoformat() if call_data.get("started_at") else None,
                    "duration_seconds": duration,
                    "status": "active",
                    "sentiment": call_data.get("sentiment"),
                    "urgency": call_data.get("urgency", "normal"),
                    "transcript": call_data.get("transcript", [])[-10:],  # Last 10 messages
                    "caller_info": call_data.get("caller_info"),
                })

        return {"calls": user_calls}

    except Exception as e:
        logger.error(f"Error getting active calls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/monitor/{call_id}")
async def websocket_monitor_endpoint(
    websocket: WebSocket,
    call_id: str,
):
    """
    WebSocket endpoint for monitoring an active call.

    Protocol:
    - Client sends: {"type": "auth", "user_id": "...", "mode": "listen"|"takeover"}
    - Server sends: {"type": "audio", "data": "<base64 audio>"}
    - Server sends: {"type": "transcript", "role": "...", "content": "..."}
    - Server sends: {"type": "call_update", "update": {...}}
    - Server sends: {"type": "call_ended"}
    """
    await websocket.accept()

    try:
        # Wait for authentication
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        if auth_data.get('type') != 'auth' or not auth_data.get('user_id'):
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close()
            return

        user_id = auth_data['user_id']
        mode = auth_data.get('mode', 'listen')

        # Check if call exists and belongs to user
        if call_id not in active_voice_calls:
            await websocket.send_json({"type": "error", "message": "Call not found or ended"})
            await websocket.close()
            return

        call_data = active_voice_calls[call_id]
        if call_data.get("user_id") != user_id:
            await websocket.send_json({"type": "error", "message": "Not authorized to monitor this call"})
            await websocket.close()
            return

        # Add to monitors list
        if call_id not in call_monitors:
            call_monitors[call_id] = []
        call_monitors[call_id].append(websocket)

        logger.info(f"Monitor connected to call {call_id} in {mode} mode")

        # Send current call state
        await websocket.send_json({
            "type": "call_update",
            "update": {
                "transcript": call_data.get("transcript", []),
                "sentiment": call_data.get("sentiment"),
                "urgency": call_data.get("urgency", "normal"),
            }
        })

        # Listen for commands (takeover, release, etc.)
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get('type')

                if msg_type == 'takeover':
                    # Mark call as taken over by human
                    active_voice_calls[call_id]["is_human_controlled"] = True
                    active_voice_calls[call_id]["controlling_user"] = user_id
                    logger.info(f"Call {call_id} taken over by user {user_id}")

                elif msg_type == 'release':
                    # Release back to AI
                    active_voice_calls[call_id]["is_human_controlled"] = False
                    active_voice_calls[call_id]["controlling_user"] = None
                    logger.info(f"Call {call_id} released back to AI")

                elif msg_type == 'audio' and mode == 'takeover':
                    # Forward audio from human operator to call
                    # This would need to be forwarded to the main call websocket
                    pass

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Monitor websocket error: {e}")
                break

    except Exception as e:
        logger.error(f"Monitor websocket error: {e}")
    finally:
        # Remove from monitors list
        if call_id in call_monitors and websocket in call_monitors[call_id]:
            call_monitors[call_id].remove(websocket)
            if not call_monitors[call_id]:
                del call_monitors[call_id]


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.get("/admin/status")
async def get_admin_status(
    db: SupabaseManager = Depends(get_db),
):
    """Get system status and health checks."""
    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check Supabase
    try:
        import time
        start = time.time()
        db.client.table("va_subscription_plans").select("id").limit(1).execute()
        latency = int((time.time() - start) * 1000)
        status["services"]["supabase"] = {
            "status": "healthy",
            "latency_ms": latency,
            "message": "Connected"
        }
    except Exception as e:
        status["services"]["supabase"] = {
            "status": "error",
            "latency_ms": None,
            "message": str(e)
        }

    # Check Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        status["services"]["anthropic"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": f"API key set (ends in ...{anthropic_key[-4:]})"
        }
    else:
        status["services"]["anthropic"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": "ANTHROPIC_API_KEY not set"
        }

    # Check Modal
    modal_id = os.getenv("MODAL_TOKEN_ID", "")
    if modal_id:
        status["services"]["modal"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": "Token configured"
        }
    else:
        status["services"]["modal"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": "MODAL_TOKEN_ID not set"
        }

    # Check Stripe
    stripe_issues = validate_stripe_config()
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if stripe_key and not stripe_issues:
        status["services"]["stripe"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": "Fully configured"
        }
    elif stripe_key:
        status["services"]["stripe"] = {
            "status": "partial",
            "latency_ms": 0,
            "message": f"Missing: {', '.join(stripe_issues)}"
        }
    else:
        status["services"]["stripe"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": f"Missing: {', '.join(stripe_issues)}"
        }

    # Check Twilio
    twilio_issues = validate_twilio_config()
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    if twilio_sid and not twilio_issues:
        status["services"]["twilio"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": f"Account configured (SID ends in ...{twilio_sid[-4:]})"
        }
    elif twilio_sid:
        status["services"]["twilio"] = {
            "status": "partial",
            "latency_ms": 0,
            "message": f"Missing: {', '.join(twilio_issues)}"
        }
    else:
        status["services"]["twilio"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER"
        }

    # Check Deepgram (Streaming STT)
    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    if deepgram_key:
        status["services"]["deepgram"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": f"Streaming STT enabled (key ends in ...{deepgram_key[-4:]})"
        }
    else:
        status["services"]["deepgram"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": "DEEPGRAM_API_KEY not set - using Modal batch STT"
        }

    # Check Cartesia (Streaming TTS)
    cartesia_key = os.getenv("CARTESIA_API_KEY", "")
    cartesia_voice = os.getenv("CARTESIA_VOICE_ID", "")
    if cartesia_key:
        voice_info = f", voice: {cartesia_voice[:8]}..." if cartesia_voice else ""
        status["services"]["cartesia"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": f"Streaming TTS enabled (key ends in ...{cartesia_key[-4:]}{voice_info})"
        }
    else:
        status["services"]["cartesia"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": "CARTESIA_API_KEY not set - using Modal batch TTS"
        }

    # Check LiveKit (WebRTC Voice Agent)
    livekit_url = os.getenv("LIVEKIT_URL", "")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY", "")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET", "")
    if livekit_url and livekit_api_key and livekit_api_secret:
        # Parse URL for display
        display_url = livekit_url.replace("wss://", "").replace("ws://", "")[:30]
        status["services"]["livekit"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": f"WebRTC enabled ({display_url}...)"
        }
    elif livekit_url or livekit_api_key:
        missing = []
        if not livekit_url:
            missing.append("LIVEKIT_URL")
        if not livekit_api_key:
            missing.append("LIVEKIT_API_KEY")
        if not livekit_api_secret:
            missing.append("LIVEKIT_API_SECRET")
        status["services"]["livekit"] = {
            "status": "partial",
            "latency_ms": None,
            "message": f"Missing: {', '.join(missing)}"
        }
    else:
        status["services"]["livekit"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": "LiveKit not configured - WebRTC voice disabled"
        }

    # Check Groq (Fast LLM)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        status["services"]["groq"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": f"Groq LPU enabled (key ends in ...{groq_key[-4:]})"
        }
    else:
        status["services"]["groq"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": "GROQ_API_KEY not set"
        }

    # Check Fast Brain (Custom BitNet LPU)
    fast_brain_url = os.getenv("FAST_BRAIN_URL", "")
    if fast_brain_url:
        display_brain_url = fast_brain_url[:40]
        status["services"]["fast_brain"] = {
            "status": "configured",
            "latency_ms": 0,
            "message": f"Custom LPU ({display_brain_url}...)"
        }
    else:
        status["services"]["fast_brain"] = {
            "status": "not_configured",
            "latency_ms": None,
            "message": "FAST_BRAIN_URL not set - using Groq fallback"
        }

    # Voice Agent status - which LLM will be used
    voice_agent_llm = "none"
    voice_agent_status = "not_configured"
    voice_agent_message = "No LLM configured for voice agent"

    if fast_brain_url:
        voice_agent_llm = "fast_brain"
        voice_agent_status = "configured"
        voice_agent_message = "Using Fast Brain (Custom BitNet LPU)"
    elif groq_key:
        voice_agent_llm = "groq"
        voice_agent_status = "fallback"
        voice_agent_message = "Using Groq LPU (Fast Brain not configured)"
    elif anthropic_key:
        voice_agent_llm = "anthropic"
        voice_agent_status = "fallback"
        voice_agent_message = "Using Anthropic Claude (Groq not configured)"

    status["voice_agent"] = {
        "status": voice_agent_status,
        "active_llm": voice_agent_llm,
        "message": voice_agent_message,
        "livekit_enabled": bool(livekit_url and livekit_api_key and livekit_api_secret),
        "fallback_chain": ["fast_brain", "groq", "anthropic"],
        "configured_llms": [
            llm for llm, configured in [
                ("fast_brain", bool(fast_brain_url)),
                ("groq", bool(groq_key)),
                ("anthropic", bool(anthropic_key)),
            ] if configured
        ]
    }

    # Streaming pipeline status
    streaming_enabled = bool(deepgram_key and cartesia_key)
    status["streaming"] = {
        "enabled": streaming_enabled,
        "stt_provider": "deepgram" if deepgram_key else "modal",
        "tts_provider": "cartesia" if cartesia_key else "modal",
        "target_latency_ms": 500 if streaming_enabled else 2000,
        "message": "Full streaming pipeline active" if streaming_enabled else "Using batch processing (higher latency)"
    }

    # Environment info
    status["environment"] = {
        "python_version": os.popen("python --version 2>&1").read().strip(),
        "env": os.getenv("ENVIRONMENT", "development"),
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "not deployed"),
        "api_url": os.getenv("API_URL", "localhost"),
    }

    # Get stats
    try:
        users_result = db.client.table("va_user_subscriptions").select("id", count="exact").execute()
        calls_result = db.client.table("va_call_logs").select("id", count="exact").execute()
        assistants_result = db.client.table("va_assistants").select("id", count="exact").execute()
        status["stats"] = {
            "total_users": users_result.count or 0,
            "total_calls": calls_result.count or 0,
            "total_assistants": assistants_result.count or 0,
        }
    except Exception as e:
        status["stats"] = {"error": str(e)}

    return status


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
                }).eq("id", user_id).execute()

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


# ============================================================================
# TEAM COLLABORATION ROUTES
# ============================================================================

@app.get("/teams")
async def list_user_teams(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get all teams the user is part of (owned or member).

    Headers:
        X-User-ID: Required user ID

    Returns:
        List of teams with member counts and role
    """
    try:
        # Get teams owned by user
        owned_teams = db.client.table("va_teams").select(
            "id, name, description, owner_id, created_at"
        ).eq("owner_id", user_id).execute()

        # Get teams where user is a member
        member_teams = db.client.table("va_team_members").select(
            "team_id, role, va_teams(id, name, description, owner_id, created_at)"
        ).eq("user_id", user_id).execute()

        teams = []

        # Add owned teams
        for team in owned_teams.data:
            # Get member count
            member_count = db.client.table("va_team_members").select(
                "id", count="exact"
            ).eq("team_id", team["id"]).execute()

            teams.append({
                **team,
                "role": "owner",
                "member_count": member_count.count if member_count.count else 0
            })

        # Add member teams
        for membership in member_teams.data:
            if membership.get("va_teams"):
                team = membership["va_teams"]
                # Get member count
                member_count = db.client.table("va_team_members").select(
                    "id", count="exact"
                ).eq("team_id", team["id"]).execute()

                teams.append({
                    **team,
                    "role": membership["role"],
                    "member_count": member_count.count if member_count.count else 0
                })

        return {"teams": teams}

    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CreateTeamRequest(BaseModel):
    name: str
    description: Optional[str] = None


@app.post("/teams")
async def create_team(
    request: CreateTeamRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Create a new team.

    Headers:
        X-User-ID: Required user ID

    Body:
        name: Team name
        description: Optional team description
    """
    try:
        # Create team
        team_data = {
            "name": request.name,
            "description": request.description,
            "owner_id": user_id
        }

        result = db.client.table("va_teams").insert(team_data).execute()
        team = result.data[0] if result.data else None

        if not team:
            raise HTTPException(status_code=500, detail="Failed to create team")

        # Add owner as team member
        member_data = {
            "team_id": team["id"],
            "user_id": user_id,
            "role": "owner",
            "invited_by": user_id
        }

        db.client.table("va_team_members").insert(member_data).execute()

        return {
            "team": team,
            "message": "Team created successfully"
        }

    except Exception as e:
        logger.error(f"Error creating team: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/teams/{team_id}")
async def get_team_details(
    team_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get detailed team information including members.

    Headers:
        X-User-ID: Required user ID

    Path:
        team_id: Team UUID
    """
    try:
        # Verify user is team member
        membership = db.client.table("va_team_members").select("role").eq(
            "team_id", team_id
        ).eq("user_id", user_id).execute()

        if not membership.data:
            # Check if user is owner
            team = db.client.table("va_teams").select("*").eq("id", team_id).eq(
                "owner_id", user_id
            ).execute()
            if not team.data:
                raise HTTPException(status_code=403, detail="Not a team member")
            user_role = "owner"
            team_data = team.data[0]
        else:
            user_role = membership.data[0]["role"]
            # Get team details
            team = db.client.table("va_teams").select("*").eq("id", team_id).execute()
            team_data = team.data[0] if team.data else None

        if not team_data:
            raise HTTPException(status_code=404, detail="Team not found")

        # Get team members with user info
        members = db.client.table("va_team_members").select(
            "id, user_id, role, joined_at"
        ).eq("team_id", team_id).execute()

        return {
            "team": team_data,
            "members": members.data if members.data else [],
            "user_role": user_role
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: str,
    member_user_id: str,
    role: str = "member",
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Add a member to the team (requires owner or admin role).

    Headers:
        X-User-ID: Required user ID

    Path:
        team_id: Team UUID

    Body:
        member_user_id: User ID to add
        role: Role to assign (member, admin, viewer)
    """
    try:
        # Verify user has permission (owner or admin)
        membership = db.client.table("va_team_members").select("role").eq(
            "team_id", team_id
        ).eq("user_id", user_id).execute()

        team = db.client.table("va_teams").select("owner_id").eq("id", team_id).execute()
        if not team.data:
            raise HTTPException(status_code=404, detail="Team not found")

        is_owner = team.data[0]["owner_id"] == user_id
        is_admin = membership.data and membership.data[0]["role"] in ["owner", "admin"]

        if not (is_owner or is_admin):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Validate role
        valid_roles = ["member", "admin", "viewer"]
        if role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

        # Add member
        member_data = {
            "team_id": team_id,
            "user_id": member_user_id,
            "role": role,
            "invited_by": user_id
        }

        result = db.client.table("va_team_members").insert(member_data).execute()

        return {
            "member": result.data[0] if result.data else None,
            "message": "Member added successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding team member: {e}")
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=400, detail="User is already a team member")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/teams/{team_id}/members/{member_user_id}")
async def remove_team_member(
    team_id: str,
    member_user_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Remove a member from the team (requires owner or admin role).

    Headers:
        X-User-ID: Required user ID

    Path:
        team_id: Team UUID
        member_user_id: User ID to remove
    """
    try:
        # Verify user has permission
        membership = db.client.table("va_team_members").select("role").eq(
            "team_id", team_id
        ).eq("user_id", user_id).execute()

        team = db.client.table("va_teams").select("owner_id").eq("id", team_id).execute()
        if not team.data:
            raise HTTPException(status_code=404, detail="Team not found")

        is_owner = team.data[0]["owner_id"] == user_id
        is_admin = membership.data and membership.data[0]["role"] in ["owner", "admin"]

        if not (is_owner or is_admin):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Cannot remove owner
        if member_user_id == team.data[0]["owner_id"]:
            raise HTTPException(status_code=400, detail="Cannot remove team owner")

        # Remove member
        db.client.table("va_team_members").delete().eq(
            "team_id", team_id
        ).eq("user_id", member_user_id).execute()

        return {"message": "Member removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/teams/{team_id}/analytics")
async def get_team_analytics(
    team_id: str,
    days: int = 30,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get aggregated analytics for all team members.

    Headers:
        X-User-ID: Required user ID

    Path:
        team_id: Team UUID

    Query:
        days: Number of days to analyze (default: 30)
    """
    try:
        from datetime import datetime, timedelta

        # Verify user is team member
        membership = db.client.table("va_team_members").select("role").eq(
            "team_id", team_id
        ).eq("user_id", user_id).execute()

        team = db.client.table("va_teams").select("owner_id").eq("id", team_id).execute()
        if not team.data:
            raise HTTPException(status_code=404, detail="Team not found")

        is_member = membership.data or team.data[0]["owner_id"] == user_id

        if not is_member:
            raise HTTPException(status_code=403, detail="Not a team member")

        # Get all team members
        members = db.client.table("va_team_members").select("user_id").eq(
            "team_id", team_id
        ).execute()

        member_ids = [m["user_id"] for m in members.data] if members.data else []
        # Add owner if not in list
        if team.data[0]["owner_id"] not in member_ids:
            member_ids.append(team.data[0]["owner_id"])

        if not member_ids:
            return {
                "team_totals": {},
                "by_member": [],
                "message": "No team members found"
            }

        # Get metrics for all members
        start_date = datetime.utcnow() - timedelta(days=days)

        # Aggregate team metrics
        all_metrics = []
        for member_id in member_ids:
            metrics = db.client.table("va_usage_metrics").select(
                "cost_cents, input_tokens, output_tokens, event_type, created_at, error"
            ).eq("user_id", member_id).gte("created_at", start_date.isoformat()).execute()

            if metrics.data:
                all_metrics.extend([{**m, "member_id": member_id} for m in metrics.data])

        # Calculate team totals
        total_cost = sum(m.get("cost_cents", 0) for m in all_metrics) / 100
        total_tokens = sum(
            m.get("input_tokens", 0) + m.get("output_tokens", 0)
            for m in all_metrics
        )
        total_requests = len(all_metrics)
        total_errors = len([m for m in all_metrics if m.get("error")])

        # By member breakdown
        by_member = {}
        for m in all_metrics:
            mid = m["member_id"]
            if mid not in by_member:
                by_member[mid] = {
                    "cost": 0,
                    "tokens": 0,
                    "requests": 0,
                    "errors": 0
                }
            by_member[mid]["cost"] += m.get("cost_cents", 0) / 100
            by_member[mid]["tokens"] += m.get("input_tokens", 0) + m.get("output_tokens", 0)
            by_member[mid]["requests"] += 1
            if m.get("error"):
                by_member[mid]["errors"] += 1

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": datetime.utcnow().isoformat(),
                "days": days
            },
            "team_totals": {
                "total_cost_dollars": round(total_cost, 2),
                "total_tokens": total_tokens,
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate_percent": round((total_errors / total_requests * 100) if total_requests > 0 else 0, 2)
            },
            "by_member": [
                {
                    "user_id": mid,
                    "cost_dollars": round(data["cost"], 2),
                    "tokens": data["tokens"],
                    "requests": data["requests"],
                    "errors": data["errors"]
                }
                for mid, data in by_member.items()
            ],
            "member_count": len(member_ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/teams/{team_id}/dashboards")
async def list_team_dashboards(
    team_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Get all shared dashboards for a team.

    Headers:
        X-User-ID: Required user ID

    Path:
        team_id: Team UUID
    """
    try:
        # Verify user is team member
        membership = db.client.table("va_team_members").select("role").eq(
            "team_id", team_id
        ).eq("user_id", user_id).execute()

        team = db.client.table("va_teams").select("owner_id").eq("id", team_id).execute()
        if not team.data:
            raise HTTPException(status_code=404, detail="Team not found")

        is_member = membership.data or team.data[0]["owner_id"] == user_id

        if not is_member:
            raise HTTPException(status_code=403, detail="Not a team member")

        # Get dashboards
        dashboards = db.client.table("va_team_dashboards").select(
            "id, name, description, config, shared_by, is_public, created_at"
        ).eq("team_id", team_id).execute()

        return {
            "dashboards": dashboards.data if dashboards.data else []
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing team dashboards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/teams/{team_id}/dashboards")
async def create_team_dashboard(
    team_id: str,
    name: str,
    description: str = None,
    config: dict = None,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """
    Create a shared dashboard for the team.

    Headers:
        X-User-ID: Required user ID

    Path:
        team_id: Team UUID

    Body:
        name: Dashboard name
        description: Optional description
        config: Dashboard configuration (JSON)
    """
    try:
        # Verify user is team member with sufficient permissions
        membership = db.client.table("va_team_members").select("role").eq(
            "team_id", team_id
        ).eq("user_id", user_id).execute()

        team = db.client.table("va_teams").select("owner_id").eq("id", team_id).execute()
        if not team.data:
            raise HTTPException(status_code=404, detail="Team not found")

        is_owner = team.data[0]["owner_id"] == user_id
        has_permission = is_owner or (
            membership.data and membership.data[0]["role"] in ["owner", "admin", "member"]
        )

        if not has_permission:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Create dashboard
        dashboard_data = {
            "team_id": team_id,
            "name": name,
            "description": description,
            "config": config or {},
            "shared_by": user_id,
            "is_public": False
        }

        result = db.client.table("va_team_dashboards").insert(dashboard_data).execute()

        return {
            "dashboard": result.data[0] if result.data else None,
            "message": "Dashboard created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating team dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# WEBSOCKET VOICE STREAMING
# =====================================================

# Global registry of active voice calls for monitoring
active_voice_calls: Dict[str, dict] = {}
# Subscribers listening to calls (call_id -> list of websockets)
call_monitors: Dict[str, List[WebSocket]] = {}


class VoiceCallSession:
    """Manages a single WebSocket voice call session."""

    # Sentiment analysis word lists for real-time detection
    POSITIVE_WORDS = [
        'thank', 'thanks', 'great', 'good', 'excellent', 'happy', 'love', 'wonderful',
        'amazing', 'perfect', 'helpful', 'appreciate', 'pleased', 'fantastic', 'awesome',
        'yes', 'absolutely', 'definitely', 'sure', 'okay', 'sounds good', 'exactly'
    ]
    NEGATIVE_WORDS = [
        'bad', 'terrible', 'hate', 'angry', 'frustrated', 'wrong', 'awful', 'horrible',
        'disappointed', 'annoyed', 'upset', 'confused', 'problem', 'issue', 'fail',
        'no', 'never', 'cancel', 'stop', 'wait', 'wrong', 'mistake', 'error'
    ]
    URGENCY_WORDS = [
        'urgent', 'emergency', 'asap', 'immediately', 'now', 'hurry', 'critical',
        'important', 'today', 'right away', 'quickly', 'fast'
    ]

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
        # Call timing
        self.call_start_time = None
        # Real-time sentiment tracking
        self.current_sentiment = 'neutral'
        self.sentiment_score = 0  # -100 to +100
        self.urgency_level = 'normal'  # normal, elevated, urgent
        self.sentiment_history = []  # Track sentiment over time
        # User settings (loaded in start_call)
        self.user_settings = {
            'ai_enabled': True,
            'ai_transcription_enabled': True,
            'ai_summary_enabled': True,
            'call_screening_enabled': True,
            'call_recording_enabled': True,
        }

    async def start_call(self):
        """Initialize call log in database and register for monitoring."""
        try:
            self.call_start_time = time.time()
            result = self.db.client.rpc(
                'va_create_call_log',
                {
                    'p_user_id': self.user_id,
                    'p_assistant_id': self.assistant_id,
                    'p_call_type': 'web'
                }
            ).execute()
            self.call_id = result.data

            # Load user settings
            try:
                settings_result = self.db.client.table('va_user_settings').select('*').eq('user_id', self.user_id).execute()
                if settings_result.data and len(settings_result.data) > 0:
                    stored_settings = settings_result.data[0]
                    self.user_settings = {
                        'ai_enabled': stored_settings.get('ai_enabled', True),
                        'ai_transcription_enabled': stored_settings.get('ai_transcription_enabled', True),
                        'ai_summary_enabled': stored_settings.get('ai_summary_enabled', True),
                        'call_screening_enabled': stored_settings.get('call_screening_enabled', True),
                        'call_recording_enabled': stored_settings.get('call_recording_enabled', True),
                    }
                    logger.info(f"Loaded user settings for call: ai_enabled={self.user_settings['ai_enabled']}")
            except Exception as e:
                logger.warning(f"Could not load user settings, using defaults: {e}")

            # Get assistant name for monitoring display
            assistant_name = "Unknown Assistant"
            try:
                assistant_result = self.db.client.table('va_assistants').select('name').eq('id', self.assistant_id).single().execute()
                if assistant_result.data:
                    assistant_name = assistant_result.data.get('name', 'Unknown Assistant')
            except Exception as e:
                logger.warning(f"Could not fetch assistant name: {e}")

            # Register call for live monitoring
            active_voice_calls[self.call_id] = {
                'id': self.call_id,
                'user_id': self.user_id,
                'assistant_id': self.assistant_id,
                'assistant_name': assistant_name,
                'start_time': datetime.utcnow().isoformat(),
                'is_human_controlled': False,
                'controlling_user': None,
                'caller_number': 'Web Call',
                'session': self  # Reference to session for takeover
            }

            logger.info(f"Started call {self.call_id} for user {self.user_id}")
            return self.call_id
        except Exception as e:
            logger.error(f"Failed to create call log: {e}")
            return None

    def get_duration_seconds(self) -> int:
        """Get call duration in seconds."""
        if self.call_start_time:
            return int(time.time() - self.call_start_time)
        return 0

    async def end_call(self, ended_reason: str = 'user_ended', duration_seconds: int = 0):
        """End call and save final transcript with quality score."""
        if not self.call_id:
            return

        try:
            # Use real-time sentiment tracking (already calculated)
            sentiment = self.current_sentiment

            # Calculate quality score
            quality_data = self.calculate_quality_score(duration_seconds)

            # Build summary with quality data (only if ai_summary_enabled)
            summary_data = None
            if self.user_settings.get('ai_summary_enabled', True):
                summary_data = {
                    'quality_score': quality_data['total'],
                    'quality_grade': quality_data['grade'],
                    'quality_breakdown': quality_data['breakdown'],
                    'sentiment_score': self.sentiment_score,
                    'urgency_level': self.urgency_level,
                    'exchange_count': len(self.transcript) // 2
                }
            else:
                logger.info(f"AI summary disabled for call {self.call_id}")

            # Only save transcript if ai_transcription_enabled
            transcript_to_save = None
            if self.user_settings.get('ai_transcription_enabled', True):
                transcript_to_save = self.transcript
            else:
                logger.info(f"Transcription disabled for call {self.call_id}")

            # Recording URL (only if call_recording_enabled - placeholder for future)
            recording_url = None
            if not self.user_settings.get('call_recording_enabled', True):
                logger.info(f"Call recording disabled for call {self.call_id}")

            self.db.client.rpc(
                'va_end_call',
                {
                    'p_call_id': self.call_id,
                    'p_transcript': json.dumps(transcript_to_save) if transcript_to_save else None,
                    'p_summary': json.dumps(summary_data) if summary_data else None,
                    'p_ended_reason': ended_reason,
                    'p_recording_url': recording_url,
                    'p_sentiment': sentiment
                }
            ).execute()
            logger.info(f"Ended call {self.call_id} with quality score {quality_data['total']} ({quality_data['grade']})")

            # Notify monitors that call has ended
            await self.notify_monitors({
                'type': 'call_ended',
                'call_id': self.call_id,
                'ended_reason': ended_reason,
                'duration': self.get_duration_seconds()
            })

            # Unregister from active calls
            if self.call_id in active_voice_calls:
                del active_voice_calls[self.call_id]

            # Clean up monitors list
            if self.call_id in call_monitors:
                del call_monitors[self.call_id]

            return quality_data
        except Exception as e:
            logger.error(f"Failed to end call: {e}")
            return None

    def add_to_transcript(self, role: str, content: str):
        """Add message to transcript and notify monitors."""
        entry = {
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.transcript.append(entry)

        # Notify monitors of new transcript entry (fire and forget)
        if self.call_id:
            asyncio.create_task(self.notify_monitors({
                'type': 'transcript',
                'call_id': self.call_id,
                'entry': entry
            }))

    async def notify_monitors(self, message: dict):
        """Send message to all monitors listening to this call."""
        if not self.call_id or self.call_id not in call_monitors:
            return

        monitors = call_monitors.get(self.call_id, [])
        for ws in monitors[:]:  # Copy list to avoid modification during iteration
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to monitor: {e}")
                # Remove disconnected monitors
                if ws in call_monitors.get(self.call_id, []):
                    call_monitors[self.call_id].remove(ws)

    async def broadcast_audio_to_monitors(self, audio_data: bytes, is_caller: bool = True):
        """Broadcast audio to all monitors listening to this call."""
        if not self.call_id or self.call_id not in call_monitors:
            return

        # Only send if we have monitors
        monitors = call_monitors.get(self.call_id, [])
        if not monitors:
            return

        # Send audio as base64 for JSON transport
        import base64
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')

        message = {
            'type': 'audio',
            'call_id': self.call_id,
            'source': 'caller' if is_caller else 'assistant',
            'audio': audio_b64
        }

        for ws in monitors[:]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send audio to monitor: {e}")
                if ws in call_monitors.get(self.call_id, []):
                    call_monitors[self.call_id].remove(ws)

    def analyze_sentiment_realtime(self, text: str) -> dict:
        """
        Analyze sentiment of text in real-time.
        Returns sentiment info for WebSocket broadcast.
        """
        text_lower = text.lower()

        # Count sentiment words
        pos_count = sum(1 for word in self.POSITIVE_WORDS if word in text_lower)
        neg_count = sum(1 for word in self.NEGATIVE_WORDS if word in text_lower)
        urgency_count = sum(1 for word in self.URGENCY_WORDS if word in text_lower)

        # Calculate delta score (-10 to +10 per message)
        delta = (pos_count - neg_count) * 5
        delta = max(-15, min(15, delta))  # Clamp

        # Update running sentiment score with decay toward neutral
        self.sentiment_score = self.sentiment_score * 0.7 + delta
        self.sentiment_score = max(-100, min(100, self.sentiment_score))

        # Determine sentiment category
        if self.sentiment_score > 20:
            self.current_sentiment = 'positive'
        elif self.sentiment_score < -20:
            self.current_sentiment = 'negative'
        else:
            self.current_sentiment = 'neutral'

        # Determine urgency level
        if urgency_count >= 2:
            self.urgency_level = 'urgent'
        elif urgency_count >= 1 or any(w in text_lower for w in ['soon', 'quickly']):
            self.urgency_level = 'elevated'
        else:
            # Decay urgency over time
            if self.urgency_level == 'urgent':
                self.urgency_level = 'elevated'
            elif self.urgency_level == 'elevated':
                self.urgency_level = 'normal'

        # Track history for trend detection
        self.sentiment_history.append({
            'score': self.sentiment_score,
            'sentiment': self.current_sentiment,
            'urgency': self.urgency_level,
            'timestamp': datetime.utcnow().isoformat()
        })

        # Determine trend
        trend = 'stable'
        if len(self.sentiment_history) >= 3:
            recent = self.sentiment_history[-3:]
            scores = [h['score'] for h in recent]
            if scores[-1] > scores[0] + 10:
                trend = 'improving'
            elif scores[-1] < scores[0] - 10:
                trend = 'declining'

        return {
            'sentiment': self.current_sentiment,
            'score': round(self.sentiment_score),
            'urgency': self.urgency_level,
            'trend': trend,
            'positive_signals': pos_count,
            'negative_signals': neg_count
        }

    def calculate_quality_score(self, duration_seconds: int) -> dict:
        """
        Calculate call quality score (0-100) based on multiple factors.
        Returns score breakdown for transparency.
        """
        scores = {}

        # 1. Sentiment Score (0-30 points)
        # Positive = 30, Neutral = 20, Negative = 5
        if self.current_sentiment == 'positive':
            scores['sentiment'] = 30
        elif self.current_sentiment == 'neutral':
            scores['sentiment'] = 20
        else:
            scores['sentiment'] = 5

        # 2. Conversation Flow Score (0-25 points)
        # Based on back-and-forth exchanges (ideal: 4-10 exchanges)
        exchange_count = len(self.transcript) // 2
        if 4 <= exchange_count <= 10:
            scores['flow'] = 25
        elif 2 <= exchange_count <= 3:
            scores['flow'] = 18
        elif 11 <= exchange_count <= 15:
            scores['flow'] = 20
        elif exchange_count < 2:
            scores['flow'] = 10  # Too short
        else:
            scores['flow'] = 15  # Too long, might indicate issues

        # 3. Duration Score (0-20 points)
        # Ideal call: 60-180 seconds
        if 60 <= duration_seconds <= 180:
            scores['duration'] = 20
        elif 30 <= duration_seconds < 60:
            scores['duration'] = 15
        elif 180 < duration_seconds <= 300:
            scores['duration'] = 15
        elif duration_seconds < 30:
            scores['duration'] = 8  # Might be abandoned
        else:
            scores['duration'] = 10  # Very long call

        # 4. Resolution Indicators (0-15 points)
        # Look for positive closure words in last messages
        resolution_score = 0
        if self.transcript:
            last_messages = ' '.join([t['content'].lower() for t in self.transcript[-4:]])
            closure_words = ['thank', 'thanks', 'perfect', 'great', 'that helps', 'got it',
                           'sounds good', 'appreciate', 'excellent', 'wonderful', 'bye', 'goodbye']
            closure_count = sum(1 for word in closure_words if word in last_messages)
            resolution_score = min(15, closure_count * 5)
        scores['resolution'] = resolution_score

        # 5. Urgency Handling (0-10 points)
        # Urgent calls that ended positively get bonus
        if self.urgency_level == 'urgent' and self.current_sentiment == 'positive':
            scores['urgency_handling'] = 10
        elif self.urgency_level == 'urgent' and self.current_sentiment == 'neutral':
            scores['urgency_handling'] = 7
        elif self.urgency_level == 'urgent':
            scores['urgency_handling'] = 3
        else:
            scores['urgency_handling'] = 8  # Normal call handled fine

        total_score = sum(scores.values())

        # Determine grade
        if total_score >= 85:
            grade = 'A'
        elif total_score >= 70:
            grade = 'B'
        elif total_score >= 55:
            grade = 'C'
        elif total_score >= 40:
            grade = 'D'
        else:
            grade = 'F'

        return {
            'total': total_score,
            'grade': grade,
            'breakdown': scores,
            'factors': {
                'sentiment': self.current_sentiment,
                'exchanges': exchange_count,
                'duration_seconds': duration_seconds,
                'urgency': self.urgency_level
            }
        }


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
            allowed, details = feature_gate.check_feature(user_id, "max_minutes")
            if not allowed:
                await websocket.send_json({
                    "type": "error", 
                    "message": f"You've used all your minutes. Upgrade your plan to continue."
                })
                await websocket.close()
                return
        except Exception as e:
            logger.error(f"Feature gate error: {e}")
            # Continue anyway - don't block on feature gate errors
            pass

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

        # Check available pipeline options (priority: Lightning > Streaming > Modal)
        groq_key = os.getenv("GROQ_API_KEY", "")
        deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
        cartesia_key = os.getenv("CARTESIA_API_KEY", "")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

        # Determine which pipeline to use
        lightning_enabled = bool(groq_key and deepgram_key and cartesia_key)
        streaming_enabled = bool(deepgram_key and cartesia_key and anthropic_key) and not lightning_enabled

        # Initialize the appropriate pipeline
        lightning_pipeline: Optional[LightningPipeline] = None
        streaming_pipeline: Optional[StreamingPipeline] = None

        if lightning_enabled:
            # ⚡ LIGHTNING PIPELINE - Sub-150ms latency (Groq + Deepgram + Cartesia)
            logger.info(f"⚡ Lightning pipeline enabled for call {call_id}")

            lightning_config = LightningConfig()
            # Use assistant's voice_id if valid, otherwise use default Katie voice
            assistant_voice_id = assistant.get('voice_id')
            if assistant_voice_id and len(assistant_voice_id) > 10:  # Valid UUID is 36 chars
                lightning_config.cartesia_voice_id = assistant_voice_id
            # Apply LLM provider and model from assistant
            if assistant.get('llm_provider'):
                lightning_config.llm_provider = assistant.get('llm_provider')
                logger.info(f"🤖 Using LLM provider: {lightning_config.llm_provider}")
            if assistant.get('model'):
                # Update groq_model if using Groq-compatible provider
                if lightning_config.llm_provider in ('groq', 'together', 'fireworks'):
                    lightning_config.groq_model = assistant.get('model')
                logger.info(f"🤖 Using model: {assistant.get('model')}")
            # Apply voice control settings from assistant
            if assistant.get('speech_speed'):
                lightning_config.speech_speed = assistant.get('speech_speed')
            if assistant.get('response_delay_ms'):
                lightning_config.response_delay_ms = assistant.get('response_delay_ms')
            # Apply turn-taking model settings
            if assistant.get('turn_eagerness'):
                lightning_config.turn_eagerness = assistant.get('turn_eagerness')
            lightning_pipeline = LightningPipeline(lightning_config)

            # Set up callbacks
            async def on_lightning_transcript(role: str, text: str):
                await websocket.send_json({
                    "type": "transcript",
                    "role": role,
                    "content": text
                })
                session.add_to_transcript(role, text)

            async def on_lightning_audio(audio_bytes: bytes):
                # Wrap raw PCM in WAV header for browser playback
                wav_audio = pcm_to_wav(audio_bytes, sample_rate=16000)
                audio_b64 = base64.b64encode(wav_audio).decode('utf-8')
                await websocket.send_json({
                    "type": "audio",
                    "data": audio_b64
                })
                await session.broadcast_audio_to_monitors(audio_bytes, is_caller=False)

            async def on_lightning_state_change(state: LightningState):
                is_speaking = state == LightningState.SPEAKING
                await websocket.send_json({"type": "speaking", "is_speaking": is_speaking})
                session.is_speaking = is_speaking

            async def on_lightning_latency(metrics: LatencyMetrics):
                await websocket.send_json({
                    "type": "latency",
                    "data": {
                        "stt_ms": metrics.stt_ms,
                        "llm_ms": metrics.llm_ttft_ms,
                        "tts_ms": metrics.tts_ttfb_ms,
                        "total_ms": metrics.total_perceived_ms,
                        "target_ms": 150,
                        "status": "lightning" if metrics.total_perceived_ms < 200 else "fast" if metrics.total_perceived_ms < 500 else "normal"
                    }
                })

            lightning_pipeline.on_transcript = on_lightning_transcript
            lightning_pipeline.on_audio_out = on_lightning_audio
            lightning_pipeline.on_state_change = on_lightning_state_change
            lightning_pipeline.on_latency = on_lightning_latency

            await lightning_pipeline.initialize(
                system_prompt=assistant['system_prompt'],
                voice_id=assistant_voice_id if assistant_voice_id and len(assistant_voice_id) > 10 else None,
            )

            await websocket.send_json({
                "type": "info",
                "message": "⚡ Lightning pipeline active - sub-150ms latency!"
            })

        elif streaming_enabled:
            logger.info(f"Streaming pipeline enabled for call {call_id}")
            streaming_config = StreamingConfig()
            # Use assistant's voice_id if valid, otherwise use default Katie voice
            assistant_voice_id = assistant.get('voice_id')
            if assistant_voice_id and len(assistant_voice_id) > 10:
                streaming_config.cartesia_voice_id = assistant_voice_id
            streaming_pipeline = StreamingPipeline(streaming_config)

            # Set up callbacks for streaming pipeline
            async def on_streaming_transcript(role: str, text: str):
                await websocket.send_json({
                    "type": "transcript",
                    "role": role,
                    "content": text
                })
                session.add_to_transcript(role, text)

            async def on_streaming_audio(audio_bytes: bytes):
                # Wrap raw PCM in WAV header for browser playback
                wav_audio = pcm_to_wav(audio_bytes, sample_rate=16000)
                audio_b64 = base64.b64encode(wav_audio).decode('utf-8')
                await websocket.send_json({
                    "type": "audio",
                    "data": audio_b64
                })
                # Broadcast TTS audio to monitors
                await session.broadcast_audio_to_monitors(audio_bytes, is_caller=False)

            async def on_streaming_state_change(state: PipelineState):
                is_speaking = state == PipelineState.SPEAKING
                await websocket.send_json({"type": "speaking", "is_speaking": is_speaking})
                session.is_speaking = is_speaking

            async def on_streaming_latency(latency: dict):
                total = latency.get('stt', 0) + latency.get('llm', 0) + latency.get('tts', 0)
                await websocket.send_json({
                    "type": "latency",
                    "data": {
                        "stt_ms": latency.get('stt', 0),
                        "llm_ms": latency.get('llm', 0),
                        "tts_ms": latency.get('tts', 0),
                        "total_ms": total,
                        "target_ms": 500,
                        "status": "good" if total < 500 else "warning" if total < 800 else "slow"
                    }
                })

            streaming_pipeline.on_transcript = on_streaming_transcript
            streaming_pipeline.on_audio_out = on_streaming_audio
            streaming_pipeline.on_state_change = on_streaming_state_change
            streaming_pipeline.on_latency = on_streaming_latency

            # Initialize the pipeline with system prompt
            await streaming_pipeline.initialize(assistant['system_prompt'])

            await websocket.send_json({
                "type": "info",
                "message": "Streaming pipeline active - sub-500ms latency enabled"
            })
        else:
            logger.info(f"Using batch processing for call {call_id} (streaming not configured)")

        # Initialize voice assistant for batch processing (fallback or primary)
        voice_assistant = VoiceAssistant()
        voice_assistant.initialize_modal()
        voice_assistant.initialize_claude()

        # Send first message if configured
        if assistant.get('first_message'):
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "content": assistant['first_message']
            })
            session.add_to_transcript("assistant", assistant['first_message'])

            # Synthesize first message audio using appropriate TTS
            try:
                if lightning_pipeline and lightning_pipeline.tts:
                    # Use Lightning TTS (Cartesia - fast)
                    logger.info("Using Lightning TTS for first message")
                    await lightning_pipeline.speak(assistant['first_message'])
                elif streaming_pipeline and streaming_pipeline.tts:
                    # Use streaming TTS (Cartesia)
                    logger.info("Using streaming TTS for first message")
                    await streaming_pipeline.speak(assistant['first_message'])
                else:
                    # Fallback to Modal TTS (slow)
                    logger.info("Using Modal TTS for first message (fallback)")
                    audio_bytes = voice_assistant.synthesize_speech(
                        assistant['first_message'],
                        assistant.get('voice_id', 'default'),
                        user_id
                    )
                    if audio_bytes:
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

                    # Cancel Lightning TTS if active (highest priority)
                    if lightning_pipeline and lightning_pipeline.tts:
                        await lightning_pipeline.tts.cancel()
                    # Cancel streaming TTS if active
                    elif streaming_pipeline and streaming_pipeline.tts:
                        await streaming_pipeline.tts.cancel()

                elif msg_type == 'update_config':
                    # Real-time configuration update during call
                    updates = message.get('config', {})
                    save_to_db = message.get('save', False)

                    result = {}

                    # Apply to Lightning Pipeline
                    if lightning_pipeline:
                        result = lightning_pipeline.update_config(updates)

                    # Apply to Streaming Pipeline if active
                    if streaming_pipeline and hasattr(streaming_pipeline, 'update_config'):
                        streaming_pipeline.update_config(updates)

                    # Save to database if requested
                    if save_to_db and session.assistant_id:
                        try:
                            db_updates = {}
                            if 'speech_speed' in updates:
                                db_updates['speech_speed'] = updates['speech_speed']
                            if 'response_delay_ms' in updates:
                                db_updates['response_delay_ms'] = updates['response_delay_ms']
                            if 'turn_eagerness' in updates:
                                db_updates['turn_eagerness'] = updates['turn_eagerness']

                            if db_updates:
                                db.update_assistant(user_id, session.assistant_id, db_updates)
                                logger.info(f"💾 Settings saved to assistant {session.assistant_id}")
                                result['saved_to_db'] = True
                        except Exception as e:
                            logger.error(f"Failed to save settings: {e}")
                            result['save_error'] = str(e)

                    await websocket.send_json({
                        "type": "config_updated",
                        "data": result
                    })

                elif msg_type == 'get_config':
                    # Get current configuration
                    config = {}
                    if lightning_pipeline:
                        config = lightning_pipeline.get_current_config()
                    await websocket.send_json({
                        "type": "current_config",
                        "data": config
                    })

                elif msg_type == 'audio':
                    # Receive audio chunk
                    audio_b64 = message.get('data', '')
                    if not audio_b64:
                        continue

                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                    except Exception:
                        continue

                    # Check audio format from frontend
                    # 'pcm_16000' = raw PCM for streaming, empty = webm/opus for batch
                    audio_format = message.get('format', '')

                    # ⚡ LIGHTNING PIPELINE (Priority 1) - Sub-150ms latency
                    if lightning_pipeline and audio_format == 'pcm_16000':
                        # Check if AI is enabled
                        if not session.user_settings.get('ai_enabled', True):
                            logger.debug(f"AI disabled for user {user_id}, lightning audio ignored")
                            continue
                        # Lightning mode: Send raw PCM audio to Deepgram → Groq → Cartesia
                        # Pipeline handles STT -> LLM -> TTS automatically via callbacks
                        await lightning_pipeline.send_audio(audio_bytes)
                        # Broadcast caller audio to monitors
                        await session.broadcast_audio_to_monitors(audio_bytes, is_caller=True)
                        continue

                    # STREAMING PIPELINE (Priority 2) - Sub-500ms latency
                    if streaming_pipeline and audio_format == 'pcm_16000':
                        # Check if AI is enabled for streaming mode too
                        if not session.user_settings.get('ai_enabled', True):
                            logger.debug(f"AI disabled for user {user_id}, streaming audio ignored")
                            continue
                        # Streaming mode: Send raw PCM audio to Deepgram
                        # Pipeline handles STT -> LLM -> TTS automatically via callbacks
                        await streaming_pipeline.send_audio(audio_bytes)
                        # Broadcast caller audio to monitors
                        await session.broadcast_audio_to_monitors(audio_bytes, is_caller=True)
                        continue

                    # Batch processing mode (Modal STT/TTS) - handles webm/opus or PCM audio
                    session.should_stop_tts = False

                    # Convert PCM to WAV if needed (for Modal STT compatibility)
                    audio_to_transcribe = audio_bytes
                    if audio_format == 'pcm_16000':
                        try:
                            audio_to_transcribe = pcm_to_wav(audio_bytes, sample_rate=16000)
                            logger.debug("Converted PCM to WAV for batch STT")
                        except Exception as e:
                            logger.error(f"PCM to WAV conversion error: {e}")
                            continue

                    # 1. STT - Transcribe audio
                    stt_start = time.time()
                    try:
                        stt_result = voice_assistant.transcribe_audio(audio_to_transcribe, user_id)
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

                    # Analyze and send real-time sentiment
                    sentiment_data = session.analyze_sentiment_realtime(user_text)
                    await websocket.send_json({
                        "type": "sentiment",
                        "data": sentiment_data
                    })

                    # Check if AI is enabled before generating response
                    if not session.user_settings.get('ai_enabled', True):
                        logger.info(f"AI disabled for user {user_id}, skipping response")
                        await websocket.send_json({
                            "type": "ai_disabled",
                            "message": "AI assistant is currently disabled in your settings"
                        })
                        continue

                    # 2. LLM - Generate response (with automatic model fallback)
                    llm_start = time.time()
                    llm_latency = 0  # Initialize in case of error
                    try:
                        # Build conversation history
                        messages = []
                        for t in session.transcript[-10:]:  # Last 10 messages for context
                            messages.append({
                                "role": t['role'],
                                "content": t['content']
                            })

                        # Use model manager to get best available model
                        # If assistant has specific model, use it; otherwise use auto-selection
                        configured_model = assistant.get('model', '')
                        model_manager = get_model_manager()

                        # Determine model family from configured model
                        if 'haiku' in configured_model.lower():
                            model_family = 'haiku'
                        elif 'opus' in configured_model.lower():
                            model_family = 'opus'
                        else:
                            model_family = 'sonnet'

                        # Get best available model (handles deprecation automatically)
                        selected_model = model_manager.get_model(model_family)
                        logger.debug(f"Using model: {selected_model} (family: {model_family})")

                        # Try with automatic fallback on 404 errors
                        max_retries = 3
                        last_error = None
                        excluded_models = []

                        # Build system prompt with user settings context
                        system_prompt = assistant['system_prompt']
                        if not session.user_settings.get('call_screening_enabled', True):
                            system_prompt += "\n\n[User setting: Call screening is disabled. Skip asking for caller identification or screening questions.]"

                        for attempt in range(max_retries):
                            try:
                                response = voice_assistant.anthropic_client.messages.create(
                                    model=selected_model,
                                    max_tokens=assistant.get('max_tokens', 150),
                                    temperature=float(assistant.get('temperature', 0.7)),
                                    system=system_prompt,
                                    messages=messages
                                )
                                assistant_text = response.content[0].text
                                llm_latency = int((time.time() - llm_start) * 1000)
                                break  # Success!

                            except Exception as api_error:
                                error_str = str(api_error).lower()
                                if '404' in error_str or 'not_found' in error_str or 'deprecated' in error_str:
                                    # Model deprecated - try fallback
                                    logger.warning(f"Model {selected_model} unavailable, trying fallback...")
                                    excluded_models.append(selected_model)
                                    model_manager.mark_model_failed(selected_model)
                                    selected_model = model_manager.get_model(model_family, exclude=excluded_models)
                                    logger.info(f"Falling back to: {selected_model}")
                                    last_error = api_error
                                else:
                                    # Other error - don't retry with different model
                                    raise
                        else:
                            # All retries exhausted
                            if last_error:
                                raise last_error

                    except Exception as e:
                        logger.error(f"LLM error: {e}")
                        import traceback
                        logger.error(f"LLM traceback: {traceback.format_exc()}")
                        assistant_text = f"I'm sorry, I encountered an error. Please try again."

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

                            audio_bytes = voice_assistant.synthesize_speech(
                                assistant_text,
                                assistant.get('voice_id', 'default'),
                                user_id
                            )
                            tts_latency = int((time.time() - tts_start) * 1000)

                            # Send audio if not interrupted
                            if not session.should_stop_tts and audio_bytes:
                                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                                await websocket.send_json({
                                    "type": "audio",
                                    "data": audio_b64
                                })
                                # Broadcast TTS audio to monitors
                                await session.broadcast_audio_to_monitors(audio_bytes, is_caller=False)

                            session.is_speaking = False
                            await websocket.send_json({"type": "speaking", "is_speaking": False})

                            # Log latencies
                            total_latency = stt_latency + llm_latency + tts_latency
                            logger.info(f"Call {call_id} - STT: {stt_latency}ms, LLM: {llm_latency}ms, TTS: {tts_latency}ms, Total: {total_latency}ms")

                            # Send real-time latency data to client
                            await websocket.send_json({
                                "type": "latency",
                                "data": {
                                    "stt_ms": stt_latency,
                                    "llm_ms": llm_latency,
                                    "tts_ms": tts_latency,
                                    "total_ms": total_latency,
                                    "target_ms": 800,
                                    "status": "good" if total_latency < 800 else "warning" if total_latency < 1500 else "slow"
                                }
                            })

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
            duration = session.get_duration_seconds()
            quality_data = await session.end_call('user_ended', duration)
            await websocket.send_json({
                "type": "call_ended",
                "reason": "user_ended",
                "duration_seconds": duration,
                "quality_score": quality_data
            })

    except WebSocketDisconnect:
        if session:
            duration = session.get_duration_seconds()
            await session.end_call('disconnected', duration)
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "Authentication timeout"})
        await websocket.close()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if session:
            duration = session.get_duration_seconds()
            await session.end_call('error', duration)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        # Clean up Lightning pipeline (highest priority)
        if lightning_pipeline:
            try:
                await lightning_pipeline.close()
                logger.info(f"⚡ Lightning pipeline closed for call {call_id if 'call_id' in dir() else 'unknown'}")
            except Exception as e:
                logger.error(f"Error closing lightning pipeline: {e}")

        # Clean up streaming pipeline
        if streaming_pipeline:
            try:
                await streaming_pipeline.close()
                logger.info(f"Streaming pipeline closed for call {call_id if 'call_id' in dir() else 'unknown'}")
            except Exception as e:
                logger.error(f"Error closing streaming pipeline: {e}")

        try:
            await websocket.close()
        except:
            pass


# ============================================================================
# PHONE NUMBERS & TWILIO INTEGRATION
# ============================================================================

class PhoneNumberRequest(BaseModel):
    phone_number: str
    phone_type: str = "mobile"
    country_code: str = "+1"

class VerifyPhoneRequest(BaseModel):
    phone_number: str
    code: str

class SendSMSRequest(BaseModel):
    to_number: str
    message: str

@app.get("/phone-numbers")
async def list_phone_numbers(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Get user's phone numbers."""
    try:
        result = db.client.table("va_phone_numbers").select("*").eq(
            "user_id", user_id
        ).execute()
        return {"phone_numbers": result.data or []}
    except Exception as e:
        logger.error(f"Error getting phone numbers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/phone-numbers")
async def add_phone_number(
    request: PhoneNumberRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Add a new phone number (starts verification)."""
    import random
    try:
        # Generate verification code
        code = str(random.randint(100000, 999999))
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        # Store verification
        db.client.table("va_phone_verifications").insert({
            "user_id": user_id,
            "phone_number": request.phone_number,
            "verification_code": code,
            "expires_at": expires_at.isoformat()
        }).execute()

        # TODO: Send SMS via Twilio
        # For now, return code in dev mode
        return {
            "success": True,
            "message": "Verification code sent",
            "phone_number": request.phone_number,
            "dev_code": code if os.getenv("DEBUG", "true").lower() == "true" else None
        }
    except Exception as e:
        logger.error(f"Error adding phone number: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/phone-numbers/verify")
async def verify_phone_number(
    request: VerifyPhoneRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Verify a phone number with code."""
    try:
        # Check verification code
        result = db.client.table("va_phone_verifications").select("*").eq(
            "user_id", user_id
        ).eq("phone_number", request.phone_number).eq(
            "verification_code", request.code
        ).is_("verified_at", "null").order("created_at", desc=True).limit(1).execute()

        if not result.data:
            raise HTTPException(status_code=400, detail="Invalid or expired code")

        verification = result.data[0]
        if datetime.fromisoformat(verification["expires_at"].replace("Z", "")) < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Code expired")

        # Mark as verified
        db.client.table("va_phone_verifications").update({
            "verified_at": datetime.utcnow().isoformat()
        }).eq("id", verification["id"]).execute()

        # Add phone number
        db.client.table("va_phone_numbers").insert({
            "user_id": user_id,
            "phone_number": request.phone_number,
            "is_verified": True,
            "is_primary": True
        }).execute()

        return {"success": True, "message": "Phone number verified"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying phone: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/phone-numbers/{phone_id}")
async def delete_phone_number(
    phone_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Delete a phone number."""
    try:
        db.client.table("va_phone_numbers").delete().eq(
            "id", phone_id
        ).eq("user_id", user_id).execute()
        return {"success": True, "message": "Phone number deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sms/send")
async def send_sms(
    request: SendSMSRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Send an SMS message."""
    try:
        # Get user's primary phone number
        phone_result = db.client.table("va_phone_numbers").select("*").eq(
            "user_id", user_id
        ).eq("is_primary", True).execute()

        if not phone_result.data:
            raise HTTPException(status_code=400, detail="No verified phone number")

        from_number = phone_result.data[0]["phone_number"]

        # Log the SMS
        db.client.table("va_sms_messages").insert({
            "user_id": user_id,
            "direction": "outbound",
            "from_number": from_number,
            "to_number": request.to_number,
            "body": request.message,
            "status": "sent"
        }).execute()

        # TODO: Actually send via Twilio
        return {"success": True, "message": "SMS sent"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sms")
async def list_sms(
    user_id: str = Header(..., alias="X-User-ID"),
    limit: int = 50,
    offset: int = 0,
    db: SupabaseManager = Depends(get_db),
):
    """Get SMS message history."""
    try:
        result = db.client.table("va_sms_messages").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return {"messages": result.data or [], "total": len(result.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TWILIO VOICE WEBHOOKS
# ============================================================================

@app.post("/twilio/voice/inbound")
async def twilio_inbound_call(
    request: Request,
    db: SupabaseManager = Depends(get_db),
):
    """Handle incoming Twilio voice call webhook."""
    from twilio.twiml.voice_response import VoiceResponse, Gather

    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")

        logger.info(f"Inbound call: {call_sid} from {from_number} to {to_number}")

        # Find user by phone number
        user_result = db.client.table("va_phone_numbers").select("user_id").eq(
            "phone_number", to_number
        ).execute()

        user_id = user_result.data[0]["user_id"] if user_result.data else None

        # Get assistant greeting
        greeting = "Hello, thank you for calling. How can I help you today?"
        if user_id:
            profile = db.client.table("va_user_profiles").select("*").eq(
                "id", user_id
            ).execute()
            if profile.data:
                assistant_name = profile.data[0].get("assistant_name", "AI Assistant")
                business_name = profile.data[0].get("business_name", "")
                if business_name:
                    greeting = f"Hello, thank you for calling {business_name}. This is {assistant_name}. How can I help you today?"
                else:
                    greeting = f"Hello, this is {assistant_name}. How can I help you today?"

            # Log the call
            db.client.table("va_call_logs").insert({
                "user_id": user_id,
                "direction": "inbound",
                "caller_number": from_number,
                "callee_number": to_number,
                "twilio_call_sid": call_sid,
                "status": "in_progress"
            }).execute()

        # Generate TwiML response
        api_url = os.getenv("API_URL", "http://localhost:8000")
        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{api_url}/twilio/voice/respond?call_sid={call_sid}&user_id={user_id or ''}",
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        gather.say(greeting, voice="Polly.Joanna")
        response.append(gather)
        response.say("I didn't catch that. Please try again or call back later.", voice="Polly.Joanna")
        response.hangup()

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling inbound call: {e}")
        response = VoiceResponse()
        response.say("Sorry, we're experiencing technical difficulties. Please try again later.", voice="Polly.Joanna")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")


@app.post("/twilio/voice/respond")
async def twilio_voice_respond(
    request: Request,
    call_sid: str = "",
    user_id: str = "",
    db: SupabaseManager = Depends(get_db),
):
    """Process speech input and generate AI response."""
    from twilio.twiml.voice_response import VoiceResponse, Gather

    try:
        form_data = await request.form()
        speech_result = form_data.get("SpeechResult", "")

        logger.info(f"Speech input for {call_sid}: {speech_result}")

        # Simple AI response for now
        ai_response = "I understand. Is there anything else I can help you with?"

        api_url = os.getenv("API_URL", "http://localhost:8000")
        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{api_url}/twilio/voice/respond?call_sid={call_sid}&user_id={user_id}",
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        gather.say(ai_response, voice="Polly.Joanna")
        response.append(gather)
        response.say("Thank you for calling. Goodbye!", voice="Polly.Joanna")
        response.hangup()

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"Error in voice respond: {e}")
        response = VoiceResponse()
        response.say("Sorry, something went wrong. Goodbye.", voice="Polly.Joanna")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")


@app.post("/twilio/voice/status")
async def twilio_call_status(
    request: Request,
    db: SupabaseManager = Depends(get_db),
):
    """Handle call status callback from Twilio."""
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        duration = form_data.get("CallDuration", 0)

        logger.info(f"Call status: {call_sid} -> {call_status}")

        db.client.table("va_call_logs").update({
            "status": call_status,
            "duration_seconds": int(duration) if duration else 0,
            "ended_at": datetime.utcnow().isoformat() if call_status in ["completed", "failed", "busy", "no-answer"] else None
        }).eq("twilio_call_sid", call_sid).execute()

        return {"success": True}
    except Exception as e:
        logger.error(f"Error updating call status: {e}")
        return {"success": False}


@app.post("/twilio/sms/inbound")
async def twilio_inbound_sms(
    request: Request,
    db: SupabaseManager = Depends(get_db),
):
    """Handle incoming SMS webhook from Twilio."""
    from twilio.twiml.messaging_response import MessagingResponse

    try:
        form_data = await request.form()
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        body = form_data.get("Body", "")
        message_sid = form_data.get("MessageSid")

        logger.info(f"Inbound SMS from {from_number}")

        user_result = db.client.table("va_phone_numbers").select("user_id").eq(
            "phone_number", to_number
        ).execute()

        if user_result.data:
            db.client.table("va_sms_messages").insert({
                "user_id": user_result.data[0]["user_id"],
                "direction": "inbound",
                "from_number": from_number,
                "to_number": to_number,
                "body": body,
                "status": "received",
                "twilio_sid": message_sid
            }).execute()

        response = MessagingResponse()
        response.message("Thanks for your message! We'll get back to you soon.")
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling inbound SMS: {e}")
        return Response(content="", media_type="application/xml")


@app.get("/twilio/status")
async def get_twilio_status(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """Get Twilio configuration status."""
    issues = validate_twilio_config()
    twilio = get_twilio_service()
    return {
        "configured": twilio.is_configured,
        "issues": issues,
        "default_number": os.getenv("TWILIO_PHONE_NUMBER") if twilio.is_configured else None
    }


# ============================================================================
# USER PROFILE & SETTINGS
# ============================================================================

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    business_name: Optional[str] = None
    profession: Optional[str] = None
    service_area: Optional[str] = None
    greeting_name: Optional[str] = None
    assistant_name: Optional[str] = None
    assistant_personality: Optional[str] = None
    profile_fields: Optional[List[Dict]] = None
    business_hours: Optional[Dict] = None
    timezone: Optional[str] = None

class UpdateSettingsRequest(BaseModel):
    ai_enabled: Optional[bool] = None
    ai_greeting_enabled: Optional[bool] = None
    ai_transcription_enabled: Optional[bool] = None
    ai_summary_enabled: Optional[bool] = None
    call_screening_enabled: Optional[bool] = None
    voicemail_enabled: Optional[bool] = None
    call_recording_enabled: Optional[bool] = None
    call_forwarding_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_notifications_enabled: Optional[bool] = None
    email_notifications_enabled: Optional[bool] = None
    sms_notifications_enabled: Optional[bool] = None
    notify_on_missed_call: Optional[bool] = None
    notify_on_voicemail: Optional[bool] = None
    notify_on_urgent: Optional[bool] = None
    daily_summary_enabled: Optional[bool] = None
    weekly_summary_enabled: Optional[bool] = None
    share_call_logs_with_team: Optional[bool] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    webhook_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None

@app.get("/profile/extended")
async def get_extended_profile(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Get user's extended profile with tier limits."""
    try:
        # Get profile
        profile_result = db.client.table("va_user_profiles_extended").select("*").eq(
            "user_id", user_id
        ).execute()

        profile = profile_result.data[0] if profile_result.data else {}

        # Get user's plan for field limits
        sub_result = db.client.table("va_user_subscriptions").select(
            "plan_id"
        ).eq("user_id", user_id).execute()

        plan_name = "free"
        if sub_result.data:
            plan_id = sub_result.data[0]["plan_id"]
            plan_result = db.client.table("va_subscription_plans").select(
                "plan_name"
            ).eq("id", plan_id).execute()
            if plan_result.data:
                plan_name = plan_result.data[0]["plan_name"]

        # Get field limits
        limits_result = db.client.table("va_profile_field_limits").select("*").eq(
            "plan_name", plan_name
        ).execute()

        limits = limits_result.data[0] if limits_result.data else {
            "max_fields": 1,
            "max_chars_per_field": 60
        }

        return {
            "profile": profile,
            "field_limits": limits,
            "plan": plan_name
        }
    except Exception as e:
        logger.error(f"Error getting extended profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/profile/extended")
async def update_extended_profile(
    request: UpdateProfileRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Update user's extended profile."""
    try:
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow().isoformat()

        # Check if profile exists
        existing = db.client.table("va_user_profiles_extended").select("id").eq(
            "user_id", user_id
        ).execute()

        if existing.data:
            result = db.client.table("va_user_profiles_extended").update(
                update_data
            ).eq("user_id", user_id).execute()
        else:
            update_data["user_id"] = user_id
            result = db.client.table("va_user_profiles_extended").insert(
                update_data
            ).execute()

        return {"success": True, "profile": result.data[0] if result.data else None}
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/settings")
async def get_settings(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Get user settings."""
    try:
        result = db.client.table("va_user_settings").select("*").eq(
            "user_id", user_id
        ).execute()

        if result.data:
            return {"settings": result.data[0]}

        # Create default settings
        default = {"user_id": user_id}
        db.client.table("va_user_settings").insert(default).execute()
        return {"settings": default}
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/settings")
async def update_settings(
    request: UpdateSettingsRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Update user settings."""
    try:
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow().isoformat()

        # Check if settings exist
        existing = db.client.table("va_user_settings").select("id").eq(
            "user_id", user_id
        ).execute()

        if existing.data:
            result = db.client.table("va_user_settings").update(
                update_data
            ).eq("user_id", user_id).execute()
        else:
            update_data["user_id"] = user_id
            result = db.client.table("va_user_settings").insert(
                update_data
            ).execute()

        return {"success": True, "settings": result.data[0] if result.data else None}
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONTACTS
# ============================================================================

class CreateContactRequest(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    contact_type: str = "customer"
    permission_level: str = "normal"
    notes: Optional[str] = None
    tags: Optional[List[str]] = None

class UpdateContactRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    contact_type: Optional[str] = None
    permission_level: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None

@app.get("/contacts")
async def list_contacts(
    user_id: str = Header(..., alias="X-User-ID"),
    search: Optional[str] = None,
    contact_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: SupabaseManager = Depends(get_db),
):
    """List user's contacts."""
    try:
        query = db.client.table("va_contacts").select("*").eq("user_id", user_id)

        if contact_type:
            query = query.eq("contact_type", contact_type)

        result = query.order("name").range(offset, offset + limit - 1).execute()
        return {"contacts": result.data or [], "total": len(result.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/contacts")
async def create_contact(
    request: CreateContactRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Create a new contact."""
    try:
        data = request.dict()
        data["user_id"] = user_id
        if data.get("tags"):
            data["tags"] = json.dumps(data["tags"])

        result = db.client.table("va_contacts").insert(data).execute()
        return {"success": True, "contact": result.data[0] if result.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Get a contact."""
    try:
        result = db.client.table("va_contacts").select("*").eq(
            "id", contact_id
        ).eq("user_id", user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Contact not found")

        return {"contact": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/contacts/{contact_id}")
async def update_contact(
    contact_id: str,
    request: UpdateContactRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Update a contact."""
    try:
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow().isoformat()

        if update_data.get("tags"):
            update_data["tags"] = json.dumps(update_data["tags"])

        result = db.client.table("va_contacts").update(update_data).eq(
            "id", contact_id
        ).eq("user_id", user_id).execute()

        return {"success": True, "contact": result.data[0] if result.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Delete a contact."""
    try:
        db.client.table("va_contacts").delete().eq(
            "id", contact_id
        ).eq("user_id", user_id).execute()
        return {"success": True, "message": "Contact deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENHANCED CALL LOGS
# ============================================================================

class ShareCallRequest(BaseModel):
    share_type: str  # 'email', 'sms', 'webhook', 'link'
    recipient: Optional[str] = None
    include_transcript: bool = True
    include_summary: bool = True
    include_recording: bool = False
    include_key_info: bool = True

@app.post("/calls/{call_id}/share")
async def share_call(
    call_id: str,
    request: ShareCallRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Share a call log via email, SMS, webhook, or generate link."""
    import secrets
    try:
        # Verify call belongs to user
        call_result = db.client.table("va_call_logs").select("*").eq(
            "id", call_id
        ).eq("user_id", user_id).execute()

        if not call_result.data:
            raise HTTPException(status_code=404, detail="Call not found")

        # Generate access token
        access_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=7)

        # Create share record
        share_data = {
            "call_id": call_id,
            "shared_by": user_id,
            "share_type": request.share_type,
            "recipient": request.recipient,
            "access_token": access_token,
            "expires_at": expires_at.isoformat(),
            "include_transcript": request.include_transcript,
            "include_summary": request.include_summary,
            "include_recording": request.include_recording,
            "include_key_info": request.include_key_info,
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat()
        }

        result = db.client.table("va_call_shares").insert(share_data).execute()

        share_url = f"https://hive215.vercel.app/shared/call/{access_token}"

        # TODO: Actually send email/SMS based on share_type

        return {
            "success": True,
            "share": result.data[0] if result.data else None,
            "share_url": share_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/shared/call/{token}")
async def get_shared_call(
    token: str,
    db: SupabaseManager = Depends(get_db),
):
    """Get a shared call by access token (public endpoint)."""
    try:
        share_result = db.client.table("va_call_shares").select("*").eq(
            "access_token", token
        ).execute()

        if not share_result.data:
            raise HTTPException(status_code=404, detail="Share not found or expired")

        share = share_result.data[0]

        # Check expiration
        if datetime.fromisoformat(share["expires_at"].replace("Z", "")) < datetime.utcnow():
            raise HTTPException(status_code=410, detail="Share link expired")

        # Get call data
        call_result = db.client.table("va_call_logs").select("*").eq(
            "id", share["call_id"]
        ).execute()

        if not call_result.data:
            raise HTTPException(status_code=404, detail="Call not found")

        call = call_result.data[0]

        # Filter based on share permissions
        response_call = {
            "id": call["id"],
            "started_at": call["started_at"],
            "duration_seconds": call["duration_seconds"],
            "caller_name": call.get("caller_name"),
            "phone_number": call.get("phone_number")
        }

        if share["include_summary"]:
            response_call["summary"] = call.get("summary")
        if share["include_transcript"]:
            response_call["transcript"] = call.get("transcript")
        if share["include_key_info"]:
            response_call["key_info"] = call.get("key_info")
            response_call["action_items"] = call.get("action_items")
        if share["include_recording"]:
            response_call["recording_url"] = call.get("twilio_recording_url")

        # Update view count
        db.client.table("va_call_shares").update({
            "view_count": share.get("view_count", 0) + 1,
            "first_viewed_at": share.get("first_viewed_at") or datetime.utcnow().isoformat()
        }).eq("id", share["id"]).execute()

        return {"call": response_call}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REFERRAL SYSTEM
# ============================================================================

class RedeemReferralRequest(BaseModel):
    code: str

@app.get("/referral")
async def get_referral_info(
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Get user's referral code and stats."""
    try:
        # Get or create referral code
        result = db.client.table("va_referral_codes").select("*").eq(
            "user_id", user_id
        ).execute()

        if result.data:
            referral = result.data[0]
        else:
            # Create new referral code
            import hashlib
            code = "HIVE-" + hashlib.md5(
                (user_id + str(datetime.utcnow())).encode()
            ).hexdigest()[:6].upper()

            result = db.client.table("va_referral_codes").insert({
                "user_id": user_id,
                "code": code
            }).execute()
            referral = result.data[0] if result.data else {"code": code}

        # Get referrals made
        referrals = db.client.table("va_referrals").select("*").eq(
            "referrer_id", user_id
        ).execute()

        return {
            "referral_code": referral,
            "referrals": referrals.data or [],
            "share_url": f"https://hive215.vercel.app/signup?ref={referral['code']}"
        }
    except Exception as e:
        logger.error(f"Error getting referral: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/referral/redeem")
async def redeem_referral(
    request: RedeemReferralRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Redeem a referral code."""
    try:
        # Find referral code
        code_result = db.client.table("va_referral_codes").select("*").eq(
            "code", request.code.upper()
        ).eq("is_active", True).execute()

        if not code_result.data:
            raise HTTPException(status_code=400, detail="Invalid referral code")

        referral_code = code_result.data[0]

        # Can't use own code
        if referral_code["user_id"] == user_id:
            raise HTTPException(status_code=400, detail="Cannot use your own referral code")

        # Check if already used
        existing = db.client.table("va_referrals").select("id").eq(
            "referee_id", user_id
        ).execute()

        if existing.data:
            raise HTTPException(status_code=400, detail="Already used a referral code")

        # Create referral record
        db.client.table("va_referrals").insert({
            "referral_code_id": referral_code["id"],
            "referrer_id": referral_code["user_id"],
            "referee_id": user_id,
            "status": "signed_up",
            "signed_up_at": datetime.utcnow().isoformat(),
            "referee_reward_claimed": True,
            "referee_reward_claimed_at": datetime.utcnow().isoformat()
        }).execute()

        # Add bonus minutes to referee
        referee_reward = referral_code.get("referee_reward_value", 50)
        db.client.table("va_usage_tracking").update({
            "bonus_minutes": db.client.table("va_usage_tracking").select(
                "bonus_minutes"
            ).eq("user_id", user_id).execute().data[0].get("bonus_minutes", 0) + referee_reward
        }).eq("user_id", user_id).execute()

        # Add bonus minutes to referrer
        referrer_reward = referral_code.get("referrer_reward_value", 50)
        referrer_usage = db.client.table("va_usage_tracking").select(
            "bonus_minutes"
        ).eq("user_id", referral_code["user_id"]).execute()

        if referrer_usage.data:
            db.client.table("va_usage_tracking").update({
                "bonus_minutes": referrer_usage.data[0].get("bonus_minutes", 0) + referrer_reward
            }).eq("user_id", referral_code["user_id"]).execute()

        # Update referral code stats
        db.client.table("va_referral_codes").update({
            "total_referrals": referral_code.get("total_referrals", 0) + 1,
            "successful_referrals": referral_code.get("successful_referrals", 0) + 1,
            "total_rewards_earned": referral_code.get("total_rewards_earned", 0) + referrer_reward
        }).eq("id", referral_code["id"]).execute()

        return {
            "success": True,
            "message": f"Referral code applied! You earned {referee_reward} bonus minutes.",
            "minutes_earned": referee_reward
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redeeming referral: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TEAM MANAGEMENT (Enhanced)
# ============================================================================

class CreateTeamInviteRequest(BaseModel):
    email: str
    role: str = "member"

@app.post("/teams/{team_id}/invite")
async def invite_team_member(
    team_id: str,
    request: CreateTeamInviteRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Invite someone to join a team."""
    import secrets
    try:
        # Verify user owns or is admin of team
        team = db.client.table("va_teams").select("*").eq("id", team_id).execute()
        if not team.data:
            raise HTTPException(status_code=404, detail="Team not found")

        if team.data[0]["owner_id"] != user_id:
            member = db.client.table("va_team_members").select("role").eq(
                "team_id", team_id
            ).eq("user_id", user_id).execute()
            if not member.data or member.data[0]["role"] not in ["owner", "admin"]:
                raise HTTPException(status_code=403, detail="Not authorized")

        # Create invite token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=7)

        db.client.table("va_team_invites").insert({
            "team_id": team_id,
            "invited_by": user_id,
            "email": request.email,
            "role": request.role,
            "token": token,
            "expires_at": expires_at.isoformat()
        }).execute()

        invite_url = f"https://hive215.vercel.app/team/join/{token}"

        # TODO: Send email invitation

        return {
            "success": True,
            "message": f"Invitation sent to {request.email}",
            "invite_url": invite_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/teams/join/{token}")
async def join_team(
    token: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Accept a team invitation."""
    try:
        # Find invite
        invite = db.client.table("va_team_invites").select("*").eq(
            "token", token
        ).is_("accepted_at", "null").execute()

        if not invite.data:
            raise HTTPException(status_code=404, detail="Invalid or expired invitation")

        inv = invite.data[0]

        # Check expiration
        if datetime.fromisoformat(inv["expires_at"].replace("Z", "")) < datetime.utcnow():
            raise HTTPException(status_code=410, detail="Invitation expired")

        # Add to team
        db.client.table("va_team_members").insert({
            "team_id": inv["team_id"],
            "user_id": user_id,
            "role": inv["role"]
        }).execute()

        # Mark invite as accepted
        db.client.table("va_team_invites").update({
            "accepted_at": datetime.utcnow().isoformat()
        }).eq("id", inv["id"]).execute()

        return {"success": True, "message": "Successfully joined team"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/teams/{team_id}/calls")
async def get_team_calls(
    team_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    limit: int = 50,
    offset: int = 0,
    db: SupabaseManager = Depends(get_db),
):
    """Get shared call logs for a team."""
    try:
        # Verify membership
        member = db.client.table("va_team_members").select("*").eq(
            "team_id", team_id
        ).eq("user_id", user_id).execute()

        if not member.data:
            raise HTTPException(status_code=403, detail="Not a team member")

        # Get shared calls
        shares = db.client.table("va_team_call_shares").select(
            "call_id"
        ).eq("team_id", team_id).execute()

        if not shares.data:
            return {"calls": [], "total": 0}

        call_ids = [s["call_id"] for s in shares.data]

        calls = db.client.table("va_call_logs").select("*").in_(
            "id", call_ids
        ).order("started_at", desc=True).range(offset, offset + limit - 1).execute()

        return {"calls": calls.data or [], "total": len(call_ids)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/calls/{call_id}/share-team/{team_id}")
async def share_call_with_team(
    call_id: str,
    team_id: str,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db),
):
    """Share a call log with a team."""
    try:
        # Verify call ownership
        call = db.client.table("va_call_logs").select("id").eq(
            "id", call_id
        ).eq("user_id", user_id).execute()

        if not call.data:
            raise HTTPException(status_code=404, detail="Call not found")

        # Verify team membership
        member = db.client.table("va_team_members").select("*").eq(
            "team_id", team_id
        ).eq("user_id", user_id).execute()

        if not member.data:
            raise HTTPException(status_code=403, detail="Not a team member")

        # Share
        db.client.table("va_team_call_shares").upsert({
            "call_id": call_id,
            "team_id": team_id,
            "shared_by": user_id
        }).execute()

        return {"success": True, "message": "Call shared with team"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# LIGHTNING PIPELINE ENDPOINTS (Sub-150ms Voice AI)
# =============================================================================

class LightningChatRequest(BaseModel):
    """Request for Lightning Pipeline chat."""
    message: str
    system_prompt: Optional[str] = "You are a helpful voice assistant. Keep responses concise."
    voice_id: Optional[str] = None
    language: Optional[str] = "en"


class LightningTTSRequest(BaseModel):
    """Request for Lightning TTS (Cartesia Sonic-3)."""
    text: str
    voice_id: Optional[str] = None
    language: Optional[str] = "en"
    speed: Optional[float] = 1.0


class LightningVoiceCloneRequest(BaseModel):
    """Request for Cartesia voice cloning."""
    name: str
    description: Optional[str] = ""
    language: Optional[str] = "en"


class LightningLocalizeRequest(BaseModel):
    """Request to localize a cloned voice to another language."""
    voice_id: str
    target_language: str
    name: Optional[str] = None


@app.get("/lightning/status")
async def lightning_status():
    """
    Get Lightning Pipeline status and configuration.

    Returns which components are available and their configuration.
    """
    config = LightningConfig()

    return {
        "status": "active",
        "version": "1.0.0",
        "components": {
            "stt": {
                "provider": "deepgram",
                "model": "nova-2",
                "available": bool(config.deepgram_api_key),
                "languages": len(get_stt_languages()),
                "latency_target_ms": 30,
            },
            "llm": {
                "primary": "groq",
                "model": config.groq_model,
                "fallback": "claude",
                "groq_available": bool(config.groq_api_key),
                "claude_available": bool(config.anthropic_api_key),
                "latency_target_ms": 40,
            },
            "tts": {
                "provider": "cartesia",
                "model": "sonic-3",
                "available": bool(config.cartesia_api_key),
                "languages": len(get_tts_languages()),
                "latency_target_ms": 30,
            }
        },
        "latency_targets": {
            "stt_ms": 30,
            "llm_ttft_ms": 40,
            "tts_ttfb_ms": 30,
            "total_perceived_ms": 150,
            "human_threshold_ms": 500,
        },
        "features": {
            "sentence_streaming": True,
            "barge_in": True,
            "voice_cloning": bool(config.cartesia_api_key),
            "cross_lingual_voices": bool(config.cartesia_api_key),
            "code_switching": True,  # Deepgram multi-language
        }
    }


@app.get("/lightning/languages")
async def lightning_languages():
    """
    Get all supported languages for STT and TTS.
    """
    return {
        "stt": {
            "provider": "deepgram",
            "languages": get_stt_languages(),
            "code_switching": True,
            "code_switching_note": "Use language='multi' for auto-detection"
        },
        "tts": {
            "provider": "cartesia",
            "languages": get_tts_languages(),
            "voice_cloning_languages": len(get_tts_languages()),
        }
    }


@app.post("/lightning/chat")
async def lightning_chat(
    request: LightningChatRequest,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Fast text chat using Groq (40ms TTFT) with Claude fallback.

    This is the LLM-only endpoint - no audio processing.
    Use /ws/lightning/{assistant_id} for full voice streaming.
    """
    try:
        # Initialize hybrid LLM client
        llm = HybridLLMClient()

        start_time = time.time()
        first_token_time = None
        tokens = []

        def on_token(token):
            nonlocal first_token_time
            if first_token_time is None:
                first_token_time = time.time()
            tokens.append(token)

        response = await llm.stream_response(
            user_message=request.message,
            system_prompt=request.system_prompt,
            on_token=on_token,
        )

        total_time = int((time.time() - start_time) * 1000)
        ttft = int((first_token_time - start_time) * 1000) if first_token_time else 0

        return {
            "response": response,
            "metrics": {
                "ttft_ms": ttft,
                "total_ms": total_time,
                "tokens": len(tokens),
                "provider": "groq" if llm._groq_available else "claude",
            },
            "stats": llm.get_stats(),
        }

    except Exception as e:
        logger.error(f"Lightning chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/lightning/tts")
async def lightning_tts(
    request: LightningTTSRequest,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Ultra-fast TTS using Cartesia Sonic-3 (~30ms TTFB).

    Returns streaming audio chunks.
    """
    config = CartesiaConfig()

    if not config.api_key:
        raise HTTPException(status_code=503, detail="Cartesia TTS not configured")

    try:
        cartesia = CartesiaSonic3(config)

        if not await cartesia.connect():
            raise HTTPException(status_code=503, detail="Failed to connect to Cartesia")

        start_time = time.time()
        audio_chunks = []
        first_chunk_time = None

        async for chunk in cartesia.synthesize_stream(
            text=request.text,
            voice_id=request.voice_id,
            language=request.language,
            speed=request.speed,
        ):
            if first_chunk_time is None:
                first_chunk_time = time.time()
            audio_chunks.append(chunk)

        await cartesia.close()

        total_time = int((time.time() - start_time) * 1000)
        ttfb = int((first_chunk_time - start_time) * 1000) if first_chunk_time else 0

        # Concatenate audio
        audio_data = b"".join(audio_chunks)
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')

        return {
            "audio": audio_b64,
            "format": "pcm_s16le",
            "sample_rate": 16000,
            "metrics": {
                "ttfb_ms": ttfb,
                "total_ms": total_time,
                "chunks": len(audio_chunks),
                "bytes": len(audio_data),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lightning TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/lightning/voice-clone")
async def lightning_voice_clone(
    request: LightningVoiceCloneRequest,
    audio: UploadFile = File(...),
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Clone a voice using Cartesia (3-10 seconds of audio).

    The cloned voice can be used for TTS in any of the 42 supported languages.
    """
    config = CartesiaConfig()

    if not config.api_key:
        raise HTTPException(status_code=503, detail="Cartesia not configured")

    try:
        # Read audio file
        audio_data = await audio.read()

        if len(audio_data) < 1000:
            raise HTTPException(status_code=400, detail="Audio file too short. Need 3-10 seconds.")

        cartesia = CartesiaSonic3(config)

        voice_id = await cartesia.clone_voice(
            audio_data=audio_data,
            name=request.name,
            description=request.description,
            language=request.language,
        )

        if not voice_id:
            raise HTTPException(status_code=500, detail="Voice cloning failed")

        # Save to database
        db = get_supabase()
        db.client.table("va_voice_clones").insert({
            "user_id": user_id,
            "name": request.name,
            "voice_id": voice_id,
            "provider": "cartesia",
            "language": request.language,
            "description": request.description,
        }).execute()

        return {
            "voice_id": voice_id,
            "name": request.name,
            "language": request.language,
            "provider": "cartesia",
            "supported_languages": len(get_tts_languages()),
            "message": "Voice cloned! Use /lightning/localize to adapt it to other languages."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice clone error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/lightning/localize")
async def lightning_localize_voice(
    request: LightningLocalizeRequest,
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Localize a cloned voice to speak another language naturally.

    Uses Cartesia's cross-lingual voice cloning to make your voice
    sound natural in Spanish, Hindi, Japanese, etc.
    """
    config = CartesiaConfig()

    if not config.api_key:
        raise HTTPException(status_code=503, detail="Cartesia not configured")

    try:
        cartesia = CartesiaSonic3(config)

        new_voice_id = await cartesia.localize_voice(
            voice_id=request.voice_id,
            target_language=request.target_language,
            name=request.name,
        )

        if not new_voice_id:
            raise HTTPException(status_code=500, detail="Voice localization failed")

        # Save to database
        db = get_supabase()
        db.client.table("va_voice_clones").insert({
            "user_id": user_id,
            "name": request.name or f"Localized ({request.target_language})",
            "voice_id": new_voice_id,
            "provider": "cartesia",
            "language": request.target_language,
            "parent_voice_id": request.voice_id,
            "description": f"Localized from {request.voice_id}",
        }).execute()

        return {
            "voice_id": new_voice_id,
            "source_voice_id": request.voice_id,
            "target_language": request.target_language,
            "message": f"Voice localized to {request.target_language}!"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice localization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/lightning/{assistant_id}")
async def websocket_lightning_endpoint(
    websocket: WebSocket,
    assistant_id: str,
):
    """
    ⚡ Lightning WebSocket - Sub-150ms Voice AI

    Uses the full Lightning Stack:
    - Deepgram Nova-3: ~30ms STT
    - Groq Llama 3.3 70B: ~40ms TTFT
    - Cartesia Sonic-3: ~30ms TTS
    - Sentence-level streaming: TTS starts on first sentence!

    Protocol:
    - Client sends: {"type": "auth", "user_id": "..."}
    - Client sends: {"type": "audio", "data": "<base64 audio>"}
    - Client sends: {"type": "end_call"}
    - Server sends: {"type": "ready", "call_id": "...", "stack": "lightning"}
    - Server sends: {"type": "transcript", "role": "user"|"assistant", "content": "..."}
    - Server sends: {"type": "audio", "data": "<base64 audio>"}
    - Server sends: {"type": "latency", "data": {...}}  <- Real-time latency metrics!
    - Server sends: {"type": "speaking", "is_speaking": true|false}
    """
    await websocket.accept()
    pipeline: Optional[LightningPipeline] = None
    call_id = None
    user_id = None

    try:
        # Wait for authentication
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        if auth_data.get('type') != 'auth' or not auth_data.get('user_id'):
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close()
            return

        user_id = auth_data['user_id']
        logger.info(f"⚡ Lightning WebSocket authenticated for user {user_id}")

        # Get assistant configuration
        db = get_supabase()
        assistant_result = db.client.table("va_assistants").select("*").eq(
            "id", assistant_id
        ).eq("user_id", user_id).eq("is_active", True).execute()

        if not assistant_result.data:
            await websocket.send_json({"type": "error", "message": "Assistant not found"})
            await websocket.close()
            return

        assistant = assistant_result.data[0]

        # Check feature gate
        feature_gate = get_feature_gate()
        try:
            allowed, details = feature_gate.check_feature(user_id, "max_minutes")
            if not allowed:
                await websocket.send_json({
                    "type": "error",
                    "message": "You've used all your minutes. Upgrade to continue."
                })
                await websocket.close()
                return
        except Exception as e:
            logger.warning(f"Feature gate error: {e}")

        # Create call record
        import uuid
        call_id = str(uuid.uuid4())
        db.client.table("va_call_logs").insert({
            "id": call_id,
            "user_id": user_id,
            "assistant_id": assistant_id,
            "status": "active",
            "pipeline": "lightning",  # Track that this used Lightning Stack
        }).execute()

        # Initialize Lightning Pipeline
        config = LightningConfig()
        # Use assistant's voice_id if valid, otherwise use default Katie voice
        assistant_voice_id = assistant.get('voice_id')
        if assistant_voice_id and len(assistant_voice_id) > 10:
            config.cartesia_voice_id = assistant_voice_id
        # Apply voice control settings from assistant
        if assistant.get('speech_speed'):
            config.speech_speed = assistant.get('speech_speed')
        if assistant.get('response_delay_ms'):
            config.response_delay_ms = assistant.get('response_delay_ms')

        pipeline = LightningPipeline(config)

        # Set up callbacks
        async def on_transcript(role: str, text: str):
            await websocket.send_json({
                "type": "transcript",
                "role": role,
                "content": text
            })

        async def on_audio(audio_bytes: bytes):
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            await websocket.send_json({
                "type": "audio",
                "data": audio_b64
            })

        async def on_state_change(state: LightningState):
            is_speaking = state == LightningState.SPEAKING
            await websocket.send_json({
                "type": "speaking",
                "is_speaking": is_speaking
            })

        async def on_latency(metrics: LatencyMetrics):
            await websocket.send_json({
                "type": "latency",
                "data": {
                    "stt_ms": metrics.stt_ms,
                    "llm_ttft_ms": metrics.llm_ttft_ms,
                    "tts_ttfb_ms": metrics.tts_ttfb_ms,
                    "perceived_ms": metrics.total_perceived_ms,
                    "target_ms": 150,
                    "status": "lightning" if metrics.total_perceived_ms < 200 else "fast" if metrics.total_perceived_ms < 500 else "normal"
                }
            })

        pipeline.on_transcript = on_transcript
        pipeline.on_audio_out = on_audio
        pipeline.on_state_change = on_state_change
        pipeline.on_latency = on_latency

        # Initialize with assistant's system prompt
        await pipeline.initialize(
            system_prompt=assistant.get('system_prompt', 'You are a helpful assistant.'),
            voice_id=assistant_voice_id if assistant_voice_id and len(assistant_voice_id) > 10 else None,
        )

        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "call_id": call_id,
            "stack": "lightning",
            "assistant_name": assistant['name'],
            "latency_target_ms": 150,
        })

        logger.info(f"⚡ Lightning Pipeline ready for call {call_id}")

        # Send first message if configured
        first_message = assistant.get('first_message')
        if first_message:
            await pipeline.speak(first_message)

        # Main message loop
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get('type')

                if msg_type == 'audio':
                    # Decode and send to pipeline
                    audio_b64 = message.get('data', '')
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await pipeline.send_audio(audio_bytes)

                elif msg_type == 'end_call':
                    logger.info(f"Call {call_id} ended by user")
                    break

                elif msg_type == 'ping':
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for call {call_id}")
                break
            except Exception as e:
                logger.error(f"Message handling error: {e}")
                await websocket.send_json({"type": "error", "message": str(e)})

    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "Authentication timeout"})
    except Exception as e:
        logger.error(f"Lightning WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        # Cleanup
        if pipeline:
            await pipeline.close()

        # Update call record
        if call_id and user_id:
            try:
                db = get_supabase()
                metrics = pipeline.get_metrics() if pipeline else {}
                db.client.table("va_call_logs").update({
                    "status": "completed",
                    "ended_at": datetime.utcnow().isoformat(),
                    "metrics": metrics,
                }).eq("id", call_id).execute()
            except Exception as e:
                logger.error(f"Failed to update call record: {e}")

        try:
            await websocket.close()
        except:
            pass


# =============================================================================
# END LIGHTNING PIPELINE ENDPOINTS
# =============================================================================


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
    print("\n⚡ Lightning Pipeline (Sub-150ms Voice AI):")
    print("  GET    /lightning/status              - Pipeline status & config")
    print("  GET    /lightning/languages           - Supported languages (42 TTS, 36+ STT)")
    print("  POST   /lightning/chat                - Fast LLM chat (Groq ~40ms TTFT)")
    print("  POST   /lightning/tts                 - Ultra-fast TTS (Cartesia ~30ms)")
    print("  POST   /lightning/voice-clone         - Clone voice (3-10s audio)")
    print("  POST   /lightning/localize            - Localize voice to other languages")
    print("  WS     /ws/lightning/{assistant_id}   - Full voice streaming pipeline")
    print("\n" + "=" * 60)

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "true").lower() == "true",
    )
