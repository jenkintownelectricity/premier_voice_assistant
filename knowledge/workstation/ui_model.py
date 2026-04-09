"""
Construction Assembly Knowledge Graph - Workstation UI Model

Defines the 5-zone workstation layout, orientation model, workflow state machine,
and UI state as typed Python structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ViewMode(str, Enum):
    """Detail view rendering modes."""
    CLEAN = "clean"
    XRAY = "xray"
    EXPLODED = "exploded"


class Overlay(str, Enum):
    """Toggleable overlay layers."""
    CONTROL_LAYERS = "control_layers"
    HIDDEN_COMPONENTS = "hidden_components"
    DRAINAGE = "drainage"
    FIRE_BOUNDARY = "fire_boundary"
    DIMENSIONS = "dimensions"
    NOTES = "notes"


class ValidationBadge(str, Enum):
    """Validation state indicators."""
    GREEN = "green"      # All rules pass
    YELLOW = "yellow"    # Warnings present
    RED = "red"          # Errors present


class WorkflowStateID(str, Enum):
    """Workflow state machine state identifiers."""
    BROWSE = "BROWSE"
    VIEW_CLEAN = "VIEW_CLEAN"
    VIEW_XRAY = "VIEW_XRAY"
    VIEW_EXPLODED = "VIEW_EXPLODED"
    INSPECT = "INSPECT"
    OVERLAY = "OVERLAY"
    VALIDATE = "VALIDATE"
    EXPORT = "EXPORT"


# ---------------------------------------------------------------------------
# Zone Definitions (5-Zone Layout)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NavigationRail:
    """LEFT_NAV zone - Project tree navigation.

    Provides hierarchical browsing of the project structure with search,
    breadcrumb support, and condition navigation.
    """
    zone: str = "LEFT_NAV"
    position: str = "left"
    features: tuple[str, ...] = (
        "project_tree",
        "assemblies_list",
        "conditions_list",
        "detail_families_list",
        "validation_summary",
        "artifacts_list",
        "search_filter",
        "breadcrumb_display",
        "previous_next_condition_arrows",
    )
    searchable: bool = True
    breadcrumb_support: bool = True
    collapsible: bool = True
    default_width_px: int = 280


@dataclass(frozen=True)
class ActionBar:
    """TOP_BAR zone - Primary action controls.

    Houses generation, validation, view mode switching, overlay toggles,
    comparison, and export actions.
    """
    zone: str = "TOP_BAR"
    position: str = "top"
    generation_actions: tuple[str, ...] = (
        "generate",
        "re_generate",
    )
    validation_actions: tuple[str, ...] = (
        "validate",
    )
    view_mode_buttons: tuple[str, ...] = (
        "clean",
        "xray",
        "exploded",
    )
    overlay_toggles: tuple[str, ...] = (
        "control_layers",
        "hidden_components",
        "drainage",
        "fire_boundary",
        "dimensions",
        "notes",
    )
    comparison_actions: tuple[str, ...] = (
        "compare_versions",
    )
    export_actions: tuple[str, ...] = (
        "export_dxf",
        "export_pdf",
    )
    camera_actions: tuple[str, ...] = (
        "fit_view",
        "reset_view",
    )


@dataclass(frozen=True)
class Viewport:
    """CENTER zone - Primary visual workspace.

    Renders the active detail view with pan, zoom, inspection, and
    overlay support. Mode switches preserve selection and camera state.
    """
    zone: str = "CENTER"
    position: str = "center"
    interactions: tuple[str, ...] = (
        "pan",
        "zoom",
        "fit",
        "reset",
        "click_to_inspect",
        "hover_highlight",
        "isolate_selected",
    )
    overlay_support: bool = True
    mode_switch_preserves_context: bool = True
    default_view_mode: ViewMode = ViewMode.CLEAN


@dataclass(frozen=True)
class InspectorPanel:
    """RIGHT zone - Object detail inspector.

    Shows full metadata for the selected graph node including material
    properties, validation status, connectivity, and lineage.
    """
    zone: str = "RIGHT"
    position: str = "right"
    fields: tuple[str, ...] = (
        "object_type",
        "deterministic_id",
        "material",
        "thickness",
        "manufacturer",
        "validation_status",
        "connected_objects",
        "install_order",
        "source_references",
        "lineage",
    )
    collapsible: bool = True
    default_width_px: int = 320
    default_visible: bool = True


@dataclass(frozen=True)
class StatusStrip:
    """BOTTOM zone - Contextual status information.

    Displays current scale, selection info, validation summary,
    and artifact metadata at a glance.
    """
    zone: str = "BOTTOM"
    position: str = "bottom"
    indicators: tuple[str, ...] = (
        "current_scale",
        "selected_object",
        "warnings_count",
        "validation_state",
        "last_generation_timestamp",
        "artifact_version",
    )
    default_height_px: int = 32


# Canonical zone layout
ZONE_LAYOUT = {
    "LEFT_NAV": NavigationRail(),
    "TOP_BAR": ActionBar(),
    "CENTER": Viewport(),
    "RIGHT": InspectorPanel(),
    "BOTTOM": StatusStrip(),
}


# ---------------------------------------------------------------------------
# Orientation Model
# ---------------------------------------------------------------------------

@dataclass
class OrientationModel:
    """Persistent orientation cues that keep the user grounded.

    Always visible regardless of active zone or workflow state.
    """
    breadcrumb_template: str = "Project > Building > Roof Area > Condition > Selected Part"
    active_view_mode_label_visible: bool = True
    validation_badge: ValidationBadge = ValidationBadge.GREEN
    mini_layer_stack_visible: bool = True
    mini_layer_stack_description: str = (
        "Vertical strip showing assembly layers in stack order, "
        "positioned at viewport edge"
    )
    tooltip_on_hover: bool = True
    tooltip_content: str = "node_type + key_attribute"
    previous_next_condition_arrows: bool = True


# ---------------------------------------------------------------------------
# Workflow State Machine
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkflowState:
    """A single state in the default user workflow state machine."""
    state_id: WorkflowStateID
    description: str
    available_actions: tuple[str, ...]
    default_next_state: Optional[WorkflowStateID]
    preserves_selection: bool
    preserves_camera: bool


WORKFLOW_STATES: dict[WorkflowStateID, WorkflowState] = {

    WorkflowStateID.BROWSE: WorkflowState(
        state_id=WorkflowStateID.BROWSE,
        description=(
            "User navigates the project tree, selects a condition. "
            "Entry point for all workflows."
        ),
        available_actions=(
            "expand_tree_node",
            "collapse_tree_node",
            "select_condition",
            "search",
            "previous_condition",
            "next_condition",
        ),
        default_next_state=WorkflowStateID.VIEW_CLEAN,
        preserves_selection=False,
        preserves_camera=False,
    ),

    WorkflowStateID.VIEW_CLEAN: WorkflowState(
        state_id=WorkflowStateID.VIEW_CLEAN,
        description=(
            "Landing state after selecting a condition. Shows the clean "
            "detail view - production-quality rendering with no annotations."
        ),
        available_actions=(
            "pan",
            "zoom",
            "fit_view",
            "reset_view",
            "click_to_inspect",
            "hover_highlight",
            "switch_to_xray",
            "switch_to_exploded",
            "toggle_overlay",
            "validate",
            "export",
            "generate",
            "re_generate",
        ),
        default_next_state=WorkflowStateID.INSPECT,
        preserves_selection=True,
        preserves_camera=True,
    ),

    WorkflowStateID.VIEW_XRAY: WorkflowState(
        state_id=WorkflowStateID.VIEW_XRAY,
        description=(
            "X-ray mode - semi-transparent layers revealing internal "
            "structure. Preserves current selection and camera position."
        ),
        available_actions=(
            "pan",
            "zoom",
            "fit_view",
            "reset_view",
            "click_to_inspect",
            "hover_highlight",
            "switch_to_clean",
            "switch_to_exploded",
            "toggle_overlay",
            "validate",
            "export",
        ),
        default_next_state=WorkflowStateID.INSPECT,
        preserves_selection=True,
        preserves_camera=True,
    ),

    WorkflowStateID.VIEW_EXPLODED: WorkflowState(
        state_id=WorkflowStateID.VIEW_EXPLODED,
        description=(
            "Exploded view - layers separated vertically to show "
            "individual components and install order. Preserves selection "
            "and camera."
        ),
        available_actions=(
            "pan",
            "zoom",
            "fit_view",
            "reset_view",
            "click_to_inspect",
            "hover_highlight",
            "switch_to_clean",
            "switch_to_xray",
            "toggle_overlay",
            "validate",
            "export",
        ),
        default_next_state=WorkflowStateID.INSPECT,
        preserves_selection=True,
        preserves_camera=True,
    ),

    WorkflowStateID.INSPECT: WorkflowState(
        state_id=WorkflowStateID.INSPECT,
        description=(
            "User clicks a layer or component. The inspector panel "
            "populates with full node metadata, connections, and lineage."
        ),
        available_actions=(
            "view_connected_objects",
            "view_source_references",
            "view_lineage",
            "isolate_selected",
            "deselect",
            "select_another",
            "validate",
            "export",
        ),
        default_next_state=WorkflowStateID.VIEW_CLEAN,
        preserves_selection=True,
        preserves_camera=True,
    ),

    WorkflowStateID.OVERLAY: WorkflowState(
        state_id=WorkflowStateID.OVERLAY,
        description=(
            "User toggles an overlay (drainage, fire boundary, dimensions, "
            "notes, etc.). Overlays compose on top of any view mode."
        ),
        available_actions=(
            "toggle_drainage",
            "toggle_fire_boundary",
            "toggle_dimensions",
            "toggle_notes",
            "toggle_control_layers",
            "toggle_hidden_components",
            "clear_all_overlays",
        ),
        default_next_state=WorkflowStateID.VIEW_CLEAN,
        preserves_selection=True,
        preserves_camera=True,
    ),

    WorkflowStateID.VALIDATE: WorkflowState(
        state_id=WorkflowStateID.VALIDATE,
        description=(
            "Run validation rules against the current assembly. Warnings "
            "and errors appear in both the status strip and the inspector "
            "panel. Validation badge updates."
        ),
        available_actions=(
            "run_all_rules",
            "run_selected_rules",
            "view_warning_details",
            "dismiss_warning",
            "fix_suggestion",
        ),
        default_next_state=WorkflowStateID.INSPECT,
        preserves_selection=True,
        preserves_camera=True,
    ),

    WorkflowStateID.EXPORT: WorkflowState(
        state_id=WorkflowStateID.EXPORT,
        description=(
            "Generate a DXF or PDF artifact with full lineage metadata. "
            "Artifact version is tracked and displayed in the status strip."
        ),
        available_actions=(
            "export_dxf",
            "export_pdf",
            "select_export_scope",
            "include_lineage",
            "set_scale",
        ),
        default_next_state=WorkflowStateID.VIEW_CLEAN,
        preserves_selection=True,
        preserves_camera=True,
    ),
}


# ---------------------------------------------------------------------------
# UI State
# ---------------------------------------------------------------------------

@dataclass
class CameraPosition:
    """2D camera state for the viewport."""
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    rotation: float = 0.0


@dataclass
class UIState:
    """Complete snapshot of the workstation UI state.

    Serializable for undo/redo, session persistence, and state transfer.
    """
    current_project_id: Optional[str] = None
    current_condition_id: Optional[str] = None
    current_view_mode: ViewMode = ViewMode.CLEAN
    selected_node_ids: list[str] = field(default_factory=list)
    camera_position: CameraPosition = field(default_factory=CameraPosition)
    active_overlays: list[Overlay] = field(default_factory=list)
    inspector_visible: bool = True
    validation_visible: bool = False
    breadcrumb_path: list[str] = field(default_factory=list)
