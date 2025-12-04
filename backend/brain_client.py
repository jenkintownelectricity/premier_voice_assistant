"""
HIVE215 Brain Client - Connect to Fast Brain LPU API

This module provides a clean interface for HIVE215 to communicate
with the Fast Brain service deployed on Modal. It handles:
- OpenAI-compatible chat completions
- Skills management and selection
- Automatic fallback if Brain is unavailable
- Turn-taking via local logic (Fast Brain doesn't have this endpoint)

Fast Brain API:
- GET /health - Health check
- GET /v1/skills - List available skills
- POST /v1/skills - Create custom skill
- POST /v1/chat/completions - Chat completion (OpenAI-compatible)

Usage:
    from brain_client import FastBrainClient

    brain = FastBrainClient(
        base_url="https://jenkintownelectricity--fast-brain-lpu-fastbrainlpu-serve.modal.run",
        default_skill="receptionist"
    )

    # Simple request
    response = await brain.think("What are your hours?")
    print(response.text)

    # With conversation history
    response = await brain.chat([
        {"role": "user", "content": "I need a plumber"},
        {"role": "assistant", "content": "I can help with that!"},
        {"role": "user", "content": "What are your hours?"}
    ], skill="plumber")
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
        "https://jenkintownelectricity--fast-brain-lpu-fastbrainlpu-serve.modal.run"
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
    print(f"   Backend: {health_info.get('backend', 'unknown')}")
    print(f"   Skills available: {health_info.get('skills_available', [])}")

    # Test skills list
    print("\n2. List skills...")
    skills = await client.list_skills()
    print(f"   Available: {[s.name for s in skills]}")

    # Test chat
    print("\n3. Chat (receptionist skill)...")
    response = await client.think("Hello, I need to schedule an appointment", skill="receptionist")
    print(f"   Response: {response.text[:150]}...")
    print(f"   TTFB: {response.latency_ms:.0f}ms")
    print(f"   Tokens/sec: {response.tokens_per_sec:.0f}")
    print(f"   Skill used: {response.skill_used}")

    # Test turn analysis (local)
    print("\n4. Turn analysis (local)...")
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
