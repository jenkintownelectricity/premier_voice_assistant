"""
Edge / Relationship Model for Construction Assembly Knowledge Graph.

Defines all typed edge families, their semantic constraints, and validation
logic for a roofing-and-building-envelope knowledge graph.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Edge Type Enumeration
# ---------------------------------------------------------------------------

class EdgeType(Enum):
    """Every legal relationship in the construction assembly graph."""

    # Structural / spatial hierarchy
    CONTAINS = "contains"
    ADJACENT_TO = "adjacent_to"
    TRANSITIONS_TO = "transitions_to"
    SUPPORTED_BY = "supported_by"
    ATTACHED_TO = "attached_to"
    PENETRATES = "penetrates"
    TERMINATES_AT = "terminates_at"
    DRAINS_TO = "drains_to"
    PROTECTS = "protects"
    OVERLAPS = "overlaps"

    # Material compatibility
    BONDS_TO = "bonds_to"
    INCOMPATIBLE_WITH = "incompatible_with"

    # Dependency / specification
    REQUIRES = "requires"
    SATISFIES = "satisfies"
    REFERENCES = "references"

    # Sequencing
    INSTALLED_BEFORE = "installed_before"
    INSTALLED_AFTER = "installed_after"

    # Analysis / validation
    GENERATES = "generates"
    VALIDATES = "validates"
    FAILS_AT = "fails_at"
    SUPERSEDES = "supersedes"

    # Visualisation / UI
    RENDERS_AS = "renders_as"
    VISIBLE_IN = "visible_in"
    HIGHLIGHTS = "highlights"
    SELECTED_IN = "selected_in"
    GROUPED_WITH = "grouped_with"

    # Provenance
    LINEAGE_OF = "lineage_of"


# ---------------------------------------------------------------------------
# Cardinality
# ---------------------------------------------------------------------------

class Cardinality(Enum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"


# ---------------------------------------------------------------------------
# Edge Definition (schema / constraint for each edge type)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EdgeDefinition:
    """Schema that constrains how an edge type may be used."""

    semantic_meaning: str
    allowed_source_types: List[str]
    allowed_target_types: List[str]
    required_metadata: Dict[str, type]
    is_directional: bool
    inverse_edge_type: Optional[str]
    cardinality: Cardinality


# ---------------------------------------------------------------------------
# Edge Instance
# ---------------------------------------------------------------------------

@dataclass
class Edge:
    """A concrete, instantiated relationship between two nodes."""

    edge_type: EdgeType
    source_id: str
    target_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1


# ---------------------------------------------------------------------------
# EDGE_REGISTRY  --  the single source of truth for relationship rules
# ---------------------------------------------------------------------------

EDGE_REGISTRY: Dict[EdgeType, EdgeDefinition] = {

    # ------------------------------------------------------------------
    # Structural / spatial hierarchy
    # ------------------------------------------------------------------

    EdgeType.CONTAINS: EdgeDefinition(
        semantic_meaning=(
            "Parent entity spatially or logically contains a child entity. "
            "Project contains Building, Building contains Zone, Zone contains "
            "Assembly, Assembly contains Layer."
        ),
        allowed_source_types=[
            "Project", "Building", "Zone", "RoofArea", "WallArea",
            "Assembly", "Layer", "Detail", "DrawingSet",
        ],
        allowed_target_types=[
            "Building", "Zone", "RoofArea", "WallArea", "Assembly",
            "Layer", "Component", "Material", "Detail", "Drawing",
            "Penetration", "Drain", "Termination",
        ],
        required_metadata={},
        is_directional=True,
        inverse_edge_type="contained_by",
        cardinality=Cardinality.ONE_TO_MANY,
    ),

    EdgeType.ADJACENT_TO: EdgeDefinition(
        semantic_meaning=(
            "Two entities share a physical boundary or are immediately next "
            "to each other -- e.g. two roof zones that share an edge, or two "
            "insulation boards laid side-by-side."
        ),
        allowed_source_types=[
            "Zone", "RoofArea", "WallArea", "Layer", "Component",
            "Assembly", "Drain",
        ],
        allowed_target_types=[
            "Zone", "RoofArea", "WallArea", "Layer", "Component",
            "Assembly", "Drain",
        ],
        required_metadata={
            "shared_edge_length_ft": float,
        },
        is_directional=False,
        inverse_edge_type=None,
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.TRANSITIONS_TO: EdgeDefinition(
        semantic_meaning=(
            "One area or assembly transitions into another -- typically at a "
            "change in slope, substrate, or wall/roof interface. "
            "RoofArea transitions_to WallArea at a parapet; low-slope "
            "transitions_to steep-slope at a mansard break."
        ),
        allowed_source_types=[
            "RoofArea", "WallArea", "Assembly", "Zone",
        ],
        allowed_target_types=[
            "RoofArea", "WallArea", "Assembly", "Zone",
        ],
        required_metadata={
            "transition_detail": str,
        },
        is_directional=True,
        inverse_edge_type="transitions_from",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.SUPPORTED_BY: EdgeDefinition(
        semantic_meaning=(
            "Physical load-path relationship. The source is held up or "
            "backed by the target. Membrane supported_by CoverBoard, "
            "CoverBoard supported_by Insulation, Insulation supported_by "
            "DeckSubstrate."
        ),
        allowed_source_types=[
            "Layer", "Component", "Material", "Membrane", "CoverBoard",
            "Insulation", "Assembly",
        ],
        allowed_target_types=[
            "Layer", "Component", "Material", "CoverBoard", "Insulation",
            "VaporBarrier", "DeckSubstrate", "StructuralMember", "Assembly",
        ],
        required_metadata={
            "attachment_method": str,
        },
        is_directional=True,
        inverse_edge_type="supports",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.ATTACHED_TO: EdgeDefinition(
        semantic_meaning=(
            "Mechanical or adhesive fastening between two entities. "
            "Differs from supported_by in that it does not imply a gravity "
            "load path -- e.g. a cleat attached_to a parapet wall."
        ),
        allowed_source_types=[
            "Component", "Layer", "Material", "Flashing", "Cleat",
            "Termination", "Fastener", "Membrane",
        ],
        allowed_target_types=[
            "Component", "Layer", "Material", "StructuralMember",
            "DeckSubstrate", "Blocking", "NailingStrip", "WallArea",
        ],
        required_metadata={
            "attachment_method": str,
            "fastener_spacing_in": float,
        },
        is_directional=True,
        inverse_edge_type="has_attachment",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.PENETRATES: EdgeDefinition(
        semantic_meaning=(
            "A penetration element passes through an assembly or layer -- "
            "pipes, conduits, HVAC curbs, skylights, drains. "
            "Penetration penetrates Assembly."
        ),
        allowed_source_types=[
            "Penetration", "Pipe", "Conduit", "HVACUnit", "Skylight",
            "Drain", "Vent", "Component",
        ],
        allowed_target_types=[
            "Assembly", "Layer", "Membrane", "Insulation", "DeckSubstrate",
        ],
        required_metadata={
            "opening_diameter_in": float,
            "flashing_method": str,
        },
        is_directional=True,
        inverse_edge_type="penetrated_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.TERMINATES_AT: EdgeDefinition(
        semantic_meaning=(
            "A membrane, flashing, or other continuous material ends at a "
            "specific termination detail. Membrane terminates_at "
            "Termination (e.g. gravel stop, drip edge, coping, parapet)."
        ),
        allowed_source_types=[
            "Membrane", "Flashing", "VaporBarrier", "Layer", "Material",
        ],
        allowed_target_types=[
            "Termination", "Coping", "GravelStop", "DripEdge", "EdgeMetal",
            "Reglet", "CounterFlashing", "Component",
        ],
        required_metadata={
            "seal_method": str,
        },
        is_directional=True,
        inverse_edge_type="receives_termination",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.DRAINS_TO: EdgeDefinition(
        semantic_meaning=(
            "Water flow path. Source area or component drains water toward "
            "the target drain, scupper, gutter, or downspout."
        ),
        allowed_source_types=[
            "RoofArea", "Zone", "TaperZone", "Cricket", "Saddle",
            "Assembly", "Drain", "Scupper",
        ],
        allowed_target_types=[
            "Drain", "Scupper", "Gutter", "Downspout", "Conductor",
            "AreaDrain", "Component",
        ],
        required_metadata={
            "slope_in_per_ft": float,
            "drainage_area_sf": float,
        },
        is_directional=True,
        inverse_edge_type="receives_drainage_from",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.PROTECTS: EdgeDefinition(
        semantic_meaning=(
            "One system or layer shields another from environmental or "
            "structural harm. FireproofingSystem protects StructuralMember; "
            "WalkPad protects Membrane."
        ),
        allowed_source_types=[
            "FireproofingSystem", "WalkPad", "SurfaceCoating",
            "Membrane", "Flashing", "Component", "Layer", "Assembly",
        ],
        allowed_target_types=[
            "StructuralMember", "Membrane", "Insulation", "Layer",
            "Component", "Assembly", "DeckSubstrate",
        ],
        required_metadata={
            "protection_type": str,
        },
        is_directional=True,
        inverse_edge_type="protected_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.OVERLAPS: EdgeDefinition(
        semantic_meaning=(
            "Two planar elements overlap each other -- sheet membrane laps, "
            "flashing overlaps, shingle courses. Includes lap width."
        ),
        allowed_source_types=[
            "Membrane", "Flashing", "Sheet", "Shingle", "Layer",
            "Component",
        ],
        allowed_target_types=[
            "Membrane", "Flashing", "Sheet", "Shingle", "Layer",
            "Component",
        ],
        required_metadata={
            "overlap_width_in": float,
            "seam_type": str,
        },
        is_directional=True,
        inverse_edge_type="overlapped_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    # ------------------------------------------------------------------
    # Material compatibility
    # ------------------------------------------------------------------

    EdgeType.BONDS_TO: EdgeDefinition(
        semantic_meaning=(
            "Chemical or adhesive bond between two materials. "
            "Membrane bonds_to Adhesive; Adhesive bonds_to CoverBoard."
        ),
        allowed_source_types=[
            "Membrane", "Material", "Adhesive", "Primer", "Sealant",
            "Component", "Layer",
        ],
        allowed_target_types=[
            "Adhesive", "Material", "CoverBoard", "Insulation",
            "DeckSubstrate", "Membrane", "Component", "Layer",
        ],
        required_metadata={
            "bond_method": str,
            "cure_time_hours": float,
        },
        is_directional=True,
        inverse_edge_type="bonded_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.INCOMPATIBLE_WITH: EdgeDefinition(
        semantic_meaning=(
            "Two materials must NOT come into direct contact. "
            "EPDM incompatible_with PVC (plasticizer migration); "
            "polystyrene insulation incompatible_with coal-tar pitch; "
            "certain sealants incompatible_with specific membranes."
        ),
        allowed_source_types=[
            "Material", "Membrane", "Insulation", "Adhesive", "Sealant",
            "Coating", "Component",
        ],
        allowed_target_types=[
            "Material", "Membrane", "Insulation", "Adhesive", "Sealant",
            "Coating", "Component",
        ],
        required_metadata={
            "reason": str,
        },
        is_directional=False,
        inverse_edge_type=None,
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    # ------------------------------------------------------------------
    # Dependency / specification
    # ------------------------------------------------------------------

    EdgeType.REQUIRES: EdgeDefinition(
        semantic_meaning=(
            "The source entity cannot be properly installed or function "
            "without the target. Assembly requires Material; "
            "Detail requires Flashing."
        ),
        allowed_source_types=[
            "Assembly", "Detail", "Layer", "Component", "Specification",
            "Penetration",
        ],
        allowed_target_types=[
            "Material", "Component", "Fastener", "Adhesive", "Sealant",
            "Primer", "Layer", "Tool", "Condition",
        ],
        required_metadata={},
        is_directional=True,
        inverse_edge_type="required_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.SATISFIES: EdgeDefinition(
        semantic_meaning=(
            "The source assembly or detail meets the requirements of a code, "
            "standard, or specification. Assembly satisfies CodeRequirement; "
            "FlashingDetail satisfies ANSI_SPRI_ES1."
        ),
        allowed_source_types=[
            "Assembly", "Detail", "Component", "Material", "Layer",
        ],
        allowed_target_types=[
            "CodeRequirement", "Standard", "Specification",
            "ManufacturerRequirement", "WarrantyRequirement",
            "WindUpliftRating", "FireRating",
        ],
        required_metadata={
            "compliance_status": str,
        },
        is_directional=True,
        inverse_edge_type="satisfied_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.REFERENCES: EdgeDefinition(
        semantic_meaning=(
            "One document, specification, or detail references another. "
            "Specification references Standard; Drawing references Detail."
        ),
        allowed_source_types=[
            "Specification", "Drawing", "Detail", "Submittal",
            "CodeRequirement", "Standard",
        ],
        allowed_target_types=[
            "Specification", "Drawing", "Detail", "Standard",
            "CodeRequirement", "ManufacturerRequirement", "Submittal",
        ],
        required_metadata={
            "reference_type": str,
        },
        is_directional=True,
        inverse_edge_type="referenced_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    # ------------------------------------------------------------------
    # Sequencing
    # ------------------------------------------------------------------

    EdgeType.INSTALLED_BEFORE: EdgeDefinition(
        semantic_meaning=(
            "Construction sequencing constraint. Source must be installed "
            "before target. DeckSubstrate installed_before VaporBarrier; "
            "Insulation installed_before CoverBoard."
        ),
        allowed_source_types=[
            "Layer", "Component", "Material", "Assembly", "Detail",
        ],
        allowed_target_types=[
            "Layer", "Component", "Material", "Assembly", "Detail",
        ],
        required_metadata={
            "min_wait_hours": float,
        },
        is_directional=True,
        inverse_edge_type="installed_after",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.INSTALLED_AFTER: EdgeDefinition(
        semantic_meaning=(
            "Inverse of installed_before. Target was already in place when "
            "source was installed."
        ),
        allowed_source_types=[
            "Layer", "Component", "Material", "Assembly", "Detail",
        ],
        allowed_target_types=[
            "Layer", "Component", "Material", "Assembly", "Detail",
        ],
        required_metadata={
            "min_wait_hours": float,
        },
        is_directional=True,
        inverse_edge_type="installed_before",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    # ------------------------------------------------------------------
    # Analysis / validation
    # ------------------------------------------------------------------

    EdgeType.GENERATES: EdgeDefinition(
        semantic_meaning=(
            "A calculation, analysis, or process produces an output artefact. "
            "WindUpliftCalc generates WindUpliftRating; TaperDesign generates "
            "TaperPlan."
        ),
        allowed_source_types=[
            "Calculation", "Analysis", "Process", "Simulation",
        ],
        allowed_target_types=[
            "WindUpliftRating", "FireRating", "TaperPlan", "Report",
            "BillOfMaterials", "Drawing", "Result",
        ],
        required_metadata={
            "tool_used": str,
        },
        is_directional=True,
        inverse_edge_type="generated_by",
        cardinality=Cardinality.ONE_TO_MANY,
    ),

    EdgeType.VALIDATES: EdgeDefinition(
        semantic_meaning=(
            "An inspection, test, or check confirms that an assembly or "
            "component meets its requirements. PullTest validates "
            "FastenerAttachment; CoreCut validates InsulationThickness."
        ),
        allowed_source_types=[
            "Inspection", "Test", "QualityCheck", "Calculation",
        ],
        allowed_target_types=[
            "Assembly", "Layer", "Component", "Material", "Detail",
            "FastenerPattern",
        ],
        required_metadata={
            "result": str,
            "date_performed": str,
        },
        is_directional=True,
        inverse_edge_type="validated_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.FAILS_AT: EdgeDefinition(
        semantic_meaning=(
            "A component or assembly fails at a specific load, condition, "
            "or threshold. Membrane fails_at WindSpeed; Fastener fails_at "
            "PulloutForce."
        ),
        allowed_source_types=[
            "Component", "Assembly", "Material", "Layer", "Fastener",
            "Membrane",
        ],
        allowed_target_types=[
            "LoadCondition", "WindSpeed", "Temperature", "Threshold",
            "ForceValue",
        ],
        required_metadata={
            "failure_mode": str,
            "test_standard": str,
        },
        is_directional=True,
        inverse_edge_type=None,
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.SUPERSEDES: EdgeDefinition(
        semantic_meaning=(
            "A newer version of a standard, specification, or detail "
            "replaces an older one. ASCE_7_22 supersedes ASCE_7_16."
        ),
        allowed_source_types=[
            "Standard", "Specification", "CodeRequirement", "Detail",
            "Drawing", "Assembly",
        ],
        allowed_target_types=[
            "Standard", "Specification", "CodeRequirement", "Detail",
            "Drawing", "Assembly",
        ],
        required_metadata={
            "effective_date": str,
        },
        is_directional=True,
        inverse_edge_type="superseded_by",
        cardinality=Cardinality.ONE_TO_ONE,
    ),

    # ------------------------------------------------------------------
    # Visualisation / UI
    # ------------------------------------------------------------------

    EdgeType.RENDERS_AS: EdgeDefinition(
        semantic_meaning=(
            "A domain entity is visually represented by a specific graphic "
            "element. Assembly renders_as DrawingElement."
        ),
        allowed_source_types=[
            "Assembly", "Layer", "Component", "Detail", "Zone",
            "RoofArea",
        ],
        allowed_target_types=[
            "DrawingElement", "Symbol", "HatchPattern", "LineStyle",
            "Graphic",
        ],
        required_metadata={
            "render_style": str,
        },
        is_directional=True,
        inverse_edge_type="rendered_from",
        cardinality=Cardinality.ONE_TO_MANY,
    ),

    EdgeType.VISIBLE_IN: EdgeDefinition(
        semantic_meaning=(
            "An entity appears on a specific drawing or view. "
            "Penetration visible_in RoofPlanDrawing."
        ),
        allowed_source_types=[
            "Component", "Assembly", "Layer", "Penetration", "Drain",
            "Detail", "Zone", "RoofArea",
        ],
        allowed_target_types=[
            "Drawing", "View", "Sheet", "Viewport",
        ],
        required_metadata={
            "sheet_number": str,
        },
        is_directional=True,
        inverse_edge_type="shows",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.HIGHLIGHTS: EdgeDefinition(
        semantic_meaning=(
            "A UI annotation or callout draws attention to a specific entity "
            "in a drawing. Callout highlights Deficiency."
        ),
        allowed_source_types=[
            "Callout", "Annotation", "Marker", "Tag",
        ],
        allowed_target_types=[
            "Component", "Assembly", "Deficiency", "Detail", "Layer",
            "Penetration",
        ],
        required_metadata={},
        is_directional=True,
        inverse_edge_type="highlighted_by",
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.SELECTED_IN: EdgeDefinition(
        semantic_meaning=(
            "An entity is part of the active user selection in a UI context. "
            "Component selected_in EditorSession."
        ),
        allowed_source_types=[
            "Component", "Assembly", "Layer", "Detail", "Zone",
            "RoofArea",
        ],
        allowed_target_types=[
            "EditorSession", "SelectionSet", "Workspace",
        ],
        required_metadata={},
        is_directional=True,
        inverse_edge_type=None,
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    EdgeType.GROUPED_WITH: EdgeDefinition(
        semantic_meaning=(
            "Two entities are logically grouped together for estimation, "
            "scheduling, or display purposes."
        ),
        allowed_source_types=[
            "Component", "Assembly", "Layer", "Material", "Zone",
            "RoofArea", "Detail",
        ],
        allowed_target_types=[
            "Component", "Assembly", "Layer", "Material", "Zone",
            "RoofArea", "Detail",
        ],
        required_metadata={
            "group_reason": str,
        },
        is_directional=False,
        inverse_edge_type=None,
        cardinality=Cardinality.MANY_TO_MANY,
    ),

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------

    EdgeType.LINEAGE_OF: EdgeDefinition(
        semantic_meaning=(
            "Tracks the origin or derivation history of an entity. "
            "RevisedDrawing lineage_of OriginalDrawing; "
            "AsBuiltAssembly lineage_of DesignAssembly."
        ),
        allowed_source_types=[
            "Drawing", "Assembly", "Detail", "Specification",
            "BillOfMaterials", "Report",
        ],
        allowed_target_types=[
            "Drawing", "Assembly", "Detail", "Specification",
            "BillOfMaterials", "Report",
        ],
        required_metadata={
            "revision_number": int,
            "change_description": str,
        },
        is_directional=True,
        inverse_edge_type="derived_from",
        cardinality=Cardinality.MANY_TO_MANY,
    ),
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class EdgeValidationError(Exception):
    """Raised when an edge fails schema validation."""


def validate_edge(
    edge: Edge,
    source_type: str,
    target_type: str,
) -> bool:
    """Validate an edge instance against its EdgeDefinition.

    Args:
        edge: The concrete Edge instance to validate.
        source_type: The node-type string of the source node
                     (e.g. "Assembly", "Membrane").
        target_type: The node-type string of the target node
                     (e.g. "CoverBoard", "Drain").

    Returns:
        True when valid.

    Raises:
        EdgeValidationError: With a human-readable message on failure.
    """
    definition = EDGE_REGISTRY.get(edge.edge_type)
    if definition is None:
        raise EdgeValidationError(
            f"Unknown edge type: {edge.edge_type!r}"
        )

    # --- source type check ---
    if source_type not in definition.allowed_source_types:
        raise EdgeValidationError(
            f"Edge {edge.edge_type.value}: source type '{source_type}' "
            f"not in allowed sources {definition.allowed_source_types}"
        )

    # --- target type check ---
    if target_type not in definition.allowed_target_types:
        raise EdgeValidationError(
            f"Edge {edge.edge_type.value}: target type '{target_type}' "
            f"not in allowed targets {definition.allowed_target_types}"
        )

    # --- required metadata ---
    for field_name, field_type in definition.required_metadata.items():
        if field_name not in edge.metadata:
            raise EdgeValidationError(
                f"Edge {edge.edge_type.value}: missing required metadata "
                f"field '{field_name}'"
            )
        value = edge.metadata[field_name]
        if not isinstance(value, field_type):
            raise EdgeValidationError(
                f"Edge {edge.edge_type.value}: metadata field "
                f"'{field_name}' must be {field_type.__name__}, "
                f"got {type(value).__name__}"
            )

    # --- self-loop guard ---
    if edge.source_id == edge.target_id:
        raise EdgeValidationError(
            f"Edge {edge.edge_type.value}: self-loops are not permitted "
            f"(source_id == target_id == '{edge.source_id}')"
        )

    return True


# ---------------------------------------------------------------------------
# Helper: look up the inverse edge type enum member
# ---------------------------------------------------------------------------

def get_inverse_edge_type(edge_type: EdgeType) -> Optional[EdgeType]:
    """Return the inverse EdgeType for a given edge type, or None."""
    definition = EDGE_REGISTRY.get(edge_type)
    if definition is None or definition.inverse_edge_type is None:
        return None
    inverse_value = definition.inverse_edge_type
    for member in EdgeType:
        if member.value == inverse_value:
            return member
    return None


# ---------------------------------------------------------------------------
# Concrete Example Edges
# ---------------------------------------------------------------------------

# 1. Project contains Building
example_contains = Edge(
    edge_type=EdgeType.CONTAINS,
    source_id="project-hive215-hq",
    target_id="building-main-warehouse",
    metadata={"note": "Primary warehouse structure"},
)

# 2. Membrane supported_by CoverBoard
example_supported_by = Edge(
    edge_type=EdgeType.SUPPORTED_BY,
    source_id="layer-tpo-membrane-60mil",
    target_id="layer-densdeck-prime-coverboard",
    metadata={"attachment_method": "adhered_with_low_rise_foam"},
)

# 3. RoofArea transitions_to WallArea at parapet
example_transitions_to = Edge(
    edge_type=EdgeType.TRANSITIONS_TO,
    source_id="roof-area-section-a",
    target_id="wall-area-parapet-north",
    metadata={"transition_detail": "base_flashing_with_termination_bar"},
)

# 4. Membrane bonds_to Adhesive
example_bonds_to = Edge(
    edge_type=EdgeType.BONDS_TO,
    source_id="layer-tpo-membrane-60mil",
    target_id="material-olybond-500-adhesive",
    metadata={
        "bond_method": "bead_applied_low_rise_foam",
        "cure_time_hours": 4.0,
    },
)

# 5. HVAC curb penetrates Assembly
example_penetrates = Edge(
    edge_type=EdgeType.PENETRATES,
    source_id="penetration-rtu-3-curb",
    target_id="assembly-low-slope-tpo",
    metadata={
        "opening_diameter_in": 48.0,
        "flashing_method": "prefab_curb_flashing_with_field_seam",
    },
)

# 6. Membrane terminates_at metal edge
example_terminates_at = Edge(
    edge_type=EdgeType.TERMINATES_AT,
    source_id="layer-tpo-membrane-60mil",
    target_id="component-gravel-stop-edge-metal",
    metadata={"seal_method": "hot_air_welded_strip_over_edge_flange"},
)

# 7. FireproofingSystem protects StructuralMember
example_protects = Edge(
    edge_type=EdgeType.PROTECTS,
    source_id="system-spray-applied-fireproofing",
    target_id="member-w12x26-beam-grid-c3",
    metadata={"protection_type": "2_hour_fire_rating_spray_applied"},
)

# 8. EPDM incompatible_with PVC
example_incompatible_with = Edge(
    edge_type=EdgeType.INCOMPATIBLE_WITH,
    source_id="material-epdm-membrane",
    target_id="material-pvc-membrane",
    metadata={
        "reason": (
            "PVC plasticizers migrate into EPDM causing swelling and "
            "premature failure. A separation sheet is required if both "
            "membranes exist on the same roof."
        ),
    },
)

# 9. CoverBoard installed_before Membrane
example_installed_before = Edge(
    edge_type=EdgeType.INSTALLED_BEFORE,
    source_id="layer-densdeck-prime-coverboard",
    target_id="layer-tpo-membrane-60mil",
    metadata={"min_wait_hours": 0.0},
)

# 10. Assembly satisfies FM wind-uplift rating
example_satisfies = Edge(
    edge_type=EdgeType.SATISFIES,
    source_id="assembly-low-slope-tpo",
    target_id="standard-fm-1-90",
    metadata={"compliance_status": "approved"},
)

# 11. RoofArea drains_to roof drain
example_drains_to = Edge(
    edge_type=EdgeType.DRAINS_TO,
    source_id="roof-area-section-a",
    target_id="drain-primary-d1",
    metadata={
        "slope_in_per_ft": 0.25,
        "drainage_area_sf": 4500.0,
    },
)

# 12. Polystyrene insulation incompatible_with coal-tar pitch
example_incompatible_polystyrene = Edge(
    edge_type=EdgeType.INCOMPATIBLE_WITH,
    source_id="material-eps-insulation",
    target_id="material-coal-tar-pitch",
    metadata={
        "reason": (
            "Coal-tar solvents dissolve expanded polystyrene. "
            "Use polyisocyanurate or mineral fiber insulation instead."
        ),
    },
)

# 13. ASCE 7-22 supersedes ASCE 7-16
example_supersedes = Edge(
    edge_type=EdgeType.SUPERSEDES,
    source_id="standard-asce-7-22",
    target_id="standard-asce-7-16",
    metadata={"effective_date": "2022-01-01"},
)

# 14. Membrane overlaps Membrane (field seam)
example_overlaps = Edge(
    edge_type=EdgeType.OVERLAPS,
    source_id="layer-tpo-sheet-row-3",
    target_id="layer-tpo-sheet-row-4",
    metadata={
        "overlap_width_in": 6.0,
        "seam_type": "hot_air_welded",
    },
)

# 15. WindUpliftCalc generates WindUpliftRating
example_generates = Edge(
    edge_type=EdgeType.GENERATES,
    source_id="calc-wind-uplift-section-a",
    target_id="rating-fm-1-90-section-a",
    metadata={"tool_used": "ASCE_7_wind_calculator_v3"},
)

# 16. Revised drawing lineage_of original drawing
example_lineage = Edge(
    edge_type=EdgeType.LINEAGE_OF,
    source_id="drawing-roof-plan-rev-b",
    target_id="drawing-roof-plan-rev-a",
    metadata={
        "revision_number": 2,
        "change_description": "Added overflow scupper locations per RFI-014",
    },
)
