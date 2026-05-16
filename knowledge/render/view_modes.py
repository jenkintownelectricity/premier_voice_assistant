"""
Construction Assembly Knowledge Graph - View Modes
====================================================

Defines the three primary rendering view modes that control how an assembly
detail is visualized.  Each mode specifies which visual elements are shown,
suppressed, or emphasized, and the rules governing their appearance.

View Mode 1 - CLEAN DETAIL:   Production-ready technical detail
View Mode 2 - X-RAY ASSEMBLY: Transparent analysis with control-layer coding
View Mode 3 - EXPLODED ASSEMBLY: Separated layers with installation sequence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.render.primitives import ViewMode


# ---------------------------------------------------------------------------
# View mode configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ViewModeConfig:
    """
    Complete configuration for a rendering view mode.

    Attributes:
        mode_id:                ViewMode enum value
        display_name:           Human-readable label
        use_case:               When to use this mode
        visual_rules:           Key/value visual rule overrides
        suppressed_elements:    Primitive or element types hidden in this mode
        emphasized_elements:    Primitive or element types given extra emphasis
        required_graph_mappings: Graph data the mode requires to render correctly
    """
    mode_id: ViewMode
    display_name: str
    use_case: str
    visual_rules: dict[str, Any]
    suppressed_elements: tuple[str, ...]
    emphasized_elements: tuple[str, ...]
    required_graph_mappings: tuple[str, ...]


# ---------------------------------------------------------------------------
# VIEW MODE 1 - CLEAN DETAIL
# ---------------------------------------------------------------------------

VIEW_MODE_CLEAN_DETAIL = ViewModeConfig(
    mode_id=ViewMode.CLEAN_DETAIL,
    display_name="Clean Detail",
    use_case=(
        "Production-oriented technical detail suitable for construction "
        "documents, submittals, and shop drawings.  Sheet-ready output with "
        "standard lineweights, hatching, dimensions, and callouts."
    ),
    visual_rules={
        # Lineweight behavior
        "use_standard_lineweights": True,
        "lineweight_override": None,

        # Hatching
        "show_hatches": True,
        "hatch_opacity": 1.0,

        # Dimensions and annotations
        "show_dimensions": True,
        "show_callouts": True,
        "show_leader_lines": True,
        "show_notes": True,

        # Transparency
        "transparency_enabled": False,
        "base_opacity": 1.0,

        # Colors
        "color_mode": "monochrome",  # "monochrome" | "control_layers" | "material"
        "background": "#FFFFFF",

        # Scale
        "diagrammatic_scaling": True,
        "minimum_layer_thickness_mm": 2.0,

        # Overlays allowed
        "allowed_overlays": [
            "slope_arrows",
            "drainage_arrows",
            "overlap_direction",
            "fastener_pattern",
            "fire_boundary",
        ],
    },
    suppressed_elements=(
        "construction_sequence_markers",
        "control_layer_highlights",
        "transparency_masks",
        "exploded_offset_transforms",
        "connector_lines",
        "installation_sequence_numbers",
    ),
    emphasized_elements=(
        "dimensions",
        "callouts",
        "hatches",
        "section_cut_lines",
    ),
    required_graph_mappings=(
        "node.attrs.thickness",
        "node.attrs.material_name",
        "node.node_type",
        "node.render_hints",
        "edge.edge_type",
        "edge.metadata.overlap_distance",
    ),
)


# ---------------------------------------------------------------------------
# VIEW MODE 2 - X-RAY ASSEMBLY
# ---------------------------------------------------------------------------

VIEW_MODE_XRAY = ViewModeConfig(
    mode_id=ViewMode.XRAY,
    display_name="X-Ray Assembly",
    use_case=(
        "Analytical view where all layers are semi-transparent, hidden "
        "components (fasteners, anchors, concealed overlaps) are fully "
        "visible, and continuity control layers are color-coded.  Used for "
        "design review, forensic analysis, and teaching."
    ),
    visual_rules={
        # Lineweight behavior
        "use_standard_lineweights": True,
        "lineweight_override": None,

        # Hatching
        "show_hatches": True,
        "hatch_opacity": 0.3,   # reduced for transparency

        # Dimensions and annotations
        "show_dimensions": False,  # suppressed by default, toggleable
        "show_callouts": True,
        "show_leader_lines": True,
        "show_notes": False,
        "dimensions_toggleable": True,

        # Transparency
        "transparency_enabled": True,
        "base_opacity": 0.55,
        "opacity_by_importance": {
            "primary": 0.70,     # membrane, deck, structural
            "secondary": 0.55,   # insulation, cover board, flashing
            "tertiary": 0.40,    # vapor retarder, air barrier, sealant
        },
        "importance_map": {
            "deck": "primary",
            "structural": "primary",
            "membrane": "primary",
            "insulation": "secondary",
            "cover_board": "secondary",
            "flashing": "secondary",
            "counter_flashing": "secondary",
            "coping": "secondary",
            "parapet_cap": "secondary",
            "wall_substrate": "primary",
            "wall_sheathing": "secondary",
            "vapor_retarder": "tertiary",
            "air_barrier": "tertiary",
            "sealant": "tertiary",
            "adhesive": "tertiary",
            "termination": "tertiary",
            "fastener": "tertiary",
        },

        # Colors shift to control-layer scheme
        "color_mode": "control_layers",
        "background": "#1A1A2E",  # dark for contrast with colored layers

        # Scale
        "diagrammatic_scaling": True,
        "minimum_layer_thickness_mm": 2.0,

        # Overlays allowed
        "allowed_overlays": [
            "slope_arrows",
            "drainage_arrows",
            "overlap_direction",
            "fastener_pattern",
            "fire_boundary",
            "control_layers",
        ],

        # Hidden component visibility
        "show_hidden_fasteners": True,
        "show_concealed_overlaps": True,
        "show_anchor_points": True,
    },
    suppressed_elements=(
        "construction_sequence_markers",
        "exploded_offset_transforms",
        "installation_sequence_numbers",
        # dimensions suppressed by default but toggleable
    ),
    emphasized_elements=(
        "attachment_points",
        "termination_details",
        "overlap_extents",
        "control_layer_highlights",
        "fastener_locations",
        "concealed_components",
    ),
    required_graph_mappings=(
        "node.attrs.thickness",
        "node.attrs.material_name",
        "node.node_type",
        "node.render_hints",
        "node.attrs.control_layers",
        "edge.edge_type",
        "edge.metadata.overlap_distance",
        "edge.metadata.attachment_type",
        "edge.metadata.fastener_spacing",
    ),
)


# ---------------------------------------------------------------------------
# VIEW MODE 3 - EXPLODED ASSEMBLY
# ---------------------------------------------------------------------------

VIEW_MODE_EXPLODED = ViewModeConfig(
    mode_id=ViewMode.EXPLODED,
    display_name="Exploded Assembly",
    use_case=(
        "Each layer is separated vertically with configurable spacing, "
        "displayed in bottom-to-top installation order.  Ghost connector "
        "lines show attachment relationships.  Ideal for installation "
        "training, material take-offs, and assembly comprehension."
    ),
    visual_rules={
        # Lineweight behavior
        "use_standard_lineweights": True,
        "lineweight_override": None,

        # Hatching - simplified for clarity
        "show_hatches": True,
        "hatch_opacity": 0.6,
        "hatch_simplified": True,  # reduced pattern density

        # Dimensions and annotations
        "show_dimensions": False,
        "show_callouts": True,
        "show_leader_lines": True,
        "show_notes": False,

        # Transparency
        "transparency_enabled": False,
        "base_opacity": 1.0,

        # Colors
        "color_mode": "material",  # each layer gets its material color
        "background": "#FFFFFF",

        # Scale
        "diagrammatic_scaling": True,
        "minimum_layer_thickness_mm": 3.0,  # thicker minimum for separated view

        # Exploded-specific settings
        "layer_spacing_mm": 12.0,
        "assembly_direction": "bottom_to_top",  # deck at bottom
        "show_connector_lines": True,
        "connector_line_style": "dashed",
        "connector_line_color": "#BDBDBD",
        "connector_line_weight_mm": 0.09,

        # Layer labels
        "show_layer_labels": True,
        "label_position": "right",  # "left" | "right" | "both"
        "show_installation_sequence_numbers": True,
        "sequence_number_position": "left",

        # Overlays allowed
        "allowed_overlays": [
            "overlap_direction",
        ],
    },
    suppressed_elements=(
        "dimensions",
        "section_cut_symbols",
        "control_layer_highlights",
        "transparency_masks",
    ),
    emphasized_elements=(
        "layer_identity_labels",
        "installation_sequence_numbers",
        "connector_lines",
        "layer_order",
        "attachment_relationships",
    ),
    required_graph_mappings=(
        "node.attrs.thickness",
        "node.attrs.material_name",
        "node.node_type",
        "node.install_sequence",
        "node.render_hints",
        "edge.edge_type",
        "edge.metadata.attachment_type",
    ),
)


# ---------------------------------------------------------------------------
# Registry and lookup
# ---------------------------------------------------------------------------

VIEW_MODES: dict[ViewMode, ViewModeConfig] = {
    ViewMode.CLEAN_DETAIL: VIEW_MODE_CLEAN_DETAIL,
    ViewMode.XRAY: VIEW_MODE_XRAY,
    ViewMode.EXPLODED: VIEW_MODE_EXPLODED,
}

# Also index by string for convenience
_VIEW_MODES_BY_STR: dict[str, ViewModeConfig] = {
    cfg.mode_id.value: cfg for cfg in VIEW_MODES.values()
}


def get_view_mode(mode: str | ViewMode) -> ViewModeConfig:
    """
    Look up a view mode configuration by enum or string.

    Raises:
        ValueError: If the mode is not recognized.
    """
    if isinstance(mode, ViewMode):
        config = VIEW_MODES.get(mode)
    else:
        config = _VIEW_MODES_BY_STR.get(mode)

    if config is None:
        valid = ", ".join(v.value for v in ViewMode)
        raise ValueError(
            f"Unknown view mode '{mode}'. Valid modes: {valid}"
        )
    return config


# Convenience aliases matching the __init__.py exports
CleanDetailMode = VIEW_MODE_CLEAN_DETAIL
XRayAssemblyMode = VIEW_MODE_XRAY
ExplodedAssemblyMode = VIEW_MODE_EXPLODED
