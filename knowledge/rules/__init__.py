"""
Construction Assembly Knowledge Graph - Validation Rules System

Domain-specific validation rules for construction assembly knowledge graphs.
Implements fail-closed validation with evidence tracking and human-review escalation.

Modules:
    engine          - Core ValidationEngine, ValidationRule, ValidationResult
    roofing         - Roofing assembly continuity and code compliance rules
    fireproofing    - SFRM/intumescent fire rating validation rules
    drainage        - Insulation taper and drainage logic rules
    membrane        - Membrane overlap and water shedding rules
    compatibility   - Material compatibility engine
    fireproofing_thickness - Fireproofing thickness selection logic
"""

from knowledge.rules.engine import (
    ValidationEngine,
    ValidationResult,
    ValidationRule,
)
from knowledge.rules.roofing import ROOFING_RULES
from knowledge.rules.fireproofing import FIREPROOFING_RULES
from knowledge.rules.drainage import DRAINAGE_RULES
from knowledge.rules.membrane import MEMBRANE_RULES
from knowledge.rules.compatibility import (
    COMPATIBILITY_RULES,
    MaterialCompatibility,
    MATERIAL_COMPATIBILITY_TABLE,
)
from knowledge.rules.fireproofing_thickness import (
    FIREPROOFING_THICKNESS_RULES,
    ThicknessLookup,
    THICKNESS_TABLE,
)

ALL_RULES = (
    ROOFING_RULES
    + FIREPROOFING_RULES
    + DRAINAGE_RULES
    + MEMBRANE_RULES
    + COMPATIBILITY_RULES
    + FIREPROOFING_THICKNESS_RULES
)

__all__ = [
    "ValidationEngine",
    "ValidationResult",
    "ValidationRule",
    "ROOFING_RULES",
    "FIREPROOFING_RULES",
    "DRAINAGE_RULES",
    "MEMBRANE_RULES",
    "COMPATIBILITY_RULES",
    "FIREPROOFING_THICKNESS_RULES",
    "ALL_RULES",
    "MaterialCompatibility",
    "MATERIAL_COMPATIBILITY_TABLE",
    "ThicknessLookup",
    "THICKNESS_TABLE",
]
