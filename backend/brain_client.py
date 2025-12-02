"""
HIVE215 Brain Client - Connect to Fast Brain API

This module provides a clean interface for HIVE215 to communicate
with the Fast Brain service. It handles:
- HTTP requests for simple think operations
- WebSocket streaming for low-latency responses
- Turn-taking signals
- Feedback logging for continuous learning
- Automatic fallback if Brain is unavailable

Usage:
    from brain_client import FastBrainClient
    
    brain = FastBrainClient(
        base_url="https://your-username--fast-brain-api-fastapi-app.modal.run",
        default_skill="plumber"
    )
    
    # Simple request
    response = await brain.think("What are your hours?")
    print(response.text)
    
    # Streaming for lowest latency
    async for token in brain.stream("I have a leak"):
        print(token, end="", flush=True)
    
    # Turn-taking
    should_respond = await brain.should_respond(transcript, silence_ms=500)
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
    """Response from the Brain's think endpoint."""
    text: str
    confidence: float
    tokens_used: int
    latency_ms: float
    skill_used: str
    
    @classmethod
    def from_dict(cls, data: dict) -> "ThinkResponse":
        return cls(
            text=data.get("response", ""),
            confidence=data.get("confidence", 0.0),
            tokens_used=data.get("tokens_used", 0),
            latency_ms=data.get("latency_ms", 0.0),
            skill_used=data.get("skill_used", "unknown"),
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
                f"{self.base_url}/api/v1/health",
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                self._is_healthy = data.get("status") == "healthy"
            else:
                self._is_healthy = False
                
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self._is_healthy = False
        
        self._last_health_check = now
        return self._is_healthy
    
    # =========================================================================
    # THINK (HTTP)
    # =========================================================================
    
    async def think(
        self,
        user_input: str,
        skill: Optional[str] = None,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 256,
    ) -> ThinkResponse:
        """
        Get AI response for user input.
        
        Args:
            user_input: What the user said
            skill: Skill adapter to use (defaults to self.default_skill)
            conversation_id: ID to track conversation
            context: Additional context (caller info, etc.)
            max_tokens: Maximum response length
            
        Returns:
            ThinkResponse with the AI's response
            
        Raises:
            BrainUnavailableError: If Brain is down and no fallback
        """
        skill = skill or self.default_skill
        
        request_data = {
            "user_input": user_input,
            "skill": skill,
            "conversation_id": conversation_id,
            "context": context,
            "max_tokens": max_tokens,
        }
        
        for attempt in range(self.max_retries):
            try:
                client = await self._get_http_client()
                response = await client.post(
                    f"{self.base_url}/api/v1/think",
                    json=request_data,
                )
                
                if response.status_code == 200:
                    return ThinkResponse.from_dict(response.json())
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
            fallback_response = await self.fallback_handler(user_input, skill)
            return ThinkResponse(
                text=fallback_response,
                confidence=0.5,
                tokens_used=0,
                latency_ms=0,
                skill_used="fallback",
            )
        
        raise BrainUnavailableError("Brain service unavailable and no fallback configured")
    
    # =========================================================================
    # STREAM (WebSocket)
    # =========================================================================
    
    async def stream(
        self,
        user_input: str,
        skill: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream AI response tokens in real-time.
        Lowest latency option for voice applications.
        
        Args:
            user_input: What the user said
            skill: Skill adapter to use
            
        Yields:
            Individual tokens as they're generated
        """
        skill = skill or self.default_skill
        
        async with self._ws_lock:
            try:
                async with websockets.connect(
                    f"{self.ws_url}/api/v1/stream",
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    # Send request
                    await ws.send(json.dumps({
                        "type": "think",
                        "text": user_input,
                        "skill": skill,
                    }))
                    
                    # Receive tokens
                    while True:
                        message = await ws.recv()
                        data = json.loads(message)
                        
                        if data["type"] == "token":
                            yield data["text"]
                        elif data["type"] == "done":
                            break
                        elif data["type"] == "error":
                            logger.error(f"Stream error: {data.get('message')}")
                            break
                            
            except ConnectionClosed as e:
                logger.warning(f"WebSocket closed: {e}")
            except Exception as e:
                logger.error(f"Stream error: {e}")
    
    async def stream_to_string(
        self,
        user_input: str,
        skill: Optional[str] = None,
    ) -> str:
        """
        Stream response and return complete string.
        Useful when you want streaming internally but need full text.
        """
        result = ""
        async for token in self.stream(user_input, skill):
            result += token
        return result
    
    # =========================================================================
    # TURN-TAKING
    # =========================================================================
    
    async def analyze_turn(
        self,
        transcript: str,
        silence_ms: float,
        is_agent_speaking: bool = False,
    ) -> TurnResult:
        """
        Analyze if the user has finished their turn.
        
        Args:
            transcript: Current transcript of user speech
            silence_ms: Milliseconds of silence detected
            is_agent_speaking: Is the agent currently speaking
            
        Returns:
            TurnResult with recommended action
        """
        try:
            client = await self._get_http_client()
            response = await client.post(
                f"{self.base_url}/api/v1/turn",
                json={
                    "transcript": transcript,
                    "silence_ms": silence_ms,
                    "is_agent_speaking": is_agent_speaking,
                },
                timeout=2.0,  # Fast timeout for turn-taking
            )
            
            if response.status_code == 200:
                data = response.json()
                return TurnResult(
                    action=TurnAction(data["action"]),
                    confidence=data["confidence"],
                    reason=data["reason"],
                )
                
        except Exception as e:
            logger.warning(f"Turn analysis failed: {e}")
        
        # Default to simple silence-based detection
        if silence_ms > 1500:
            return TurnResult(
                action=TurnAction.RESPOND,
                confidence=0.7,
                reason="Fallback: long silence"
            )
        return TurnResult(
            action=TurnAction.WAIT,
            confidence=0.5,
            reason="Fallback: default wait"
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
        List all available skill adapters.
        
        Returns:
            List of Skill objects
        """
        try:
            client = await self._get_http_client()
            response = await client.get(f"{self.base_url}/api/v1/skills")
            
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
    
    # =========================================================================
    # FEEDBACK
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
        
        Args:
            conversation_id: ID of the conversation
            user_input: What the user said
            agent_response: What the agent responded
            rating: Rating 1-5
            correction: Better response if rating is low
            skill: Which skill was used
            
        Returns:
            True if feedback was logged successfully
        """
        try:
            client = await self._get_http_client()
            response = await client.post(
                f"{self.base_url}/api/v1/feedback",
                json={
                    "conversation_id": conversation_id,
                    "user_input": user_input,
                    "agent_response": agent_response,
                    "rating": rating,
                    "correction": correction,
                    "skill": skill or self.default_skill,
                },
            )
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Failed to log feedback: {e}")
            return False


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
    """Test the Brain client."""
    import os
    
    url = os.environ.get("FAST_BRAIN_URL", "http://localhost:8000")
    print(f"Testing Brain client against: {url}")
    
    client = FastBrainClient(base_url=url)
    
    # Test health
    print("\n1. Health check...")
    healthy = await client.is_healthy()
    print(f"   Healthy: {healthy}")
    
    if not healthy:
        print("   Brain not available, skipping other tests")
        return
    
    # Test think
    print("\n2. Think...")
    response = await client.think("What are your hours?", skill="plumber")
    print(f"   Response: {response.text[:100]}...")
    print(f"   Latency: {response.latency_ms:.0f}ms")
    
    # Test turn
    print("\n3. Turn analysis...")
    result = await client.analyze_turn("Yeah so I was wondering...", silence_ms=300)
    print(f"   Action: {result.action}")
    print(f"   Reason: {result.reason}")
    
    # Test skills
    print("\n4. List skills...")
    skills = await client.list_skills()
    print(f"   Available: {[s.name for s in skills]}")
    
    await client.close()
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_client())
