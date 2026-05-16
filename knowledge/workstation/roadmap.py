"""
Construction Assembly Knowledge Graph - Implementation Roadmap

Structured data defining the phased implementation plan for roofing
and fireproofing detail families, plus the overall build order for
the workstation platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RoadmapPhase:
    """A phase in the implementation roadmap for a domain."""
    phase_id: str
    phase_number: int
    domain: str  # "roofing" | "fireproofing" | "platform"
    title: str
    description: str
    detail_family_ids: tuple[str, ...]
    goals: tuple[str, ...]
    dependencies: tuple[str, ...]  # phase_ids this depends on
    estimated_complexity: str  # "low" | "medium" | "high"


@dataclass(frozen=True)
class BuildStep:
    """A single step in the overall build order."""
    step_number: int
    title: str
    description: str
    deliverables: tuple[str, ...]
    depends_on_steps: tuple[int, ...]
    category: str  # "engine" | "content" | "validation" | "render" | "ui" | "export"
    estimated_effort: str  # "small" | "medium" | "large"


# ---------------------------------------------------------------------------
# Roofing Phases
# ---------------------------------------------------------------------------

ROOFING_PHASES: tuple[RoadmapPhase, ...] = (

    RoadmapPhase(
        phase_id="roofing_phase_1",
        phase_number=1,
        domain="roofing",
        title="Fastest Path - Core Details",
        description=(
            "Ship the four highest-value roofing detail families first. "
            "These cover the most common conditions encountered on every "
            "commercial roof project and establish the rendering and "
            "validation patterns for all subsequent families."
        ),
        detail_family_ids=(
            "parapet",
            "roof_to_wall",
            "pipe_penetration",
            "edge_metal",
        ),
        goals=(
            "End-to-end generation of parapet detail from graph to SVG",
            "Validation engine running first 5 rules per family",
            "Clean view mode fully operational",
            "Inspector panel populated from graph node metadata",
            "DXF export for parapet and roof-to-wall details",
        ),
        dependencies=(),
        estimated_complexity="high",
    ),

    RoadmapPhase(
        phase_id="roofing_phase_2",
        phase_number=2,
        domain="roofing",
        title="Validation Expansion - Drainage & Corners",
        description=(
            "Add drainage-related details (drain, scupper, overflow) and "
            "geometric corner conditions. Expands the validation rule "
            "library and introduces the drainage overlay system."
        ),
        detail_family_ids=(
            "drain",
            "scupper",
            "curb",
            "overflow",
            "inside_corner",
            "outside_corner",
        ),
        goals=(
            "Drainage overlay functional with flow arrows",
            "Corner details with plan + section dual views",
            "Curb detail with equipment clearance validation",
            "Overflow height-above-primary rule enforced",
            "All Phase 1 rules regression-tested",
        ),
        dependencies=("roofing_phase_1",),
        estimated_complexity="high",
    ),

    RoadmapPhase(
        phase_id="roofing_phase_3",
        phase_number=3,
        domain="roofing",
        title="Automation - Expansion Joints & Batch Generation",
        description=(
            "Complete the roofing family set with expansion joints, then "
            "enable project-scale batch generation and export workflows."
        ),
        detail_family_ids=(
            "expansion_joint",
        ),
        goals=(
            "Expansion joint with thermal movement calculation",
            "Project-scale generation: all conditions in one pass",
            "Batch DXF/PDF export with consistent sheet layout",
            "Version comparison across regeneration cycles",
            "Full overlay system (all 6 overlays operational)",
        ),
        dependencies=("roofing_phase_2",),
        estimated_complexity="medium",
    ),
)


# ---------------------------------------------------------------------------
# Fireproofing Phases
# ---------------------------------------------------------------------------

FIREPROOFING_PHASES: tuple[RoadmapPhase, ...] = (

    RoadmapPhase(
        phase_id="fireproofing_phase_1",
        phase_number=1,
        domain="fireproofing",
        title="Basic SFRM - Beams & Columns",
        description=(
            "Establish the fireproofing domain with the two most common "
            "structural members. Focus on SFRM (spray-applied fireproofing) "
            "with UL design reference lookup."
        ),
        detail_family_ids=(
            "beam_detail",
            "column_detail",
        ),
        goals=(
            "Beam cross-section with SFRM thickness envelope",
            "Column cross-section with SFRM thickness envelope",
            "UL design number lookup and validation",
            "Thickness selection logic based on fire rating",
            "Fire boundary overlay for fireproofing nodes",
        ),
        dependencies=("roofing_phase_1",),  # reuses engine, render, UI
        estimated_complexity="medium",
    ),

    RoadmapPhase(
        phase_id="fireproofing_phase_2",
        phase_number=2,
        domain="fireproofing",
        title="Deck Interface & Intumescent",
        description=(
            "Add deck-to-beam interface details and introduce intumescent "
            "coatings as an alternative to SFRM. UL design lookup becomes "
            "the primary validation mechanism."
        ),
        detail_family_ids=(
            "deck_interface",
        ),
        goals=(
            "Deck interface with beam transition rendering",
            "Intumescent coating option in material selector",
            "UL design lookup expanded for deck assemblies",
            "Material type toggle in inspector (SFRM vs intumescent)",
            "Concrete topping thickness validation",
        ),
        dependencies=("fireproofing_phase_1",),
        estimated_complexity="medium",
    ),

    RoadmapPhase(
        phase_id="fireproofing_phase_3",
        phase_number=3,
        domain="fireproofing",
        title="Rated Penetrations & Field Verification",
        description=(
            "Complete the fireproofing domain with rated penetrations "
            "(firestop systems) and introduce field verification integration "
            "for quality assurance workflows."
        ),
        detail_family_ids=(
            "rated_penetration",
        ),
        goals=(
            "Rated penetration detail with UL system reference",
            "Firestop material selector with manufacturer listings",
            "Annular space calculation and validation",
            "Field verification checklist generation",
            "Fire boundary overlay shows all rated assemblies",
        ),
        dependencies=("fireproofing_phase_2",),
        estimated_complexity="high",
    ),
)


# ---------------------------------------------------------------------------
# Overall Build Order
# ---------------------------------------------------------------------------

OVERALL_BUILD_ORDER: tuple[BuildStep, ...] = (

    BuildStep(
        step_number=1,
        title="Graph Engine + Ontology",
        description=(
            "Build the core knowledge graph engine and freeze the node/edge "
            "ontology schema. This is the foundation everything else depends on. "
            "Schema changes after this point require migration tooling."
        ),
        deliverables=(
            "Node type registry with typed attributes",
            "Edge type registry with cardinality constraints",
            "Graph CRUD operations",
            "Deterministic ID generation",
            "Schema versioning and freeze mechanism",
        ),
        depends_on_steps=(),
        category="engine",
        estimated_effort="large",
    ),

    BuildStep(
        step_number=2,
        title="Seed Graph - Roof-Wall Transition",
        description=(
            "Populate the first real assembly graph: a roof-to-wall "
            "transition condition. This validates the ontology against "
            "actual construction knowledge and exposes schema gaps early."
        ),
        deliverables=(
            "Roof-to-wall seed graph with all required nodes",
            "Material property data for common membranes and flashings",
            "Install order metadata on edges",
            "Source reference links to code sections",
        ),
        depends_on_steps=(1,),
        category="content",
        estimated_effort="medium",
    ),

    BuildStep(
        step_number=3,
        title="Validation Engine + First 5 Roofing Rules",
        description=(
            "Build the rule execution engine and implement the first five "
            "validation rules for the roof-to-wall transition. Establishes "
            "the rule authoring pattern for all future rules."
        ),
        deliverables=(
            "Rule engine with pass/warn/fail output",
            "Rule registry with metadata",
            "RULE_ROOF_WALL_FLASHING_HEIGHT",
            "RULE_ROOF_WALL_COUNTER_FLASHING",
            "RULE_ROOF_WALL_MEMBRANE_TERMINATION",
            "RULE_ROOF_WALL_SEALANT",
            "RULE_ROOF_WALL_INSULATION_CONTINUITY",
        ),
        depends_on_steps=(2,),
        category="validation",
        estimated_effort="medium",
    ),

    BuildStep(
        step_number=4,
        title="Render Primitives + Visual System",
        description=(
            "Create the base rendering primitives: lines, fills, hatching, "
            "dimension callouts, and material patterns. These are reused by "
            "every detail family."
        ),
        deliverables=(
            "Line renderer (solid, dashed, hidden)",
            "Fill renderer (solid, hatched, gradient)",
            "Material hatching patterns (concrete, insulation, metal, membrane)",
            "Dimension line renderer with leader and text",
            "Annotation renderer (labels, callouts, notes)",
        ),
        depends_on_steps=(1,),
        category="render",
        estimated_effort="large",
    ),

    BuildStep(
        step_number=5,
        title="Clean Detail View Mode",
        description=(
            "Implement the CLEAN view mode that renders a production-quality "
            "detail drawing from the graph. This is the default landing view "
            "when a user selects a condition."
        ),
        deliverables=(
            "Graph-to-visual pipeline for roof-to-wall",
            "Layer ordering and z-index management",
            "Material fill rendering in cross-section",
            "Dimension auto-placement",
            "Clean mode viewport rendering",
        ),
        depends_on_steps=(2, 4),
        category="render",
        estimated_effort="large",
    ),

    BuildStep(
        step_number=6,
        title="SVG Export",
        description=(
            "Export the rendered detail view as SVG. This is the fastest "
            "path to a tangible output artifact and validates the entire "
            "graph-to-visual pipeline."
        ),
        deliverables=(
            "SVG serializer from render primitives",
            "Layer preservation in SVG groups",
            "Metadata embedding (node IDs, lineage)",
            "Scale and viewport mapping",
        ),
        depends_on_steps=(5,),
        category="export",
        estimated_effort="medium",
    ),

    BuildStep(
        step_number=7,
        title="Basic UI Shell (5-Zone Layout)",
        description=(
            "Build the 5-zone workstation UI shell: LEFT_NAV, TOP_BAR, "
            "CENTER viewport, RIGHT inspector, BOTTOM status strip. Wire "
            "up the project tree navigation and condition selection."
        ),
        deliverables=(
            "5-zone responsive layout",
            "Navigation rail with project tree",
            "Action bar with view mode buttons",
            "Viewport with pan, zoom, fit, reset",
            "Inspector panel with node metadata display",
            "Status strip with scale and selection info",
        ),
        depends_on_steps=(5,),
        category="ui",
        estimated_effort="large",
    ),

    BuildStep(
        step_number=8,
        title="X-Ray View Mode",
        description=(
            "Implement the X-RAY view mode with semi-transparent layers "
            "revealing internal assembly structure. Must preserve selection "
            "and camera state when switching from CLEAN mode."
        ),
        deliverables=(
            "Transparency rendering for all layer types",
            "Layer edge emphasis (wireframe overlay)",
            "State preservation on mode switch",
            "X-ray toggle in action bar",
        ),
        depends_on_steps=(5, 7),
        category="render",
        estimated_effort="medium",
    ),

    BuildStep(
        step_number=9,
        title="Fireproofing Nodes + Rules",
        description=(
            "Extend the ontology with fireproofing node types (steel members, "
            "SFRM, intumescent, UL systems) and implement beam/column "
            "validation rules."
        ),
        deliverables=(
            "Fireproofing node types in ontology",
            "Beam and column seed graphs",
            "SFRM thickness envelope logic",
            "UL design reference data structure",
            "RULE_BEAM_FIRE_RATING and RULE_COLUMN_FIRE_RATING",
            "RULE_BEAM_SFRM_THICKNESS and RULE_COLUMN_SFRM_THICKNESS",
        ),
        depends_on_steps=(3,),
        category="content",
        estimated_effort="medium",
    ),

    BuildStep(
        step_number=10,
        title="Exploded View Mode",
        description=(
            "Implement the EXPLODED view mode that separates layers "
            "vertically to show individual components and install order. "
            "Includes animated transition from CLEAN to EXPLODED."
        ),
        deliverables=(
            "Layer separation algorithm based on install order",
            "Vertical offset calculation per layer",
            "Connection lines between separated layers",
            "Install order labels",
            "Animated transition (CLEAN to EXPLODED)",
            "State preservation on mode switch",
        ),
        depends_on_steps=(5, 7),
        category="render",
        estimated_effort="medium",
    ),

    BuildStep(
        step_number=11,
        title="DXF / PDF Export",
        description=(
            "Production-quality DXF and PDF export with lineage metadata, "
            "title blocks, and scale management. DXF targets CAD workflows; "
            "PDF targets documentation and review."
        ),
        deliverables=(
            "DXF writer with layer mapping",
            "PDF writer with title block template",
            "Lineage metadata embedding",
            "Scale selection and sheet sizing",
            "Batch export for multiple conditions",
        ),
        depends_on_steps=(6,),
        category="export",
        estimated_effort="large",
    ),

    BuildStep(
        step_number=12,
        title="Full UI with Inspector",
        description=(
            "Complete the inspector panel with all metadata fields, "
            "connected object navigation, source reference links, and "
            "lineage display. Wire up the complete workflow state machine."
        ),
        deliverables=(
            "Inspector: all 10 metadata fields populated",
            "Connected object click-through navigation",
            "Source reference hyperlinks",
            "Lineage tree display",
            "Workflow state machine implementation",
            "Breadcrumb navigation",
            "Previous/Next condition arrows",
        ),
        depends_on_steps=(7,),
        category="ui",
        estimated_effort="large",
    ),

    BuildStep(
        step_number=13,
        title="Overlay System",
        description=(
            "Implement all six overlay layers that compose on top of any "
            "view mode: control layers, hidden components, drainage, fire "
            "boundary, dimensions, and notes."
        ),
        deliverables=(
            "Control layers overlay",
            "Hidden components overlay (dashed outlines)",
            "Drainage overlay with flow arrows",
            "Fire boundary overlay with rating labels",
            "Dimensions overlay (toggleable)",
            "Notes overlay (toggleable annotations)",
            "Overlay compositing engine (multiple simultaneous)",
        ),
        depends_on_steps=(8, 10, 12),
        category="render",
        estimated_effort="large",
    ),

    BuildStep(
        step_number=14,
        title="Manufacturer Compatibility Engine",
        description=(
            "Add manufacturer product data and compatibility validation. "
            "The graph can now enforce that specified products are compatible "
            "with each other and with the assembly conditions."
        ),
        deliverables=(
            "Manufacturer product node type",
            "Compatibility edge type (product-to-product)",
            "Manufacturer warranty rule framework",
            "Product substitution suggestions",
            "Inspector: manufacturer field populated with lookup",
        ),
        depends_on_steps=(3, 12),
        category="engine",
        estimated_effort="large",
    ),

    BuildStep(
        step_number=15,
        title="Project-Scale Generation",
        description=(
            "Enable generation of all detail conditions for an entire "
            "project in a single pass. Includes batch validation, batch "
            "export, and project-level reporting."
        ),
        deliverables=(
            "Project-level condition enumeration",
            "Batch graph generation",
            "Batch validation with summary report",
            "Batch DXF/PDF export with sheet index",
            "Project validation dashboard in UI",
            "Version comparison across regeneration cycles",
        ),
        depends_on_steps=(11, 13, 14),
        category="engine",
        estimated_effort="large",
    ),
)
