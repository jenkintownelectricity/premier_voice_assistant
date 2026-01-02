"""
HIVE215 Skills Package

Custom skills for the Fast Brain LLM. Each skill defines a persona,
system prompt, and knowledge base for specific use cases.

Available Skills:
- receptionist: General business receptionist for routing calls
- electrician: Electrical service expertise
- plumber: Plumbing service expertise
- lawyer: Legal intake specialist
- solar: Solar panel sales and consultation
- tara-sales: Tara's Sales Assistant for TheDashTool demos

Usage:
    from skills import get_skill, get_all_skills, detect_skill

    # Get a specific skill
    skill = get_skill("electrician")

    # Get all skills
    all_skills = get_all_skills()

    # Auto-detect skill from user input
    skill_id = detect_skill("I need help with my wiring")  # Returns "electrician"

    # Sync all skills with Fast Brain
    from skills import sync_all_skills
    from backend.brain_client import FastBrainClient

    client = FastBrainClient(base_url=FAST_BRAIN_URL)
    results = await sync_all_skills(client)
"""

# Base classes
from .base import SkillDefinition, create_skill

# Individual skills
from .receptionist import RECEPTIONIST_SKILL, SKILL_ID as RECEPTIONIST_ID
from .electrician import ELECTRICIAN_SKILL, SKILL_ID as ELECTRICIAN_ID
from .plumber import PLUMBER_SKILL, SKILL_ID as PLUMBER_ID
from .lawyer import LAWYER_SKILL, SKILL_ID as LAWYER_ID
from .solar import SOLAR_SKILL, SKILL_ID as SOLAR_ID
from .tara_sales import TARA_SALES_SKILL, SKILL_ID as TARA_SKILL_ID, create_tara_skill

# Registry and utilities
from .registry import (
    registry,
    get_skill,
    get_all_skills,
    get_skill_ids,
    detect_skill,
    sync_all_skills,
    ALL_SKILLS,
    DEFAULT_SKILL_ID,
    SKILL_KEYWORDS,
)

# Skill router for dynamic switching
from .router import (
    SkillRouter,
    SkillSwitch,
    router as skill_router,
    analyze_for_switch,
    route_input,
    get_transition_phrase,
    TRANSITION_PHRASES,
)

# Multi-skill agent for dynamic skill orchestration
from .multi_skill_agent import (
    MultiSkillAgent,
    MultiSkillConfig,
    SkillContext,
    create_multi_skill_agent,
    create_receptionist_trio,
    create_legal_intake_agent,
    create_solar_sales_agent,
)

# LiveKit integration for voice agents
from .livekit_integration import (
    MultiSkillBrainLLM,
    create_multi_skill_brain_llm,
    load_assistant_skills,
)

__all__ = [
    # Base
    "SkillDefinition",
    "create_skill",
    # Individual skills
    "RECEPTIONIST_SKILL",
    "ELECTRICIAN_SKILL",
    "PLUMBER_SKILL",
    "LAWYER_SKILL",
    "SOLAR_SKILL",
    "TARA_SALES_SKILL",
    # Skill IDs
    "RECEPTIONIST_ID",
    "ELECTRICIAN_ID",
    "PLUMBER_ID",
    "LAWYER_ID",
    "SOLAR_ID",
    "TARA_SKILL_ID",
    # Registry
    "registry",
    "get_skill",
    "get_all_skills",
    "get_skill_ids",
    "detect_skill",
    "sync_all_skills",
    "ALL_SKILLS",
    "DEFAULT_SKILL_ID",
    "SKILL_KEYWORDS",
    # Router
    "SkillRouter",
    "SkillSwitch",
    "skill_router",
    "analyze_for_switch",
    "route_input",
    "get_transition_phrase",
    "TRANSITION_PHRASES",
    # Multi-Skill Agent
    "MultiSkillAgent",
    "MultiSkillConfig",
    "SkillContext",
    "create_multi_skill_agent",
    "create_receptionist_trio",
    "create_legal_intake_agent",
    "create_solar_sales_agent",
    # LiveKit Integration
    "MultiSkillBrainLLM",
    "create_multi_skill_brain_llm",
    "load_assistant_skills",
    # Legacy
    "create_tara_skill",
]
