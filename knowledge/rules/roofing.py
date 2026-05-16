"""
Roofing domain validation rules.

Concrete ValidationRule instances covering membrane continuity, code-required
minimums, insulation support chains, and edge securement for low-slope
commercial roofing assemblies.
"""

from __future__ import annotations

from typing import Any, Dict, List

from knowledge.rules.engine import RuleCategory, Severity, ValidationRule


# ---------------------------------------------------------------------------
# Helper evaluation callables
# ---------------------------------------------------------------------------

def _membrane_continuity(ctx: Dict[str, Any]) -> bool:
    """Membrane must be continuous or properly lapped at every transition."""
    transitions = ctx.get("transitions", [])
    for t in transitions:
        if not t.get("membrane_continuous") and not t.get("properly_lapped"):
            return False
    return True


def _termination_height(ctx: Dict[str, Any]) -> bool:
    """Membrane termination must not be below minimum height."""
    min_height_inches = ctx.get("min_termination_height_inches", 4.0)
    termination_height = ctx.get("termination_height_inches", 0.0)
    return termination_height >= min_height_inches


def _base_flashing_height(ctx: Dict[str, Any]) -> bool:
    """Base flashing must meet minimum height (8in typical, 4in code min)."""
    flashing_height = ctx.get("base_flashing_height_inches", 0.0)
    code_min = ctx.get("code_min_flashing_height_inches", 4.0)
    return flashing_height >= code_min


def _overlap_direction(ctx: Dict[str, Any]) -> bool:
    """Membrane overlap must shed water downhill (upper over lower)."""
    overlaps = ctx.get("overlaps", [])
    for lap in overlaps:
        if lap.get("upper_sheet_elevation", 0) <= lap.get("lower_sheet_elevation", 0):
            # Upper sheet is not above lower at the lap
            if not lap.get("shed_direction_correct", False):
                return False
    return True


def _insulation_layer_support(ctx: Dict[str, Any]) -> bool:
    """Every insulation layer must be supported_by something (deck, other layer)."""
    layers = ctx.get("insulation_layers", [])
    for layer in layers:
        if not layer.get("supported_by"):
            return False
    return True


def _cover_board_requirement(ctx: Dict[str, Any]) -> bool:
    """Cover board required over polyiso under certain membranes."""
    insulation_type = ctx.get("top_insulation_type", "").lower()
    membrane_type = ctx.get("membrane_type", "").lower()
    has_cover_board = ctx.get("has_cover_board", False)

    if insulation_type == "polyiso" and membrane_type in ("tpo", "pvc", "epdm"):
        return has_cover_board
    return True


def _vapor_retarder_placement(ctx: Dict[str, Any]) -> bool:
    """Vapor retarder must be on the warm side of insulation."""
    vr_position = ctx.get("vapor_retarder_position", "")
    climate = ctx.get("climate_zone", "heating")  # heating or cooling

    if climate == "heating":
        # Warm side = below insulation (interior side)
        return vr_position == "below_insulation"
    elif climate == "cooling":
        # Warm side = above insulation (exterior side)
        return vr_position == "above_insulation"
    return False


def _drain_sump_depth(ctx: Dict[str, Any]) -> bool:
    """Drain sump must meet minimum depth for proper drainage."""
    sump_depth_inches = ctx.get("sump_depth_inches", 0.0)
    min_sump_depth = ctx.get("min_sump_depth_inches", 1.0)
    return sump_depth_inches >= min_sump_depth


def _minimum_slope(ctx: Dict[str, Any]) -> bool:
    """Roof slope must be at least 1/4 inch per foot."""
    slope_per_foot = ctx.get("slope_inches_per_foot", 0.0)
    min_slope = ctx.get("min_slope_inches_per_foot", 0.25)
    return slope_per_foot >= min_slope


def _edge_metal_securement(ctx: Dict[str, Any]) -> bool:
    """Edge metal must be mechanically secured per ANSI/SPRI ES-1."""
    edge_details = ctx.get("edge_details", [])
    for edge in edge_details:
        if not edge.get("mechanically_secured", False):
            return False
        if not edge.get("meets_es1", False):
            return False
    return True


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

