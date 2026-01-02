"""
Skill Registry - Central management for all HIVE215 skills.

This module provides:
1. A registry of all available skills
2. Methods to sync skills with Fast Brain
3. Skill lookup and routing capabilities
"""

import asyncio
import logging
from typing import Optional, Union

from .base import SkillDefinition
from .receptionist import RECEPTIONIST_SKILL
from .electrician import ELECTRICIAN_SKILL
from .plumber import PLUMBER_SKILL
from .lawyer import LAWYER_SKILL
from .solar import SOLAR_SKILL
from .tara_sales import TARA_SALES_SKILL, SKILL_ID as TARA_SKILL_ID

logger = logging.getLogger(__name__)


# =============================================================================
# SKILL CONVERSION
# =============================================================================

def _ensure_skill_definition(skill: Union[SkillDefinition, dict]) -> SkillDefinition:
    """Convert dict to SkillDefinition if needed."""
    if isinstance(skill, SkillDefinition):
        return skill
    # Convert dict to SkillDefinition
    return SkillDefinition(
        skill_id=skill.get("skill_id"),
        name=skill.get("name"),
        description=skill.get("description", ""),
        system_prompt=skill.get("system_prompt", ""),
        knowledge=skill.get("knowledge", []),
    )


# Convert TARA_SALES_SKILL dict to SkillDefinition
TARA_SKILL_DEF = _ensure_skill_definition(TARA_SALES_SKILL)


# =============================================================================
# SKILL REGISTRY
# =============================================================================

# All available skills indexed by skill_id
ALL_SKILLS: dict[str, SkillDefinition] = {
    "receptionist": RECEPTIONIST_SKILL,
    "electrician": ELECTRICIAN_SKILL,
    "plumber": PLUMBER_SKILL,
    "lawyer": LAWYER_SKILL,
    "solar": SOLAR_SKILL,
    "tara-sales": TARA_SKILL_DEF,
}

# Default skill when none specified
DEFAULT_SKILL_ID = "receptionist"

# Skill routing keywords for automatic detection
SKILL_KEYWORDS: dict[str, list[str]] = {
    "electrician": [
        "electrical", "electric", "wiring", "outlet", "breaker", "panel",
        "circuit", "power outage", "lights", "switch", "voltage", "fuse",
        "ev charger", "generator", "rewire"
    ],
    "plumber": [
        "plumbing", "plumber", "pipe", "leak", "drain", "clog", "toilet",
        "faucet", "water heater", "shower", "sink", "sewer", "backup",
        "flood", "water pressure", "garbage disposal"
    ],
    "lawyer": [
        "lawyer", "attorney", "legal", "lawsuit", "sue", "court", "case",
        "accident", "injury", "divorce", "custody", "will", "estate",
        "contract", "wrongful", "discrimination"
    ],
    "solar": [
        "solar", "panel", "energy", "electric bill", "renewable", "green",
        "sunlight", "photovoltaic", "inverter", "battery backup", "powerwall",
        "net metering", "tax credit"
    ],
    "tara-sales": [
        "tara", "dash", "thedashtool", "demo", "crm", "sales tool",
        "pipeline", "sales automation"
    ],
}


class SkillRegistry:
    """
    Central registry for managing HIVE215 skills.

    Provides:
    - Skill lookup by ID
    - Automatic skill detection from user input
    - Sync with Fast Brain API
    """

    def __init__(self):
        self.skills = ALL_SKILLS.copy()
        self.default_skill_id = DEFAULT_SKILL_ID
        self._brain_client = None

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        """Get a skill by ID."""
        return self.skills.get(skill_id)

    def get_all_skills(self) -> list[SkillDefinition]:
        """Get all registered skills."""
        return list(self.skills.values())

    def get_skill_ids(self) -> list[str]:
        """Get all registered skill IDs."""
        return list(self.skills.keys())

    def detect_skill(self, user_input: str) -> str:
        """
        Detect the appropriate skill based on user input.

        Uses keyword matching to determine which skill should handle
        the user's request. Falls back to default skill.

        Args:
            user_input: The user's message

        Returns:
            skill_id of the best matching skill
        """
        input_lower = user_input.lower()

        # Score each skill based on keyword matches
        scores: dict[str, int] = {}
        for skill_id, keywords in SKILL_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > 0:
                scores[skill_id] = score

        if scores:
            # Return skill with highest score
            return max(scores.items(), key=lambda x: x[1])[0]

        # No keywords matched, use default
        return self.default_skill_id

    async def sync_with_fast_brain(self, brain_client) -> dict[str, bool]:
        """
        Sync all skills with Fast Brain.

        Args:
            brain_client: FastBrainClient instance

        Returns:
            Dict mapping skill_id to success status
        """
        results = {}

        for skill_id, skill in self.skills.items():
            try:
                logger.info(f"Syncing skill: {skill_id}")
                result = await brain_client.create_skill(**skill.to_dict())
                results[skill_id] = result is not None
                if result:
                    logger.info(f"  ✓ {skill_id} synced successfully")
                else:
                    logger.warning(f"  ✗ {skill_id} failed to sync")
            except Exception as e:
                logger.error(f"  ✗ {skill_id} error: {e}")
                results[skill_id] = False

        return results

    async def verify_skills_on_fast_brain(self, brain_client) -> dict[str, bool]:
        """
        Verify which skills exist on Fast Brain.

        Args:
            brain_client: FastBrainClient instance

        Returns:
            Dict mapping skill_id to exists status
        """
        try:
            remote_skills = await brain_client.list_skills()
            remote_ids = {s.id for s in remote_skills}

            return {
                skill_id: skill_id in remote_ids
                for skill_id in self.skills.keys()
            }
        except Exception as e:
            logger.error(f"Failed to verify skills: {e}")
            return {skill_id: False for skill_id in self.skills.keys()}


# Global registry instance
registry = SkillRegistry()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_skill(skill_id: str) -> Optional[SkillDefinition]:
    """Get a skill by ID."""
    return registry.get_skill(skill_id)


def get_all_skills() -> list[SkillDefinition]:
    """Get all registered skills."""
    return registry.get_all_skills()


def get_skill_ids() -> list[str]:
    """Get all registered skill IDs."""
    return registry.get_skill_ids()


def detect_skill(user_input: str) -> str:
    """Detect the appropriate skill based on user input."""
    return registry.detect_skill(user_input)


async def sync_all_skills(brain_client) -> dict[str, bool]:
    """Sync all skills with Fast Brain."""
    return await registry.sync_with_fast_brain(brain_client)
