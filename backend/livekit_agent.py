"""
LiveKit Voice Agent - WebRTC-powered Voice AI Pipeline

Sub-200ms perceived latency using:
- LiveKit WebRTC: ~10-20ms UDP transport
- Silero VAD: Built-in voice activity detection
- Deepgram Nova-2: Streaming STT (~30ms)
- Groq Llama 3.3 70B: Ultra-fast LLM (~40ms TTFT)
- Cartesia Sonic: Streaming TTS (~30ms)

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│  User Browser ──WebRTC (UDP)──▶ LiveKit Server ──▶ Agent      │
│                    ~10-20ms          │                          │
│                                      ▼                          │
│  Audio ──▶ VAD ──▶ Deepgram ──▶ Groq ──▶ Cartesia ──▶ Audio   │
│             │       ~30ms      ~40ms    ~30ms                   │
│                                                                 │
│  Total perceived latency: ~200-250ms                           │
└─────────────────────────────────────────────────────────────────┘

This is the next evolution of the Lightning Pipeline - now with WebRTC!
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# LiveKit Agents SDK
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    llm as lk_llm,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.agents.pipeline.pipeline_agent import AgentCallContext
from livekit import rtc

# LiveKit Plugins
from livekit.plugins import silero, deepgram, cartesia, openai

# For database access
from backend.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class LiveKitAgentConfig:
    """Configuration for LiveKit Voice Agent."""

    # LiveKit Server
    livekit_url: str = field(default_factory=lambda: os.getenv("LIVEKIT_URL", ""))
    livekit_api_key: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_KEY", ""))
    livekit_api_secret: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", ""))

    # STT (Deepgram)
    deepgram_api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))
    deepgram_model: str = "nova-2"
    deepgram_language: str = "en-US"

    # LLM (Groq)
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 150
    temperature: float = 0.7

    # TTS (Cartesia)
    cartesia_api_key: str = field(default_factory=lambda: os.getenv("CARTESIA_API_KEY", ""))
    cartesia_voice_id: str = field(default_factory=lambda: os.getenv("CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091"))
    cartesia_model: str = "sonic-english"
    speech_speed: float = 1.0

    # Fallback LLM (Anthropic/OpenAI)
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # Pipeline settings
    response_delay_ms: int = 100
    enable_barge_in: bool = True
    min_endpointing_delay: float = 0.5  # seconds


# ============================================================================
# ASSISTANT CONFIGURATION LOADER
# ============================================================================

async def load_assistant_config(assistant_id: str) -> Dict[str, Any]:
    """Load assistant configuration from Supabase database."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("va_assistants").select("*").eq("id", assistant_id).single().execute()

        if result.data:
            return result.data
        else:
            logger.warning(f"Assistant {assistant_id} not found, using defaults")
            return {}
    except Exception as e:
        logger.error(f"Failed to load assistant config: {e}")
        return {}


