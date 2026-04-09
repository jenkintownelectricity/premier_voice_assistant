"""
Construction Assembly Knowledge Graph - Render Primitives
==========================================================

Typed dataclass definitions for every visual element that can appear in a
construction detail drawing.  Each primitive carries its own purpose string,
required parameters, compatible node/edge emitters, and allowed view modes.

These primitives are the atomic drawing instructions consumed by export
backends (SVG, DXF, PDF) and the interactive UI renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union


# ---------------------------------------------------------------------------
# Core value types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Point2D:
    """An immutable 2-D coordinate in drawing space (millimeters)."""
    x: float
    y: float

    def offset(self, dx: float, dy: float) -> Point2D:
        return Point2D(self.x + dx, self.y + dy)

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def __iter__(self):
        yield self.x
        yield self.y


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Lineweight(str, Enum):
    """ISO-aligned lineweight hierarchy for construction details."""
    HEAVY = "heavy"      # 0.70 mm - section cuts, primary cut objects
    MEDIUM = "medium"    # 0.35 mm - primary visible objects
    LIGHT = "light"      # 0.18 mm - secondary components
    THIN = "thin"        # 0.09 mm - accessories, hidden, reference

    @property
    def mm(self) -> float:
        return _LINEWEIGHT_MM[self]


_LINEWEIGHT_MM: dict[Lineweight, float] = {
    Lineweight.HEAVY: 0.70,
    Lineweight.MEDIUM: 0.35,
    Lineweight.LIGHT: 0.18,
    Lineweight.THIN: 0.09,
}


class LineStyle(str, Enum):
    """Line dash patterns."""
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    CENTER = "center"       # long-short-long pattern


class HatchPattern(str, Enum):
    """Material-family hatch patterns.  Each material maps to exactly one."""
    CONCRETE = "concrete"
    METAL_DECK = "metal_deck"
    RIGID_INSULATION = "rigid_insulation"
    MEMBRANE = "membrane"
    SEALANT = "sealant"
    FLASHING = "flashing"
    FIREPROOFING = "fireproofing"
    AVB_WATERPROOFING = "avb_waterproofing"
    WOOD = "wood"
    EARTH = "earth"
    GRAVEL = "gravel"
    AIR_SPACE = "air_space"


class AnchorPosition(str, Enum):
    """Text anchor / justification."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class ArrowHeadStyle(str, Enum):
    """Arrow head variants."""
    OPEN = "open"
    CLOSED = "closed"
    DOT = "dot"
    TICK = "tick"
    NONE = "none"


class ArrowPurpose(str, Enum):
    """Semantic purpose of an arrow overlay."""
    SLOPE = "slope"
    DRAINAGE = "drainage"
    OVERLAP = "overlap"
    FASTENER = "fastener"
    FORCE = "force"


class SymbolType(str, Enum):
    """Standard AEC drawing symbols."""
    SECTION_CUT = "section_cut"
    DETAIL_REFERENCE = "detail_reference"
    ELEVATION_MARKER = "elevation_marker"
    NORTH_ARROW = "north_arrow"
    BREAK_LINE = "break_line"


class DimensionStyle(str, Enum):
    """Dimension annotation styles."""
    LINEAR = "linear"
    ALIGNED = "aligned"
    ANGULAR = "angular"


class ViewMode(str, Enum):
    """The three primary rendering view modes."""
    CLEAN_DETAIL = "clean_detail"
    XRAY = "xray"
    EXPLODED = "exploded"


# Alias used by the __init__.py exports (the original name in the stub)
ViewModeID = ViewMode


# ---------------------------------------------------------------------------
# Primitive metadata helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PrimitiveMeta:
    """Describes which graph elements can emit a primitive and where it renders."""
    emitting_node_types: frozenset[str]
    emitting_edge_types: frozenset[str]
    allowed_view_modes: frozenset[ViewMode]


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

@dataclass
class RenderPrimitive:
    """
    Abstract base for all render primitives.

    Every concrete primitive inherits from this and adds its own typed fields.
    The ``purpose`` field is a human-readable description of *why* this
    primitive exists (e.g., "section cut through metal deck").
    """
    purpose: str = ""

    def primitive_type(self) -> str:
        return type(self).__name__

    def to_dict(self) -> dict[str, Any]:
        """Shallow serialization (overridden by subclasses for nested types)."""
        result: dict[str, Any] = {"_type": self.primitive_type()}
        for k, v in self.__dict__.items():
            if isinstance(v, Point2D):
                result[k] = v.to_tuple()
            elif isinstance(v, list) and v and isinstance(v[0], Point2D):
                result[k] = [p.to_tuple() for p in v]
            elif isinstance(v, Enum):
                result[k] = v.value
            elif isinstance(v, frozenset):
                result[k] = sorted(str(i) for i in v)
            else:
                result[k] = v
        return result


# ---------------------------------------------------------------------------
# Concrete primitives
# ---------------------------------------------------------------------------