ROOFING_RULES: List[ValidationRule] = [
    ValidationRule(
        rule_id="ROOF-001",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual, Chapter 3 - Membrane Continuity",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Assembly contains membrane transitions (wall, curb, edge, penetration).",
        required_inputs=["transitions"],
        evaluation_logic=_membrane_continuity,
        pass_criteria="Membrane is continuous or properly lapped at all transitions.",
        fail_criteria="One or more transitions lack membrane continuity or proper lapping.",
        fail_closed_behavior="Rule fails when transition data is missing. Inspect assembly transitions manually.",
        escalation_behavior="Always escalate -- membrane discontinuity is a critical leak risk.",
        error_message_template=(
            "ROOF-001 FAIL: Membrane discontinuity detected at one or more "
            "transitions. Every transition must have continuous membrane or "
            "properly lapped overlap."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-002",
        rule_version="1.0.0",
        rule_source="IBC 1503.2 - Minimum Flashing Height",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Membrane terminates at a vertical surface.",
        required_inputs=["termination_height_inches"],
        evaluation_logic=_termination_height,
        pass_criteria="Membrane termination is at or above minimum height.",
        fail_criteria="Membrane termination is below minimum height (4in code minimum).",
        fail_closed_behavior="Rule fails when termination height data is missing.",
        escalation_behavior="Always escalate -- improper termination height causes water ingress.",
        error_message_template=(
            "ROOF-002 FAIL: Membrane termination at {termination_height_inches}in "
            "is below the code minimum. IBC 1503.2 requires minimum 4in."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-003",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Base Flashing Requirements",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Base flashing is present at vertical transitions.",
        required_inputs=["base_flashing_height_inches"],
        evaluation_logic=_base_flashing_height,
        pass_criteria="Base flashing meets minimum height (8in typical, 4in code minimum).",
        fail_criteria="Base flashing below code minimum height.",
        fail_closed_behavior="Rule fails when flashing height data is missing.",
        escalation_behavior="Escalate when height is between 4in and 8in (code min vs. best practice).",
        error_message_template=(
            "ROOF-003 FAIL: Base flashing height of {base_flashing_height_inches}in "
            "does not meet minimum. Code minimum 4in, NRCA recommends 8in."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-004",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Shingle/Membrane Lap Direction",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Membrane overlaps exist in the assembly.",
        required_inputs=["overlaps"],
        evaluation_logic=_overlap_direction,
        pass_criteria="All membrane overlaps shed water downhill (upper sheet over lower).",
        fail_criteria="One or more overlaps are oriented uphill, trapping water.",
        fail_closed_behavior="Rule fails when overlap data is missing.",
        escalation_behavior="Always escalate -- reversed laps are a guaranteed leak source.",
        error_message_template=(
            "ROOF-004 FAIL: Membrane overlap direction incorrect. Upper sheet "
            "must overlap lower sheet to shed water downhill."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-005",
        rule_version="1.0.0",
        rule_source="FM Global DS 1-29 - Insulation Attachment",
        category=RuleCategory.SUPPORT,
        severity=Severity.ERROR,
        trigger_condition="Assembly contains insulation layers.",
        required_inputs=["insulation_layers"],
        evaluation_logic=_insulation_layer_support,
        pass_criteria="Every insulation layer is supported by a structural element or another layer.",
        fail_criteria="One or more insulation layers have no support defined.",
        fail_closed_behavior="Rule fails when insulation layer data is missing.",
        escalation_behavior="Escalate if support chain cannot be validated.",
        error_message_template=(
            "ROOF-005 FAIL: Insulation layer lacks a 'supported_by' "
            "reference. Every layer must be supported by deck or another layer."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-006",
        rule_version="1.0.0",
        rule_source="Manufacturer Requirements - Cover Board over Polyiso",
        category=RuleCategory.COMPATIBILITY,
        severity=Severity.WARNING,
        trigger_condition="Polyiso insulation is the top insulation layer under a single-ply membrane.",
        required_inputs=["top_insulation_type", "membrane_type", "has_cover_board"],
        evaluation_logic=_cover_board_requirement,
        pass_criteria="Cover board is present over polyiso under single-ply membrane.",
        fail_criteria="Polyiso directly under single-ply membrane without cover board.",
        fail_closed_behavior="Rule fails when insulation or membrane type data is missing.",
        escalation_behavior="Escalate to verify manufacturer warranty requirements.",
        error_message_template=(
            "ROOF-006 FAIL: Cover board required over polyiso insulation "
            "under {membrane_type} membrane. Direct contact may void warranty."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-007",
        rule_version="1.0.0",
        rule_source="ASHRAE 90.1 / Building Science - Vapor Retarder Placement",
        category=RuleCategory.SEQUENCING,
        severity=Severity.ERROR,
        trigger_condition="Assembly includes a vapor retarder.",
        required_inputs=["vapor_retarder_position", "climate_zone"],
        evaluation_logic=_vapor_retarder_placement,
        pass_criteria="Vapor retarder is on the warm side of insulation.",
        fail_criteria="Vapor retarder is on the cold side, risking interstitial condensation.",
        fail_closed_behavior="Rule fails when vapor retarder position or climate zone is missing.",
        escalation_behavior="Always escalate -- incorrect VR placement causes hidden moisture damage.",
        error_message_template=(
            "ROOF-007 FAIL: Vapor retarder at '{vapor_retarder_position}' is "
            "not on the warm side for climate zone '{climate_zone}'. "
            "Interstitial condensation risk."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-008",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Drain Sump Requirements",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.WARNING,
        trigger_condition="Assembly includes roof drains with sumps.",
        required_inputs=["sump_depth_inches"],
        evaluation_logic=_drain_sump_depth,
        pass_criteria="Drain sump depth meets or exceeds minimum.",
        fail_criteria="Drain sump is too shallow for effective drainage.",
        fail_closed_behavior="Rule fails when sump depth data is missing.",
        escalation_behavior="Escalate if sump depth is borderline.",
        error_message_template=(
            "ROOF-008 FAIL: Drain sump depth of {sump_depth_inches}in is "
            "below minimum. Typical requirement is 1in minimum."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-009",
        rule_version="1.0.0",
        rule_source="IBC 1502 / NRCA - Minimum Slope for Low-Slope Roofing",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Roof assembly has defined slope.",
        required_inputs=["slope_inches_per_foot"],
        evaluation_logic=_minimum_slope,
        pass_criteria="Roof slope is at least 1/4 inch per foot.",
        fail_criteria="Roof slope is below 1/4 inch per foot minimum.",
        fail_closed_behavior="Rule fails when slope data is missing.",
        escalation_behavior="Always escalate -- insufficient slope causes ponding water.",
        error_message_template=(
            "ROOF-009 FAIL: Roof slope of {slope_inches_per_foot}in/ft is "
            "below the 1/4in/ft minimum required by code."
        ),
    ),

    ValidationRule(
        rule_id="ROOF-010",
        rule_version="1.0.0",
        rule_source="ANSI/SPRI ES-1 - Edge Metal Securement",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Assembly includes roof edge metal.",
        required_inputs=["edge_details"],
        evaluation_logic=_edge_metal_securement,
        pass_criteria="All edge metal is mechanically secured per ANSI/SPRI ES-1.",
        fail_criteria="Edge metal is not properly secured or does not meet ES-1.",
        fail_closed_behavior="Rule fails when edge detail data is missing.",
        escalation_behavior="Always escalate -- edge metal failure is a wind damage risk.",
        error_message_template=(
            "ROOF-010 FAIL: Edge metal is not mechanically secured per "
            "ANSI/SPRI ES-1. All edge metal must meet wind uplift requirements."
        ),
    ),
]
