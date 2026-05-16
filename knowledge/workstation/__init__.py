"""
Construction Assembly Knowledge Graph - Workstation UI Module

Exports the workstation UI model, detail family definitions,
and implementation roadmap for the Construction Assembly Knowledge Graph.
"""

from .ui_model import (
    NavigationRail,
    ActionBar,
    Viewport,
    InspectorPanel,
    StatusStrip,
    CameraPosition,
    UIState,
    WorkflowState,
    OrientationModel,
    ViewMode,
    Overlay,
    WORKFLOW_STATES,
    ZONE_LAYOUT,
)

from .detail_families import (
    DetailFamily,
    ROOFING_DETAIL_FAMILIES,
    FIREPROOFING_DETAIL_FAMILIES,
    ALL_DETAIL_FAMILIES,
)

from .roadmap import (
    RoadmapPhase,
    BuildStep,
    ROOFING_PHASES,
    FIREPROOFING_PHASES,
    OVERALL_BUILD_ORDER,
)

__all__ = [
    # UI Model
    "NavigationRail",
    "ActionBar",
    "Viewport",
    "InspectorPanel",
    "StatusStrip",
    "CameraPosition",
    "UIState",
    "WorkflowState",
    "OrientationModel",
    "ViewMode",
    "Overlay",
    "WORKFLOW_STATES",
    "ZONE_LAYOUT",
    # Detail Families
    "DetailFamily",
    "ROOFING_DETAIL_FAMILIES",
    "FIREPROOFING_DETAIL_FAMILIES",
    "ALL_DETAIL_FAMILIES",
    # Roadmap
    "RoadmapPhase",
    "BuildStep",
    "ROOFING_PHASES",
    "FIREPROOFING_PHASES",
    "OVERALL_BUILD_ORDER",
]
