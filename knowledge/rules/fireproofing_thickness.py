"""
Fireproofing thickness selection logic.

Provides thickness lookup rules by member type, fire rating, system type,
and W/D ratio. References real UL design numbers with representative
thickness values for structural steel fireproofing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from knowledge.rules.engine import RuleCategory, Severity, ValidationRule


# ---------------------------------------------------------------------------
# Thickness lookup data model
# ---------------------------------------------------------------------------

@dataclass
class ThicknessLookup:
    """Fireproofing thickness requirement for a specific configuration.

    Attributes:
        member_type:        Structural member category (W-beam, HSS column, pipe, deck).
        member_size:        Specific member size (e.g., "W10x49", "HSS 6x6").
        fire_rating:        Required rating (1hr, 1.5hr, 2hr, 3hr, 4hr).
        system_type:        Fireproofing system (SFRM standard, SFRM high-density, intumescent).
        ul_design_number:   UL Fire Resistance Directory design number.
        required_thickness_inches:  Minimum thickness per UL listing.
        wd_ratio:           W/D or A/P ratio for the member (if applicable).
        notes:              Additional application notes.
    """
    member_type: str
    member_size: str
    fire_rating: str
    system_type: str
    ul_design_number: str
    required_thickness_inches: float
    wd_ratio: Optional[float] = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Thickness lookup table (representative values from UL directory)
# ---------------------------------------------------------------------------

THICKNESS_TABLE: List[ThicknessLookup] = [
    # --- W-beams / SFRM standard ---
    ThicknessLookup(
        member_type="W-beam",
        member_size="W10x49",
        fire_rating="2hr",
        system_type="SFRM standard",
        ul_design_number="D916",
        required_thickness_inches=1.0625,  # 1-1/16"
        wd_ratio=1.06,
        notes="Restrained assembly. W/D >= 0.78 for this thickness.",
    ),
    ThicknessLookup(
        member_type="W-beam",
        member_size="W12x26",
        fire_rating="2hr",
        system_type="SFRM standard",
        ul_design_number="D916",
        required_thickness_inches=1.3125,  # 1-5/16"
        wd_ratio=0.62,
        notes="Restrained assembly. Lighter beam requires more SFRM.",
    ),
    ThicknessLookup(
        member_type="W-beam",
        member_size="W16x40",
        fire_rating="1hr",
        system_type="SFRM standard",
        ul_design_number="D916",
        required_thickness_inches=0.5625,  # 9/16"
        wd_ratio=0.82,
        notes="Restrained assembly, 1-hour rating.",
    ),
    ThicknessLookup(
        member_type="W-beam",
        member_size="W24x76",
        fire_rating="3hr",
        system_type="SFRM standard",
        ul_design_number="D916",
        required_thickness_inches=1.5625,  # 1-9/16"
        wd_ratio=1.27,
        notes="Restrained assembly, 3-hour rating.",
    ),

    # --- W-columns / SFRM standard ---
    ThicknessLookup(
        member_type="W-column",
        member_size="W14x90",
        fire_rating="2hr",
        system_type="SFRM standard",
        ul_design_number="X772",
        required_thickness_inches=0.875,  # 7/8"
        wd_ratio=1.67,
        notes="Column application. W/D >= 1.20 for this thickness.",
    ),
    ThicknessLookup(
        member_type="W-column",
        member_size="W14x90",
        fire_rating="3hr",
        system_type="SFRM standard",
        ul_design_number="X772",
        required_thickness_inches=1.375,  # 1-3/8"
        wd_ratio=1.67,
        notes="Column application, 3-hour rating.",
    ),
    ThicknessLookup(
        member_type="W-column",
        member_size="W10x49",
        fire_rating="2hr",
        system_type="SFRM standard",
        ul_design_number="X772",
        required_thickness_inches=1.125,  # 1-1/8"
        wd_ratio=1.06,
        notes="Lighter column requires more SFRM.",
    ),

    # --- HSS columns / intumescent ---
    ThicknessLookup(
        member_type="HSS column",
        member_size="HSS 6x6x3/8",
        fire_rating="2hr",
        system_type="intumescent",
        ul_design_number="X631",
        required_thickness_inches=0.0,  # Varies by product (DFT specified by mfr)
        wd_ratio=None,
        notes=(
            "Intumescent coating thickness (DFT) varies by manufacturer product. "
            "Consult specific product UL listing for exact DFT at A/P ratio. "
            "Typical range: 200-500 mils DFT for 2-hour HSS."
        ),
    ),
    ThicknessLookup(
        member_type="HSS column",
        member_size="HSS 8x8x1/2",
        fire_rating="1hr",
        system_type="intumescent",
        ul_design_number="X631",
        required_thickness_inches=0.0,
        wd_ratio=None,
        notes=(
            "Intumescent coating for 1-hour HSS column. DFT per manufacturer "
            "product listing. Typical range: 80-200 mils DFT."
        ),
    ),

    # --- SFRM high-density ---
    ThicknessLookup(
        member_type="W-column",
        member_size="W14x90",
        fire_rating="2hr",
        system_type="SFRM high-density",
        ul_design_number="X772",
        required_thickness_inches=0.625,  # 5/8"
        wd_ratio=1.67,
        notes=(
            "High-density SFRM (>= 22 pcf) allows reduced thickness vs. "
            "standard density. Used in high-traffic/impact areas."
        ),
    ),

    # --- Steel deck ---
    ThicknessLookup(
        member_type="steel deck",
        member_size="20 ga composite deck",
        fire_rating="2hr",
        system_type="SFRM standard",
        ul_design_number="D916",
        required_thickness_inches=0.5,  # 1/2" at flutes
        wd_ratio=None,
        notes=(
            "Restrained assembly. Thickness measured at deck flutes. "
            "Per UL D916 for composite steel deck with concrete topping."
        ),
    ),
    ThicknessLookup(
        member_type="steel deck",
        member_size="18 ga composite deck",
        fire_rating="1hr",
        system_type="SFRM standard",
        ul_design_number="D916",
        required_thickness_inches=0.375,  # 3/8"
        wd_ratio=None,
        notes="Restrained assembly, 1-hour deck rating.",
    ),

    # --- Pipe ---
    ThicknessLookup(
        member_type="pipe",
        member_size='4" Schedule 40 steel pipe',
        fire_rating="2hr",
        system_type="SFRM standard",
        ul_design_number="X772",
        required_thickness_inches=1.5,  # 1-1/2"
        wd_ratio=None,
        notes="Pipe column application. Smaller diameter = more SFRM.",
    ),
]


# ---------------------------------------------------------------------------
# Evaluation callables
# ---------------------------------------------------------------------------

def _thickness_meets_requirement(ctx: Dict[str, Any]) -> bool:
    """Verify applied fireproofing thickness meets the UL listing requirement.

    Looks up the requirement from THICKNESS_TABLE based on member_type,
    member_size, fire_rating, and system_type. If no matching entry exists,
    falls back to explicit required_thickness_inches in context.
    """
    member_type = ctx.get("member_type", "")
    member_size = ctx.get("member_size", "")
    fire_rating = ctx.get("fire_rating", "")
    system_type = ctx.get("system_type", "")
    applied_thickness = ctx.get("applied_thickness_inches", 0.0)

    # Try to find a matching entry in the lookup table
    required = None
    for entry in THICKNESS_TABLE:
        if (
            entry.member_type.lower() == member_type.lower()
            and entry.member_size.lower() == member_size.lower()
            and entry.fire_rating.lower() == fire_rating.lower()
            and entry.system_type.lower() == system_type.lower()
        ):
            required = entry.required_thickness_inches
            break

    # Fallback to explicit context value
    if required is None:
        required = ctx.get("required_thickness_inches", None)

    if required is None:
        return False  # No matching lookup and no explicit requirement = fail-closed

    if required == 0.0:
        # Intumescent with product-specific DFT: cannot validate without mfr data
        return False  # Fail-closed: needs manufacturer-specific lookup

    return applied_thickness >= required


def _ul_design_referenced(ctx: Dict[str, Any]) -> bool:
    """Every fireproofing specification must cite a UL design number."""
    ul_design = ctx.get("ul_design_number", "")
    return bool(ul_design and ul_design.strip())


def _wd_ratio_validated(ctx: Dict[str, Any]) -> bool:
    """Verify the W/D ratio used for thickness selection is correct.

    The W/D (weight-to-heated-perimeter) ratio determines the required
    SFRM thickness. A wrong W/D ratio leads to wrong thickness.
    """
    stated_wd = ctx.get("stated_wd_ratio", None)
    calculated_wd = ctx.get("calculated_wd_ratio", None)

    if stated_wd is None or calculated_wd is None:
        return False  # Fail-closed: cannot verify without both values

    # Allow 5% tolerance for rounding
    tolerance = 0.05
    if abs(stated_wd - calculated_wd) / max(calculated_wd, 0.01) > tolerance:
        return False
    return True


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

FIREPROOFING_THICKNESS_RULES: List[ValidationRule] = [
    ValidationRule(
        rule_id="FP-THICK-001",
        rule_version="1.0.0",
        rule_source="UL Fire Resistance Directory (D916, X772, X631)",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Fireproofing is applied to a structural member with a fire rating.",
        required_inputs=[
            "member_type", "member_size", "fire_rating",
            "system_type", "applied_thickness_inches",
        ],
        evaluation_logic=_thickness_meets_requirement,
        pass_criteria="Applied fireproofing thickness meets or exceeds UL design requirement.",
        fail_criteria=(
            "Applied thickness is below UL listing minimum for the member/rating combination."
        ),
        fail_closed_behavior=(
            "Rule fails when thickness data or lookup parameters are missing. "
            "Cannot verify fire rating compliance without complete data."
        ),
        escalation_behavior="Always escalate -- insufficient thickness voids fire rating.",
        error_message_template=(
            "FP-THICK-001 FAIL: Applied fireproofing on {member_size} ({member_type}) "
            "for {fire_rating} rating using {system_type} does not meet UL requirement. "
            "Applied: {applied_thickness_inches}in."
        ),
    ),

    ValidationRule(
        rule_id="FP-THICK-002",
        rule_version="1.0.0",
        rule_source="IBC 703.2 / UL Fire Resistance Directory",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Fireproofing thickness is specified for a member.",
        required_inputs=["ul_design_number"],
        evaluation_logic=_ul_design_referenced,
        pass_criteria="Fireproofing specification cites a valid UL design number.",
        fail_criteria="No UL design number referenced. Cannot verify thickness requirement.",
        fail_closed_behavior="Rule fails when UL design number is missing.",
        escalation_behavior="Always escalate -- thickness without UL reference is unverifiable.",
        error_message_template=(
            "FP-THICK-002 FAIL: No UL design number referenced for fireproofing. "
            "Every thickness specification must cite the applicable UL design "
            "(e.g., D916 for beams, X772 for columns)."
        ),
    ),

    ValidationRule(
        rule_id="FP-THICK-003",
        rule_version="1.0.0",
        rule_source="UL Fire Resistance Directory - W/D Ratio Method",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.WARNING,
        trigger_condition="SFRM thickness is determined by W/D ratio method.",
        required_inputs=["stated_wd_ratio", "calculated_wd_ratio"],
        evaluation_logic=_wd_ratio_validated,
        pass_criteria="Stated W/D ratio matches calculated W/D ratio within 5% tolerance.",
        fail_criteria="Stated W/D ratio does not match calculated value. Thickness may be wrong.",
        fail_closed_behavior=(
            "Rule fails when W/D ratio data is missing. Cannot verify thickness "
            "selection without both stated and calculated W/D values."
        ),
        escalation_behavior=(
            "Escalate to fire protection engineer -- incorrect W/D ratio leads "
            "to incorrect thickness and compromised fire rating."
        ),
        error_message_template=(
            "FP-THICK-003 FAIL: Stated W/D ratio ({stated_wd_ratio}) does not "
            "match calculated W/D ratio ({calculated_wd_ratio}). Verify member "
            "properties and recalculate required thickness."
        ),
    ),
]
