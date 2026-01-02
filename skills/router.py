"""
Skill Router - Dynamic skill switching for voice agents.

This module provides intelligent skill routing that can:
1. Detect when a user needs a different skill
2. Smoothly transition between skills mid-conversation
3. Maintain conversation context across skill switches

Integration with Voice Agent:
    The SkillRouter can be used as a sub-agent that monitors
    conversations and triggers skill switches when appropriate.
"""

import logging
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass

from .registry import registry, detect_skill, get_skill, SKILL_KEYWORDS

logger = logging.getLogger(__name__)


@dataclass
class SkillSwitch:
    """Represents a skill switch decision."""
    should_switch: bool
    from_skill: str
    to_skill: str
    confidence: float
    reason: str
    transition_phrase: Optional[str] = None


# Transition phrases for smooth skill handoffs
TRANSITION_PHRASES = {
    # From receptionist to specialists
    ("receptionist", "electrician"): "Let me connect you with our electrical specialist.",
    ("receptionist", "plumber"): "I'll transfer you to our plumbing expert.",
    ("receptionist", "lawyer"): "Let me connect you with our legal intake team.",
    ("receptionist", "solar"): "I'll connect you with our solar consultant.",
    # Between specialists
    ("electrician", "plumber"): "That sounds more like a plumbing issue. Let me get our plumber on the line.",
    ("plumber", "electrician"): "That might be an electrical issue. Let me connect you with our electrician.",
    # Back to receptionist
    ("electrician", "receptionist"): "Let me transfer you back to our main line.",
    ("plumber", "receptionist"): "Let me transfer you back to our main line.",
    ("lawyer", "receptionist"): "Let me transfer you back to our main line.",
    ("solar", "receptionist"): "Let me transfer you back to our main line.",
}


class SkillRouter:
    """
    Routes conversations to appropriate skills dynamically.

    Can be used as:
    1. A pre-processor to determine initial skill
    2. A monitor that triggers mid-conversation skill switches
    3. An integration point for the voice agent's BrainLLM
    """

    def __init__(
        self,
        default_skill: str = "receptionist",
        switch_threshold: float = 0.6,
        on_skill_switch: Optional[Callable[[SkillSwitch], Awaitable[None]]] = None,
    ):
        """
        Initialize the skill router.

        Args:
            default_skill: Skill to use when no clear match
            switch_threshold: Minimum confidence to trigger switch (0-1)
            on_skill_switch: Callback when skill switch is triggered
        """
        self.default_skill = default_skill
        self.switch_threshold = switch_threshold
        self.on_skill_switch = on_skill_switch
        self.current_skill = default_skill
        self._conversation_context = []

    def analyze_for_switch(
        self,
        user_input: str,
        current_skill: Optional[str] = None,
    ) -> SkillSwitch:
        """
        Analyze if user input warrants a skill switch.

        Args:
            user_input: The user's latest message
            current_skill: Override current skill (uses self.current_skill if None)

        Returns:
            SkillSwitch with decision and details
        """
        current = current_skill or self.current_skill
        detected = self._score_skills(user_input)

        if not detected:
            return SkillSwitch(
                should_switch=False,
                from_skill=current,
                to_skill=current,
                confidence=0.0,
                reason="No skill keywords detected",
            )

        # Get best match
        best_skill, best_score = max(detected.items(), key=lambda x: x[1])

        # Calculate confidence (normalize score)
        max_possible = max(len(kws) for kws in SKILL_KEYWORDS.values())
        confidence = min(best_score / max_possible, 1.0)

        # Check if switch is warranted
        should_switch = (
            best_skill != current and
            confidence >= self.switch_threshold
        )

        # Get transition phrase
        transition = None
        if should_switch:
            transition = TRANSITION_PHRASES.get(
                (current, best_skill),
                f"Let me connect you with our {best_skill} specialist."
            )

        return SkillSwitch(
            should_switch=should_switch,
            from_skill=current,
            to_skill=best_skill if should_switch else current,
            confidence=confidence,
            reason=f"Matched {best_score} keywords for {best_skill}",
            transition_phrase=transition,
        )

    def _score_skills(self, text: str) -> dict[str, int]:
        """Score each skill based on keyword matches."""
        text_lower = text.lower()
        scores = {}

        for skill_id, keywords in SKILL_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[skill_id] = score

        return scores

    async def process_input(
        self,
        user_input: str,
        current_skill: Optional[str] = None,
    ) -> tuple[str, Optional[SkillSwitch]]:
        """
        Process user input and potentially switch skills.

        Args:
            user_input: The user's message
            current_skill: Override current skill

        Returns:
            Tuple of (skill_id to use, SkillSwitch if switch occurred)
        """
        switch = self.analyze_for_switch(user_input, current_skill)

        if switch.should_switch:
            self.current_skill = switch.to_skill
            logger.info(
                f"Skill switch: {switch.from_skill} → {switch.to_skill} "
                f"(confidence: {switch.confidence:.2f})"
            )

            # Call callback if registered
            if self.on_skill_switch:
                await self.on_skill_switch(switch)

            return switch.to_skill, switch

        return switch.from_skill, None

    def get_routing_prompt(self) -> str:
        """
        Get a system prompt addition for skill routing.

        This can be prepended to the skill's system prompt to enable
        the LLM to detect when routing is needed.
        """
        skills_list = "\n".join(
            f"- {sid}: {get_skill(sid).description}"
            for sid in registry.get_skill_ids()
        )

        return f"""You are also a skill router. If the caller's request is better
handled by a different skill, indicate this by saying:
"Let me connect you with our [specialist type] who can better help with that."

Available skills:
{skills_list}

Current skill: {self.current_skill}
"""

    def reset(self):
        """Reset router to default state."""
        self.current_skill = self.default_skill
        self._conversation_context = []


# Global router instance
router = SkillRouter()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def analyze_for_switch(user_input: str, current_skill: str = None) -> SkillSwitch:
    """Analyze if input warrants a skill switch."""
    return router.analyze_for_switch(user_input, current_skill)


async def route_input(user_input: str, current_skill: str = None) -> tuple[str, Optional[SkillSwitch]]:
    """Process input and return skill to use."""
    return await router.process_input(user_input, current_skill)


def get_transition_phrase(from_skill: str, to_skill: str) -> str:
    """Get a transition phrase for skill handoff."""
    return TRANSITION_PHRASES.get(
        (from_skill, to_skill),
        f"Let me connect you with our {to_skill} specialist."
    )
