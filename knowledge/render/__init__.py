"""
Construction Assembly Knowledge Graph - Rendering System
=========================================================

Provides typed render primitives, visual system rules, and view mode definitions
for generating construction detail drawings from knowledge graph data.

Modules:
    primitives      - Typed dataclass definitions for every render primitive
    visual_system   - Lineweight hierarchy, hatch discipline, control layer
                      highlighting, layer spacing, and overlay definitions
    view_modes      - Clean Detail, X-Ray Assembly, and Exploded Assembly
                      view mode configurations
"""

from knowledge.render.primitives import (
    # Enums
    Lineweight,
    LineStyle,
    HatchPattern,
    AnchorPosition,
    ArrowHeadStyle,
    ArrowPurpose,
    SymbolType,
    DimensionStyle,
    ViewModeID,
    # Primitives
    Line,
    Polyline,
    Arc,
    Rectangle,
    Polygon,
    HatchRegion,
    TextLabel,
    LeaderCallout,
    DimensionLine,
    Arrow,
    SymbolMarker,
    PatternFill,
    TransparencyMask,
    ExplodedOffsetTransform,
    RenderPrimitive,
    PRIMITIVE_REGISTRY,
)

from knowledge.render.visual_system import (
    VisualSystem,
    LineweightMapping,
    HatchDiscipline,
    ControlLayerHighlight,
    LayerSpacingRules,
    OverlayDefinition,
    VISUAL_SYSTEM,
)

from knowledge.render.view_modes import (
    ViewModeConfig,
    VIEW_MODE_CLEAN_DETAIL,
    VIEW_MODE_XRAY,
    VIEW_MODE_EXPLODED,
    VIEW_MODES,
    get_view_mode,
)

__all__ = [
    # Enums
    "Lineweight",
    "LineStyle",
    "HatchPattern",
    "AnchorPosition",
    "ArrowHeadStyle",
    "ArrowPurpose",
    "SymbolType",
    "DimensionStyle",
    "ViewModeID",
    # Primitives
    "Line",
    "Polyline",
    "Arc",
    "Rectangle",
    "Polygon",
    "HatchRegion",
    "TextLabel",
    "LeaderCallout",
    "DimensionLine",
    "Arrow",
    "SymbolMarker",
    "PatternFill",
    "TransparencyMask",
    "ExplodedOffsetTransform",
    "RenderPrimitive",
    "PRIMITIVE_REGISTRY",
    # Visual system
    "VisualSystem",
    "LineweightMapping",
    "HatchDiscipline",
    "ControlLayerHighlight",
    "LayerSpacingRules",
    "OverlayDefinition",
    "VISUAL_SYSTEM",
    # View modes
    "ViewModeConfig",
    "VIEW_MODE_CLEAN_DETAIL",
    "VIEW_MODE_XRAY",
    "VIEW_MODE_EXPLODED",
    "VIEW_MODES",
    "get_view_mode",
]
