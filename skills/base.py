"""
Base Skill Definition

Provides a standard structure for all HIVE215 skills.
Each skill should inherit from this base or follow this pattern.
"""

from typing import Optional
from dataclasses import dataclass, field


@dataclass
class SkillDefinition:
    """
    Standard skill definition structure.

    All skills must have these fields to be registered with Fast Brain.
    """
    skill_id: str           # Unique identifier (e.g., "electrician")
    name: str               # Display name (e.g., "Master Electrician")
    description: str        # What this skill does
    system_prompt: str      # Full system prompt defining behavior
    knowledge: list[str] = field(default_factory=list)  # Knowledge items
    greeting: str = ""      # Optional custom greeting
    voice_description: str = "A professional, friendly voice"  # For TTS

    def to_dict(self) -> dict:
        """Convert to dictionary for API registration."""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "knowledge": self.knowledge,
        }


def create_skill(
    skill_id: str,
    name: str,
    role: str,
    company: str = "HIVE215",
    personality: str = "professional, helpful, and friendly",
    expertise: list[str] = None,
    services: list[str] = None,
    knowledge: list[str] = None,
    objection_handling: dict[str, str] = None,
    greeting: str = None,
) -> SkillDefinition:
    """
    Factory function to create a skill with common structure.

    Args:
        skill_id: Unique identifier
        name: Display name
        role: The role (e.g., "electrician", "receptionist")
        company: Company name
        personality: Personality traits
        expertise: List of expertise areas
        services: List of services offered
        knowledge: Knowledge items
        objection_handling: Common objections and responses
        greeting: Custom greeting

    Returns:
        SkillDefinition ready for registration
    """
    expertise = expertise or []
    services = services or []
    knowledge = knowledge or []
    objection_handling = objection_handling or {}

    # Build system prompt
    system_prompt = f"""You are a {role} assistant for {company}.

## Your Personality
You are {personality}. You speak naturally like a real person, not a robot.
Use conversational language, acknowledge what the caller says, and be empathetic.

## Your Role
{role.title()} specialist who helps callers with their needs.

## Your Expertise
{chr(10).join(f"- {e}" for e in expertise) if expertise else "General assistance"}

## Services You Can Help With
{chr(10).join(f"- {s}" for s in services) if services else "General inquiries"}

## Key Guidelines
1. Listen carefully to understand what the caller needs
2. Ask clarifying questions when needed
3. Provide helpful, accurate information
4. If you can't help, offer to connect them with someone who can
5. Keep responses concise for voice (1-2 sentences when possible)
6. Sound natural - use contractions, casual phrases, verbal acknowledgments

## Handling Objections
{chr(10).join(f"When they say '{k}': {v}" for k, v in objection_handling.items()) if objection_handling else "Handle objections with empathy and understanding."}

## Voice Style
Speak warmly and conversationally. Avoid reading lists. Turn information into natural dialogue.
"""

    default_greeting = f"Hi there! This is {company}, how can I help you today?"

    return SkillDefinition(
        skill_id=skill_id,
        name=name,
        description=f"{role.title()} assistant for {company}",
        system_prompt=system_prompt,
        knowledge=knowledge,
        greeting=greeting or default_greeting,
    )
