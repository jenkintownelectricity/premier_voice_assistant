"""
Membrane overlap and water shedding validation rules.

Concrete ValidationRule instances covering lap direction, minimum overlap
distances by material type, base flashing height, termination bar spacing,
corner wrapping, membrane-to-AVB transitions, vertical transitions, and
curb flashing overlap requirements.
"""

from __future__ import annotations

from typing import Any, Dict, List

from knowledge.rules.engine import RuleCategory, Severity, ValidationRule


# ---------------------------------------------------------------------------
# Material-specific minimum overlap distances (inches)
# ---------------------------------------------------------------------------

MINIMUM_OVERLAPS: Dict[str, Dict[str, float]] = {
    "tpo": {"field_seam": 6.0, "t_joint": 6.0, "flashing": 6.0},
    "epdm": {"field_seam": 3.0, "t_joint": 3.0, "flashing": 3.0},   # with tape
    "pvc": {"field_seam": 6.0, "t_joint": 6.0, "flashing": 6.0},
    "mod_bit": {"field_seam": 4.0, "t_joint": 4.0, "flashing": 4.0},
}


# ---------------------------------------------------------------------------
# Helper evaluation callables
# ---------------------------------------------------------------------------

def _lap_direction_vs_slope(ctx: Dict[str, Any]) -> bool:
    """Upper sheet must overlap lower sheet (shingling downhill)."""
    laps = ctx.get("membrane_laps", [])
    for lap in laps:
        upper_elevation = lap.get("upper_edge_elevation", 0)
        lower_elevation = lap.get("lower_edge_elevation", 0)
        upper_over_lower = lap.get("upper_sheet_over_lower", False)
        if upper_elevation > lower_elevation and not upper_over_lower:
            return False
        if upper_elevation <= lower_elevation and upper_over_lower:
            # This is correct shingling -- upper sheet on the higher side laps over
            pass
    return True


def _minimum_overlap_by_material(ctx: Dict[str, Any]) -> bool:
    """Overlap distance must meet minimum for the membrane material type."""
    membrane_type = ctx.get("membrane_type", "").lower()
    laps = ctx.get("membrane_laps", [])
    minimums = MINIMUM_OVERLAPS.get(membrane_type, {})
    if not minimums:
        return False  # Unknown material = fail-closed

    for lap in laps:
        seam_type = lap.get("seam_type", "field_seam")
        actual_overlap = lap.get("overlap_inches", 0.0)
        required = minimums.get(seam_type, minimums.get("field_seam", 6.0))
        if actual_overlap < required:
            return False
    return True


def _base_flashing_min_height(ctx: Dict[str, Any]) -> bool:
    """Base flashing must extend minimum 8 inches above finished roof surface."""
    flashing_height = ctx.get("base_flashing_height_inches", 0.0)
    min_height = ctx.get("min_base_flashing_height_inches", 8.0)
    return flashing_height >= min_height


def _termination_bar_spacing(ctx: Dict[str, Any]) -> bool:
    """Termination bar fasteners must be spaced at 12 inches OC typical."""
    term_bars = ctx.get("termination_bars", [])
    for bar in term_bars:
        spacing = bar.get("fastener_spacing_inches", 0)
        max_spacing = bar.get("max_spacing_inches", 12.0)
        if spacing > max_spacing or spacing <= 0:
            return False
    return True


def _inside_corner_wrapping(ctx: Dict[str, Any]) -> bool:
    """Inside corners must have proper membrane wrapping / reinforcement.

    Inside corners require a pre-formed membrane boot or two-piece
    flashing detail to prevent bridging and stress cracking.
    """
    inside_corners = ctx.get("inside_corners", [])
    for corner in inside_corners:
        has_reinforcement = corner.get("has_corner_reinforcement", False)
        is_bridged = corner.get("membrane_bridged", True)
        if not has_reinforcement or is_bridged:
            return False
    return True


def _outside_corner_wrapping(ctx: Dict[str, Any]) -> bool:
    """Outside corners must have proper wrapping with continuous membrane coverage.

    Outside corners require membrane to wrap continuously without gaps.
    Typical detail uses a pie-cut and heat-weld overlap.
    """
    outside_corners = ctx.get("outside_corners", [])
    for corner in outside_corners:
        wrapped_continuously = corner.get("wrapped_continuously", False)
        has_coverage_gap = corner.get("has_coverage_gap", True)
        if not wrapped_continuously or has_coverage_gap:
            return False
    return True


