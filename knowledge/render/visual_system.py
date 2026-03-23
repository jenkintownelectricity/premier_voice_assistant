"""
Construction Assembly Knowledge Graph - Visual System
======================================================

The authoritative visual ruleset for all generated construction details.

Governs:
    A. Lineweight hierarchy (node type -> default pen weight)
    B. Hatch discipline (material family -> pattern, no exceptions)
    C. Control layer highlighting (continuity layers -> color emphasis)
    D. Layer spacing rules (diagrammatic scaling for readability)
    E. Overlay system (toggleable information layers)

Imported by the ArtifactGenerator and view-mode resolvers to ensure every
drawing produced by the system is visually consistent and code-compliant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from knowledge.render.primitives import (
    HatchPattern,
    Lineweight,
    ViewMode,
)


# ---------------------------------------------------------------------------
# A. Lineweight Hierarchy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LineweightMapping:
    """Maps a graph node type to its default lineweight."""
    node_type: str
    lineweight: Lineweight
    rationale: str


# Authoritative mapping: node_type -> Lineweight
_LINEWEIGHT_MAP: dict[str, Lineweight] = {
    # HEAVY (0.70 mm) - Section cuts, primary cut objects
    "deck": Lineweight.HEAVY,
    "structural": Lineweight.HEAVY,
    "wall_substrate": Lineweight.HEAVY,

    # MEDIUM (0.35 mm) - Primary visible objects
    "membrane": Lineweight.MEDIUM,
    "insulation": Lineweight.MEDIUM,
    "cover_board": Lineweight.MEDIUM,
    "flashing": Lineweight.MEDIUM,
    "counter_flashing": Lineweight.MEDIUM,
    "coping": Lineweight.MEDIUM,
    "parapet_cap": Lineweight.MEDIUM,
    "wall_sheathing": Lineweight.MEDIUM,

    # LIGHT (0.18 mm) - Secondary components
    "vapor_retarder": Lineweight.LIGHT,
    "air_barrier": Lineweight.LIGHT,
    "adhesive": Lineweight.LIGHT,
    "sealant": Lineweight.LIGHT,
    "termination": Lineweight.LIGHT,

    # THIN (0.09 mm) - Accessories, hidden, reference
    "fastener": Lineweight.THIN,
    "generic": Lineweight.THIN,
}

_RATIONALE: dict[str, str] = {
    "deck": "Primary structural cut - heaviest pen weight for section emphasis",
    "structural": "Load-bearing member always reads as the dominant line",
    "wall_substrate": "Wall structure cut through section plane",
    "membrane": "Primary waterproofing surface, must be clearly visible",
    "insulation": "Bulk layer visible in section with distinct hatch",
    "cover_board": "Protective layer between insulation and membrane",
    "flashing": "Transition/termination element, clear visibility required",
    "counter_flashing": "Overlapping weather protection, medium emphasis",
    "coping": "Top-of-wall cap, visible profile element",
    "parapet_cap": "Parapet termination detail, visible profile element",
    "wall_sheathing": "Exterior sheathing in wall section",
    "vapor_retarder": "Thin continuous layer, lighter than primary components",
    "air_barrier": "Thin continuous layer, lighter than primary components",
    "adhesive": "Bonding layer too thin for heavy line, but must be present",
    "sealant": "Joint seal, small but intentional",
    "termination": "Bar or clip, secondary hardware",
    "fastener": "Thinnest pen - small hardware that should not dominate",
    "generic": "Catch-all, minimal visual weight",
}

LINEWEIGHT_MAPPINGS: list[LineweightMapping] = [
    LineweightMapping(
        node_type=nt,
        lineweight=lw,
        rationale=_RATIONALE.get(nt, ""),
    )
    for nt, lw in _LINEWEIGHT_MAP.items()
]


class LineweightHierarchy:
    """Resolve the correct lineweight for any node type."""

    @staticmethod
    def get(node_type: str) -> Lineweight:
        """Return the lineweight for a node type, defaulting to THIN."""
        return _LINEWEIGHT_MAP.get(node_type, Lineweight.THIN)

    @staticmethod
    def get_mm(node_type: str) -> float:
        """Return the lineweight in millimeters."""
        return LineweightHierarchy.get(node_type).mm

    @staticmethod
    def all_mappings() -> dict[str, Lineweight]:
        """Return the full node-type -> Lineweight map."""
        return dict(_LINEWEIGHT_MAP)


# ---------------------------------------------------------------------------
# B. Hatch Discipline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HatchSpec:
    """Complete hatch specification for a material family."""
    pattern: HatchPattern
    description: str
    base_color: str          # hex color
    angle: float             # primary angle in degrees
    secondary_angle: float   # for cross-hatch patterns (0 = none)
    spacing: float           # distance between pattern strokes in mm
    includes_dots: bool      # dot overlay (concrete, sealant)
    includes_circles: bool   # circle overlay (insulation cells, gravel)
    includes_wavy: bool      # wavy strokes (AVB)


# One pattern per material family.  No deviation allowed.
_HATCH_SPECS: dict[HatchPattern, HatchSpec] = {
    HatchPattern.CONCRETE: HatchSpec(
        pattern=HatchPattern.CONCRETE,
        description="45-degree cross-hatch with dots",
        base_color="#A0A0A0",
        angle=45.0,
        secondary_angle=135.0,
        spacing=3.0,
        includes_dots=True,
        includes_circles=False,
        includes_wavy=False,
    ),
    HatchPattern.METAL_DECK: HatchSpec(
        pattern=HatchPattern.METAL_DECK,
        description="Alternating diagonal lines representing flutes",
        base_color="#707070",
        angle=60.0,
        secondary_angle=120.0,
        spacing=4.0,
        includes_dots=False,
        includes_circles=False,
        includes_wavy=False,
    ),
    HatchPattern.RIGID_INSULATION: HatchSpec(
        pattern=HatchPattern.RIGID_INSULATION,
        description="Diagonal lines with circles representing closed cells",
        base_color="#D4A843",
        angle=45.0,
        secondary_angle=0.0,
        spacing=5.0,
        includes_dots=False,
        includes_circles=True,
        includes_wavy=False,
    ),
    HatchPattern.MEMBRANE: HatchSpec(
        pattern=HatchPattern.MEMBRANE,
        description="Solid thin fill",
        base_color="#333333",
        angle=0.0,
        secondary_angle=0.0,
        spacing=0.0,  # solid fill, no pattern strokes
        includes_dots=False,
        includes_circles=False,
        includes_wavy=False,
    ),
    HatchPattern.SEALANT: HatchSpec(
        pattern=HatchPattern.SEALANT,
        description="Stipple / dots",
        base_color="#5A5A5A",
        angle=0.0,
        secondary_angle=0.0,
        spacing=1.5,
        includes_dots=True,
        includes_circles=False,
        includes_wavy=False,
    ),
    HatchPattern.FLASHING: HatchSpec(
        pattern=HatchPattern.FLASHING,
        description="Cross-hatch tight",
        base_color="#606060",
        angle=45.0,
        secondary_angle=135.0,
        spacing=1.5,
        includes_dots=False,
        includes_circles=False,
        includes_wavy=False,
    ),
    HatchPattern.FIREPROOFING: HatchSpec(
        pattern=HatchPattern.FIREPROOFING,
        description="Irregular stipple representing spray texture",
        base_color="#B8860B",
        angle=0.0,
        secondary_angle=0.0,
        spacing=2.0,
        includes_dots=True,
        includes_circles=False,
        includes_wavy=False,
    ),
    HatchPattern.AVB_WATERPROOFING: HatchSpec(
        pattern=HatchPattern.AVB_WATERPROOFING,
        description="Wavy horizontal lines",
        base_color="#4682B4",
        angle=0.0,
        secondary_angle=0.0,
        spacing=2.5,
        includes_dots=False,
        includes_circles=False,
        includes_wavy=True,
    ),
    HatchPattern.WOOD: HatchSpec(
        pattern=HatchPattern.WOOD,
        description="Grain lines",
        base_color="#8B7355",
        angle=0.0,
        secondary_angle=0.0,
        spacing=2.0,
        includes_dots=False,
        includes_circles=False,
        includes_wavy=False,
    ),
    HatchPattern.EARTH: HatchSpec(
        pattern=HatchPattern.EARTH,
        description="Random dots with short lines",
        base_color="#8B6914",
        angle=0.0,
        secondary_angle=0.0,
        spacing=3.0,
        includes_dots=True,
        includes_circles=False,
        includes_wavy=False,
    ),
    HatchPattern.GRAVEL: HatchSpec(
        pattern=HatchPattern.GRAVEL,
        description="Circles of varying size",
        base_color="#9E9E9E",
        angle=0.0,
        secondary_angle=0.0,
        spacing=4.0,
        includes_dots=False,
        includes_circles=True,
        includes_wavy=False,
    ),
    HatchPattern.AIR_SPACE: HatchSpec(
        pattern=HatchPattern.AIR_SPACE,
        description="Empty with small diagonal lines at boundary",
        base_color="#FFFFFF",
        angle=45.0,
        secondary_angle=0.0,
        spacing=6.0,
        includes_dots=False,
        includes_circles=False,
        includes_wavy=False,
    ),
}

# Node type -> HatchPattern mapping
_NODE_TO_HATCH: dict[str, HatchPattern] = {
    "deck": HatchPattern.METAL_DECK,
    "structural": HatchPattern.CONCRETE,
    "wall_substrate": HatchPattern.CONCRETE,
    "insulation": HatchPattern.RIGID_INSULATION,
    "cover_board": HatchPattern.RIGID_INSULATION,
    "membrane": HatchPattern.MEMBRANE,
    "flashing": HatchPattern.FLASHING,
    "counter_flashing": HatchPattern.FLASHING,
    "coping": HatchPattern.FLASHING,
    "parapet_cap": HatchPattern.FLASHING,
    "sealant": HatchPattern.SEALANT,
    "vapor_retarder": HatchPattern.MEMBRANE,
    "air_barrier": HatchPattern.AVB_WATERPROOFING,
    "wall_sheathing": HatchPattern.WOOD,
    "fastener": HatchPattern.FLASHING,
    "adhesive": HatchPattern.SEALANT,
}


class HatchDiscipline:
    """Resolve hatch patterns by material family or node type."""

    @staticmethod
    def get_spec(pattern: HatchPattern) -> HatchSpec:
        """Return the full hatch specification for a pattern enum."""
        spec = _HATCH_SPECS.get(pattern)
        if spec is None:
            raise ValueError(f"No hatch spec defined for pattern '{pattern.value}'")
        return spec

    @staticmethod
    def get_for_node(node_type: str) -> HatchSpec:
        """Return the hatch spec for a graph node type."""
        pattern = _NODE_TO_HATCH.get(node_type)
        if pattern is None:
            # Fallback: concrete for unknown structural, membrane for unknown layers
            pattern = HatchPattern.CONCRETE
        return HatchDiscipline.get_spec(pattern)

    @staticmethod
    def pattern_for_node(node_type: str) -> HatchPattern:
        """Return just the HatchPattern enum for a node type."""
        return _NODE_TO_HATCH.get(node_type, HatchPattern.CONCRETE)

    @staticmethod
    def all_specs() -> dict[HatchPattern, HatchSpec]:
        """Return the full pattern -> spec map."""
        return dict(_HATCH_SPECS)


# ---------------------------------------------------------------------------
# C. Control Layer Highlighting
# ---------------------------------------------------------------------------

class ControlLayerType(str, Enum):
    """The five continuity control layers in building enclosure design."""
    WATER = "water"
    AIR = "air"
    VAPOR = "vapor"
    THERMAL = "thermal"
    FIRE = "fire"


@dataclass(frozen=True)
class ControlLayerHighlight:
    """Visual emphasis settings for a control layer."""
    layer_type: ControlLayerType
    display_name: str
    color: str             # hex color for emphasis stroke/fill
    stroke_width_mm: float # emphasis stroke added on top of base lineweight
    fill_opacity: float    # 0.0-1.0 for translucent tint overlay
    dash_pattern: str      # "solid", "dashed", "dotted" for the emphasis stroke
    node_types: frozenset[str]  # which node types can carry this layer


_CONTROL_HIGHLIGHTS: dict[ControlLayerType, ControlLayerHighlight] = {
    ControlLayerType.WATER: ControlLayerHighlight(
        layer_type=ControlLayerType.WATER,
        display_name="Water Control Layer",
        color="#2196F3",       # blue
        stroke_width_mm=0.25,
        fill_opacity=0.15,
        dash_pattern="solid",
        node_types=frozenset({
            "membrane", "flashing", "counter_flashing", "sealant",
            "coping", "parapet_cap",
        }),
    ),
    ControlLayerType.AIR: ControlLayerHighlight(
        layer_type=ControlLayerType.AIR,
        display_name="Air Barrier",
        color="#4CAF50",       # green
        stroke_width_mm=0.20,
        fill_opacity=0.12,
        dash_pattern="dashed",
        node_types=frozenset({
            "air_barrier", "membrane", "sealant",
        }),
    ),
    ControlLayerType.VAPOR: ControlLayerHighlight(
        layer_type=ControlLayerType.VAPOR,
        display_name="Vapor Control Layer",
        color="#9C27B0",       # purple
        stroke_width_mm=0.20,
        fill_opacity=0.12,
        dash_pattern="dotted",
        node_types=frozenset({
            "vapor_retarder", "membrane",
        }),
    ),
    ControlLayerType.THERMAL: ControlLayerHighlight(
        layer_type=ControlLayerType.THERMAL,
        display_name="Thermal Layer",
        color="#FF9800",       # orange
        stroke_width_mm=0.20,
        fill_opacity=0.10,
        dash_pattern="solid",
        node_types=frozenset({
            "insulation", "cover_board",
        }),
    ),
    ControlLayerType.FIRE: ControlLayerHighlight(
        layer_type=ControlLayerType.FIRE,
        display_name="Fire-Resistance Boundary",
        color="#F44336",       # red
        stroke_width_mm=0.30,
        fill_opacity=0.18,
        dash_pattern="dashed",
        node_types=frozenset({
            "deck", "structural", "wall_substrate",
        }),
    ),
}


class ControlLayerHighlighting:
    """Resolve control-layer visual emphasis for nodes."""

    @staticmethod
    def get(layer_type: ControlLayerType) -> ControlLayerHighlight:
        highlight = _CONTROL_HIGHLIGHTS.get(layer_type)
        if highlight is None:
            raise ValueError(f"No highlight defined for layer type '{layer_type.value}'")
        return highlight

    @staticmethod
    def applicable_layers(node_type: str) -> list[ControlLayerHighlight]:
        """Return all control-layer highlights that apply to a node type."""
        return [
            h for h in _CONTROL_HIGHLIGHTS.values()
            if node_type in h.node_types
        ]

    @staticmethod
    def all_highlights() -> dict[ControlLayerType, ControlLayerHighlight]:
        return dict(_CONTROL_HIGHLIGHTS)


# ---------------------------------------------------------------------------
# D. Layer Spacing Rules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayerSpacingRules:
    """
    Diagrammatic scaling rules ensuring thin layers remain readable.

    All values are in millimeters at output (print) scale.
    """
    minimum_visual_thickness_mm: float = 2.0
    maximum_expansion_ratio: float = 3.0
    inter_layer_gap_mm: float = 0.5
    exploded_view_spacing_mm: float = 12.0

    def resolve_thickness(
        self,
        true_thickness_mm: float,
        output_scale: float,
    ) -> float:
        """
        Compute the rendered thickness for a layer.

        Args:
            true_thickness_mm: Physical thickness in mm.
            output_scale: Drawing scale factor (e.g., 1.0 for 1:1,
                          0.5 for half-size).

        Returns:
            Rendered thickness in mm, respecting minimum visibility
            and maximum expansion constraints.
        """
        scaled = true_thickness_mm * output_scale
        if scaled >= self.minimum_visual_thickness_mm:
            return scaled

        expanded = min(
            self.minimum_visual_thickness_mm,
            true_thickness_mm * output_scale * self.maximum_expansion_ratio,
        )
        return max(expanded, self.minimum_visual_thickness_mm)

    def stack_offset(
        self,
        layer_index: int,
        layer_thicknesses: list[float],
    ) -> float:
        """
        Compute the Y offset for a layer in a stacked assembly.

        Returns the bottom-edge Y position accounting for inter-layer gaps.
        """
        offset = 0.0
        for i in range(layer_index):
            offset += layer_thicknesses[i] + self.inter_layer_gap_mm
        return offset


# Singleton default rules
DEFAULT_SPACING_RULES = LayerSpacingRules()


# ---------------------------------------------------------------------------
# E. Overlay System
# ---------------------------------------------------------------------------

class OverlayType(str, Enum):
    """Toggleable information overlays."""
    SLOPE_ARROWS = "slope_arrows"
    DRAINAGE_ARROWS = "drainage_arrows"
    OVERLAP_DIRECTION = "overlap_direction"
    FASTENER_PATTERN = "fastener_pattern"
    FIRE_BOUNDARY = "fire_boundary"
    CONTROL_LAYERS = "control_layers"


@dataclass(frozen=True)
class OverlayDefinition:
    """Configuration for a single toggleable overlay."""
    overlay_id: OverlayType
    display_name: str
    default_visibility: bool
    color_scheme: dict[str, str]  # role -> hex color
    applicable_view_modes: frozenset[ViewMode]
    description: str = ""


_OVERLAYS: dict[OverlayType, OverlayDefinition] = {
    OverlayType.SLOPE_ARROWS: OverlayDefinition(
        overlay_id=OverlayType.SLOPE_ARROWS,
        display_name="Slope Arrows",
        default_visibility=True,
        color_scheme={
            "arrow": "#1565C0",
            "label": "#0D47A1",
        },
        applicable_view_modes=frozenset({ViewMode.CLEAN_DETAIL, ViewMode.XRAY}),
        description="Directional arrows showing roof slope for drainage",
    ),
    OverlayType.DRAINAGE_ARROWS: OverlayDefinition(
        overlay_id=OverlayType.DRAINAGE_ARROWS,
        display_name="Drainage Flow",
        default_visibility=False,
        color_scheme={
            "primary_flow": "#2196F3",
            "secondary_flow": "#64B5F6",
            "collection_point": "#0D47A1",
        },
        applicable_view_modes=frozenset({ViewMode.CLEAN_DETAIL, ViewMode.XRAY}),
        description="Water flow paths across the roof surface",
    ),
    OverlayType.OVERLAP_DIRECTION: OverlayDefinition(
        overlay_id=OverlayType.OVERLAP_DIRECTION,
        display_name="Overlap Direction",
        default_visibility=False,
        color_scheme={
            "shingle_flow": "#FF6F00",
            "indicator": "#E65100",
        },
        applicable_view_modes=frozenset({
            ViewMode.CLEAN_DETAIL, ViewMode.XRAY, ViewMode.EXPLODED,
        }),
        description="Membrane and flashing lap direction (shingle-flow)",
    ),
    OverlayType.FASTENER_PATTERN: OverlayDefinition(
        overlay_id=OverlayType.FASTENER_PATTERN,
        display_name="Fastener Pattern",
        default_visibility=False,
        color_scheme={
            "field_fastener": "#616161",
            "perimeter_fastener": "#D32F2F",
            "corner_fastener": "#B71C1C",
            "plate_washer": "#9E9E9E",
        },
        applicable_view_modes=frozenset({ViewMode.CLEAN_DETAIL, ViewMode.XRAY}),
        description="Mechanical fastener locations and zones (field/perimeter/corner)",
    ),
    OverlayType.FIRE_BOUNDARY: OverlayDefinition(
        overlay_id=OverlayType.FIRE_BOUNDARY,
        display_name="Fire-Resistance Boundary",
        default_visibility=False,
        color_scheme={
            "boundary_line": "#F44336",
            "rating_label": "#B71C1C",
            "fill_tint": "#FFCDD2",
        },
        applicable_view_modes=frozenset({ViewMode.CLEAN_DETAIL, ViewMode.XRAY}),
        description="Fire-rated assembly boundaries and UL design references",
    ),
    OverlayType.CONTROL_LAYERS: OverlayDefinition(
        overlay_id=OverlayType.CONTROL_LAYERS,
        display_name="Control Layers",
        default_visibility=False,
        color_scheme={
            "water": "#2196F3",
            "air": "#4CAF50",
            "vapor": "#9C27B0",
            "thermal": "#FF9800",
            "fire": "#F44336",
        },
        applicable_view_modes=frozenset({ViewMode.XRAY}),
        description="Building enclosure control-layer continuity visualization",
    ),
}


# ---------------------------------------------------------------------------
# Unified Visual System facade
# ---------------------------------------------------------------------------

class VisualSystem:
    """
    Top-level facade aggregating all visual rules.

    Usage:
        vs = VisualSystem()
        lw = vs.lineweight("membrane")          # Lineweight.MEDIUM
        hatch = vs.hatch_for_node("insulation")  # HatchSpec(...)
        highlights = vs.control_highlights("membrane")  # [water, air, ...]
        thickness = vs.resolve_thickness(0.8, 0.5)      # >= 2.0 mm
    """

    def __init__(
        self,
        spacing_rules: LayerSpacingRules | None = None,
    ):
        self.spacing = spacing_rules or DEFAULT_SPACING_RULES

    # -- A. Lineweight --
    def lineweight(self, node_type: str) -> Lineweight:
        return LineweightHierarchy.get(node_type)

    def lineweight_mm(self, node_type: str) -> float:
        return LineweightHierarchy.get_mm(node_type)

    # -- B. Hatch --
    def hatch_for_node(self, node_type: str) -> HatchSpec:
        return HatchDiscipline.get_for_node(node_type)

    def hatch_pattern_for_node(self, node_type: str) -> HatchPattern:
        return HatchDiscipline.pattern_for_node(node_type)

    # -- C. Control layers --
    def control_highlights(self, node_type: str) -> list[ControlLayerHighlight]:
        return ControlLayerHighlighting.applicable_layers(node_type)

    def control_highlight(self, layer_type: ControlLayerType) -> ControlLayerHighlight:
        return ControlLayerHighlighting.get(layer_type)

    # -- D. Spacing --
    def resolve_thickness(
        self,
        true_thickness_mm: float,
        output_scale: float = 1.0,
    ) -> float:
        return self.spacing.resolve_thickness(true_thickness_mm, output_scale)

    def stack_offset(
        self,
        layer_index: int,
        layer_thicknesses: list[float],
    ) -> float:
        return self.spacing.stack_offset(layer_index, layer_thicknesses)

    # -- E. Overlays --
    @staticmethod
    def overlay(overlay_type: OverlayType) -> OverlayDefinition:
        defn = _OVERLAYS.get(overlay_type)
        if defn is None:
            raise ValueError(f"Unknown overlay type '{overlay_type}'")
        return defn

    @staticmethod
    def overlays_for_mode(view_mode: ViewMode) -> list[OverlayDefinition]:
        """Return all overlays applicable to a view mode."""
        return [
            o for o in _OVERLAYS.values()
            if view_mode in o.applicable_view_modes
        ]

    @staticmethod
    def all_overlays() -> dict[OverlayType, OverlayDefinition]:
        return dict(_OVERLAYS)


# Module-level singleton for convenience
VISUAL_SYSTEM = VisualSystem()
