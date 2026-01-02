"""
Construction Trio - Custom skill configuration for construction/estimating AI.

This configures the MultiSkillAgent to work with your 3 Fast Brain skills:
- The Detailer: Specs, Codes & Compliance
- The Estimator: Quantities & JSON Logic
- The Eyes: Spatial Relationships & Drawing Analysis

Usage:
    from skills.construction_trio import create_construction_agent, CONSTRUCTION_KEYWORDS

    agent = create_construction_agent(brain_client)

    # Agent will auto-switch based on conversation:
    # "What's the code requirement?" → The Detailer
    # "How many do I need?" → The Estimator
    # "Look at this drawing" → The Eyes
"""

from typing import Optional
from .multi_skill_agent import MultiSkillAgent


# =============================================================================
# SKILL IDs - MATCHED TO YOUR FAST BRAIN
# =============================================================================

# Your actual Fast Brain skill IDs (from /v1/skills endpoint)
DETAILER_SKILL_ID = "the_detailer_specs"       # Specs, Codes & Compliance
ESTIMATOR_SKILL_ID = "the_estimator_quantities" # Quantities & JSON Logic
EYES_SKILL_ID = "the_eyes_spatial_analysis"     # Spatial Relationships & Drawing Analysis


# =============================================================================
# KEYWORD DETECTION - WHEN TO SWITCH SKILLS
# =============================================================================

CONSTRUCTION_KEYWORDS = {
    # The Detailer: Specs, Codes & Compliance
    # "Ingests Assembly Letters, Spec Sheets, Wind Uplift Reports, Manufacturer Details"
    # "Enforces warranty compliance, material compatibility, code requirements"
    DETAILER_SKILL_ID: [
        # Codes & Standards
        "code", "codes", "compliance", "ansi", "spri", "es-1", "asce-7", "asce",
        "fm", "ul", "astm", "ibc", "nrca", "standard", "standards",
        # Specs & Documentation
        "spec", "specs", "specification", "assembly letter", "spec sheet",
        "manufacturer", "data sheet", "submittal", "warranty",
        # Materials & Compatibility
        "material", "pvc", "tpo", "epdm", "asphalt", "modified bitumen",
        "compatibility", "compatible", "membrane", "insulation", "cover board",
        # Wind & Structural
        "wind uplift", "wind load", "uplift", "fastener", "attachment",
        "securement", "fm approved", "rated", "rating",
        # Rules & Requirements
        "requirement", "requirements", "rule", "rules", "governing",
        "detail", "details", "flashing", "termination", "edge metal",
    ],

    # The Estimator: Quantities & JSON Logic
    # "Calculate Linear Feet (LF), Square Footage (SF), Item Counts"
    # "Applies waste factors, unit conversions, bills of materials"
    ESTIMATOR_SKILL_ID: [
        # Quantities
        "quantity", "quantities", "how many", "count", "total", "amount",
        "linear feet", "lf", "square feet", "sf", "square footage",
        # Calculations
        "calculate", "calculation", "compute", "formula", "waste factor",
        "waste", "10%", "15%", "taper", "conversion", "convert",
        # Takeoffs & Estimates
        "estimate", "estimation", "takeoff", "take-off", "take off",
        "bill of materials", "bom", "materials list", "order",
        # Data & JSON
        "json", "data", "dxf", "dwg", "export", "structured",
        "millimeters", "feet", "inches", "unit", "units",
        # Costs
        "cost", "pricing", "budget", "price", "labor", "material cost",
    ],

    # The Eyes: Spatial Relationships & Drawing Analysis
    # "Cross-references Taper Plans, Arch Plans, Details"
    # "Identifies spatial conflicts (X, Y, Z axis), water flow, elevation data"
    EYES_SKILL_ID: [
        # Drawings & Plans
        "drawing", "drawings", "plan", "plans", "taper plan", "arch plan",
        "architectural", "shop drawing", "fabrication", "blueprint",
        # Visual Analysis
        "look at", "analyze", "see", "show me", "what do you see",
        "identify", "find", "locate", "check", "review", "compare",
        # Spatial
        "spatial", "conflict", "x axis", "y axis", "z axis",
        "location", "position", "layout", "orientation",
        # Elevation & Flow
        "elevation", "slope", "water flow", "drainage", "drain",
        "high point", "low point", "cricket", "saddle", "tapered",
        # Dimensions
        "dimension", "dimensions", "distance", "length", "width",
        "north", "south", "east", "west", "adjacent",
        # Design Intent vs Reality
        "design intent", "fabrication", "reality", "missing", "discrepancy",
    ],
}

