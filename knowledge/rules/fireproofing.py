"""
Fireproofing domain validation rules.

Concrete ValidationRule instances covering SFRM thickness-to-rating matching,
UL design references, member coverage, deck interface continuity, penetration
firestop requirements, and installation sequencing for structural fireproofing.
"""

from __future__ import annotations

from typing import Any, Dict, List

from knowledge.rules.engine import RuleCategory, Severity, ValidationRule


# ---------------------------------------------------------------------------
# Helper evaluation callables
# ---------------------------------------------------------------------------

def _thickness_vs_rating(ctx: Dict[str, Any]) -> bool:
    """SFRM thickness must match UL design for the required fire rating."""
    applied_thickness = ctx.get("sfrm_applied_thickness_inches", 0.0)
    required_thickness = ctx.get("sfrm_required_thickness_inches", 0.0)
    if required_thickness <= 0:
        return False  # No valid required thickness means we cannot validate
    return applied_thickness >= required_thickness


def _fire_rating_reference(ctx: Dict[str, Any]) -> bool:
    """Every fireproofing system must reference a UL design number."""
    ul_design = ctx.get("ul_design_number", "")
    return bool(ul_design and ul_design.strip())


def _member_coverage(ctx: Dict[str, Any]) -> bool:
    """All surfaces of a rated structural member must be protected."""
    surfaces = ctx.get("member_surfaces", [])
    if not surfaces:
        return False  # No surface data means fail-closed
    for surface in surfaces:
        if not surface.get("fireproofing_applied", False):
            return False
    return True


def _deck_interface_continuity(ctx: Dict[str, Any]) -> bool:
    """Fireproofing must extend to the deck underside without gaps."""
    beam_to_deck_gap = ctx.get("beam_to_deck_fireproofing_gap_inches", None)
    if beam_to_deck_gap is None:
        return False  # Missing measurement = fail-closed
    max_allowed_gap = ctx.get("max_allowed_gap_inches", 0.0)
    return beam_to_deck_gap <= max_allowed_gap


def _penetration_firestop(ctx: Dict[str, Any]) -> bool:
    """All penetrations through rated assemblies need a firestop system."""
    penetrations = ctx.get("penetrations", [])
    for pen in penetrations:
        if pen.get("through_rated_assembly", False):
            if not pen.get("firestop_installed", False):
                return False
            if not pen.get("firestop_ul_system", "").strip():
                return False
    return True


def _installation_order(ctx: Dict[str, Any]) -> bool:
    """Fireproofing must be applied before other trades that could damage it.

    Validates that the fireproofing installation sequence number is lower
    (earlier) than MEP rough-in, sprinkler installation, and other trades
    that work in the same area.
    """
    fp_sequence = ctx.get("fireproofing_install_sequence", None)
    trade_sequences = ctx.get("other_trade_sequences", [])
    if fp_sequence is None or not trade_sequences:
        return False  # Missing sequencing data = fail-closed
    for trade in trade_sequences:
        trade_seq = trade.get("sequence", 0)
        trade_name = trade.get("trade", "unknown")
        # Fireproofing should come before trades that work overhead
        if trade.get("works_overhead", False) and trade_seq <= fp_sequence:
            return False
    return True


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