async def save_call_log(
    user_id: str,
    assistant_id: str,
    call_type: str = "livekit",
    duration_seconds: int = 0,
    transcript: List[Dict] = None,
    metadata: Dict = None,
) -> Optional[str]:
    """Save call log to database."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("va_call_logs").insert({
            "user_id": user_id,
            "assistant_id": assistant_id,
            "call_type": call_type,
            "duration_seconds": duration_seconds,
            "transcript": transcript or [],
            "metadata": metadata or {},
            "ended_reason": "completed",
        }).execute()

        if result.data:
            return result.data[0].get("id")
        return None
    except Exception as e:
        logger.error(f"Failed to save call log: {e}")
        return None


# ============================================================================
# LIVEKIT VOICE AGENT
# ============================================================================

class HiveVoiceAgent:
    """
    HIVE215 Voice Agent using LiveKit's VoicePipelineAgent.

    Integrates with:
    - Deepgram for STT
    - Groq (or Claude/GPT as fallback) for LLM
    - Cartesia for TTS
    - Silero for VAD
    """

    def __init__(
        self,
        config: Optional[LiveKitAgentConfig] = None,
        assistant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.config = config or LiveKitAgentConfig()
        self.assistant_id = assistant_id
        self.user_id = user_id

        # Assistant config from DB
        self.assistant_config: Dict[str, Any] = {}

        # Transcript tracking
        self.transcript: List[Dict[str, str]] = []
        self.call_start_time: Optional[float] = None

        # Pipeline components
        self._vad: Optional[silero.VAD] = None
        self._stt: Optional[deepgram.STT] = None
        self._llm: Optional[Any] = None
        self._tts: Optional[cartesia.TTS] = None
        self._agent: Optional[VoicePipelineAgent] = None

    async def initialize(self) -> bool:
        """Initialize all pipeline components."""

        # Load assistant config from database
        if self.assistant_id:
            self.assistant_config = await load_assistant_config(self.assistant_id)
            logger.info(f"Loaded assistant config: {self.assistant_config.get('name', 'Unknown')}")

        # Override config with assistant settings
        if self.assistant_config:
            if self.assistant_config.get("voice_id"):
                self.config.cartesia_voice_id = self.assistant_config["voice_id"]
            if self.assistant_config.get("model"):
                # Map model names to Groq models
                model_map = {
                    "llama-3.3-70b": "llama-3.3-70b-versatile",
                    "llama-3.1-70b": "llama-3.1-70b-versatile",
                    "mixtral-8x7b": "mixtral-8x7b-32768",
                }
                self.config.groq_model = model_map.get(
                    self.assistant_config["model"],
                    self.assistant_config["model"]
                )

        try:
            # Initialize VAD (Silero)
            self._vad = silero.VAD.load()
            logger.info("Silero VAD loaded")

            # Initialize STT (Deepgram)
            if self.config.deepgram_api_key:
                self._stt = deepgram.STT(
                    model=self.config.deepgram_model,
                    language=self.config.deepgram_language,
                    smart_format=True,
                    punctuate=True,
                    interim_results=True,
                )
                logger.info(f"Deepgram STT initialized (model={self.config.deepgram_model})")
            else:
                logger.error("Deepgram API key not configured")
                return False

            # Initialize LLM (Groq with OpenAI fallback)
            if self.config.groq_api_key:
                # Use OpenAI plugin with Groq's OpenAI-compatible API
                self._llm = openai.LLM.with_groq(
                    model=self.config.groq_model,
                    temperature=self.config.temperature,
                )
                logger.info(f"Groq LLM initialized (model={self.config.groq_model})")
            elif self.config.openai_api_key:
                self._llm = openai.LLM(
                    model="gpt-4o",
                    temperature=self.config.temperature,
                )
                logger.info("OpenAI LLM initialized as fallback")
            else:
                logger.error("No LLM API key configured (Groq or OpenAI)")
                return False

            # Initialize TTS (Cartesia)
            if self.config.cartesia_api_key:
                self._tts = cartesia.TTS(
                    model=self.config.cartesia_model,
                    voice=self.config.cartesia_voice_id,
                    speed=self.config.speech_speed,
                )
                logger.info(f"Cartesia TTS initialized (voice={self.config.cartesia_voice_id[:8]}...)")
            else:
                logger.error("Cartesia API key not configured")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            return False

    def get_system_prompt(self) -> str:
        """Get system prompt from assistant config or use default."""
        if self.assistant_config.get("system_prompt"):
            return self.assistant_config["system_prompt"]

        return """You are a helpful, friendly voice assistant.

