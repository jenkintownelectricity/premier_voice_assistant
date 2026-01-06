"""
Voice Agent - Integrated Voice AI with Context-Aware Latency Masking and Turn-Taking

This module combines:
1. LatencyMasker - Context-aware filler sounds while waiting for LLM response
   - Acoustic (<200ms): "Hmm...", "Uh-huh..." (Immediate reaction)
   - Process (2s+): "Running the estimate...", "Checking the calendar..." (Justifies delay)
2. TurnManager - State-of-the-art turn-taking for natural conversation flow

Usage:
    from worker.voice_agent import VoiceAgent

    agent = VoiceAgent(skill_type="electrician")

    # In your voice pipeline, wrap LLM generation with context-aware latency masking
    async for chunk in agent.generate(user_input, llm, context="calculation"):
        send_to_tts(chunk)  # "Running those numbers..." while LLM thinks
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
        context: str = "general",
    ) -> AsyncGenerator[str, None]:
        """
        Generate a response with context-aware latency masking.

        This wraps the LLM generation to add natural, context-aware fillers
        while waiting for the LLM to respond, creating a more conversational feel.

        Args:
            user_input: The user's input text
            llm_generator: Async generator that yields LLM response chunks
            use_latency_masking: Whether to add filler sounds
            context: Context for filler selection. Options:
                     "general", "technical", "scheduling", "calculation",
                     "sales", "customer_service", "electrician", "plumber",
                     "solar", "lawyer"

        Yields:
            Response chunks (including fillers if enabled)

        Example:
            # For a calculation query, use context="calculation"
            # Agent will say "Running those numbers..." instead of "Hmm..."
            async for chunk in agent.generate(query, llm_stream, context="calculation"):
                send_to_tts(chunk)
        """
        self._last_user_input = user_input
        self._is_speaking = True

        try:
            if use_latency_masking:
                # Wrap with context-aware latency masking
                async for chunk in self.latency_masker.mask_latency(
                    llm_generator, context=context
                ):
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
        context: str = "general",
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat completion with context-aware latency masking.

        This is the recommended method for integrating with LLM chat APIs.
        It automatically wraps the LLM call with context-aware latency masking.

        Args:
            messages: List of message dicts (role, content)
            llm: LLM client with a chat() method that returns an async generator
            use_latency_masking: Whether to add filler sounds
            context: Context for filler selection. Options:
                     "general", "technical", "scheduling", "calculation",
                     "sales", "customer_service", "electrician", "plumber",
                     "solar", "lawyer"

        Yields:
            Response chunks (including fillers if enabled)

        Example:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "How much will this cost?"}
            ]

            # Use context="calculation" for estimate queries
            async for chunk in agent.chat(messages, llm, context="calculation"):
                print(chunk, end="", flush=True)
                # Output: "Running those numbers... The total comes to $1,500."
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

        # Wrap with context-aware latency masking
        if use_latency_masking:
            stream = self.latency_masker.mask_latency(stream, context=context)

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
            skill_type: One of:
                - "general" - Generic fillers
                - "technical" - Construction/roofing specs
                - "scheduling" - Calendar/CRM operations
                - "calculation" - Math/estimates
                - "sales" - Sales/negotiation
                - "customer_service" - Empathetic responses
                - "electrician" - Electrical codes/specs
                - "plumber" - Plumbing calculations
                - "solar" - Solar panel estimates
                - "lawyer" - Legal intake
        """
        self.latency_masker.skill_type = skill_type
        logger.info(f"VoiceAgent skill type changed to: {skill_type}")

    # =========================================================================
    # IRON EAR V3 - HONEY POT METHODS
    # =========================================================================

    def start_honeypot(self):
        """
        Start the Honey Pot calibration phase for speaker verification.

        Call this when asking the user a question designed to elicit
        a longer response (e.g., "Could you state your name and reason for calling?")

        The system will collect ~10 seconds of speech to create a voice fingerprint,
        then use it to filter out background voices/imposters.
        """
        self.turn_manager.start_honeypot()
        logger.info("[Iron Ear] Honey Pot sequence started")

    def get_honeypot_prompt(self, skill_type: Optional[str] = None) -> str:
        """
        Get the appropriate Honey Pot prompt for the current skill.

        Args:
            skill_type: Override the default skill type

        Returns:
            A prompt designed to elicit a ~10-15 second response
        """
        from .identity_manager import get_honeypot_prompt
        skill = skill_type or getattr(self.latency_masker, 'skill_type', 'default')
        return get_honeypot_prompt(skill)

    @property
    def is_identity_calibrated(self) -> bool:
        """Check if speaker identity has been locked."""
        return self.turn_manager.is_identity_calibrated()

    @property
    def calibration_progress(self) -> float:
        """Get identity calibration progress (0-1)."""
        return self.turn_manager.get_calibration_progress()

    def check_connection_quality(self) -> Optional[str]:
        """
        Check if the audio environment is too noisy.

        Returns:
            A prompt asking user to improve audio quality, or None if OK

        Example:
            quality_prompt = agent.check_connection_quality()
            if quality_prompt:
                yield quality_prompt  # "Are you on speakerphone?"
        """
        return self.turn_manager.check_connection_quality()

    def get_identity_stats(self) -> Optional[dict]:
        """Get identity verification statistics for debugging."""
        return self.turn_manager.get_identity_stats()

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
    context: str = "general",
) -> AsyncGenerator[str, None]:
    """
    Quick helper to add context-aware latency masking to any LLM stream.

    Usage:
        # Basic usage
        async for chunk in create_masked_stream(llm.chat(messages)):
            print(chunk, end="")

        # With context for domain-specific fillers
        async for chunk in create_masked_stream(llm.chat(messages), context="calculation"):
            print(chunk, end="")  # "Running those numbers... $1,500 total."
    """
    masker = LatencyMasker(skill_type=skill_type)
    async for chunk in masker.mask_latency(llm_stream, context=context):
        yield chunk
