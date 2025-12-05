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
import time
import json
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
# SENTIMENT ANALYSIS
# ============================================================================

class SentimentAnalyzer:
    """
    Simple sentiment analysis for voice conversations.
    Tracks user mood throughout the call.
    """

    POSITIVE_WORDS = {
        'great', 'good', 'awesome', 'excellent', 'love', 'thanks', 'thank', 'perfect',
        'amazing', 'wonderful', 'fantastic', 'happy', 'pleased', 'helpful', 'nice',
        'appreciate', 'brilliant', 'best', 'super', 'cool', 'yes', 'yeah', 'absolutely'
    }

    NEGATIVE_WORDS = {
        'bad', 'terrible', 'awful', 'hate', 'angry', 'frustrated', 'annoying',
        'stupid', 'wrong', 'confused', 'disappointed', 'problem', 'issue', 'broken',
        'fail', 'failed', 'useless', 'worst', 'no', 'not', 'never', 'cant', "can't"
    }

    def __init__(self):
        self.scores: List[Dict[str, Any]] = []
        self._room = None

    def set_room(self, room):
        self._room = room

    def analyze(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text."""
        text_lower = text.lower()
        words = set(text_lower.split())

        positive_count = len(words & self.POSITIVE_WORDS)
        negative_count = len(words & self.NEGATIVE_WORDS)

        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            sentiment = "neutral"
        else:
            score = (positive_count - negative_count) / total
            if score > 0.3:
                sentiment = "positive"
            elif score < -0.3:
                sentiment = "negative"
            else:
                sentiment = "neutral"

        result = {
            "score": round(score, 2),
            "sentiment": sentiment,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "timestamp": time.time(),
        }
        self.scores.append(result)
        return result

    def get_overall(self) -> Dict[str, Any]:
        """Get overall sentiment for the call."""
        if not self.scores:
            return {"overall": "neutral", "avg_score": 0.0, "trend": "stable"}

        avg_score = sum(s["score"] for s in self.scores) / len(self.scores)

        if avg_score > 0.2:
            overall = "positive"
        elif avg_score < -0.2:
            overall = "negative"
        else:
            overall = "neutral"

        # Calculate trend
        if len(self.scores) >= 3:
            recent_avg = sum(s["score"] for s in self.scores[-3:]) / 3
            older_avg = sum(s["score"] for s in self.scores[:-3]) / max(1, len(self.scores) - 3)
            if recent_avg > older_avg + 0.2:
                trend = "improving"
            elif recent_avg < older_avg - 0.2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {"overall": overall, "avg_score": round(avg_score, 2), "trend": trend}

    async def publish(self, text: str):
        """Analyze and publish sentiment update."""
        if not self._room:
            return

        result = self.analyze(text)
        overall = self.get_overall()

        try:
            data = json.dumps({
                "type": "sentiment",
                "current": result,
                "overall": overall,
            }).encode()
            await self._room.local_participant.publish_data(data, topic="sentiment", reliable=True)
        except Exception as e:
            logger.warning(f"Failed to publish sentiment: {e}")


# ============================================================================
# LATENCY TRACKING
# ============================================================================

class LatencyTracker:
    """
    Tracks latency metrics for each phase of the voice pipeline.
    Sends real-time updates to the frontend via data channel.
    """

    def __init__(self):
        self.current_turn: Dict[str, float] = {}
        self.metrics_history: List[Dict[str, Any]] = []
        self._data_publisher = None
        self._room = None

    def set_room(self, room):
        """Set the LiveKit room for publishing metrics."""
        self._room = room

    def start_stt(self):
        """Mark the start of speech-to-text processing."""
        self.current_turn = {"stt_start": time.time()}

    def end_stt(self):
        """Mark the end of STT, calculate latency."""
        if "stt_start" in self.current_turn:
            self.current_turn["stt_end"] = time.time()
            self.current_turn["stt_ms"] = int((self.current_turn["stt_end"] - self.current_turn["stt_start"]) * 1000)

    def start_llm(self):
        """Mark the start of LLM processing."""
        self.current_turn["llm_start"] = time.time()

    def end_llm_first_token(self):
        """Mark when first token arrives (TTFT)."""
        if "llm_start" in self.current_turn:
            self.current_turn["llm_ttft"] = time.time()
            self.current_turn["llm_ttft_ms"] = int((self.current_turn["llm_ttft"] - self.current_turn["llm_start"]) * 1000)

    def end_llm(self):
        """Mark the end of LLM processing."""
        if "llm_start" in self.current_turn:
            self.current_turn["llm_end"] = time.time()
            self.current_turn["llm_total_ms"] = int((self.current_turn["llm_end"] - self.current_turn["llm_start"]) * 1000)

    def start_tts(self):
        """Mark the start of text-to-speech."""
        self.current_turn["tts_start"] = time.time()

    def end_tts_first_byte(self):
        """Mark when first audio byte is ready (TTFB)."""
        if "tts_start" in self.current_turn:
            self.current_turn["tts_ttfb"] = time.time()
            self.current_turn["tts_ttfb_ms"] = int((self.current_turn["tts_ttfb"] - self.current_turn["tts_start"]) * 1000)

    def end_tts(self):
        """Mark the end of TTS."""
        if "tts_start" in self.current_turn:
            self.current_turn["tts_end"] = time.time()
            self.current_turn["tts_total_ms"] = int((self.current_turn["tts_end"] - self.current_turn["tts_start"]) * 1000)

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get the current turn's metrics."""
        # Calculate total perceived latency (user done speaking to first audio)
        total_ms = 0
        if self.current_turn.get("stt_ms"):
            total_ms += self.current_turn["stt_ms"]
        if self.current_turn.get("llm_ttft_ms"):
            total_ms += self.current_turn["llm_ttft_ms"]
        if self.current_turn.get("tts_ttfb_ms"):
            total_ms += self.current_turn["tts_ttfb_ms"]

        return {
            "type": "latency",
            "stt_ms": self.current_turn.get("stt_ms", 0),
            "llm_ttft_ms": self.current_turn.get("llm_ttft_ms", 0),
            "llm_total_ms": self.current_turn.get("llm_total_ms", 0),
            "tts_ttfb_ms": self.current_turn.get("tts_ttfb_ms", 0),
            "tts_total_ms": self.current_turn.get("tts_total_ms", 0),
            "total_ms": total_ms,
            "timestamp": time.time(),
        }

    async def publish_metrics(self):
        """Publish current metrics to the frontend via data channel."""
        if not self._room:
            return

        try:
            metrics = self.get_current_metrics()
            data = json.dumps(metrics).encode()
            await self._room.local_participant.publish_data(
                data,
                topic="latency",
                reliable=True,
            )
            logger.debug(f"Published latency metrics: {metrics}")
        except Exception as e:
            logger.warning(f"Failed to publish latency metrics: {e}")

    def finalize_turn(self):
        """Store current turn metrics and reset."""
        if self.current_turn:
            self.metrics_history.append(self.get_current_metrics())
        self.current_turn = {}

    def get_average_metrics(self) -> Dict[str, float]:
        """Get average metrics across all turns."""
        if not self.metrics_history:
            return {}

        avg = {}
        for key in ["stt_ms", "llm_ttft_ms", "tts_ttfb_ms", "total_ms"]:
            values = [m.get(key, 0) for m in self.metrics_history if m.get(key)]
            if values:
                avg[f"avg_{key}"] = sum(values) / len(values)

        return avg


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
                self._llm = openai.LLM(
                    model=self.config.groq_model,
                    temperature=self.config.temperature,
                    api_key=self.config.groq_api_key,
                    base_url="https://api.groq.com/openai/v1",
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

    # Initialize latency tracker
    latency = LatencyTracker()
    latency.set_room(ctx.room)

    # Initialize sentiment analyzer
    sentiment = SentimentAnalyzer()
    sentiment.set_room(ctx.room)

    # Parse room metadata for call info
    call_id = None
    user_id = None
    assistant_id = None
    try:
        if ctx.room.metadata:
            room_meta = json.loads(ctx.room.metadata)
            call_id = room_meta.get("call_id")
            user_id = room_meta.get("user_id")
            assistant_id = room_meta.get("assistant_id")
            logger.info(f"Room metadata: call_id={call_id}, user_id={user_id}, assistant_id={assistant_id}")
    except Exception as e:
        logger.warning(f"Could not parse room metadata: {e}")

    # Track transcript
    transcript: List[Dict[str, str]] = []
    call_start_time = time.time()

    # Initialize STT (Deepgram)
    stt = deepgram.STT(
        model="nova-2",
        language="en-US",
    )
    logger.info("Deepgram STT initialized")

    # Initialize LLM with fallback chain: Fast Brain -> Groq -> OpenAI
    llm = None
    llm_name = "unknown"

    # Try Fast Brain first (custom BitNet LPU)
    if config.fast_brain_url and BRAIN_CLIENT_AVAILABLE:
        try:
            brain_client = FastBrainClient(
                base_url=config.fast_brain_url,
                default_skill=config.default_skill,
            )
            if await brain_client.is_healthy():
                llm = BrainLLM(brain_client, skill=config.default_skill)
                llm_name = "fast-brain"
                logger.info(f"Fast Brain LLM initialized: {config.fast_brain_url[:40]}... (skill={config.default_skill})")
            else:
                logger.warning("Fast Brain not healthy, trying fallback...")
        except Exception as e:
            logger.warning(f"Fast Brain initialization failed: {e}, trying fallback...")

    # Fallback to Groq (using OpenAI-compatible API)
    if llm is None and config.groq_api_key:
        llm = openai.LLM(
            model=config.groq_model,
            temperature=config.temperature,
            api_key=config.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        llm_name = config.groq_model
        logger.info(f"Groq LLM initialized: {config.groq_model}")

    # Fallback to Anthropic Claude
    if llm is None and config.anthropic_api_key:
        llm = anthropic.LLM(model="claude-sonnet-4-20250514")
        llm_name = "claude-sonnet-4"
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

    # Create and start the session with turn detection settings
    # min_endpointing_delay: Wait longer before considering turn complete (reduces choppy responses)
    # This helps prevent the agent from interrupting during natural speech pauses
    session = AgentSession(
        vad=vad,
        stt=stt,
        llm=llm,
        tts=tts,
        min_endpointing_delay=0.8,  # Wait 0.8s of silence before responding (default is 0.5)
        max_endpointing_delay=6.0,  # Max wait time
        allow_interruptions=True,   # Allow user to interrupt agent
    )

    # Note: transcript, call_start_time, call_id, user_id, assistant_id, latency, sentiment
    # are already initialized above (lines 831-854). No re-initialization needed here.

    # Set up session event handlers for transcript and latency tracking
    # Using current LiveKit SDK event names

    @session.on("user_state_changed")
    def on_user_state_changed(event):
        """Track user state changes for latency."""
        state = event.state if hasattr(event, 'state') else str(event)
        if state == "speaking":
            latency.start_stt()
            logger.debug("User started speaking")
        elif state == "listening":
            latency.end_stt()
            logger.debug("User stopped speaking")

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        """User speech transcribed - capture for transcript."""
        try:
            # Get transcript text from event
            text = ""
            if hasattr(event, 'transcript'):
                text = event.transcript
            elif hasattr(event, 'text'):
                text = event.text
            else:
                text = str(event)

            # Only capture final transcripts, not interim
            is_final = getattr(event, 'is_final', True)
            if is_final and text.strip():
                transcript.append({
                    "role": "user",
                    "content": text,
                    "timestamp": time.strftime("%H:%M:%S")
                })
                logger.info(f"User: {text[:50]}...")
                # Publish transcript update
                asyncio.create_task(_publish_transcript(ctx.room, "user", text))
                # Analyze and publish sentiment
                asyncio.create_task(sentiment.publish(text))
                latency.start_llm()  # LLM processing starts
        except Exception as e:
            logger.warning(f"Error processing user transcript: {e}")

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        """Track agent state changes."""
        state = event.state if hasattr(event, 'state') else str(event)
        if state == "speaking":
            latency.end_llm_first_token()
            latency.start_tts()
            latency.end_tts_first_byte()
            asyncio.create_task(latency.publish_metrics())
            logger.debug("Agent started speaking")
        elif state == "listening":
            latency.end_tts()
            latency.end_llm()
            latency.finalize_turn()
            logger.debug("Agent stopped speaking")

    @session.on("conversation_item_added")
    def on_conversation_item_added(event):
        """Capture conversation items for transcript."""
        try:
            # Get the item from the event
            item = getattr(event, 'item', event)
            role = getattr(item, 'role', None)

            # Only capture assistant messages (user messages handled by user_input_transcribed)
            if role == "assistant":
                content = ""
                if hasattr(item, 'content'):
                    # Content might be a list of parts or a string
                    if isinstance(item.content, list):
                        content = " ".join(str(p) for p in item.content)
                    else:
                        content = str(item.content)
                elif hasattr(item, 'text'):
                    content = item.text
                else:
                    content = str(item)

                if content.strip():
                    transcript.append({
                        "role": "assistant",
                        "content": content,
                        "timestamp": time.strftime("%H:%M:%S")
                    })
                    logger.info(f"Assistant: {content[:50]}...")
                    asyncio.create_task(_publish_transcript(ctx.room, "assistant", content))
        except Exception as e:
            logger.warning(f"Error processing conversation item: {e}")

    # Handle settings updates from frontend
    @ctx.room.on("data_received")
    def on_data_received(data_packet):
        """Process settings updates from the user."""
        try:
            if hasattr(data_packet, 'topic') and data_packet.topic == 'settings':
                payload = data_packet.data.decode() if hasattr(data_packet, 'data') else str(data_packet)
                settings_data = json.loads(payload)
                if settings_data.get('type') == 'settings':
                    logger.info(f"Received settings update: {settings_data}")
                    # Apply temperature if LLM supports it
                    if hasattr(llm, 'temperature'):
                        llm.temperature = settings_data.get('temperature', 0.7)
                    # Note: Speech speed and barge-in would require TTS/session reconfiguration
                    # which isn't easily done mid-call. These settings are logged for future use.
        except Exception as e:
            logger.warning(f"Failed to process settings update: {e}")

    await session.start(
        agent=agent,
        room=ctx.room,
    )
    logger.info("AgentSession started")

    # Send initial config to frontend
    try:
        config_data = json.dumps({
            "type": "config",
            "llm": llm_name,
            "stt": "deepgram-nova-2",
            "tts": "cartesia-sonic",
            "voice_id": config.cartesia_voice_id[:8] + "...",
        }).encode()
        await ctx.room.local_participant.publish_data(config_data, topic="config", reliable=True)
    except Exception as e:
        logger.warning(f"Failed to publish config: {e}")

    # Generate initial greeting
    await session.generate_reply(
        instructions="Greet the user warmly and ask how you can help them today."
    )

    # Wait for the session to end (room closes)
    try:
        # Keep running until room is closed
        while True:
            await asyncio.sleep(1)
            if not ctx.room.connection_state.name == "CONNECTED":
                break
    except asyncio.CancelledError:
        pass
    finally:
        # Calculate quality score
        quality_score = _calculate_quality_score(
            latency.get_average_metrics(),
            sentiment.get_overall(),
            len(transcript),
            int(time.time() - call_start_time),
        )

        # Save call log on disconnect
        if call_id and SUPABASE_AVAILABLE:
            try:
                duration = int(time.time() - call_start_time)
                avg_metrics = latency.get_average_metrics()
                sentiment_data = sentiment.get_overall()
                supabase = get_supabase().client
                # Determine overall sentiment
                overall_sentiment = "neutral"
                if sentiment_data.get("average", 0) > 0.2:
                    overall_sentiment = "positive"
                elif sentiment_data.get("average", 0) < -0.2:
                    overall_sentiment = "negative"

                supabase.table("va_call_logs").update({
                    "transcript": transcript,
                    "duration_seconds": duration,
                    "status": "completed",
                    "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "sentiment": overall_sentiment,
                    "summary": {
                        "quality_score": quality_score.get("score", 0),
                        "quality_grade": quality_score.get("grade", "C"),
                        "quality_breakdown": quality_score.get("breakdown", {}),
                        "sentiment_score": round(sentiment_data.get("average", 0) * 100),
                        "urgency_level": "normal",
                        "exchange_count": len(transcript) // 2,
                    },
                    "metadata": {
                        "llm": llm_name,
                        "latency": avg_metrics,
                        "sentiment_data": sentiment_data,
                        "transport": "webrtc",
                    }
                }).eq("id", call_id).execute()
                logger.info(f"Call log updated: {call_id}, duration={duration}s, quality={quality_score['grade']}")
            except Exception as e:
                logger.error(f"Failed to update call log: {e}")

        # Publish final quality score to frontend
        try:
            quality_data = json.dumps({
                "type": "quality_score",
                **quality_score,
            }).encode()
            await ctx.room.local_participant.publish_data(
                quality_data, topic="quality", reliable=True
            )
        except Exception as e:
            logger.warning(f"Failed to publish quality score: {e}")


def _calculate_quality_score(
    latency_metrics: Dict[str, Any],
    sentiment_data: Dict[str, Any],
    message_count: int,
    duration_seconds: int,
) -> Dict[str, Any]:
    """
    Calculate an A-F quality grade for the call.

    Factors:
    - Latency (lower is better)
    - Sentiment (positive is better)
    - Engagement (more messages = better interaction)
    - Duration (not too short, not too long)
    """
    score = 100  # Start with perfect score

    # Latency scoring (0-30 points)
    avg_latency = latency_metrics.get("avg_total_ms", 300)
    if avg_latency < 200:
        latency_score = 30
    elif avg_latency < 300:
        latency_score = 25
    elif avg_latency < 400:
        latency_score = 20
    elif avg_latency < 500:
        latency_score = 15
    else:
        latency_score = 10

    # Sentiment scoring (0-30 points)
    sentiment_score_val = sentiment_data.get("avg_score", 0)
    if sentiment_score_val > 0.5:
        sentiment_score = 30
    elif sentiment_score_val > 0.2:
        sentiment_score = 25
    elif sentiment_score_val > 0:
        sentiment_score = 20
    elif sentiment_score_val > -0.2:
        sentiment_score = 15
    else:
        sentiment_score = 10

    # Engagement scoring (0-20 points)
    if message_count >= 10:
        engagement_score = 20
    elif message_count >= 6:
        engagement_score = 15
    elif message_count >= 3:
        engagement_score = 10
    else:
        engagement_score = 5

    # Duration scoring (0-20 points)
    if 60 <= duration_seconds <= 300:  # 1-5 minutes is ideal
        duration_score = 20
    elif 30 <= duration_seconds < 60:
        duration_score = 15
    elif 300 < duration_seconds <= 600:
        duration_score = 15
    elif duration_seconds < 30:
        duration_score = 10  # Too short
    else:
        duration_score = 10  # Too long

    # Calculate total
    total_score = latency_score + sentiment_score + engagement_score + duration_score

    # Convert to letter grade
    if total_score >= 90:
        grade = "A"
    elif total_score >= 80:
        grade = "B"
    elif total_score >= 70:
        grade = "C"
    elif total_score >= 60:
        grade = "D"
    else:
        grade = "F"

    return {
        "grade": grade,
        "score": total_score,
        "breakdown": {
            "latency": latency_score,
            "sentiment": sentiment_score,
            "engagement": engagement_score,
            "duration": duration_score,
        },
        "message_count": message_count,
        "duration_seconds": duration_seconds,
    }


async def _publish_transcript(room, role: str, content: str):
    """Helper to publish transcript updates to frontend."""
    try:
        data = json.dumps({
            "type": "transcript",
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }).encode()
        await room.local_participant.publish_data(data, topic="transcript", reliable=True)
    except Exception as e:
        logger.warning(f"Failed to publish transcript: {e}")


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