@dataclass
class Line(RenderPrimitive):
    """A single straight line segment."""
    start_point: Point2D = field(default_factory=lambda: Point2D(0, 0))
    end_point: Point2D = field(default_factory=lambda: Point2D(0, 0))
    lineweight: Lineweight = Lineweight.MEDIUM
    line_style: LineStyle = LineStyle.SOLID
    color: str = "#000000"

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "membrane", "insulation", "cover_board", "flashing",
            "structural", "wall_substrate", "wall_sheathing", "termination",
            "counter_flashing", "coping", "parapet_cap", "vapor_retarder",
        }),
        emitting_edge_types=frozenset({
            "supports", "adhered_to", "mechanically_attached", "terminates_at",
            "transitions_to", "covers", "laps_over",
        }),
        allowed_view_modes=frozenset(ViewMode),
    )


@dataclass
class Polyline(RenderPrimitive):
    """An ordered sequence of connected line segments, optionally closed."""
    points: list[Point2D] = field(default_factory=list)
    closed: bool = False
    lineweight: Lineweight = Lineweight.MEDIUM
    line_style: LineStyle = LineStyle.SOLID

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "membrane", "insulation", "cover_board", "flashing",
            "structural", "wall_substrate", "vapor_retarder", "air_barrier",
        }),
        emitting_edge_types=frozenset({
            "supports", "transitions_to", "laps_over",
        }),
        allowed_view_modes=frozenset(ViewMode),
    )


@dataclass
class Arc(RenderPrimitive):
    """A circular arc defined by center, radius, and sweep angles (degrees)."""
    center: Point2D = field(default_factory=lambda: Point2D(0, 0))
    radius: float = 0.0
    start_angle: float = 0.0
    end_angle: float = 360.0
    lineweight: Lineweight = Lineweight.MEDIUM

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "membrane", "flashing", "sealant", "termination",
        }),
        emitting_edge_types=frozenset({
            "terminates_at", "seals",
        }),
        allowed_view_modes=frozenset(ViewMode),
    )


@dataclass
class Rectangle(RenderPrimitive):
    """An axis-aligned rectangle with optional rotation."""
    origin: Point2D = field(default_factory=lambda: Point2D(0, 0))
    width: float = 0.0
    height: float = 0.0
    lineweight: Lineweight = Lineweight.MEDIUM
    rotation: float = 0.0  # degrees, counter-clockwise from +X

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "insulation", "cover_board", "structural",
            "wall_substrate", "wall_sheathing",
        }),
        emitting_edge_types=frozenset({
            "supports", "adhered_to", "mechanically_attached",
        }),
        allowed_view_modes=frozenset(ViewMode),
    )


@dataclass
class Polygon(RenderPrimitive):
    """An arbitrary closed polygon defined by vertex list."""
    points: list[Point2D] = field(default_factory=list)
    lineweight: Lineweight = Lineweight.MEDIUM

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "insulation", "membrane", "flashing",
            "structural", "cover_board",
        }),
        emitting_edge_types=frozenset({
            "supports", "transitions_to",
        }),
        allowed_view_modes=frozenset(ViewMode),
    )


@dataclass
class HatchRegion(RenderPrimitive):
    """A hatched fill region representing a material in section."""
    boundary: Polyline = field(default_factory=Polyline)
    hatch_pattern: HatchPattern = HatchPattern.CONCRETE
    scale: float = 1.0
    rotation: float = 0.0
    color: str = "#888888"

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "insulation", "cover_board", "membrane", "sealant",
            "flashing", "structural", "vapor_retarder", "air_barrier",
            "wall_substrate", "wall_sheathing",
        }),
        emitting_edge_types=frozenset(),
        allowed_view_modes=frozenset({ViewMode.CLEAN_DETAIL, ViewMode.XRAY}),
    )


@dataclass
class TextLabel(RenderPrimitive):
    """A positioned text annotation."""
    position: Point2D = field(default_factory=lambda: Point2D(0, 0))
    text: str = ""
    font_size: float = 2.5  # mm at output scale
    anchor: AnchorPosition = AnchorPosition.LEFT
    rotation: float = 0.0

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "insulation", "cover_board", "membrane", "flashing",
            "sealant", "structural", "vapor_retarder", "air_barrier",
            "termination", "counter_flashing", "coping", "parapet_cap",
            "wall_substrate", "wall_sheathing", "fastener", "adhesive",
        }),
        emitting_edge_types=frozenset(),
        allowed_view_modes=frozenset(ViewMode),
    )


@dataclass
class LeaderCallout(RenderPrimitive):
    """A text callout with a leader line and arrow pointing to the subject."""
    text: str = ""
    text_position: Point2D = field(default_factory=lambda: Point2D(0, 0))
    leader_points: list[Point2D] = field(default_factory=list)
    arrow_style: ArrowHeadStyle = ArrowHeadStyle.CLOSED

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "insulation", "cover_board", "membrane", "flashing",
            "sealant", "structural", "vapor_retarder", "air_barrier",
            "termination", "counter_flashing", "coping", "parapet_cap",
            "wall_substrate", "wall_sheathing", "fastener", "adhesive",
        }),
        emitting_edge_types=frozenset({
            "terminates_at", "seals", "fastened_to",
        }),
        allowed_view_modes=frozenset({ViewMode.CLEAN_DETAIL, ViewMode.EXPLODED}),
    )