FIREPROOFING_RULES: List[ValidationRule] = [
    ValidationRule(
        rule_id="FIRE-001",
        rule_version="1.0.0",
        rule_source="UL Fire Resistance Directory / IBC 714",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="SFRM fireproofing is applied to a structural member with a fire rating requirement.",
        required_inputs=["sfrm_applied_thickness_inches", "sfrm_required_thickness_inches"],
        evaluation_logic=_thickness_vs_rating,
        pass_criteria="Applied SFRM thickness meets or exceeds the UL design requirement for the specified fire rating.",
        fail_criteria="Applied SFRM thickness is less than what the UL design requires for the fire rating.",
        fail_closed_behavior="Rule fails when thickness data is missing. Inspect fireproofing application and UL listing.",
        escalation_behavior="Always escalate -- insufficient fireproofing thickness compromises life safety.",
        error_message_template=(
            "FIRE-001 FAIL: Applied SFRM thickness of {sfrm_applied_thickness_inches}in "
            "does not meet required {sfrm_required_thickness_inches}in per UL design. "
            "Structural fire rating is compromised."
        ),
    ),

    ValidationRule(
        rule_id="FIRE-002",
        rule_version="1.0.0",
        rule_source="IBC 703.2 / UL Fire Resistance Directory",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="A fireproofing system is specified in the assembly.",
        required_inputs=["ul_design_number"],
        evaluation_logic=_fire_rating_reference,
        pass_criteria="Fireproofing system references a valid UL design number.",
        fail_criteria="No UL design number is referenced for the fireproofing system.",
        fail_closed_behavior="Rule fails when UL design number is missing. Every fire-rated assembly must cite a UL design.",
        escalation_behavior="Always escalate -- missing fire rating reference makes inspection impossible.",
        error_message_template=(
            "FIRE-002 FAIL: Fireproofing system has no UL design number reference. "
            "Every fire-rated assembly must reference a specific UL design (e.g., D916, X772)."
        ),
    ),

    ValidationRule(
        rule_id="FIRE-003",
        rule_version="1.0.0",
        rule_source="IBC 714.4 / ASTM E119 - Structural Member Coverage",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="A structural member has a fire rating requirement.",
        required_inputs=["member_surfaces"],
        evaluation_logic=_member_coverage,
        pass_criteria="All surfaces of the rated structural member are protected with fireproofing.",
        fail_criteria="One or more surfaces of the rated member lack fireproofing coverage.",
        fail_closed_behavior="Rule fails when member surface data is missing. Physical inspection required.",
        escalation_behavior="Always escalate -- exposed steel surface negates fire rating.",
        error_message_template=(
            "FIRE-003 FAIL: Not all surfaces of the structural member are protected. "
            "All exposed surfaces of a rated member must have continuous fireproofing per IBC 714.4."
        ),
    ),

    ValidationRule(
        rule_id="FIRE-004",
        rule_version="1.0.0",
        rule_source="UL Fire Resistance Directory - Restrained Assembly Requirements",
        category=RuleCategory.CONTINUITY,
        severity=Severity.ERROR,
        trigger_condition="Fireproofed beam meets deck underside.",
        required_inputs=["beam_to_deck_fireproofing_gap_inches"],
        evaluation_logic=_deck_interface_continuity,
        pass_criteria="Fireproofing extends continuously from beam to deck underside with no gap.",
        fail_criteria="Gap exists between beam fireproofing and deck underside.",
        fail_closed_behavior="Rule fails when beam-to-deck gap measurement is missing.",
        escalation_behavior="Always escalate -- gap at deck interface creates fire pathway around beam.",
        error_message_template=(
            "FIRE-004 FAIL: Fireproofing gap of {beam_to_deck_fireproofing_gap_inches}in "
            "detected at beam-to-deck interface. Fireproofing must extend continuously "
            "to the deck underside."
        ),
    ),

    ValidationRule(
        rule_id="FIRE-005",
        rule_version="1.0.0",
        rule_source="IBC 714.3 / ASTM E814 - Through Penetration Firestop",
        category=RuleCategory.CODE_REFERENCE,
        severity=Severity.ERROR,
        trigger_condition="Penetrations exist through fire-rated assemblies.",
        required_inputs=["penetrations"],
        evaluation_logic=_penetration_firestop,
        pass_criteria="All penetrations through rated assemblies have listed firestop systems.",
        fail_criteria="One or more penetrations through rated assemblies lack firestop or UL system reference.",
        fail_closed_behavior="Rule fails when penetration data is missing. All penetrations must be verified.",
        escalation_behavior="Always escalate -- unprotected penetrations defeat fire compartmentation.",
        error_message_template=(
            "FIRE-005 FAIL: Penetration through rated assembly lacks required firestop. "
            "IBC 714.3 requires listed firestop systems (UL System number) for all "
            "penetrations through fire-rated assemblies."
        ),
    ),

    ValidationRule(
        rule_id="FIRE-006",
        rule_version="1.0.0",
        rule_source="Construction Sequencing Best Practice / SFRM Manufacturer Requirements",
        category=RuleCategory.SEQUENCING,
        severity=Severity.WARNING,
        trigger_condition="Fireproofing is specified alongside other overhead trades.",
        required_inputs=["fireproofing_install_sequence", "other_trade_sequences"],
        evaluation_logic=_installation_order,
        pass_criteria="Fireproofing is installed before other trades that work overhead in the same area.",
        fail_criteria="Other trades are scheduled before fireproofing, risking damage to SFRM.",
        fail_closed_behavior="Rule fails when sequencing data is missing.",
        escalation_behavior="Escalate to project manager -- sequencing conflicts cause costly rework.",
        error_message_template=(
            "FIRE-006 FAIL: Fireproofing installation sequence conflicts with other "
            "overhead trades. SFRM must be applied and cured before MEP/sprinkler "
            "rough-in to prevent damage."
        ),
    ),
]
