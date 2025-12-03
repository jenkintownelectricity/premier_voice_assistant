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
    JobContext,
    JobProcess,
    WorkerOptions,
    llm as lk_llm,
)
from livekit import rtc

# LiveKit Plugins
from livekit.plugins import silero, deepgram, cartesia, openai, anthropic

# For database access (optional - may not be configured for local testing)
try:
    from backend.supabase_client import get_supabase
    SUPABASE_AVAILABLE = True
except (ImportError, ValueError) as e:
    SUPABASE_AVAILABLE = False
    logging.getLogger(__name__).warning(f"Supabase not available: {e}")

# Brain client for Fast Brain integration
try:
    from backend.brain_client import FastBrainClient, TurnAction
    BRAIN_CLIENT_AVAILABLE = True
except ImportError:
    BRAIN_CLIENT_AVAILABLE = False

logger = logging.getLogger(__name__)


def _normalize_livekit_url(url: str) -> str:
    """
    Normalize LIVEKIT_URL to ensure it has the wss:// prefix.
    This handles common configuration mistakes where users forget the prefix.
    """
    if not url:
        return url

    # Remove any trailing slashes
    url = url.rstrip("/")

    # Handle various formats
    if url.startswith("wss://") or url.startswith("ws://"):
        # Already has websocket prefix
        return url
    elif url.startswith("https://"):
        # Convert HTTPS to WSS
        return "wss://" + url[8:]
    elif url.startswith("http://"):
        # Convert HTTP to WS (for local development)
        return "ws://" + url[7:]
    else:
        # No prefix, add wss://
        return "wss://" + url


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class LiveKitAgentConfig:
    """Configuration for LiveKit Voice Agent."""

    # LiveKit Server
    livekit_url: str = field(default_factory=lambda: _normalize_livekit_url(os.getenv("LIVEKIT_URL", "")))
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
# BRAIN LLM ADAPTER (LiveKit v1.x Compatible)
# ============================================================================

