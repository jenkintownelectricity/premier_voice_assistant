"""
Construction Assembly Knowledge Graph - Detail Families

Defines roofing and fireproofing detail families with their graph input
requirements, validation rules, artifact outputs, render needs, and
implementation priority.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DetailFamily:
    """A detail family represents a category of construction assembly details.

    Each family declares the graph inputs it needs, the validation rules it
    must satisfy, the artifacts it can produce, and metadata used to plan
    rendering, UI integration, and implementation sequencing.
    """
    family_id: str
    display_name: str
    domain: str  # "roofing" | "fireproofing"

    # Graph requirements
    required_graph_inputs: tuple[str, ...]
    required_validation_rules: tuple[str, ...]
    minimum_viable_rules: tuple[str, ...]

    # Output
    output_artifact_types: tuple[str, ...]

    # Render & UI
    render_requirements: tuple[str, ...]
    ui_requirements: tuple[str, ...]

    # Planning
    complexity_level: int  # 1 (simple) to 5 (complex)
    implementation_priority: int  # 1 = highest priority


# ---------------------------------------------------------------------------
# Roofing Detail Families
# ---------------------------------------------------------------------------

ROOFING_DETAIL_FAMILIES: dict[str, DetailFamily] = {

    "parapet": DetailFamily(
        family_id="parapet",
        display_name="Parapet",
        domain="roofing",
        required_graph_inputs=(
            "wall_node",
            "membrane_node",
            "flashing_node",
            "coping_node",
            "insulation_node",
            "substrate_node",
        ),
        required_validation_rules=(
            "RULE_PARAPET_MIN_HEIGHT",
            "RULE_PARAPET_FLASHING_OVERLAP",
            "RULE_PARAPET_COPING_OVERHANG",
            "RULE_PARAPET_MEMBRANE_TERMINATION",
            "RULE_PARAPET_DRAINAGE_CLEARANCE",
        ),
        minimum_viable_rules=(
            "RULE_PARAPET_MIN_HEIGHT",
            "RULE_PARAPET_FLASHING_OVERLAP",
            "RULE_PARAPET_MEMBRANE_TERMINATION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "wall_cross_section",
            "membrane_layer_fill",
            "flashing_profile",
            "coping_cap_profile",
            "dimension_lines",
            "material_hatching",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "overlay_drainage",
            "exploded_view_support",
        ),
        complexity_level=3,
        implementation_priority=1,
    ),

    "curb": DetailFamily(
        family_id="curb",
        display_name="Curb",
        domain="roofing",
        required_graph_inputs=(
            "curb_frame_node",
            "membrane_node",
            "flashing_node",
            "insulation_node",
            "equipment_mount_node",
            "substrate_node",
        ),
        required_validation_rules=(
            "RULE_CURB_MIN_HEIGHT",
            "RULE_CURB_FLASHING_OVERLAP",
            "RULE_CURB_INSULATION_CONTINUITY",
            "RULE_CURB_MEMBRANE_TERMINATION",
            "RULE_CURB_EQUIPMENT_CLEARANCE",
        ),
        minimum_viable_rules=(
            "RULE_CURB_MIN_HEIGHT",
            "RULE_CURB_FLASHING_OVERLAP",
            "RULE_CURB_MEMBRANE_TERMINATION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "curb_cross_section",
            "membrane_wrap",
            "flashing_profile",
            "equipment_mount_outline",
            "insulation_fill",
            "dimension_lines",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "exploded_view_support",
        ),
        complexity_level=3,
        implementation_priority=2,
    ),

    "drain": DetailFamily(
        family_id="drain",
        display_name="Drain",
        domain="roofing",
        required_graph_inputs=(
            "drain_body_node",
            "membrane_node",
            "clamping_ring_node",
            "insulation_node",
            "substrate_node",
            "leader_pipe_node",
            "tapered_insulation_node",
        ),
        required_validation_rules=(
            "RULE_DRAIN_SUMP_DEPTH",
            "RULE_DRAIN_MEMBRANE_CLAMPING",
            "RULE_DRAIN_STRAINER_PRESENT",
            "RULE_DRAIN_INSULATION_TAPER",
            "RULE_DRAIN_LEADER_SIZE",
            "RULE_DRAIN_FLOW_RATE",
        ),
        minimum_viable_rules=(
            "RULE_DRAIN_SUMP_DEPTH",
            "RULE_DRAIN_MEMBRANE_CLAMPING",
            "RULE_DRAIN_STRAINER_PRESENT",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "drain_body_section",
            "clamping_ring_detail",
            "membrane_interface",
            "tapered_insulation_fill",
            "leader_pipe_connection",
            "dimension_lines",
            "drainage_flow_arrows",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "overlay_drainage",
            "exploded_view_support",
        ),
        complexity_level=4,
        implementation_priority=2,
    ),

    "scupper": DetailFamily(
        family_id="scupper",
        display_name="Scupper",
        domain="roofing",
        required_graph_inputs=(
            "scupper_body_node",
            "wall_node",
            "membrane_node",
            "flashing_node",
            "conductor_head_node",
            "substrate_node",
        ),
        required_validation_rules=(
            "RULE_SCUPPER_SIZE",
            "RULE_SCUPPER_HEIGHT_ABOVE_MEMBRANE",
            "RULE_SCUPPER_FLASHING_INTEGRATION",
            "RULE_SCUPPER_FLOW_CAPACITY",
            "RULE_SCUPPER_CONDUCTOR_SIZE",
        ),
        minimum_viable_rules=(
            "RULE_SCUPPER_SIZE",
            "RULE_SCUPPER_HEIGHT_ABOVE_MEMBRANE",
            "RULE_SCUPPER_FLASHING_INTEGRATION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "wall_opening_section",
            "scupper_body_profile",
            "membrane_interface",
            "flashing_wrap",
            "conductor_connection",
            "dimension_lines",
            "drainage_flow_arrows",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "overlay_drainage",
            "exploded_view_support",
        ),
        complexity_level=3,
        implementation_priority=2,
    ),

    "pipe_penetration": DetailFamily(
        family_id="pipe_penetration",
        display_name="Pipe Penetration",
        domain="roofing",
        required_graph_inputs=(
            "pipe_node",
            "membrane_node",
            "flashing_boot_node",
            "sealant_node",
            "insulation_node",
            "substrate_node",
        ),
        required_validation_rules=(
            "RULE_PENETRATION_FLASHING_OVERLAP",
            "RULE_PENETRATION_SEALANT_TYPE",
            "RULE_PENETRATION_MEMBRANE_TERMINATION",
            "RULE_PENETRATION_PITCH_POCKET_DEPTH",
            "RULE_PENETRATION_CLEARANCE_FROM_EDGE",
        ),
        minimum_viable_rules=(
            "RULE_PENETRATION_FLASHING_OVERLAP",
            "RULE_PENETRATION_SEALANT_TYPE",
            "RULE_PENETRATION_MEMBRANE_TERMINATION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "pipe_cross_section",
            "flashing_boot_profile",
            "membrane_interface",
            "sealant_bead",
            "dimension_lines",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "exploded_view_support",
        ),
        complexity_level=2,
        implementation_priority=1,
    ),

    "edge_metal": DetailFamily(
        family_id="edge_metal",
        display_name="Edge Metal",
        domain="roofing",
        required_graph_inputs=(
            "edge_metal_node",
            "membrane_node",
            "fascia_node",
            "cleat_node",
            "substrate_node",
            "insulation_node",
        ),
        required_validation_rules=(
            "RULE_EDGE_METAL_WIND_RATING",
            "RULE_EDGE_METAL_ANSI_SPRI_ES1",
            "RULE_EDGE_METAL_OVERLAP",
            "RULE_EDGE_METAL_CLEAT_SPACING",
            "RULE_EDGE_METAL_MEMBRANE_TERMINATION",
        ),
        minimum_viable_rules=(
            "RULE_EDGE_METAL_WIND_RATING",
            "RULE_EDGE_METAL_ANSI_SPRI_ES1",
            "RULE_EDGE_METAL_MEMBRANE_TERMINATION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "edge_metal_profile",
            "cleat_detail",
            "membrane_termination",
            "fascia_profile",
            "dimension_lines",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "exploded_view_support",
        ),
        complexity_level=2,
        implementation_priority=1,
    ),

    "expansion_joint": DetailFamily(
        family_id="expansion_joint",
        display_name="Expansion Joint",
        domain="roofing",
        required_graph_inputs=(
            "expansion_joint_cover_node",
            "curb_node_a",
            "curb_node_b",
            "membrane_node_a",
            "membrane_node_b",
            "insulation_node",
            "substrate_node",
        ),
        required_validation_rules=(
            "RULE_EXPANSION_JOINT_MOVEMENT_CAPACITY",
            "RULE_EXPANSION_JOINT_HEIGHT",
            "RULE_EXPANSION_JOINT_MEMBRANE_TERMINATION",
            "RULE_EXPANSION_JOINT_WATERPROOFING",
            "RULE_EXPANSION_JOINT_THERMAL_CALC",
        ),
        minimum_viable_rules=(
            "RULE_EXPANSION_JOINT_MOVEMENT_CAPACITY",
            "RULE_EXPANSION_JOINT_HEIGHT",
            "RULE_EXPANSION_JOINT_MEMBRANE_TERMINATION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "dual_curb_cross_section",
            "expansion_cover_profile",
            "membrane_terminations",
            "movement_arrows",
            "dimension_lines",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "exploded_view_support",
            "movement_animation",
        ),
        complexity_level=4,
        implementation_priority=3,
    ),

    "roof_to_wall": DetailFamily(
        family_id="roof_to_wall",
        display_name="Roof-to-Wall Transition",
        domain="roofing",
        required_graph_inputs=(
            "wall_node",
            "membrane_node",
            "base_flashing_node",
            "counter_flashing_node",
            "insulation_node",
            "substrate_node",
            "sealant_node",
        ),
        required_validation_rules=(
            "RULE_ROOF_WALL_FLASHING_HEIGHT",
            "RULE_ROOF_WALL_COUNTER_FLASHING",
            "RULE_ROOF_WALL_MEMBRANE_TERMINATION",
            "RULE_ROOF_WALL_SEALANT",
            "RULE_ROOF_WALL_INSULATION_CONTINUITY",
        ),
        minimum_viable_rules=(
            "RULE_ROOF_WALL_FLASHING_HEIGHT",
            "RULE_ROOF_WALL_COUNTER_FLASHING",
            "RULE_ROOF_WALL_MEMBRANE_TERMINATION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "wall_cross_section",
            "base_flashing_profile",
            "counter_flashing_profile",
            "membrane_layer_fill",
            "sealant_bead",
            "dimension_lines",
            "material_hatching",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "exploded_view_support",
        ),
        complexity_level=3,
        implementation_priority=1,
    ),

    "inside_corner": DetailFamily(
        family_id="inside_corner",
        display_name="Inside Corner",
        domain="roofing",
        required_graph_inputs=(
            "wall_node_a",
            "wall_node_b",
            "membrane_node",
            "flashing_node",
            "corner_patch_node",
            "substrate_node",
        ),
        required_validation_rules=(
            "RULE_INSIDE_CORNER_PATCH_SIZE",
            "RULE_INSIDE_CORNER_OVERLAP",
            "RULE_INSIDE_CORNER_MEMBRANE_CONTINUITY",
            "RULE_INSIDE_CORNER_FLASHING_WRAP",
        ),
        minimum_viable_rules=(
            "RULE_INSIDE_CORNER_PATCH_SIZE",
            "RULE_INSIDE_CORNER_OVERLAP",
            "RULE_INSIDE_CORNER_MEMBRANE_CONTINUITY",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "corner_plan_view",
            "corner_section_view",
            "patch_overlay",
            "membrane_wrap",
            "dimension_lines",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "dual_view_plan_and_section",
        ),
        complexity_level=3,
        implementation_priority=2,
    ),

    "outside_corner": DetailFamily(
        family_id="outside_corner",
        display_name="Outside Corner",
        domain="roofing",
        required_graph_inputs=(
            "wall_node_a",
            "wall_node_b",
            "membrane_node",
            "flashing_node",
            "corner_patch_node",
            "substrate_node",
        ),
        required_validation_rules=(
            "RULE_OUTSIDE_CORNER_PATCH_SIZE",
            "RULE_OUTSIDE_CORNER_OVERLAP",
            "RULE_OUTSIDE_CORNER_MEMBRANE_CONTINUITY",
            "RULE_OUTSIDE_CORNER_WIND_UPLIFT",
        ),
        minimum_viable_rules=(
            "RULE_OUTSIDE_CORNER_PATCH_SIZE",
            "RULE_OUTSIDE_CORNER_OVERLAP",
            "RULE_OUTSIDE_CORNER_MEMBRANE_CONTINUITY",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "corner_plan_view",
            "corner_section_view",
            "patch_overlay",
            "membrane_wrap",
            "dimension_lines",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "dual_view_plan_and_section",
        ),
        complexity_level=3,
        implementation_priority=2,
    ),

    "overflow": DetailFamily(
        family_id="overflow",
        display_name="Overflow Drain / Scupper",
        domain="roofing",
        required_graph_inputs=(
            "overflow_body_node",
            "membrane_node",
            "flashing_node",
            "wall_node",
            "substrate_node",
            "primary_drain_reference_node",
        ),
        required_validation_rules=(
            "RULE_OVERFLOW_HEIGHT_ABOVE_PRIMARY",
            "RULE_OVERFLOW_CAPACITY",
            "RULE_OVERFLOW_FLASHING_INTEGRATION",
            "RULE_OVERFLOW_VISIBILITY",
        ),
        minimum_viable_rules=(
            "RULE_OVERFLOW_HEIGHT_ABOVE_PRIMARY",
            "RULE_OVERFLOW_CAPACITY",
            "RULE_OVERFLOW_FLASHING_INTEGRATION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "overflow_body_section",
            "height_relationship_to_primary",
            "membrane_interface",
            "flashing_wrap",
            "dimension_lines",
            "drainage_flow_arrows",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "overlay_drainage",
            "linked_primary_drain_highlight",
        ),
        complexity_level=3,
        implementation_priority=2,
    ),
}


# ---------------------------------------------------------------------------
# Fireproofing Detail Families
# ---------------------------------------------------------------------------

FIREPROOFING_DETAIL_FAMILIES: dict[str, DetailFamily] = {

    "beam_detail": DetailFamily(
        family_id="beam_detail",
        display_name="Beam Fireproofing Detail",
        domain="fireproofing",
        required_graph_inputs=(
            "steel_beam_node",
            "fireproofing_material_node",
            "deck_node",
            "connection_node",
        ),
        required_validation_rules=(
            "RULE_BEAM_FIRE_RATING",
            "RULE_BEAM_SFRM_THICKNESS",
            "RULE_BEAM_UL_DESIGN",
            "RULE_BEAM_COVERAGE_CONTINUITY",
            "RULE_BEAM_EDGE_CLEARANCE",
        ),
        minimum_viable_rules=(
            "RULE_BEAM_FIRE_RATING",
            "RULE_BEAM_SFRM_THICKNESS",
            "RULE_BEAM_UL_DESIGN",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "beam_cross_section",
            "sfrm_thickness_envelope",
            "deck_interface_line",
            "thickness_dimension_callouts",
            "ul_design_reference_label",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "thickness_selection_control",
            "ul_design_lookup_link",
        ),
        complexity_level=2,
        implementation_priority=1,
    ),

    "column_detail": DetailFamily(
        family_id="column_detail",
        display_name="Column Fireproofing Detail",
        domain="fireproofing",
        required_graph_inputs=(
            "steel_column_node",
            "fireproofing_material_node",
            "base_plate_node",
            "connection_node",
        ),
        required_validation_rules=(
            "RULE_COLUMN_FIRE_RATING",
            "RULE_COLUMN_SFRM_THICKNESS",
            "RULE_COLUMN_UL_DESIGN",
            "RULE_COLUMN_COVERAGE_CONTINUITY",
            "RULE_COLUMN_BASE_TERMINATION",
        ),
        minimum_viable_rules=(
            "RULE_COLUMN_FIRE_RATING",
            "RULE_COLUMN_SFRM_THICKNESS",
            "RULE_COLUMN_UL_DESIGN",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "column_cross_section",
            "sfrm_thickness_envelope",
            "base_plate_detail",
            "thickness_dimension_callouts",
            "ul_design_reference_label",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "thickness_selection_control",
            "ul_design_lookup_link",
        ),
        complexity_level=2,
        implementation_priority=1,
    ),

    "deck_interface": DetailFamily(
        family_id="deck_interface",
        display_name="Deck Interface Detail",
        domain="fireproofing",
        required_graph_inputs=(
            "deck_node",
            "beam_node",
            "fireproofing_material_node",
            "concrete_topping_node",
            "shear_stud_node",
        ),
        required_validation_rules=(
            "RULE_DECK_FIRE_RATING",
            "RULE_DECK_UNDERSIDE_COVERAGE",
            "RULE_DECK_BEAM_TRANSITION",
            "RULE_DECK_CONCRETE_THICKNESS",
            "RULE_DECK_UL_DESIGN",
            "RULE_DECK_INTUMESCENT_COMPATIBILITY",
        ),
        minimum_viable_rules=(
            "RULE_DECK_FIRE_RATING",
            "RULE_DECK_UNDERSIDE_COVERAGE",
            "RULE_DECK_BEAM_TRANSITION",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "deck_cross_section",
            "beam_to_deck_interface",
            "fireproofing_envelope",
            "concrete_topping_fill",
            "shear_stud_detail",
            "dimension_lines",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "thickness_selection_control",
            "material_type_toggle",
        ),
        complexity_level=3,
        implementation_priority=2,
    ),

    "rated_penetration": DetailFamily(
        family_id="rated_penetration",
        display_name="Rated Penetration / Firestop",
        domain="fireproofing",
        required_graph_inputs=(
            "rated_assembly_node",
            "penetrating_item_node",
            "firestop_material_node",
            "annular_space_node",
            "ul_system_node",
        ),
        required_validation_rules=(
            "RULE_PENETRATION_UL_SYSTEM",
            "RULE_PENETRATION_ANNULAR_SPACE",
            "RULE_PENETRATION_FIRESTOP_DEPTH",
            "RULE_PENETRATION_THROUGH_ITEM_TYPE",
            "RULE_PENETRATION_RATING_MATCH",
            "RULE_PENETRATION_MANUFACTURER_LISTING",
        ),
        minimum_viable_rules=(
            "RULE_PENETRATION_UL_SYSTEM",
            "RULE_PENETRATION_ANNULAR_SPACE",
            "RULE_PENETRATION_FIRESTOP_DEPTH",
        ),
        output_artifact_types=("dxf", "pdf", "svg"),
        render_requirements=(
            "rated_assembly_section",
            "penetrating_item_profile",
            "firestop_material_fill",
            "annular_space_callout",
            "ul_system_reference_label",
            "dimension_lines",
        ),
        ui_requirements=(
            "layer_stack_navigator",
            "click_to_inspect_layers",
            "ul_system_lookup_link",
            "firestop_material_selector",
            "overlay_fire_boundary",
        ),
        complexity_level=4,
        implementation_priority=3,
    ),
}


# ---------------------------------------------------------------------------
# Combined Registry
# ---------------------------------------------------------------------------

ALL_DETAIL_FAMILIES: dict[str, DetailFamily] = {
    **ROOFING_DETAIL_FAMILIES,
    **FIREPROOFING_DETAIL_FAMILIES,
}
