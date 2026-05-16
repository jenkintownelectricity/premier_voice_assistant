"""
Insulation taper and drainage logic validation rules.

Concrete ValidationRule instances covering minimum slope, drain high points,
cricket requirements, sump logic, overflow scupper elevation, and parapet
drainage safety. Includes JSON-serializable rule metadata.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from knowledge.rules.engine import RuleCategory, Severity, ValidationRule


# ---------------------------------------------------------------------------
# Helper evaluation callables
# ---------------------------------------------------------------------------

def _minimum_slope(ctx: Dict[str, Any]) -> bool:
    """Roof slope must be at least 1/4 inch per foot (default)."""
    slope = ctx.get("slope_inches_per_foot", 0.0)
    min_slope = ctx.get("min_slope_inches_per_foot", 0.25)
    return slope >= min_slope


def _drain_high_point(ctx: Dict[str, Any]) -> bool:
    """Drains must be at the low point; high points must slope toward drains.

    Validates that every high point in the taper layout has a defined slope
    path toward at least one drain.
    """
    high_points = ctx.get("taper_high_points", [])
    drains = ctx.get("drain_locations", [])
    if not drains:
        return False  # No drains defined = fail-closed

    for hp in high_points:
        has_path_to_drain = hp.get("slopes_to_drain", False)
        if not has_path_to_drain:
            return False
    return True


def _cricket_behind_curbs(ctx: Dict[str, Any]) -> bool:
    """Curbs wider than 12 inches on the upslope side need a cricket."""
    curbs = ctx.get("curbs", [])
    for curb in curbs:
        width_inches = curb.get("width_inches", 0)
        is_upslope = curb.get("on_upslope_side", False)
        has_cricket = curb.get("has_cricket", False)
        if width_inches > 12 and is_upslope and not has_cricket:
            return False
    return True


def _sump_logic(ctx: Dict[str, Any]) -> bool:
    """Tapered sump around drains: typically 4ft square, minimum depth.

    Validates that each drain has a properly sized sump.
    """
    drains = ctx.get("drain_locations", [])
    for drain in drains:
        sump = drain.get("sump", {})
        if not sump:
            return False  # Every drain needs a sump
        sump_width_ft = sump.get("width_ft", 0)
        sump_depth_inches = sump.get("depth_inches", 0)
        if sump_width_ft < 4.0:
            return False
        if sump_depth_inches < 1.0:
            return False
    return True


def _overflow_scupper_elevation(ctx: Dict[str, Any]) -> bool:
    """Overflow scupper must be set 2 inches above primary drain elevation."""
    primary_drain_elevation = ctx.get("primary_drain_elevation_inches", None)
    overflow_scupper_elevation = ctx.get("overflow_scupper_elevation_inches", None)
    if primary_drain_elevation is None or overflow_scupper_elevation is None:
        return False  # Missing data = fail-closed
    min_offset = ctx.get("min_overflow_offset_inches", 2.0)
    return overflow_scupper_elevation >= (primary_drain_elevation + min_offset)


def _parapet_drainage_safety(ctx: Dict[str, Any]) -> bool:
    """No negative slope toward parapet without a scupper or overflow.

    If water slopes toward a parapet wall, there must be a scupper or
    overflow drain at that parapet to prevent ponding.
    """
    parapet_edges = ctx.get("parapet_edges", [])
    for edge in parapet_edges:
        slope_toward_parapet = edge.get("slope_toward_parapet", False)
        has_scupper = edge.get("has_scupper", False)
        has_overflow = edge.get("has_overflow_drain", False)
        if slope_toward_parapet and not (has_scupper or has_overflow):
            return False
    return True


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

DRAINAGE_RULES: List[ValidationRule] = [
    ValidationRule(
        rule_id="DRAIN-001",
        rule_version="1.0.0",
        rule_source="IBC 1502 / NRCA - Minimum Slope for Positive Drainage",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Roof taper system is defined.",
        required_inputs=["slope_inches_per_foot"],
        evaluation_logic=_minimum_slope,
        pass_criteria="Roof slope is at least 1/4 inch per foot.",
        fail_criteria="Roof slope is below 1/4 inch per foot minimum.",
        fail_closed_behavior="Rule fails when slope data is missing.",
        escalation_behavior="Always escalate -- insufficient slope causes ponding water and structural risk.",
        error_message_template=(
            "DRAIN-001 FAIL: Roof slope of {slope_inches_per_foot}in/ft is "
            "below the 1/4in/ft minimum. Ponding water risk."
        ),
    ),

    ValidationRule(
        rule_id="DRAIN-002",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Taper Layout Design",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Taper layout contains high points and drain locations.",
        required_inputs=["taper_high_points", "drain_locations"],
        evaluation_logic=_drain_high_point,
        pass_criteria="Every taper high point has a defined slope path to at least one drain.",
        fail_criteria="One or more high points have no slope path to a drain, creating ponding zones.",
        fail_closed_behavior="Rule fails when taper high point or drain location data is missing.",
        escalation_behavior="Always escalate -- orphan high points create permanent ponding.",
        error_message_template=(
            "DRAIN-002 FAIL: Taper high point has no slope path to a drain. "
            "All high points must slope toward at least one drain location."
        ),
    ),

    ValidationRule(
        rule_id="DRAIN-003",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Cricket and Saddle Requirements",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.WARNING,
        trigger_condition="Curbs wider than 12 inches exist on the upslope side.",
        required_inputs=["curbs"],
        evaluation_logic=_cricket_behind_curbs,
        pass_criteria="All wide upslope curbs have crickets to divert water.",
        fail_criteria="Wide curb on upslope side lacks a cricket, creating ponding behind the curb.",
        fail_closed_behavior="Rule fails when curb data is missing.",
        escalation_behavior="Escalate when curb width is borderline (10-14in).",
        error_message_template=(
            "DRAIN-003 FAIL: Curb wider than 12in on upslope side has no cricket. "
            "Water will pond behind the curb. Install a tapered cricket."
        ),
    ),

    ValidationRule(
        rule_id="DRAIN-004",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Drain Sump Design",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.WARNING,
        trigger_condition="Roof drains are present in the assembly.",
        required_inputs=["drain_locations"],
        evaluation_logic=_sump_logic,
        pass_criteria="Each drain has a tapered sump at least 4ft square with minimum 1in depth.",
        fail_criteria="One or more drains lack a properly sized sump.",
        fail_closed_behavior="Rule fails when drain sump data is missing.",
        escalation_behavior="Escalate if sump is undersized relative to drainage area.",
        error_message_template=(
            "DRAIN-004 FAIL: Drain sump does not meet minimum dimensions. "
            "Typical requirement: 4ft x 4ft minimum, 1in minimum depth."
        ),
    ),

    ValidationRule(
        rule_id="DRAIN-005",
        rule_version="1.0.0",
        rule_source="IBC 1502.2 / Plumbing Code - Overflow Drainage",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Primary drains and overflow scuppers are defined.",
        required_inputs=["primary_drain_elevation_inches", "overflow_scupper_elevation_inches"],
        evaluation_logic=_overflow_scupper_elevation,
        pass_criteria="Overflow scupper is at least 2 inches above primary drain elevation.",
        fail_criteria="Overflow scupper is too close to primary drain elevation.",
        fail_closed_behavior="Rule fails when elevation data is missing.",
        escalation_behavior="Always escalate -- improper overflow height risks structural overload in storm events.",
        error_message_template=(
            "DRAIN-005 FAIL: Overflow scupper elevation is not at least 2in above "
            "primary drain. IBC requires overflow to engage only when primary drainage fails."
        ),
    ),

    ValidationRule(
        rule_id="DRAIN-006",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual - Parapet Drainage Safety",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Roof slope directs water toward a parapet wall.",
        required_inputs=["parapet_edges"],
        evaluation_logic=_parapet_drainage_safety,
        pass_criteria="All parapet edges receiving water have scuppers or overflow drains.",
        fail_criteria="Water slopes toward parapet with no scupper or overflow drain.",
        fail_closed_behavior="Rule fails when parapet edge data is missing.",
        escalation_behavior="Always escalate -- trapped water at parapet causes structural overload and leaks.",
        error_message_template=(
            "DRAIN-006 FAIL: Negative slope toward parapet wall with no scupper "
            "or overflow. Water will pond against the parapet. Install a scupper "
            "or redirect slope."
        ),
    ),
]


# ---------------------------------------------------------------------------
# JSON-serializable rule table for external consumers
# ---------------------------------------------------------------------------

def _rules_to_json_table() -> List[Dict[str, Any]]:
    """Export drainage rules as JSON-serializable dicts (no callables)."""
    table = []
    for rule in DRAINAGE_RULES:
        table.append({
            "rule_id": rule.rule_id,
            "rule_version": rule.rule_version,
            "rule_source": rule.rule_source,
            "category": rule.category.value,
            "severity": rule.severity.value,
            "trigger_condition": rule.trigger_condition,
            "required_inputs": rule.required_inputs,
            "pass_criteria": rule.pass_criteria,
            "fail_criteria": rule.fail_criteria,
            "fail_closed_behavior": rule.fail_closed_behavior,
            "escalation_behavior": rule.escalation_behavior,
            "error_message_template": rule.error_message_template,
        })
    return table


DRAINAGE_RULES_JSON = _rules_to_json_table()

# Convenience: serialized JSON string
DRAINAGE_RULES_JSON_STR = json.dumps(DRAINAGE_RULES_JSON, indent=2)
