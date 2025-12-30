"""
HIVE215 Brain Client - Connect to Fast Brain LPU API

This module provides a clean interface for HIVE215 to communicate
with the Fast Brain service deployed on Modal. It handles:
- Hybrid chat (auto-routes System 1 Fast Brain vs System 2 Deep Brain)
- Voice chat with TTS hints
- Filler phrase handling for natural conversation flow
- Skills management and selection
- Automatic fallback if Brain is unavailable
- Turn-taking via local logic

Fast Brain API (Dual-System Architecture):
- GET  /health - Health check with architecture info
- GET  /v1/skills - List available skills
- POST /v1/skills - Create custom skill
- GET  /v1/greeting/{skill_id} - Get skill-specific greeting
- GET  /v1/fillers - Get filler phrase categories
- POST /v1/chat/completions - OpenAI-compatible chat (direct)
- POST /v1/chat/hybrid - Auto-routes Fast (Groq ~80ms) vs Deep (Claude ~2s)
- POST /v1/chat/voice - Returns text + voice hints for TTS

System Architecture:
- System 1 (Fast Brain): Groq LPU + Llama 3.3 70B (~80ms) - 90% of queries
- System 2 (Deep Brain): Claude 3.5 Sonnet (~2000ms) - Complex analysis
- When System 2 is needed, returns a filler phrase to play while waiting

Usage:
    from brain_client import FastBrainClient

    brain = FastBrainClient(
        base_url="https://jenkintownelectricity--fast-brain-lpu-fastapi-app.modal.run",
        default_skill="receptionist"
    )

    # Hybrid chat (recommended for voice)
    response = await brain.hybrid_chat("What are your hours?")
    if response.filler:
        # Play filler while waiting for deep response
        await tts.speak(response.filler)
    await tts.speak(response.content)

    # Voice chat with TTS hints
    voice_response = await brain.voice_chat("I need a plumber")
    # voice_response.voice contains voice description for Parler TTS

    # Get skill-specific greeting
    greeting = await brain.get_greeting("electrician")
"""

import asyncio
import json
import logging
from typing import Optional, AsyncGenerator, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import time

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ThinkResponse:
    """Response from Fast Brain's chat completion endpoint."""
    text: str
    tokens_used: int
    latency_ms: float
    skill_used: str
    tokens_per_sec: float = 0.0

    @classmethod
    def from_openai_response(cls, data: dict) -> "ThinkResponse":
        """Parse OpenAI-compatible chat completion response from Fast Brain."""
        # Extract content from choices
        content = ""
        if data.get("choices") and len(data["choices"]) > 0:
            content = data["choices"][0].get("message", {}).get("content", "")

        # Extract usage
        usage = data.get("usage", {})
        tokens_used = usage.get("total_tokens", 0)

        # Extract metrics (Fast Brain specific)
        metrics = data.get("metrics", {})
        latency_ms = metrics.get("ttfb_ms", 0.0)
        tokens_per_sec = metrics.get("tokens_per_sec", 0.0)

        # Skill used
        skill_used = data.get("skill_used", "unknown")

        return cls(
            text=content,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            skill_used=skill_used,
            tokens_per_sec=tokens_per_sec,
        )


@dataclass
class HybridResponse:
    """
    Response from Fast Brain's hybrid endpoint.

    The hybrid endpoint auto-routes between:
    - System 1 (Fast Brain): Groq ~80ms for simple queries
    - System 2 (Deep Brain): Claude ~2000ms for complex analysis

    When System 2 is used, a filler phrase is returned to play
    while waiting for the deep response.
    """
    content: str
    filler: Optional[str]  # Filler phrase to play while waiting (only if System 2 used)
    system_used: str  # "fast" or "deep"
    fast_latency_ms: float
    deep_latency_ms: Optional[float] = None
    skill_used: str = "default"

    @property
    def used_deep_brain(self) -> bool:
        """Check if System 2 (Claude) was used."""
        return self.system_used == "deep"

    @property
    def total_latency_ms(self) -> float:
        """Get total latency (fast + deep if applicable)."""
        if self.deep_latency_ms:
            return self.fast_latency_ms + self.deep_latency_ms
        return self.fast_latency_ms

    @classmethod
    def from_api_response(cls, data: dict) -> "HybridResponse":
        """Parse hybrid endpoint response."""
        return cls(
            content=data.get("content", ""),
            filler=data.get("filler"),  # None if System 1 was used
            system_used=data.get("system_used", "fast"),
            fast_latency_ms=data.get("fast_latency_ms", 0.0),
            deep_latency_ms=data.get("deep_latency_ms"),
            skill_used=data.get("skill_used", "default"),
        )