@dataclass
class DimensionLine(RenderPrimitive):
    """A linear, aligned, or angular dimension annotation."""
    start: Point2D = field(default_factory=lambda: Point2D(0, 0))
    end: Point2D = field(default_factory=lambda: Point2D(0, 0))
    offset_distance: float = 8.0  # mm from measured edge
    text_override: str | None = None
    style: DimensionStyle = DimensionStyle.LINEAR

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "insulation", "cover_board", "membrane", "flashing",
            "structural", "wall_substrate",
        }),
        emitting_edge_types=frozenset({
            "supports", "laps_over",
        }),
        allowed_view_modes=frozenset({ViewMode.CLEAN_DETAIL}),
    )


@dataclass
class Arrow(RenderPrimitive):
    """A directional arrow conveying flow, slope, overlap, or force."""
    start: Point2D = field(default_factory=lambda: Point2D(0, 0))
    end: Point2D = field(default_factory=lambda: Point2D(0, 0))
    arrow_head_style: ArrowHeadStyle = ArrowHeadStyle.CLOSED
    arrow_purpose: ArrowPurpose = ArrowPurpose.SLOPE

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "membrane", "insulation", "flashing", "fastener",
        }),
        emitting_edge_types=frozenset({
            "laps_over", "mechanically_attached", "fastened_to",
        }),
        allowed_view_modes=frozenset(ViewMode),
    )


@dataclass
class SymbolMarker(RenderPrimitive):
    """A standard AEC symbol placed at a location on the drawing."""
    position: Point2D = field(default_factory=lambda: Point2D(0, 0))
    symbol_type: SymbolType = SymbolType.SECTION_CUT
    scale: float = 1.0

    META = PrimitiveMeta(
        emitting_node_types=frozenset(),
        emitting_edge_types=frozenset(),
        allowed_view_modes=frozenset(ViewMode),
    )


@dataclass
class PatternFill(RenderPrimitive):
    """A colored or patterned fill region (non-hatch, e.g., control layer tint)."""
    boundary: Polyline = field(default_factory=Polyline)
    pattern: str = "solid"  # "solid", "stipple", "crosshatch", ...
    color: str = "#CCCCCC"
    opacity: float = 1.0

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "membrane", "insulation", "vapor_retarder", "air_barrier",
            "deck", "cover_board", "sealant", "flashing",
        }),
        emitting_edge_types=frozenset(),
        allowed_view_modes=frozenset({ViewMode.CLEAN_DETAIL, ViewMode.XRAY}),
    )


@dataclass
class TransparencyMask(RenderPrimitive):
    """An opacity overlay for x-ray and emphasis rendering."""
    boundary: Polyline = field(default_factory=Polyline)
    opacity: float = 0.5  # 0.0 fully transparent, 1.0 fully opaque
    mask_purpose: str = ""  # e.g., "xray_fade", "emphasis_highlight"

    META = PrimitiveMeta(
        emitting_node_types=frozenset({
            "deck", "insulation", "cover_board", "membrane", "flashing",
            "structural", "vapor_retarder", "air_barrier",
        }),
        emitting_edge_types=frozenset(),
        allowed_view_modes=frozenset({ViewMode.XRAY}),
    )


@dataclass
class ExplodedOffsetTransform(RenderPrimitive):
    """
    A transform instruction that separates layers in exploded view.

    Applied *after* primitives are resolved: the target primitives are
    translated by ``offset_vector`` with ``spacing`` between successive groups.
    Optional connector lines show where layers re-stack.
    """
    target_primitive_ids: list[str] = field(default_factory=list)
    offset_vector: Point2D = field(default_factory=lambda: Point2D(0, 10))
    spacing: float = 12.0  # mm between exploded layers
    show_connector_lines: bool = True

    META = PrimitiveMeta(
        emitting_node_types=frozenset(),
        emitting_edge_types=frozenset({
            "supports", "adhered_to", "mechanically_attached",
        }),
        allowed_view_modes=frozenset({ViewMode.EXPLODED}),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PRIMITIVE_REGISTRY: dict[str, type[RenderPrimitive]] = {
    "Line": Line,
    "Polyline": Polyline,
    "Arc": Arc,
    "Rectangle": Rectangle,
    "Polygon": Polygon,
    "HatchRegion": HatchRegion,
    "TextLabel": TextLabel,
    "LeaderCallout": LeaderCallout,
    "DimensionLine": DimensionLine,
    "Arrow": Arrow,
    "SymbolMarker": SymbolMarker,
    "PatternFill": PatternFill,
    "TransparencyMask": TransparencyMask,
    "ExplodedOffsetTransform": ExplodedOffsetTransform,
}