Guidelines:
- Keep responses concise and conversational (1-2 sentences when possible)
- Be natural and engaging, like talking to a friend
- Ask clarifying questions when needed
- If you don't know something, say so honestly
- Match the user's energy and communication style"""

    def get_first_message(self) -> str:
        """Get initial greeting from assistant config or use default."""
        if self.assistant_config.get("first_message"):
            return self.assistant_config["first_message"]

        name = self.assistant_config.get("name", "")
        if name:
            return f"Hello! I'm {name}. How can I help you today?"
        return "Hello! How can I help you today?"

    def create_agent(self, ctx: JobContext) -> VoicePipelineAgent:
        """Create the VoicePipelineAgent for a job context."""

        # Create chat context with system prompt
        initial_ctx = lk_llm.ChatContext()
        initial_ctx.append(
            role="system",
            text=self.get_system_prompt(),
        )

        # Create the voice pipeline agent
        self._agent = VoicePipelineAgent(
            vad=self._vad,
            stt=self._stt,
            llm=self._llm,
            tts=self._tts,
            chat_ctx=initial_ctx,
            allow_interruptions=self.config.enable_barge_in,
            interrupt_speech_duration=0.5,
            interrupt_min_words=2,
            min_endpointing_delay=self.config.min_endpointing_delay,
            preemptive_synthesis=True,  # Start TTS early
        )

        # Set up event handlers
        self._setup_event_handlers()

        return self._agent

    def _setup_event_handlers(self):
        """Set up event handlers for transcript tracking."""
        if not self._agent:
            return

        @self._agent.on("user_speech_committed")
        def on_user_speech(msg: lk_llm.ChatMessage):
            """Track user speech."""
            self.transcript.append({
                "role": "user",
                "content": msg.content,
            })
            logger.info(f"User: {msg.content[:50]}...")

        @self._agent.on("agent_speech_committed")
        def on_agent_speech(msg: lk_llm.ChatMessage):
            """Track agent speech."""
            self.transcript.append({
                "role": "assistant",
                "content": msg.content,
            })
            logger.info(f"Assistant: {msg.content[:50]}...")

        @self._agent.on("agent_speech_interrupted")
        def on_interrupted():
            """Handle user interruption (barge-in)."""
            logger.info("User interrupted assistant")

    async def start(self, ctx: JobContext):
        """Start the voice agent for a job context."""
        import time
        self.call_start_time = time.time()

        # Create and start the agent
        agent = self.create_agent(ctx)
        agent.start(ctx.room)

        # Say initial greeting
        first_message = self.get_first_message()
        await agent.say(first_message, allow_interruptions=True)

        logger.info(f"Agent started for room {ctx.room.name}")

    async def stop(self):
        """Stop the agent and save call log."""
        import time

        if self._agent:
            # Calculate duration
            duration = int(time.time() - self.call_start_time) if self.call_start_time else 0

            # Save call log
            if self.user_id and self.assistant_id:
                await save_call_log(
                    user_id=self.user_id,
                    assistant_id=self.assistant_id,
                    call_type="livekit",
                    duration_seconds=duration,
                    transcript=self.transcript,
                    metadata={
                        "llm_model": self.config.groq_model,
                        "voice_id": self.config.cartesia_voice_id,
                        "transport": "webrtc",
                    }
                )

            logger.info(f"Agent stopped. Duration: {duration}s, Messages: {len(self.transcript)}")


# ============================================================================
# AGENT ENTRYPOINT
# ============================================================================

async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for LiveKit Agent jobs.

    This function is called when a new room is created and an agent
    needs to join. The assistant_id and user_id are passed via room metadata.
    """
    logger.info(f"Agent job started for room: {ctx.room.name}")

    # Connect to the room (audio only for voice agents)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Get assistant_id and user_id from room metadata
    room_metadata = ctx.room.metadata or "{}"
    import json
    try:
        metadata = json.loads(room_metadata)
    except json.JSONDecodeError:
        metadata = {}

    assistant_id = metadata.get("assistant_id")
    user_id = metadata.get("user_id")

    logger.info(f"Room metadata: assistant_id={assistant_id}, user_id={user_id}")

    # Create and initialize the voice agent
    config = LiveKitAgentConfig()
    agent = HiveVoiceAgent(
        config=config,
        assistant_id=assistant_id,
        user_id=user_id,
    )

    if not await agent.initialize():
        logger.error("Failed to initialize agent")
        return

    # Start the agent
    await agent.start(ctx)

    # Wait for the call to end (participant leaves)
    @ctx.room.on("participant_disconnected")
    def on_participant_left(participant: rtc.RemoteParticipant):
        logger.info(f"Participant left: {participant.identity}")

    # Keep agent running until room is closed
    try:
        while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await agent.stop()
        logger.info("Agent job completed")


def prewarm(proc: JobProcess):
    """
    Prewarm function - load models before processing jobs.
    This runs once when the worker starts.
    """
    logger.info("Prewarming agent worker...")

    # Load Silero VAD model (takes a few seconds)
    proc.userdata["vad"] = silero.VAD.load()

    logger.info("Prewarm complete - VAD model loaded")


# ============================================================================
# WORKER ENTRY
# ============================================================================

def create_worker_options() -> WorkerOptions:
    """Create worker options for LiveKit agent."""
    return WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
    )


if __name__ == "__main__":
    """
    Run the agent worker directly.

    Usage:
        python -m backend.livekit_agent dev  # Development mode
        python -m backend.livekit_agent start  # Production mode
    """
    from livekit.agents import cli

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    cli.run_app(create_worker_options())