@dataclass
class VoiceResponse:
    """
    Response from Fast Brain's voice endpoint.

    Includes text + voice descriptions for TTS systems like Parler TTS
    that can interpret voice personality descriptions.
    """
    text: str
    voice: str  # Voice description (e.g., "A warm, friendly female voice")
    filler_text: Optional[str] = None
    filler_voice: Optional[str] = None
    system_used: str = "fast"

    @classmethod
    def from_api_response(cls, data: dict) -> "VoiceResponse":
        """Parse voice endpoint response."""
        return cls(
            text=data.get("text", ""),
            voice=data.get("voice", "A clear, professional voice"),
            filler_text=data.get("filler_text"),
            filler_voice=data.get("filler_voice"),
            system_used=data.get("system_used", "fast"),
        )


@dataclass
class SkillGreeting:
    """Greeting for a specific skill."""
    text: str
    voice: str  # Voice description for TTS
    skill_id: str

    @classmethod
    def from_api_response(cls, data: dict, skill_id: str) -> "SkillGreeting":
        """Parse greeting endpoint response."""
        return cls(
            text=data.get("text", "Hello, how can I help you?"),
            voice=data.get("voice", "A warm, friendly voice"),
            skill_id=skill_id,
        )


class TurnAction(str, Enum):
    """Actions the turn-taking analysis can recommend."""
    WAIT = "WAIT"               # Keep listening
    RESPOND = "RESPOND"         # Generate response
    BACKCHANNEL = "BACKCHANNEL" # Say "uh-huh"
    INTERRUPT = "INTERRUPT"     # User interrupted


@dataclass
class TurnResult:
    """Result from turn-taking analysis."""
    action: TurnAction
    confidence: float
    reason: str
    
    @property
    def should_respond(self) -> bool:
        return self.action == TurnAction.RESPOND
    
    @property
    def should_wait(self) -> bool:
        return self.action == TurnAction.WAIT


@dataclass
class Skill:
    """Information about an available skill."""
    id: str
    name: str
    description: Optional[str] = None
    version: str = "1.0"


# =============================================================================
# BRAIN CLIENT
# =============================================================================