# Transition phrases for smooth handoffs
CONSTRUCTION_TRANSITIONS = {
    (DETAILER_SKILL_ID, ESTIMATOR_SKILL_ID):
        "Let me switch to my estimating mode to calculate those quantities.",
    (DETAILER_SKILL_ID, EYES_SKILL_ID):
        "Let me take a look at the drawings to analyze that.",
    (ESTIMATOR_SKILL_ID, DETAILER_SKILL_ID):
        "Let me check the specs and code requirements for that.",
    (ESTIMATOR_SKILL_ID, EYES_SKILL_ID):
        "Let me look at the drawings to verify the measurements.",
    (EYES_SKILL_ID, DETAILER_SKILL_ID):
        "Based on what I see, let me check the code requirements.",
    (EYES_SKILL_ID, ESTIMATOR_SKILL_ID):
        "Now let me calculate the quantities based on what I see.",
}


# =============================================================================
# CONSTRUCTION MULTI-SKILL AGENT
# =============================================================================

class ConstructionAgent(MultiSkillAgent):
    """
    Multi-skill agent for construction/estimating work.

    Uses 3 specialized skills:
    - The Detailer: Codes, specs, compliance
    - The Estimator: Quantities, calculations, JSON
    - The Eyes: Drawing analysis, spatial relationships
    """

    def __init__(
        self,
        brain_client,
        primary_skill: str = None,
        auto_switch: bool = True,
        **kwargs
    ):
        """
        Initialize construction agent.

        Args:
            brain_client: FastBrainClient instance
            primary_skill: Default skill (defaults to Detailer)
            auto_switch: Enable automatic skill switching
        """
        skills = [DETAILER_SKILL_ID, ESTIMATOR_SKILL_ID, EYES_SKILL_ID]
        primary = primary_skill or DETAILER_SKILL_ID

        super().__init__(
            brain_client=brain_client,
            skills=skills,
            primary_skill=primary,
            auto_switch=auto_switch,
            **kwargs
        )

        # Override keywords with construction-specific ones
        self._skill_keywords = CONSTRUCTION_KEYWORDS

        # Use construction-specific transitions
        self._transitions = CONSTRUCTION_TRANSITIONS

    def _get_transition_phrase(self, from_skill: str, to_skill: str) -> str:
        """Get construction-specific transition phrase."""
        return self._transitions.get(
            (from_skill, to_skill),
            f"Let me switch to {to_skill} for that."
        )


def create_construction_agent(
    brain_client,
    primary_skill: str = None,
    auto_switch: bool = True,
) -> ConstructionAgent:
    """
    Create a construction multi-skill agent.

    Args:
        brain_client: FastBrainClient instance
        primary_skill: Default skill (Detailer, Estimator, or Eyes)
        auto_switch: Enable auto-switching based on conversation

    Returns:
        Configured ConstructionAgent

    Example:
        agent = create_construction_agent(brain_client)

        # These will auto-route to the right skill:
        await agent.chat("What's the fire rating code for this wall?")  # → Detailer
        await agent.chat("How many outlets do I need?")  # → Estimator
        await agent.chat("Look at this floor plan")  # → Eyes
    """
    return ConstructionAgent(
        brain_client=brain_client,
        primary_skill=primary_skill,
        auto_switch=auto_switch,
    )


# =============================================================================
# VERIFICATION
# =============================================================================

def verify_skills_exist(brain_client) -> dict:
    """
    Verify that the construction skills exist on Fast Brain.

    Returns:
        Dict with skill_id -> exists (bool)
    """
    import asyncio

    async def check():
        skills = await brain_client.list_skills()
        skill_ids = {s.id for s in skills}

        return {
            DETAILER_SKILL_ID: DETAILER_SKILL_ID in skill_ids,
            ESTIMATOR_SKILL_ID: ESTIMATOR_SKILL_ID in skill_ids,
            EYES_SKILL_ID: EYES_SKILL_ID in skill_ids,
        }

    return asyncio.run(check())