class BrainLLMStream(lk_llm.LLMStream):
    """
    LLM stream that pulls tokens from Fast Brain API.

    Implements the LiveKit v1.x LLMStream interface by streaming
    tokens from our Brain client and emitting ChatChunks.
    """

    def __init__(
        self,
        llm: "BrainLLM",
        *,
        chat_ctx: lk_llm.ChatContext,
        tools: list,
        conn_options,
        user_message: str,
        skill: str,
    ):
        super().__init__(llm, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        self._user_message = user_message
        self._skill = skill
        self._brain = llm.brain

    async def _run(self) -> None:
        """
        Stream tokens from Brain and emit as ChatChunks.
        This is the abstract method required by LLMStream.
        """
        request_id = f"brain-{id(self)}"

        try:
            async for token in self._brain.stream(self._user_message, skill=self._skill):
                chunk = lk_llm.ChatChunk(
                    id=request_id,
                    delta=lk_llm.ChoiceDelta(
                        role="assistant",
                        content=token,
                    ),
                )
                self._event_ch.send_nowait(chunk)
        except Exception as e:
            logger.error(f"Brain streaming error: {e}")
            # Emit a fallback response
            fallback = "I apologize, but I'm having trouble processing that right now."
            chunk = lk_llm.ChatChunk(
                id=request_id,
                delta=lk_llm.ChoiceDelta(
                    role="assistant",
                    content=fallback,
                ),
            )
            self._event_ch.send_nowait(chunk)


class BrainLLM(lk_llm.LLM):
    """
    LiveKit v1.x compatible LLM that connects to Fast Brain API.

    Properly implements the abstract LLM interface with:
    - chat() method returning an LLMStream
    - Streaming tokens via BrainLLMStream
    - Fallback handling on errors
    """

    def __init__(
        self,
        brain_client: "FastBrainClient",
        skill: str = "default",
    ):
        super().__init__()
        self.brain = brain_client
        self.skill = skill
        self._model_name = "fast-brain"

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "fast-brain"

    def chat(
        self,
        *,
        chat_ctx: lk_llm.ChatContext,
        tools: list = None,
        conn_options = None,
        parallel_tool_calls = None,
        tool_choice = None,
        extra_kwargs = None,
    ) -> BrainLLMStream:
        """
        Generate a response given conversation context.
        Returns an LLMStream that yields ChatChunks.
        """
        from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

        # Get the latest user message from chat context
        user_message = ""
        for msg in reversed(chat_ctx.items):
            if hasattr(msg, 'role') and msg.role == "user":
                # Handle different message formats
                if hasattr(msg, 'text'):
                    user_message = msg.text
                elif hasattr(msg, 'content'):
                    user_message = str(msg.content)
                break

        if not user_message:
            user_message = "Hello"  # Fallback

        return BrainLLMStream(
            self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options or DEFAULT_API_CONNECT_OPTIONS,
            user_message=user_message,
            skill=self.skill,
        )

    def set_skill(self, skill: str):
        """Change the skill adapter mid-conversation."""
        self.skill = skill
        logger.info(f"Switched to skill: {skill}")

    async def aclose(self) -> None:
        """Cleanup resources."""
        if self.brain:
            await self.brain.close()


# ============================================================================
# ASSISTANT CONFIGURATION LOADER
# ============================================================================

async def load_assistant_config(assistant_id: str) -> Dict[str, Any]:
    """Load assistant configuration from Supabase database."""
    if not SUPABASE_AVAILABLE:
        logger.warning("Supabase not available, using default assistant config")
        return {}
    try:
        supabase = get_supabase().client
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
    if not SUPABASE_AVAILABLE:
        logger.warning("Supabase not available, call log not saved")
        return None
    try:
        supabase = get_supabase().client
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
        # Keep it simple - let defaults handle the rest
        self._session = AgentSession(
            vad=self._vad,
            stt=self._stt,
            llm=self._llm,
            tts=self._tts,
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
    Simplified v1.x pattern for reliable audio handling.

    LLM Priority: Fast Brain -> Groq -> OpenAI
    """
    logger.info(f"Agent job started for room: {ctx.room.name}")

    # Connect to the room
    await ctx.connect()

    # Get config
    config = LiveKitAgentConfig()

    # Initialize STT (Deepgram)
    stt = deepgram.STT(
        model="nova-2",
        language="en-US",
    )
    logger.info("Deepgram STT initialized")

    # Initialize LLM with fallback chain: Fast Brain -> Groq -> OpenAI
    llm = None

    # Try Fast Brain first (custom BitNet LPU)
    if config.fast_brain_url and BRAIN_CLIENT_AVAILABLE:
        try:
            brain_client = FastBrainClient(
                base_url=config.fast_brain_url,
                default_skill=config.default_skill,
            )
            if await brain_client.is_healthy():
                llm = BrainLLM(brain_client, skill=config.default_skill)
                logger.info(f"Fast Brain LLM initialized: {config.fast_brain_url[:40]}... (skill={config.default_skill})")
            else:
                logger.warning("Fast Brain not healthy, trying fallback...")
        except Exception as e:
            logger.warning(f"Fast Brain initialization failed: {e}, trying fallback...")

    # Fallback to Groq
    if llm is None and config.groq_api_key:
        llm = openai.LLM.with_groq(
            model=config.groq_model,
            temperature=config.temperature,
        )
        logger.info(f"Groq LLM initialized: {config.groq_model}")

    # Fallback to Anthropic Claude
    if llm is None and config.anthropic_api_key:
        llm = anthropic.LLM(model="claude-sonnet-4-20250514")
        logger.info("Anthropic Claude initialized as fallback")

    if llm is None:
        logger.error("No LLM configured (Fast Brain, Groq, or Anthropic)")
        return

    # Initialize TTS (Cartesia)
    tts = cartesia.TTS(
        model="sonic-english",
        voice=config.cartesia_voice_id,
    )
    logger.info("Cartesia TTS initialized")

    # Initialize VAD (Silero) - required for detecting user speech
    vad = silero.VAD.load()
    logger.info("Silero VAD initialized")

    # Create the agent with instructions
    agent = Agent(
        instructions="""You are a helpful, friendly voice assistant.
Keep responses concise and conversational (1-2 sentences when possible).
Be natural and engaging, like talking to a friend."""
    )

    # Create and start the session (v1.x standard pattern)
    session = AgentSession(
        vad=vad,
        stt=stt,
        llm=llm,
        tts=tts,
    )

    await session.start(
        agent=agent,
        room=ctx.room,
    )
    logger.info("AgentSession started")

    # Generate initial greeting
    await session.generate_reply(
        instructions="Greet the user warmly and ask how you can help them today."
    )


def prewarm(proc: JobProcess):
    """
    Prewarm function - load models before processing jobs.
    This runs once when the worker starts.
    """
    logger.info("Prewarming agent worker...")
    logger.info("Prewarm complete")


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
