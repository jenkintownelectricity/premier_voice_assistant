"""
Voice Agent - Integrated Voice AI with Latency Masking and Turn-Taking

This module combines:
1. LatencyMasker - Natural filler sounds while waiting for LLM response
2. TurnManager - State-of-the-art turn-taking for natural conversation flow

Usage:
    from worker.voice_agent import VoiceAgent

    agent = VoiceAgent()

    # In your voice pipeline, wrap LLM generation with latency masking
    async for chunk in agent.generate(user_input, llm):
        send_to_tts(chunk)
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any, Callable

# Import the transplanted voice features
from .latency_manager import LatencyMasker
from .turn_taking import TurnManager, TurnState, TurnConfig

logger = logging.getLogger(__name__)


class VoiceAgent:
    """
    Voice Agent with integrated latency masking and turn-taking.

    This agent wraps LLM calls with natural filler sounds ("Hmm...", "Let me think...")
    and manages conversation turn-taking for natural dialogue flow.

    Attributes:
        latency_masker: Generates fillers during LLM wait times
        turn_manager: Manages conversation state and turn-taking
    """

    def __init__(
        self,
        skill_type: Optional[str] = None,
        turn_config: Optional[TurnConfig] = None,
    ):
        """
        Initialize the Voice Agent.

        Args:
            skill_type: Type of skill for domain-specific fillers
                       (e.g., "technical", "customer_service", "sales")
            turn_config: Configuration for turn-taking behavior
        """
        # Initialize latency masker with optional skill-specific fillers
        self.latency_masker = LatencyMasker(skill_type=skill_type)

        # Initialize turn manager for natural conversation flow
        self.turn_manager = TurnManager(config=turn_config)

        # Conversation state
        self._is_speaking = False
        self._last_user_input = ""

        logger.info(f"VoiceAgent initialized (skill_type={skill_type})")

    async def generate(
        self,
        user_input: str,
        llm_generator: AsyncGenerator[str, None],
        use_latency_masking: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a response with latency masking.

        This wraps the LLM generation to add natural fillers like "Hmm..."
        while waiting for the LLM to respond, creating a more conversational feel.

        Args:
            user_input: The user's input text
            llm_generator: Async generator that yields LLM response chunks
            use_latency_masking: Whether to add filler sounds

        Yields:
            Response chunks (including fillers if enabled)
        """
        self._last_user_input = user_input
        self._is_speaking = True

        try:
            if use_latency_masking:
                # Wrap with latency masking - adds "Hmm..." while waiting
                async for chunk in self.latency_masker.mask_latency(llm_generator):
                    yield chunk
            else:
                # Pass through without modification
                async for chunk in llm_generator:
                    yield chunk
        finally:
            self._is_speaking = False

    async def chat(
        self,
        messages: list,
        llm: Any,
        use_latency_masking: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat completion with latency masking.

        This is the recommended method for integrating with LLM chat APIs.
        It automatically wraps the LLM call with latency masking.

        Args:
            messages: List of message dicts (role, content)
            llm: LLM client with a chat() method that returns an async generator
            use_latency_masking: Whether to add filler sounds

        Yields:
            Response chunks (including fillers if enabled)

        Example:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ]

            async for chunk in agent.chat(messages, llm):
                print(chunk, end="", flush=True)
        """
        # Get the LLM stream
        if hasattr(llm, 'chat'):
            stream = llm.chat(messages)
        elif hasattr(llm, 'generate'):
            # Fallback for generate-style APIs
            prompt = messages[-1].get("content", "") if messages else ""
            stream = llm.generate(prompt)
        else:
            raise ValueError("LLM must have either chat() or generate() method")

        # Wrap with latency masking
        if use_latency_masking:
            stream = self.latency_masker.mask_latency(stream)

        async for chunk in stream:
            yield chunk

    def process_audio_frame(
        self,
        is_speech: bool,
        transcript: str = "",
        energy: float = 0.0,
    ) -> TurnState:
        """
        Process an audio frame through the turn manager.

        This should be called for each audio frame to track conversation state.

        Args:
            is_speech: Whether VAD detected speech in this frame
            transcript: Current transcript text (can be partial)
            energy: Audio energy level (0-1)

        Returns:
            Current TurnState
        """
        return self.turn_manager.process(
            is_speech=is_speech,
            transcript=transcript,
            energy=energy,
        )

    def start_agent_turn(self, utterance: str = ""):
        """Call when agent starts speaking."""
        self.turn_manager.start_agent_turn(utterance)
        self._is_speaking = True

    def finish_agent_turn(self):
        """Call when agent finishes speaking."""
        self.turn_manager.finish_agent_turn()
        self._is_speaking = False

    @property
    def current_state(self) -> TurnState:
        """Get the current turn state."""
        return self.turn_manager.state

    @property
    def is_user_done(self) -> bool:
        """Check if user has finished their turn."""
        return self.turn_manager.state == TurnState.USER_DONE

    @property
    def was_interrupted(self) -> bool:
        """Check if agent was interrupted by user."""
        return self.turn_manager.state == TurnState.AGENT_INTERRUPTED

    def set_skill_type(self, skill_type: str):
        """
        Change the skill type for domain-specific fillers.

        Args:
            skill_type: One of "technical", "customer_service", "scheduling", "sales"
        """
        self.latency_masker.skill_type = skill_type
        logger.info(f"VoiceAgent skill type changed to: {skill_type}")

    def reset(self):
        """Reset the agent state for a new conversation."""
        self.turn_manager.reset()
        self.latency_masker.fillers_used = []
        self._is_speaking = False
        self._last_user_input = ""
        logger.info("VoiceAgent state reset")


# Convenience function for quick integration
async def create_masked_stream(
    llm_stream: AsyncGenerator[str, None],
    skill_type: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Quick helper to add latency masking to any LLM stream.

    Usage:
        async for chunk in create_masked_stream(llm.chat(messages)):
            print(chunk, end="")
    """
    masker = LatencyMasker(skill_type=skill_type)
    async for chunk in masker.mask_latency(llm_stream):
        yield chunk