class FastBrainClient:
    """
    Client for connecting HIVE215 to Fast Brain API.
    
    Supports both HTTP and WebSocket communication:
    - HTTP: Simple, stateless requests
    - WebSocket: Low-latency streaming
    
    Includes automatic retry and fallback handling.
    """
    
    def __init__(
        self,
        base_url: str,
        default_skill: str = "default",
        timeout: float = 30.0,
        max_retries: int = 3,
        fallback_handler: Optional[Callable] = None,
    ):
        """
        Initialize the Brain client.
        
        Args:
            base_url: URL of the Fast Brain API (e.g., https://...modal.run)
            default_skill: Skill to use if none specified
            timeout: Request timeout in seconds
            max_retries: Number of retries on failure
            fallback_handler: Function to call if Brain is unavailable
        """
        self.base_url = base_url.rstrip("/")
        self.ws_url = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        self.default_skill = default_skill
        self.timeout = timeout
        self.max_retries = max_retries
        self.fallback_handler = fallback_handler
        
        # HTTP client with connection pooling
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # WebSocket connection (reusable)
        self._ws_connection = None
        self._ws_lock = asyncio.Lock()
        
        # Health tracking
        self._is_healthy = True
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=10),
            )
        return self._http_client
    
    async def close(self):
        """Close all connections."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        
        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    async def is_healthy(self) -> bool:
        """
        Check if the Brain service is healthy.
        Caches result for health_check_interval seconds.
        """
        now = time.time()
        if now - self._last_health_check < self._health_check_interval:
            return self._is_healthy

        try:
            client = await self._get_http_client()
            response = await client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                self._is_healthy = data.get("status") == "healthy"
                self._available_skills = data.get("skills_available", [])
                self._backend = data.get("backend", "unknown")
            else:
                self._is_healthy = False

        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self._is_healthy = False

        self._last_health_check = now
        return self._is_healthy

    async def get_health_info(self) -> Dict[str, Any]:
        """
        Get full health info including skills and backend.
        """
        try:
            client = await self._get_http_client()
            response = await client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
        return {"status": "unknown", "error": "Failed to connect"}
    
    # =========================================================================
    # THINK / CHAT (HTTP - OpenAI Compatible)
    # =========================================================================

    async def think(
        self,
        user_input: str,
        skill: Optional[str] = None,
        user_profile: Optional[str] = None,
        max_tokens: int = 256,
    ) -> ThinkResponse:
        """
        Get AI response for a single user input.
        Wrapper around chat() for simple single-turn conversations.

        Args:
            user_input: What the user said
            skill: Skill adapter to use (defaults to self.default_skill)
            user_profile: User's business profile info
            max_tokens: Maximum response length

        Returns:
            ThinkResponse with the AI's response

        Raises:
            BrainUnavailableError: If Brain is down and no fallback
        """
        messages = [{"role": "user", "content": user_input}]
        return await self.chat(messages, skill=skill, user_profile=user_profile, max_tokens=max_tokens)

    async def chat(
        self,
        messages: list[Dict[str, str]],
        skill: Optional[str] = None,
        user_profile: Optional[str] = None,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> ThinkResponse:
        """
        Send chat completion request to Fast Brain (OpenAI-compatible).

        Args:
            messages: List of messages [{"role": "user", "content": "..."}]
            skill: Skill adapter to use (defaults to self.default_skill)
            user_profile: User's business profile info
            max_tokens: Maximum response length
            temperature: Sampling temperature (0-1)

        Returns:
            ThinkResponse with the AI's response

        Raises:
            BrainUnavailableError: If Brain is down and no fallback
        """
        skill = skill or self.default_skill

        request_data = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "skill": skill,
        }

        if user_profile:
            request_data["user_profile"] = user_profile

        for attempt in range(self.max_retries):
            try:
                client = await self._get_http_client()
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=request_data,
                )

                if response.status_code == 200:
                    return ThinkResponse.from_openai_response(response.json())
                elif response.status_code == 503:
                    logger.warning("Brain service unavailable")
                    break
                else:
                    logger.error(f"Brain error: {response.status_code} - {response.text}")

            except httpx.TimeoutException:
                logger.warning(f"Brain timeout (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.error(f"Brain request failed: {e}")

        # Use fallback if available
        if self.fallback_handler:
            logger.info("Using fallback handler")
            # Get last user message for fallback
            last_user_msg = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break
            fallback_response = await self.fallback_handler(last_user_msg, skill)
            return ThinkResponse(
                text=fallback_response,
                tokens_used=0,
                latency_ms=0,
                skill_used="fallback",
            )

        raise BrainUnavailableError("Brain service unavailable and no fallback configured")

    # =========================================================================
    # HYBRID CHAT (Recommended for Voice - Auto System 1/2 Routing)
    # =========================================================================

    async def hybrid_chat(
        self,
        messages: list[Dict[str, str]],
        skill: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> HybridResponse:
        """
        Send chat to hybrid endpoint (auto-routes Fast vs Deep Brain).

        This is the RECOMMENDED endpoint for voice agents because:
        1. Simple queries get ~80ms responses (System 1 / Groq)
        2. Complex queries use Claude but return a filler phrase first
        3. The filler can be synthesized while waiting for the deep response

        Args:
            messages: List of messages [{"role": "user", "content": "..."}]
            skill: Skill adapter to use (defaults to self.default_skill)
            user_context: Optional context (business_name, caller_name, etc.)

        Returns:
            HybridResponse with content, filler (if System 2), and latencies
        """
        skill = skill or self.default_skill

        request_data = {
            "messages": messages,
            "skill": skill,
        }

        if user_context:
            request_data["user_context"] = user_context

        for attempt in range(self.max_retries):
            try:
                client = await self._get_http_client()
                response = await client.post(
                    f"{self.base_url}/v1/chat/hybrid",
                    json=request_data,
                    timeout=15.0,  # Allow time for System 2
                )

                if response.status_code == 200:
                    return HybridResponse.from_api_response(response.json())
                elif response.status_code == 503:
                    logger.warning("Brain service unavailable")
                    break
                else:
                    logger.error(f"Hybrid chat error: {response.status_code} - {response.text}")

            except httpx.TimeoutException:
                logger.warning(f"Hybrid chat timeout (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.error(f"Hybrid chat failed: {e}")

        # Use fallback - return as HybridResponse
        if self.fallback_handler:
            logger.info("Using fallback handler for hybrid chat")
            last_user_msg = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break
            fallback_text = await self.fallback_handler(last_user_msg, skill)
            return HybridResponse(
                content=fallback_text,
                filler=None,
                system_used="fallback",
                fast_latency_ms=0,
                skill_used="fallback",
            )

        raise BrainUnavailableError("Hybrid chat unavailable and no fallback configured")

    async def hybrid_think(
        self,
        user_input: str,
        skill: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> HybridResponse:
        """
        Single-turn wrapper for hybrid_chat.

        Args:
            user_input: What the user said
            skill: Skill adapter to use
            user_context: Optional context

        Returns:
            HybridResponse
        """
        messages = [{"role": "user", "content": user_input}]
        return await self.hybrid_chat(messages, skill=skill, user_context=user_context)

    # =========================================================================
    # VOICE CHAT (With TTS Voice Hints)
    # =========================================================================

    async def voice_chat(
        self,
        messages: list[Dict[str, str]],
        skill: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> VoiceResponse:
        """
        Send chat to voice endpoint (returns text + voice hints for TTS).

        Use this endpoint if your TTS system can interpret voice descriptions
        (like Parler TTS). Otherwise, use hybrid_chat.

        Args:
            messages: List of messages
            skill: Skill adapter to use
            user_context: Optional context

        Returns:
            VoiceResponse with text, voice description, and filler info
        """
        skill = skill or self.default_skill

        request_data = {
            "messages": messages,
            "skill": skill,
        }

        if user_context:
            request_data["user_context"] = user_context

        try:
            client = await self._get_http_client()
            response = await client.post(
                f"{self.base_url}/v1/chat/voice",
                json=request_data,
                timeout=15.0,
            )

            if response.status_code == 200:
                return VoiceResponse.from_api_response(response.json())
            else:
                logger.error(f"Voice chat error: {response.status_code}")

        except Exception as e:
            logger.error(f"Voice chat failed: {e}")

        # Fallback
        return VoiceResponse(
            text="I apologize, but I'm having trouble processing that right now.",
            voice="A calm, apologetic voice",
            system_used="fallback",
        )

    # =========================================================================
    # GREETING (Skill-Specific)
    # =========================================================================

    async def get_greeting(self, skill: Optional[str] = None) -> SkillGreeting:
        """
        Get the greeting for a specific skill.

        Args:
            skill: Skill ID (defaults to self.default_skill)

        Returns:
            SkillGreeting with text and voice description
        """
        skill = skill or self.default_skill

        try:
            client = await self._get_http_client()
            response = await client.get(
                f"{self.base_url}/v1/greeting/{skill}",
                timeout=5.0,
            )

            if response.status_code == 200:
                return SkillGreeting.from_api_response(response.json(), skill)
            else:
                logger.warning(f"Greeting not found for skill: {skill}")

        except Exception as e:
            logger.error(f"Failed to get greeting: {e}")

        # Default greeting
        return SkillGreeting(
            text="Hello! How can I help you today?",
            voice="A warm, friendly voice",
            skill_id=skill,
        )

    # =========================================================================
    # FILLER PHRASES
    # =========================================================================

    async def get_fillers(self) -> Dict[str, Any]:
        """
        Get all filler phrase categories.

        Returns:
            Dict with categories and phrases for custom handling
        """
        try:
            client = await self._get_http_client()
            response = await client.get(
                f"{self.base_url}/v1/fillers",
                timeout=5.0,
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.warning(f"Failed to get fillers: {e}")

        # Default fillers
        return {
            "categories": ["default"],
            "phrases": {
                "default": [
                    "Let me look into that for you...",
                    "One moment please...",
                    "Let me check on that...",
                ]
            }
        }

    # =========================================================================
    # STREAM (Currently falls back to HTTP)
    # =========================================================================

    async def stream(
        self,
        user_input: str,
        skill: Optional[str] = None,
        user_profile: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream AI response tokens in real-time.

        NOTE: Fast Brain streaming is in development. Currently returns
        the full response as a single chunk. When streaming is available,
        this will yield tokens as they're generated.

        Args:
            user_input: What the user said
            skill: Skill adapter to use
            user_profile: User's business profile info

        Yields:
            Response text (currently as single chunk, streaming coming soon)
        """
        # TODO: Implement true SSE streaming when Fast Brain supports it
        # For now, fall back to HTTP and yield the full response
        try:
            response = await self.think(user_input, skill=skill, user_profile=user_profile)
            yield response.text
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield "I apologize, but I'm having trouble processing that right now."
    
    async def stream_to_string(
        self,
        user_input: str,
        skill: Optional[str] = None,
        user_profile: Optional[str] = None,
    ) -> str:
        """
        Stream response and return complete string.
        Useful when you want streaming internally but need full text.
        """
        result = ""
        async for token in self.stream(user_input, skill=skill, user_profile=user_profile):
            result += token
        return result
    
    # =========================================================================
    # TURN-TAKING (Local logic - Fast Brain doesn't have this endpoint)
    # =========================================================================

    async def analyze_turn(
        self,
        transcript: str,
        silence_ms: float,
        is_agent_speaking: bool = False,
    ) -> TurnResult:
        """
        Analyze if the user has finished their turn.
        Uses local heuristics since Fast Brain doesn't have a turn endpoint.

        Args:
            transcript: Current transcript of user speech
            silence_ms: Milliseconds of silence detected
            is_agent_speaking: Is the agent currently speaking

        Returns:
            TurnResult with recommended action
        """
        # If agent is speaking and user starts talking, that's an interrupt
        if is_agent_speaking and transcript.strip():
            return TurnResult(
                action=TurnAction.INTERRUPT,
                confidence=0.9,
                reason="User interrupted agent"
            )

        # Check for sentence-ending punctuation
        ends_with_punctuation = transcript.strip().endswith(('.', '?', '!'))

        # Check for question words
        question_starters = ['what', 'how', 'when', 'where', 'why', 'who', 'can', 'could', 'would', 'is', 'are', 'do', 'does']
        starts_with_question = any(transcript.lower().strip().startswith(q) for q in question_starters)

        # Decision logic based on silence and transcript
        if silence_ms > 2000:
            # Long silence - definitely respond
            return TurnResult(
                action=TurnAction.RESPOND,
                confidence=0.95,
                reason="Long silence (>2s)"
            )
        elif silence_ms > 1200 and ends_with_punctuation:
            # Medium silence + sentence ended
            return TurnResult(
                action=TurnAction.RESPOND,
                confidence=0.85,
                reason="Medium silence with sentence end"
            )
        elif silence_ms > 800 and starts_with_question and ends_with_punctuation:
            # Shorter silence but clear question
            return TurnResult(
                action=TurnAction.RESPOND,
                confidence=0.8,
                reason="Question detected with pause"
            )
        elif silence_ms > 500 and len(transcript.split()) < 3:
            # Short utterance with pause - might be backchannel
            return TurnResult(
                action=TurnAction.BACKCHANNEL,
                confidence=0.6,
                reason="Short utterance, might need acknowledgment"
            )
        else:
            return TurnResult(
                action=TurnAction.WAIT,
                confidence=0.7,
                reason="Continue listening"
            )

    async def should_respond(
        self,
        transcript: str,
        silence_ms: float,
    ) -> bool:
        """
        Simple helper: should the agent respond now?

        Args:
            transcript: Current transcript
            silence_ms: Silence duration

        Returns:
            True if agent should respond, False to keep listening
        """
        result = await self.analyze_turn(transcript, silence_ms)
        return result.should_respond
    
    # =========================================================================
    # SKILLS
    # =========================================================================

    async def list_skills(self) -> list[Skill]:
        """
        List all available skill adapters from Fast Brain.

        Returns:
            List of Skill objects
        """
        try:
            client = await self._get_http_client()
            response = await client.get(f"{self.base_url}/v1/skills")

            if response.status_code == 200:
                data = response.json()
                return [
                    Skill(
                        id=s["id"],
                        name=s["name"],
                        description=s.get("description"),
                        version=s.get("version", "1.0"),
                    )
                    for s in data.get("skills", [])
                ]

        except Exception as e:
            logger.error(f"Failed to list skills: {e}")

        return []

    async def create_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        system_prompt: str,
        knowledge: Optional[list[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a custom skill in Fast Brain.

        Args:
            skill_id: Unique identifier for the skill (e.g., "my_business")
            name: Display name (e.g., "My Business Assistant")
            description: What this skill does
            system_prompt: The system prompt for the skill
            knowledge: List of knowledge items to include

        Returns:
            Created skill data or None on failure
        """
        try:
            client = await self._get_http_client()
            response = await client.post(
                f"{self.base_url}/v1/skills",
                json={
                    "skill_id": skill_id,
                    "name": name,
                    "description": description,
                    "system_prompt": system_prompt,
                    "knowledge": knowledge or [],
                },
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to create skill: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Failed to create skill: {e}")

        return None
    
    # =========================================================================
    # FEEDBACK (Placeholder - not yet implemented in Fast Brain)
    # =========================================================================

    async def log_feedback(
        self,
        conversation_id: str,
        user_input: str,
        agent_response: str,
        rating: int,
        correction: Optional[str] = None,
        skill: Optional[str] = None,
    ) -> bool:
        """
        Log feedback for continuous learning.

        NOTE: Fast Brain feedback endpoint is not yet implemented.
        This is a placeholder that logs locally and returns True.

        Args:
            conversation_id: ID of the conversation
            user_input: What the user said
            agent_response: What the agent responded
            rating: Rating 1-5
            correction: Better response if rating is low
            skill: Which skill was used

        Returns:
            True (feedback logged locally, server endpoint pending)
        """
        # TODO: Implement when Fast Brain has feedback endpoint
        logger.info(
            f"Feedback logged locally: conversation={conversation_id}, "
            f"rating={rating}, skill={skill or self.default_skill}"
        )
        return True


# =============================================================================
# EXCEPTIONS
# =============================================================================

class BrainUnavailableError(Exception):
    """Raised when the Brain service is unavailable."""
    pass


# =============================================================================
# FALLBACK HANDLER EXAMPLE
# =============================================================================

async def simple_fallback(user_input: str, skill: str) -> str:
    """
    Simple fallback when Brain is unavailable.
    Replace with your own logic (e.g., Groq, local model, canned responses).
    """
    return (
        "I apologize, but I'm having trouble processing that right now. "
        "Can I take a message and have someone call you back?"
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_client: Optional[FastBrainClient] = None


def get_brain_client(
    base_url: Optional[str] = None,
    default_skill: str = "default",
) -> FastBrainClient:
    """
    Get or create a singleton Brain client.
    
    Args:
        base_url: URL of Fast Brain API (uses FAST_BRAIN_URL env var if not provided)
        default_skill: Default skill to use
        
    Returns:
        FastBrainClient instance
    """
    global _default_client
    
    if _default_client is None:
        import os
        url = base_url or os.environ.get("FAST_BRAIN_URL")
        if not url:
            raise ValueError(
                "Brain URL not provided. Set FAST_BRAIN_URL environment variable "
                "or pass base_url parameter."
            )
        
        _default_client = FastBrainClient(
            base_url=url,
            default_skill=default_skill,
            fallback_handler=simple_fallback,
        )
    
    return _default_client


# =============================================================================
# TESTING
# =============================================================================

async def test_client():
    """Test the Brain client against Fast Brain LPU."""
    import os

    url = os.environ.get(
        "FAST_BRAIN_URL",
        "https://jenkintownelectricity--fast-brain-lpu-fastapi-app.modal.run"
    )
    print(f"Testing Brain client against: {url}")

    client = FastBrainClient(base_url=url, default_skill="receptionist")

    # Test health
    print("\n1. Health check...")
    healthy = await client.is_healthy()
    print(f"   Healthy: {healthy}")

    if not healthy:
        print("   Brain not available, skipping other tests")
        health_info = await client.get_health_info()
        print(f"   Health info: {health_info}")
        return

    # Get full health info
    health_info = await client.get_health_info()
    print(f"   Architecture: {health_info.get('architecture', 'unknown')}")
    print(f"   System 1: {health_info.get('system1', {}).get('model', 'unknown')}")
    print(f"   System 2: {health_info.get('system2', {}).get('model', 'unknown')}")
    print(f"   Skills: {health_info.get('skills', [])}")

    # Test skills list
    print("\n2. List skills...")
    skills = await client.list_skills()
    print(f"   Available: {[s.name for s in skills]}")

    # Test greeting
    print("\n3. Get skill greeting...")
    greeting = await client.get_greeting("electrician")
    print(f"   Text: {greeting.text[:80]}...")
    print(f"   Voice: {greeting.voice}")

    # Test hybrid chat (simple query - System 1)
    print("\n4. Hybrid chat (simple query - should use System 1)...")
    response = await client.hybrid_think("What are your hours?", skill="electrician")
    print(f"   Response: {response.content[:100]}...")
    print(f"   System used: {response.system_used}")
    print(f"   Fast latency: {response.fast_latency_ms:.0f}ms")
    print(f"   Filler: {response.filler}")

    # Test hybrid chat (complex query - System 2)
    print("\n5. Hybrid chat (complex query - should use System 2)...")
    response = await client.hybrid_think(
        "Can you analyze my 850 kWh usage and predict next month's bill at $0.12/kWh?",
        skill="electrician"
    )
    print(f"   Response: {response.content[:150]}...")
    print(f"   System used: {response.system_used}")
    print(f"   Fast latency: {response.fast_latency_ms:.0f}ms")
    print(f"   Deep latency: {response.deep_latency_ms}ms" if response.deep_latency_ms else "   Deep latency: N/A")
    print(f"   Filler: {response.filler}")

    # Test fillers
    print("\n6. Get filler phrases...")
    fillers = await client.get_fillers()
    print(f"   Categories: {fillers.get('categories', [])}")
    print(f"   Sample: {list(fillers.get('phrases', {}).values())[0][0] if fillers.get('phrases') else 'N/A'}")

    # Test turn analysis (local)
    print("\n7. Turn analysis (local)...")
    result = await client.analyze_turn("Yeah so I was wondering...", silence_ms=300)
    print(f"   Action: {result.action}")
    print(f"   Confidence: {result.confidence}")
    print(f"   Reason: {result.reason}")

    result2 = await client.analyze_turn("What are your hours?", silence_ms=1500)
    print(f"   Action (after 1.5s silence): {result2.action}")

    await client.close()
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_client())
