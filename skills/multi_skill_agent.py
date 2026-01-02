"""
Multi-Skill Agent - Dynamic skill orchestration for voice assistants.

This module enables an assistant to use MULTIPLE skills dynamically,
switching between them based on conversation context.

Example: A receptionist assistant with 3 skills:
- receptionist (default, handles routing)
- electrician (for electrical inquiries)
- plumber (for plumbing inquiries)

The agent detects when to switch and handles transitions smoothly.

Usage:
    from skills.multi_skill_agent import MultiSkillAgent

    # Create agent with multiple skills
    agent = MultiSkillAgent(
        brain_client=brain_client,
        skills=["receptionist", "electrician", "plumber"],
        primary_skill="receptionist",
    )

    # Process user input - automatically routes to correct skill
    response, skill_used = await agent.process("I have a wiring issue")
    # skill_used = "electrician"
"""

import logging
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, field

from .registry import get_skill, get_skill_ids
from .router import SkillRouter, SkillSwitch, TRANSITION_PHRASES

logger = logging.getLogger(__name__)


@dataclass
class MultiSkillConfig:
    """Configuration for multi-skill agent."""
    skills: list[str]                    # List of skill IDs this agent can use
    primary_skill: str                   # Default/fallback skill
    auto_switch: bool = True             # Automatically switch skills based on context
    switch_threshold: float = 0.6        # Confidence threshold for auto-switching
    announce_switch: bool = True         # Announce skill transitions to caller
    max_switches_per_call: int = 5       # Prevent excessive switching


@dataclass
class SkillContext:
    """Tracks skill usage during a conversation."""
    current_skill: str
    switch_count: int = 0
    skill_history: list[str] = field(default_factory=list)

    def record_switch(self, new_skill: str):
        """Record a skill switch."""
        self.skill_history.append(self.current_skill)
        self.current_skill = new_skill
        self.switch_count += 1