def _membrane_to_avb_transition(ctx: Dict[str, Any]) -> bool:
    """Membrane must overlap the air/vapor barrier at transitions.

    At roof-to-wall transitions the membrane or its flashing must overlap
    the AVB by a minimum amount to maintain the air/moisture barrier
    continuity.
    """
    transitions = ctx.get("membrane_avb_transitions", [])
    for t in transitions:
        overlap = t.get("overlap_inches", 0.0)
        min_overlap = t.get("min_overlap_inches", 4.0)
        if overlap < min_overlap:
            return False
    return True


def _vertical_transition_overlap(ctx: Dict[str, Any]) -> bool:
    """Vertical transitions (wall, curb) must have proper membrane overlap."""
    transitions = ctx.get("vertical_transitions", [])
    for t in transitions:
        field_to_flashing_overlap = t.get("field_to_flashing_overlap_inches", 0.0)
        min_overlap = t.get("min_overlap_inches", 4.0)
        if field_to_flashing_overlap < min_overlap:
            return False
    return True


def _curb_flashing_overlap(ctx: Dict[str, Any]) -> bool:
    """Curb flashing must overlap field membrane and extend over curb top.

    The base flashing must extend down over the field membrane by at least
    4 inches, and the top must extend over the curb or be clamped.
    """
    curb_flashings = ctx.get("curb_flashings", [])
    for cf in curb_flashings:
        base_overlap = cf.get("base_overlap_inches", 0.0)
        extends_over_top = cf.get("extends_over_curb_top", False)
        clamped_at_top = cf.get("clamped_at_top", False)
        min_base_overlap = cf.get("min_base_overlap_inches", 4.0)
        if base_overlap < min_base_overlap:
            return False
        if not extends_over_top and not clamped_at_top:
            return False
    return True


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

