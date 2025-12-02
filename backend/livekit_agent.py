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
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass, field

# LiveKit Agents SDK v1.x
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    llm as lk_llm,
)
from livekit import rtc

# LiveKit Plugins
from livekit.plugins import silero, deepgram, cartesia, openai

# For database access
from backend.supabase_client import get_supabase_client

# Brain client for Fast Brain integration
try:
    from backend.brain_client import FastBrainClient, TurnAction
    BRAIN_CLIENT_AVAILABLE = True
except ImportError:
    BRAIN_CLIENT_AVAILABLE = False

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

    # Fast Brain (optional - use instead of Groq for custom BitNet LPU)
    fast_brain_url: str = field(default_factory=lambda: os.getenv("FAST_BRAIN_URL", ""))
    default_skill: str = field(default_factory=lambda: os.getenv("DEFAULT_SKILL", "default"))

    # Pipeline settings
    response_delay_ms: int = 100
    enable_barge_in: bool = True
    min_endpointing_delay: float = 0.5  # seconds


# ============================================================================
# BRAIN LLM ADAPTER
# ============================================================================

class BrainLLM:
    """
    Adapter that makes Fast Brain look like a standard LLM to LiveKit.

    LiveKit's AgentSession expects an LLM with certain methods.
    This wraps our Brain client to provide that interface.
    """

    def __init__(
        self,
        brain_client: "FastBrainClient",
        skill: str = "default",
    ):
        self.brain = brain_client
        self.skill = skill
        self._conversation_history = []

    async def chat(
        self,
        chat_ctx: lk_llm.ChatContext,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a response given conversation context.
        This is called by AgentSession when it's time to respond.

        Yields tokens as they're generated for lowest latency.
        """
        # Get the latest user message from chat context
        user_message = ""
        for msg in reversed(chat_ctx.messages):
            if msg.role == "user":
                user_message = msg.content
                break

        if not user_message:
            return

        # Stream response from Brain
        try:
            async for token in self.brain.stream(user_message, skill=self.skill):
                yield token
        except Exception as e:
            logger.error(f"Brain streaming error: {e}")
            # Fallback response
            yield "I apologize, but I'm having trouble processing that right now. Could you please repeat that?"

    def set_skill(self, skill: str):
        """Change the skill adapter mid-conversation."""
        self.skill = skill
        logger.info(f"Switched to skill: {skill}")


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
    HIVE215 Voice Agent using LiveKit's AgentSession (v1.x API).

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
        self._session: Optional[AgentSession] = None

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

            # Initialize LLM (Brain > Groq > OpenAI fallback chain)
            if self.config.fast_brain_url and BRAIN_CLIENT_AVAILABLE:
                # Use Fast Brain for custom BitNet LPU
                brain_client = FastBrainClient(
                    base_url=self.config.fast_brain_url,
                    default_skill=self.config.default_skill,
                )
                # Check if Brain is healthy
                if await brain_client.is_healthy():
                    self._llm = BrainLLM(brain_client, skill=self.config.default_skill)
                    logger.info(f"Fast Brain LLM initialized (url={self.config.fast_brain_url[:30]}..., skill={self.config.default_skill})")
                else:
                    logger.warning("Fast Brain not healthy, falling back to Groq/OpenAI")
                    self._llm = None

            if self._llm is None and self.config.groq_api_key:
                # Use OpenAI plugin with Groq's OpenAI-compatible API
                self._llm = openai.LLM.with_groq(
                    model=self.config.groq_model,
                    temperature=self.config.temperature,
                )
                logger.info(f"Groq LLM initialized (model={self.config.groq_model})")
            elif self._llm is None and self.config.openai_api_key:
                self._llm = openai.LLM(
                    model="gpt-4o",
                    temperature=self.config.temperature,
                )
                logger.info("OpenAI LLM initialized as fallback")
            elif self._llm is None:
                logger.error("No LLM configured (Fast Brain, Groq, or OpenAI)")
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

    def create_session(self) -> AgentSession:
        """Create the AgentSession for voice interactions (v1.x API)."""

        # Create the voice session with all pipeline components
        self._session = AgentSession(
            vad=self._vad,
            stt=self._stt,
            llm=self._llm,
            tts=self._tts,
            # Enable preemptive generation for lower latency
            preemptive_generation=True,
            # Handle background noise gracefully
            resume_false_interruption=True,
            false_interruption_timeout=1.0,
            # Make interruption detection responsive
            min_interruption_duration=0.2,
        )

        # Set up event handlers
        self._setup_event_handlers()

        return self._session

    def create_agent(self) -> Agent:
        """Create the Agent with instructions (v1.x API)."""
        return Agent(instructions=self.get_system_prompt())

    def _setup_event_handlers(self):
        """Set up event handlers for transcript tracking."""
        if not self._session:
            return

        @self._session.on("user_message")
        def on_user_message(msg):
            """Track user speech."""
            content = str(msg.content) if hasattr(msg, 'content') else str(msg)
            self.transcript.append({
                "role": "user",
                "content": content,
            })
            logger.info(f"User: {content[:50]}...")

        @self._session.on("agent_message")
        def on_agent_message(msg):
            """Track agent speech."""
            content = str(msg.content) if hasattr(msg, 'content') else str(msg)
            self.transcript.append({
                "role": "assistant",
                "content": content,
            })
            logger.info(f"Assistant: {content[:50]}...")

        @self._session.on("agent_speech_interrupted")
        def on_interrupted():
            """Handle user interruption (barge-in)."""
            logger.info("User interrupted assistant")

    async def start(self, ctx: JobContext):
        """Start the voice agent for a job context."""
        import time
        self.call_start_time = time.time()

        # Create session and agent (v1.x API)
        session = self.create_session()
        agent = self.create_agent()

        # Start the session with the agent (v1.x API)
        await session.start(
            agent=agent,
            room=ctx.room,
        )

        # Say initial greeting using generate_reply
        first_message = self.get_first_message()
        await session.generate_reply(instructions=f"Say exactly this greeting: {first_message}")

        logger.info(f"Agent started for room {ctx.room.name}")

    async def stop(self):
        """Stop the agent and save call log."""
        import time

        if self._session:
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
