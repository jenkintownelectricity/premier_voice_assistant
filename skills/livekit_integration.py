"""
LiveKit Integration for Multi-Skill Agent

This module provides integration between the MultiSkillAgent and LiveKit's
voice agent system. It can be used to create a BrainLLM wrapper that
supports dynamic skill switching.

Usage in livekit_agent.py:

    from skills.livekit_integration import create_multi_skill_brain_llm

    # Instead of:
    #   brain_llm = BrainLLM(brain_client, skill=assistant_skill)
    # Use:
    brain_llm = await create_multi_skill_brain_llm(
        brain_client,
        skills=["receptionist", "electrician", "plumber"],
        primary_skill="receptionist",
        room=room,  # For publishing skill switch events
    )
"""

import logging
from typing import Optional, List, Dict, Any, Callable, Awaitable

from .multi_skill_agent import MultiSkillAgent, SkillSwitch
from .registry import get_skill_ids

logger = logging.getLogger(__name__)


class MultiSkillBrainLLM:
    """
    BrainLLM wrapper that supports dynamic multi-skill switching.

    This wraps the MultiSkillAgent to provide a BrainLLM-compatible
    interface for LiveKit while enabling dynamic skill switching.
    """

    def __init__(
        self,
        brain_client,
        skills: List[str],
        primary_skill: str = None,
        user_context: Optional[Dict[str, Any]] = None,
        room=None,  # LiveKit room for publishing events
        announce_switch: bool = True,
    ):
        """
        Initialize multi-skill BrainLLM.

        Args:
            brain_client: FastBrainClient instance
            skills: List of skill IDs to use
            primary_skill: Default skill
            user_context: User context dict
            room: LiveKit room for publishing skill switch events
            announce_switch: Whether to announce skill transitions
        """
        self.brain = brain_client
        self._room = room
        self._model_name = "fast-brain-hybrid-multi"

        # Create multi-skill agent
        self.agent = MultiSkillAgent(
            brain_client=brain_client,
            skills=skills,
            primary_skill=primary_skill or (skills[0] if skills else "receptionist"),
            auto_switch=True,
            announce_switch=announce_switch,
            on_skill_switch=self._on_skill_switch,
        )

        self.user_context = user_context or {}
        self._greeting_cache = {}

    @property
    def skill(self) -> str:
        """Current active skill."""
        return self.agent.current_skill

    @property
    def skills(self) -> List[str]:
        """Available skills."""
        return self.agent.available_skills

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "fast-brain-multi"

    def set_room(self, room):
        """Set LiveKit room for event publishing."""
        self._room = room

    async def _on_skill_switch(self, switch: SkillSwitch):
        """Handle skill switch events."""
        logger.info(
            f"Skill switch: {switch.from_skill} → {switch.to_skill} "
            f"(confidence: {switch.confidence:.2f})"
        )

        # Publish to LiveKit room if available
        if self._room:
            try:
                import json
                await self._room.local_participant.publish_data(
                    json.dumps({
                        "type": "skill_switch",
                        "from_skill": switch.from_skill,
                        "to_skill": switch.to_skill,
                        "confidence": switch.confidence,
                        "transition": switch.transition_phrase,
                    }).encode(),
                    topic="skill_events",
                )
            except Exception as e:
                logger.warning(f"Failed to publish skill switch event: {e}")

    def set_skill(self, skill: str) -> bool:
        """
        Manually switch to a specific skill.

        Args:
            skill: Skill ID to switch to

        Returns:
            True if switch successful
        """
        return self.agent.set_skill(skill)

    def set_user_context(self, context: Dict[str, Any]):
        """Update user context."""
        self.user_context.update(context)

    async def analyze_and_maybe_switch(self, user_input: str) -> Optional[SkillSwitch]:
        """
        Analyze user input and switch skills if needed.

        Args:
            user_input: User's message

        Returns:
            SkillSwitch if a switch occurred, None otherwise
        """
        _, switch = await self.agent.process_input(user_input)
        return switch

    async def get_greeting(self, skill: str = None) -> str:
        """Get greeting for current or specified skill."""
        skill = skill or self.skill

        if skill in self._greeting_cache:
            return self._greeting_cache[skill]

        try:
            greeting = await self.brain.get_greeting(skill)
            self._greeting_cache[skill] = greeting.text
            return greeting.text
        except Exception as e:
            logger.warning(f"Failed to get greeting for {skill}: {e}")
            return "Hello! How can I help you today?"

    async def chat(self, user_input: str) -> tuple[str, str, Optional[str]]:
        """
        Chat with auto skill switching.

        Args:
            user_input: User's message

        Returns:
            Tuple of (response_text, skill_used, transition_phrase or None)
        """
        return await self.agent.chat(user_input)

    def get_status(self) -> dict:
        """Get agent status for debugging."""
        return self.agent.get_status()

    async def aclose(self):
        """Cleanup resources."""
        if self.brain:
            await self.brain.close()


async def create_multi_skill_brain_llm(
    brain_client,
    skills: List[str] = None,
    primary_skill: str = None,
    user_context: Dict[str, Any] = None,
    room=None,
    announce_switch: bool = True,
) -> MultiSkillBrainLLM:
    """
    Factory function to create a multi-skill BrainLLM.

    Args:
        brain_client: FastBrainClient instance
        skills: List of skill IDs (defaults to all available)
        primary_skill: Default skill (defaults to first skill)
        user_context: User context dict
        room: LiveKit room for events
        announce_switch: Announce skill transitions

    Returns:
        Configured MultiSkillBrainLLM
    """
    # Default to all available skills if not specified
    if not skills:
        skills = get_skill_ids()

    return MultiSkillBrainLLM(
        brain_client=brain_client,
        skills=skills,
        primary_skill=primary_skill,
        user_context=user_context,
        room=room,
        announce_switch=announce_switch,
    )


async def load_assistant_skills(
    supabase_client,
    assistant_id: str,
) -> tuple[List[str], str, bool, bool]:
    """
    Load multi-skill configuration from database.

    Args:
        supabase_client: Supabase client
        assistant_id: Assistant UUID

    Returns:
        Tuple of (skills[], primary_skill, auto_switch, announce_switch)
    """
    try:
        result = supabase_client.table("va_assistants").select(
            "skills, primary_skill, auto_switch_skills, announce_skill_switch, fast_brain_skill"
        ).eq("id", assistant_id).single().execute()

        if result.data:
            # Get skills array or fall back to single skill
            skills = result.data.get("skills") or [
                result.data.get("fast_brain_skill", "default")
            ]

            # Get primary skill
            primary = result.data.get("primary_skill") or (
                result.data.get("fast_brain_skill") or
                (skills[0] if skills else "default")
            )

            # Get flags with defaults
            auto_switch = result.data.get("auto_switch_skills", True)
            announce = result.data.get("announce_skill_switch", True)

            return skills, primary, auto_switch, announce

    except Exception as e:
        logger.warning(f"Failed to load assistant skills: {e}")

    # Default fallback
    return ["default"], "default", True, True