MEMBRANE_RULES: List[ValidationRule] = [
    ValidationRule(
        rule_id="MEMB-001",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Membrane Lap Direction",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Membrane laps exist in the assembly.",
        required_inputs=["membrane_laps"],
        evaluation_logic=_lap_direction_vs_slope,
        pass_criteria="All membrane laps are oriented with upper sheet over lower (shingling downhill).",
        fail_criteria="One or more laps are reversed, trapping water under the seam.",
        fail_closed_behavior="Rule fails when membrane lap data is missing.",
        escalation_behavior="Always escalate -- reversed laps are a guaranteed leak.",
        error_message_template=(
            "MEMB-001 FAIL: Membrane lap direction is incorrect. Upper sheet must "
            "overlap lower sheet to shed water downhill."
        ),
    ),

    ValidationRule(
        rule_id="MEMB-002",
        rule_version="1.0.0",
        rule_source="Manufacturer Installation Guidelines / NRCA",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Membrane laps exist and material type is defined.",
        required_inputs=["membrane_type", "membrane_laps"],
        evaluation_logic=_minimum_overlap_by_material,
        pass_criteria=(
            "All membrane overlaps meet minimum distance for the material type "
            "(TPO: 6in, EPDM: 3in w/tape, PVC: 6in, Mod Bit: 4in)."
        ),
        fail_criteria="One or more overlaps are below the minimum for the material type.",
        fail_closed_behavior="Rule fails when material type or overlap data is missing.",
        escalation_behavior="Always escalate -- insufficient overlap risks seam failure.",
        error_message_template=(
            "MEMB-002 FAIL: Membrane overlap does not meet minimum for {membrane_type}. "
            "Check manufacturer requirements: TPO/PVC=6in, EPDM=3in(tape), Mod Bit=4in."
        ),
    ),

    ValidationRule(
        rule_id="MEMB-003",
        rule_version="1.0.0",
        rule_source="IBC 1503.2 / NRCA - Base Flashing Height",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Base flashing is present at a vertical transition.",
        required_inputs=["base_flashing_height_inches"],
        evaluation_logic=_base_flashing_min_height,
        pass_criteria="Base flashing extends at least 8 inches above finished roof surface.",
        fail_criteria="Base flashing height is below 8 inches (NRCA best practice).",
        fail_closed_behavior="Rule fails when base flashing height data is missing.",
        escalation_behavior="Always escalate -- low base flashing height risks water entry at wall transition.",
        error_message_template=(
            "MEMB-003 FAIL: Base flashing height of {base_flashing_height_inches}in "
            "is below the 8in NRCA recommended minimum."
        ),
    ),

    ValidationRule(
        rule_id="MEMB-004",
        rule_version="1.0.0",
        rule_source="Manufacturer Installation Guidelines - Termination Bar",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.WARNING,
        trigger_condition="Termination bars are used in the assembly.",
        required_inputs=["termination_bars"],
        evaluation_logic=_termination_bar_spacing,
        pass_criteria="Termination bar fasteners are spaced at 12 inches OC or less.",
        fail_criteria="Termination bar fastener spacing exceeds maximum.",
        fail_closed_behavior="Rule fails when termination bar data is missing.",
        escalation_behavior="Escalate if spacing exceeds 12in -- wind uplift risk at termination.",
        error_message_template=(
            "MEMB-004 FAIL: Termination bar fastener spacing exceeds maximum. "
            "Typical requirement is 12in OC. Excessive spacing risks blow-off."
        ),
    ),

    ValidationRule(
        rule_id="MEMB-005",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Inside Corner Detail",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Inside corners exist in the membrane assembly.",
        required_inputs=["inside_corners"],
        evaluation_logic=_inside_corner_wrapping,
        pass_criteria="All inside corners have proper reinforcement and no membrane bridging.",
        fail_criteria="Inside corner membrane is bridged or lacks reinforcement.",
        fail_closed_behavior="Rule fails when inside corner data is missing.",
        escalation_behavior="Always escalate -- bridged inside corners crack and leak.",
        error_message_template=(
            "MEMB-005 FAIL: Inside corner membrane is bridged or lacks reinforcement. "
            "Install pre-formed boot or two-piece flashing detail."
        ),
    ),

    ValidationRule(
        rule_id="MEMB-006",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Outside Corner Detail",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Outside corners exist in the membrane assembly.",
        required_inputs=["outside_corners"],
        evaluation_logic=_outside_corner_wrapping,
        pass_criteria="All outside corners have continuous membrane wrapping with no coverage gaps.",
        fail_criteria="Outside corner membrane has a coverage gap or is not continuously wrapped.",
        fail_closed_behavior="Rule fails when outside corner data is missing.",
        escalation_behavior="Always escalate -- gaps at outside corners are direct water entry points.",
        error_message_template=(
            "MEMB-006 FAIL: Outside corner membrane is not continuously wrapped. "
            "Use pie-cut and heat-weld overlap to ensure continuous coverage."
        ),
    ),

    ValidationRule(
        rule_id="MEMB-007",
        rule_version="1.0.0",
        rule_source="Building Enclosure Best Practice - Membrane to AVB Transition",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Membrane transitions to an air/vapor barrier.",
        required_inputs=["membrane_avb_transitions"],
        evaluation_logic=_membrane_to_avb_transition,
        pass_criteria="Membrane overlaps the AVB by the required minimum at all transitions.",
        fail_criteria="Membrane-to-AVB overlap is insufficient, breaking the air/moisture barrier plane.",
        fail_closed_behavior="Rule fails when membrane-to-AVB transition data is missing.",
        escalation_behavior="Always escalate -- break in air barrier plane causes condensation and energy loss.",
        error_message_template=(
            "MEMB-007 FAIL: Membrane-to-AVB transition overlap is below minimum. "
            "The roofing membrane must overlap the air/vapor barrier to maintain "
            "continuity of the building enclosure."
        ),
    ),

    ValidationRule(
        rule_id="MEMB-008",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Vertical Transition Details",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Vertical transitions (wall, curb, equipment) exist.",
        required_inputs=["vertical_transitions"],
        evaluation_logic=_vertical_transition_overlap,
        pass_criteria="Field membrane to flashing overlap meets minimum at all vertical transitions.",
        fail_criteria="Insufficient overlap between field membrane and vertical flashing.",
        fail_closed_behavior="Rule fails when vertical transition data is missing.",
        escalation_behavior="Always escalate -- insufficient vertical overlap leads to water entry.",
        error_message_template=(
            "MEMB-008 FAIL: Vertical transition overlap is below minimum. "
            "Field membrane must overlap base flashing by at least 4 inches."
        ),
    ),

    ValidationRule(
        rule_id="MEMB-009",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Curb Flashing Detail",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Curb flashings are present in the assembly.",
        required_inputs=["curb_flashings"],
        evaluation_logic=_curb_flashing_overlap,
        pass_criteria=(
            "Curb flashing overlaps field membrane by minimum required distance "
            "and extends over or is clamped at curb top."
        ),
        fail_criteria="Curb flashing has insufficient base overlap or does not cover curb top.",
        fail_closed_behavior="Rule fails when curb flashing data is missing.",
        escalation_behavior="Always escalate -- curb flashing failure is a common leak source.",
        error_message_template=(
            "MEMB-009 FAIL: Curb flashing does not meet overlap requirements. "
            "Base must overlap field membrane by 4in minimum. Top must extend "
            "over curb or be mechanically clamped."
        ),
    ),
]
