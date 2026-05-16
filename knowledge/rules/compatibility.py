"""
Manufacturer material compatibility engine.

Defines MaterialCompatibility relationships and ValidationRule instances
for detecting incompatible material combinations in construction assemblies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from knowledge.rules.engine import RuleCategory, Severity, ValidationRule


# ---------------------------------------------------------------------------
# Compatibility data model
# ---------------------------------------------------------------------------

@dataclass
class MaterialCompatibility:
    """Defines a compatibility relationship between two materials.

    Attributes:
        material_a:       First material in the pair.
        material_b:       Second material in the pair.
        compatible:       Whether the materials can be used together.
        condition:        Optional condition that modifies compatibility
                          (e.g., "requires cover board").
        reason:           Technical explanation for the compatibility ruling.
        source:           Reference standard or manufacturer bulletin.
    """
    material_a: str
    material_b: str
    compatible: bool
    condition: Optional[str] = None
    reason: str = ""
    source: str = ""


# ---------------------------------------------------------------------------
# Material compatibility table (10+ real relationships)
# ---------------------------------------------------------------------------

MATERIAL_COMPATIBILITY_TABLE: List[MaterialCompatibility] = [
    MaterialCompatibility(
        material_a="TPO membrane",
        material_b="TPO bonding adhesive",
        compatible=True,
        condition=None,
        reason="TPO bonding adhesive is formulated for TPO membrane adhesion.",
        source="Manufacturer installation guide (Carlisle, GAF, Firestone)",
    ),
    MaterialCompatibility(
        material_a="EPDM membrane",
        material_b="PVC membrane",
        compatible=False,
        condition=None,
        reason=(
            "PVC plasticizers migrate into EPDM, causing embrittlement of the "
            "EPDM and degradation of the PVC. Direct contact must be avoided."
        ),
        source="NRCA Roofing Manual / Manufacturer technical bulletins",
    ),
    MaterialCompatibility(
        material_a="Polyiso insulation",
        material_b="Torch-applied modified bitumen",
        compatible=False,
        condition="requires cover board",
        reason=(
            "Open-flame torch application over polyiso is a fire hazard. "
            "A non-combustible cover board (gypsum, HD polyiso, perlite) "
            "must separate polyiso from the torch."
        ),
        source="FM Global DS 1-28, manufacturer fire safety bulletins",
    ),
    MaterialCompatibility(
        material_a="EPDM membrane",
        material_b="Solvent-based contact adhesive",
        compatible=True,
        condition=None,
        reason="Solvent-based contact adhesive is the standard bonding method for EPDM.",
        source="Firestone / Carlisle EPDM installation guide",
    ),
    MaterialCompatibility(
        material_a="TPO membrane",
        material_b="EPDM splice tape",
        compatible=False,
        condition=None,
        reason=(
            "EPDM splice tape does not bond to TPO. TPO requires hot-air "
            "welding or TPO-specific adhesive tape."
        ),
        source="Manufacturer technical bulletins",
    ),
    MaterialCompatibility(
        material_a="Spray polyurethane foam (SPF)",
        material_b="UV exposure",
        compatible=False,
        condition="requires protective coating",
        reason=(
            "SPF degrades rapidly under UV exposure. A UV-protective "
            "elastomeric coating must be applied within 72 hours of foam "
            "installation."
        ),
        source="SPFA (Spray Polyurethane Foam Alliance) guidelines",
    ),
    MaterialCompatibility(
        material_a="PVC membrane",
        material_b="Asphalt-based products",
        compatible=False,
        condition=None,
        reason=(
            "Asphalt extracts plasticizers from PVC membrane, causing it to "
            "become brittle and crack. A separator sheet is required if PVC "
            "is installed over existing asphalt roofing."
        ),
        source="NRCA Roofing Manual, PVC manufacturer technical bulletins",
    ),
    MaterialCompatibility(
        material_a="Modified bitumen membrane",
        material_b="Polyiso insulation",
        compatible=False,
        condition="requires cover board",
        reason=(
            "Direct torch or hot-asphalt application of mod bit over polyiso "
            "is a fire hazard. A cover board (gypsum, perlite, HD polyiso) "
            "is required between the insulation and the membrane."
        ),
        source="FM Global DS 1-28, NRCA Roofing Manual",
    ),
    MaterialCompatibility(
        material_a="TPO membrane",
        material_b="Water-based adhesive",
        compatible=True,
        condition="for fully adhered systems",
        reason=(
            "Water-based adhesive is the standard low-VOC bonding method "
            "for fully adhered TPO membrane installations."
        ),
        source="Manufacturer installation guide (Carlisle, GAF, Firestone)",
    ),
    MaterialCompatibility(
        material_a="SFRM fireproofing",
        material_b="High humidity before cure",
        compatible=False,
        condition=None,
        reason=(
            "SFRM (spray-applied fire-resistive material) requires controlled "
            "humidity during cure. High humidity before full cure causes the "
            "material to sag, crack, or lose adhesion, compromising the fire "
            "rating."
        ),
        source="SFRM manufacturer technical data sheets (Isolatek, GCP)",
    ),
]


# ---------------------------------------------------------------------------
# Evaluation callable
# ---------------------------------------------------------------------------

def _check_compatibility(ctx: Dict[str, Any]) -> bool:
    """Check all material pairs in the assembly against the compatibility table.

    Context must contain ``material_pairs`` -- a list of dicts, each with
    keys ``material_a`` and ``material_b``.
    """
    pairs = ctx.get("material_pairs", [])
    for pair in pairs:
        mat_a = pair.get("material_a", "").lower()
        mat_b = pair.get("material_b", "").lower()
        for entry in MATERIAL_COMPATIBILITY_TABLE:
            ea = entry.material_a.lower()
            eb = entry.material_b.lower()
            # Check both orderings
            if (mat_a == ea and mat_b == eb) or (mat_a == eb and mat_b == ea):
                if not entry.compatible and not pair.get("mitigation_applied", False):
                    return False
    return True


def _check_conditional_compatibility(ctx: Dict[str, Any]) -> bool:
    """Check that conditional compatibility requirements are met.

    For pairs that are conditionally compatible (e.g., "requires cover board"),
    verify the condition is satisfied.
    """
    pairs = ctx.get("material_pairs", [])
    for pair in pairs:
        mat_a = pair.get("material_a", "").lower()
        mat_b = pair.get("material_b", "").lower()
        for entry in MATERIAL_COMPATIBILITY_TABLE:
            ea = entry.material_a.lower()
            eb = entry.material_b.lower()
            if (mat_a == ea and mat_b == eb) or (mat_a == eb and mat_b == ea):
                if entry.condition and not pair.get("condition_met", False):
                    return False
    return True


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

COMPATIBILITY_RULES: List[ValidationRule] = [
    ValidationRule(
        rule_id="COMPAT-001",
        rule_version="1.0.0",
        rule_source="NRCA Roofing Manual / Manufacturer Technical Bulletins",
        category=RuleCategory.COMPATIBILITY,
        severity=Severity.ERROR,
        trigger_condition="Assembly contains two or more materials in contact.",
        required_inputs=["material_pairs"],
        evaluation_logic=_check_compatibility,
        pass_criteria="All material pairs are compatible or have mitigation applied.",
        fail_criteria="One or more material pairs are incompatible without mitigation.",
        fail_closed_behavior="Rule fails when material pair data is missing.",
        escalation_behavior="Always escalate -- incompatible materials cause premature system failure.",
        error_message_template=(
            "COMPAT-001 FAIL: Incompatible material pair detected in assembly. "
            "Check all material-to-material contact points against manufacturer "
            "compatibility requirements."
        ),
    ),

    ValidationRule(
        rule_id="COMPAT-002",
        rule_version="1.0.0",
        rule_source="FM Global DS 1-28 / Manufacturer Requirements",
        category=RuleCategory.COMPATIBILITY,
        severity=Severity.WARNING,
        trigger_condition="Assembly contains conditionally compatible material pairs.",
        required_inputs=["material_pairs"],
        evaluation_logic=_check_conditional_compatibility,
        pass_criteria="All conditional compatibility requirements are met (e.g., cover board installed).",
        fail_criteria="Conditional compatibility requirement not met.",
        fail_closed_behavior="Rule fails when material pair data is missing.",
        escalation_behavior="Escalate to verify condition is met in field.",
        error_message_template=(
            "COMPAT-002 FAIL: Conditional compatibility requirement not met. "
            "Some material combinations require specific mitigation (e.g., cover "
            "board between polyiso and torch-applied membrane)."
        ),
    ),
]