class MultiSkillAgent:
    """
    Agent that can dynamically switch between multiple skills.

    This wraps a BrainLLM or FastBrainClient and adds:
    - Multi-skill assignment
    - Automatic skill detection from user input
    - Smooth skill transitions with announcements
    - Skill usage tracking
    """

    def __init__(
        self,
        brain_client,
        skills: list[str],
        primary_skill: str = None,
        auto_switch: bool = True,
        switch_threshold: float = 0.6,
        announce_switch: bool = True,
        on_skill_switch: Optional[Callable[[SkillSwitch], Awaitable[None]]] = None,
    ):
        """
        Initialize multi-skill agent.

        Args:
            brain_client: FastBrainClient instance
            skills: List of skill IDs this agent can use
            primary_skill: Default skill (first in list if not specified)
            auto_switch: Enable automatic skill switching
            switch_threshold: Confidence threshold for switching (0-1)
            announce_switch: Announce transitions to caller
            on_skill_switch: Callback when skill switches
        """
        # Validate skills
        valid_skills = get_skill_ids()
        for skill_id in skills:
            if skill_id not in valid_skills:
                logger.warning(f"Skill '{skill_id}' not in registry. Available: {valid_skills}")

        self.brain = brain_client
        self.skills = skills
        self.primary_skill = primary_skill or (skills[0] if skills else "receptionist")
        self.config = MultiSkillConfig(
            skills=skills,
            primary_skill=self.primary_skill,
            auto_switch=auto_switch,
            switch_threshold=switch_threshold,
            announce_switch=announce_switch,
        )

        # Initialize router with only our assigned skills
        self.router = SkillRouter(
            default_skill=self.primary_skill,
            switch_threshold=switch_threshold,
            on_skill_switch=on_skill_switch,
        )

        # Limit router to only our skills
        self._filter_router_keywords()

        # Track conversation context
        self.context = SkillContext(current_skill=self.primary_skill)
        self._on_skill_switch = on_skill_switch

    def _filter_router_keywords(self):
        """Limit router to only detect our assigned skills."""
        from .registry import SKILL_KEYWORDS

        # Create filtered keyword map
        self._skill_keywords = {
            skill_id: keywords
            for skill_id, keywords in SKILL_KEYWORDS.items()
            if skill_id in self.skills
        }

    @property
    def current_skill(self) -> str:
        """Get current active skill."""
        return self.context.current_skill

    @property
    def available_skills(self) -> list[str]:
        """Get list of available skills for this agent."""
        return self.skills.copy()

    def analyze_input(self, user_input: str) -> SkillSwitch:
        """
        Analyze user input to determine if skill switch is needed.

        Args:
            user_input: The user's message

        Returns:
            SkillSwitch with decision and details
        """
        # Score only our assigned skills
        input_lower = user_input.lower()
        scores = {}

        for skill_id, keywords in self._skill_keywords.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > 0:
                scores[skill_id] = score

        if not scores:
            return SkillSwitch(
                should_switch=False,
                from_skill=self.current_skill,
                to_skill=self.current_skill,
                confidence=0.0,
                reason="No matching keywords for assigned skills",
            )

        # Get best match
        best_skill, best_score = max(scores.items(), key=lambda x: x[1])

        # Calculate confidence
        max_possible = max(len(kws) for kws in self._skill_keywords.values()) if self._skill_keywords else 1
        confidence = min(best_score / max_possible, 1.0)

        # Check if switch warranted
        should_switch = (
            best_skill != self.current_skill and
            confidence >= self.config.switch_threshold and
            self.context.switch_count < self.config.max_switches_per_call
        )

        # Get transition phrase
        transition = None
        if should_switch:
            transition = TRANSITION_PHRASES.get(
                (self.current_skill, best_skill),
                f"Let me connect you with our {best_skill} specialist."
            )

        return SkillSwitch(
            should_switch=should_switch,
            from_skill=self.current_skill,
            to_skill=best_skill if should_switch else self.current_skill,
            confidence=confidence,
            reason=f"Matched {best_score} keywords for {best_skill}",
            transition_phrase=transition,
        )

    async def process_input(
        self,
        user_input: str,
        force_skill: str = None,
    ) -> tuple[str, Optional[SkillSwitch]]:
        """
        Process user input, potentially switching skills.

        Args:
            user_input: The user's message
            force_skill: Force a specific skill (bypasses auto-detection)

        Returns:
            Tuple of (skill_id to use, SkillSwitch if switch occurred)
        """
        # Force skill if specified
        if force_skill and force_skill in self.skills:
            if force_skill != self.current_skill:
                old_skill = self.current_skill
                self.context.record_switch(force_skill)

                switch = SkillSwitch(
                    should_switch=True,
                    from_skill=old_skill,
                    to_skill=force_skill,
                    confidence=1.0,
                    reason="Forced skill switch",
                    transition_phrase=TRANSITION_PHRASES.get(
                        (old_skill, force_skill),
                        f"Switching to {force_skill}."
                    ),
                )

                if self._on_skill_switch:
                    await self._on_skill_switch(switch)

                return force_skill, switch

            return force_skill, None

        # Auto-detect if enabled
        if self.config.auto_switch:
            switch = self.analyze_input(user_input)

            if switch.should_switch:
                self.context.record_switch(switch.to_skill)
                logger.info(
                    f"MultiSkillAgent: {switch.from_skill} → {switch.to_skill} "
                    f"(confidence: {switch.confidence:.2f})"
                )

                if self._on_skill_switch:
                    await self._on_skill_switch(switch)

                return switch.to_skill, switch

        return self.current_skill, None

    async def chat(
        self,
        user_input: str,
        force_skill: str = None,
    ) -> tuple[str, str, Optional[str]]:
        """
        Send message to brain with appropriate skill.

        Args:
            user_input: The user's message
            force_skill: Force a specific skill

        Returns:
            Tuple of (response_text, skill_used, transition_phrase or None)
        """
        skill_to_use, switch = await self.process_input(user_input, force_skill)

        # Update brain client skill
        if hasattr(self.brain, 'default_skill'):
            self.brain.default_skill = skill_to_use

        # Get response from brain
        try:
            response = await self.brain.think(user_input, skill=skill_to_use)
            response_text = response.text
        except Exception as e:
            logger.error(f"MultiSkillAgent chat error: {e}")
            response_text = "I'm sorry, I'm having trouble processing that. Could you repeat?"

        # Return transition phrase if we switched
        transition = switch.transition_phrase if switch and self.config.announce_switch else None

        return response_text, skill_to_use, transition

    def set_skill(self, skill_id: str) -> bool:
        """
        Manually set the current skill.

        Args:
            skill_id: Skill to switch to

        Returns:
            True if switch was successful
        """
        if skill_id not in self.skills:
            logger.warning(f"Cannot switch to '{skill_id}' - not in assigned skills: {self.skills}")
            return False

        if skill_id != self.current_skill:
            self.context.record_switch(skill_id)
            logger.info(f"Manual skill switch: {self.context.skill_history[-1]} → {skill_id}")

        return True

    def reset(self):
        """Reset agent to initial state."""
        self.context = SkillContext(current_skill=self.primary_skill)
        self.router.reset()

    def get_status(self) -> dict:
        """Get agent status for debugging."""
        return {
            "current_skill": self.current_skill,
            "available_skills": self.skills,
            "primary_skill": self.primary_skill,
            "switch_count": self.context.switch_count,
            "skill_history": self.context.skill_history,
            "auto_switch": self.config.auto_switch,
            "max_switches": self.config.max_switches_per_call,
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_multi_skill_agent(
    brain_client,
    skills: list[str],
    primary_skill: str = None,
    **kwargs,
) -> MultiSkillAgent:
    """
    Create a multi-skill agent with the specified skills.

    Args:
        brain_client: FastBrainClient instance
        skills: List of skill IDs (e.g., ["receptionist", "electrician", "plumber"])
        primary_skill: Default skill (uses first skill if not specified)
        **kwargs: Additional config options

    Returns:
        Configured MultiSkillAgent
    """
    return MultiSkillAgent(
        brain_client=brain_client,
        skills=skills,
        primary_skill=primary_skill,
        **kwargs,
    )


def create_receptionist_trio(brain_client) -> MultiSkillAgent:
    """
    Create a receptionist with electrician and plumber skills.

    Common configuration for trade service businesses.
    """
    return create_multi_skill_agent(
        brain_client=brain_client,
        skills=["receptionist", "electrician", "plumber"],
        primary_skill="receptionist",
        announce_switch=True,
    )


def create_legal_intake_agent(brain_client) -> MultiSkillAgent:
    """
    Create a legal intake agent with receptionist fallback.
    """
    return create_multi_skill_agent(
        brain_client=brain_client,
        skills=["receptionist", "lawyer"],
        primary_skill="lawyer",
        announce_switch=True,
    )


def create_solar_sales_agent(brain_client) -> MultiSkillAgent:
    """
    Create a solar sales agent with receptionist fallback.
    """
    return create_multi_skill_agent(
        brain_client=brain_client,
        skills=["receptionist", "solar"],
        primary_skill="solar",
        announce_switch=True,
    )
