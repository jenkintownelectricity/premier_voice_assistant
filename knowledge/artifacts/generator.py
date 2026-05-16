"""
Construction Assembly Knowledge Graph - Artifact Generator
===========================================================

Transforms a knowledge-graph subgraph and a view mode into a fully traceable
drawing artifact containing resolved render primitives, deterministic IDs,
SHA-256 fingerprints, and lineage metadata.

Primary export format is SVG.  PDF delegates to SVG rendering.  DXF is
provided as a placeholder interface for future CAD-native export.

Usage:
    from knowledge.graph.core import AssemblyGraph
    from knowledge.render.view_modes import get_view_mode, ViewMode
    from knowledge.artifacts.generator import ArtifactGenerator

    graph = AssemblyGraph.load("project.json")
    gen = ArtifactGenerator(engine_version="1.0.0")

    artifact = gen.generate(
        graph=graph,
        view_mode=ViewMode.CLEAN_DETAIL,
        project_id="PROJ-001",
    )

    svg_str = gen.export_svg(artifact)
"""

from __future__ import annotations

import hashlib
import json
import math
import textwrap
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from knowledge.graph.core import AssemblyGraph, Edge, Node, NodeType
from knowledge.render.primitives import (
    Arc,
    Arrow,
    ArrowPurpose,
    DimensionLine,
    ExplodedOffsetTransform,
    HatchRegion,
    LeaderCallout,
    Line,
    LineStyle,
    Lineweight,
    PatternFill,
    Point2D,
    Polygon,
    Polyline,
    Rectangle,
    RenderPrimitive,
    SymbolMarker,
    TextLabel,
    TransparencyMask,
    ViewMode,
)
from knowledge.render.view_modes import ViewModeConfig, get_view_mode
from knowledge.render.visual_system import (
    ControlLayerHighlighting,
    ControlLayerType,
    HatchDiscipline,
    LayerSpacingRules,
    LineweightHierarchy,
    OverlayType,
    VisualSystem,
    DEFAULT_SPACING_RULES,
)


# ---------------------------------------------------------------------------
# Artifact types
# ---------------------------------------------------------------------------

class ArtifactType(str, Enum):
    """Output artifact formats and conceptual types."""
    DXF = "dxf"
    PDF = "pdf"
    SVG = "svg"
    UI_VIEW = "ui_view"
    CLEAN_DETAIL = "clean_detail"
    XRAY_VIEW = "xray_view"
    EXPLODED_VIEW = "exploded_view"
    INSTALLATION_SEQUENCE = "installation_sequence"


# ---------------------------------------------------------------------------
# DetailArtifact
# ---------------------------------------------------------------------------

@dataclass
class DetailArtifact:
    """
    A complete, traceable drawing artifact produced from graph data.

    Every artifact carries enough metadata to reproduce, verify, and
    trace its lineage back to the source graph nodes and edges.
    """
    artifact_id: str
    artifact_type: ArtifactType
    source_graph_node_ids: list[str]
    source_graph_edge_ids: list[str]
    generation_timestamp: datetime
    engine_version: str
    project_id: str
    fingerprint_token: str          # SHA-256 of content + metadata
    lineage_parent_ids: list[str]   # IDs of artifacts this was derived from
    view_mode: str
    render_primitives: list[RenderPrimitive]
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- Serialization --

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type.value,
            "source_graph_node_ids": self.source_graph_node_ids,
            "source_graph_edge_ids": self.source_graph_edge_ids,
            "generation_timestamp": self.generation_timestamp.isoformat(),
            "engine_version": self.engine_version,
            "project_id": self.project_id,
            "fingerprint_token": self.fingerprint_token,
            "lineage_parent_ids": self.lineage_parent_ids,
            "view_mode": self.view_mode,
            "render_primitives": [p.to_dict() for p in self.render_primitives],
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


# ---------------------------------------------------------------------------
# ArtifactGenerator
# ---------------------------------------------------------------------------

class ArtifactGenerator:
    """
    Engine that transforms a graph subgraph + view mode into a DetailArtifact.

    Responsibilities:
        1. Walk graph nodes/edges and resolve render primitives
        2. Apply visual-system rules (lineweights, hatching, spacing)
        3. Apply view-mode suppression and emphasis
        4. Package primitives into a fingerprinted DetailArtifact
        5. Export to SVG (primary), PDF (via SVG), DXF (placeholder)
    """

    def __init__(
        self,
        engine_version: str = "1.0.0",
        visual_system: VisualSystem | None = None,
        spacing_rules: LayerSpacingRules | None = None,
    ):
        self.engine_version = engine_version
        self.vs = visual_system or VisualSystem(spacing_rules)
        self.spacing = spacing_rules or DEFAULT_SPACING_RULES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        graph: AssemblyGraph,
        view_mode: str | ViewMode,
        project_id: str | None = None,
        lineage_parent_ids: list[str] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> DetailArtifact:
        """
        Generate a complete artifact from a graph and view mode.

        Args:
            graph:              The AssemblyGraph (or subgraph) to render.
            view_mode:          One of the three ViewMode values.
            project_id:         Project identifier (defaults to graph.project_id).
            lineage_parent_ids: Artifacts this one is derived from.
            extra_metadata:     Freeform metadata attached to the artifact.

        Returns:
            A fully populated DetailArtifact with resolved primitives
            and a SHA-256 fingerprint.
        """
        mode_cfg = get_view_mode(view_mode)
        mode_enum = mode_cfg.mode_id
        pid = project_id or graph.project_id
        parents = lineage_parent_ids or []

        # Resolve primitives from graph nodes
        primitives: list[RenderPrimitive] = []
        node_ids: list[str] = []
        edge_ids: list[str] = []

        stack = graph.get_assembly_stack()
        all_nodes = stack if stack else graph.nodes

        # Compute rendered thicknesses for the full stack
        layer_thicknesses = self._compute_layer_thicknesses(all_nodes, mode_cfg)

        for idx, node in enumerate(all_nodes):
            node_ids.append(node.node_id)
            node_prims = self._resolve_node_primitives(
                node, idx, layer_thicknesses, mode_cfg,
            )
            primitives.extend(node_prims)

        # Resolve edge-based primitives
        for edge in graph.edges:
            edge_ids.append(f"{edge.source_id}->{edge.target_id}")
            edge_prims = self._resolve_edge_primitives(edge, graph, mode_cfg)
            primitives.extend(edge_prims)

        # Apply view-mode filters
        primitives = self._apply_view_mode_filters(primitives, mode_cfg)

        # Apply exploded-view transforms if needed
        if mode_enum == ViewMode.EXPLODED:
            primitives = self._apply_exploded_transform(
                primitives, all_nodes, layer_thicknesses, mode_cfg,
            )

        # Build artifact
        timestamp = datetime.now(timezone.utc)
        artifact_id = self._deterministic_id(pid, mode_enum.value, node_ids, timestamp)
        fingerprint = self._compute_fingerprint(primitives, node_ids, edge_ids, pid)

        metadata = {
            "node_count": len(node_ids),
            "edge_count": len(edge_ids),
            "primitive_count": len(primitives),
            "view_mode_display": mode_cfg.display_name,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        return DetailArtifact(
            artifact_id=artifact_id,
            artifact_type=self._mode_to_artifact_type(mode_enum),
            source_graph_node_ids=node_ids,
            source_graph_edge_ids=edge_ids,
            generation_timestamp=timestamp,
            engine_version=self.engine_version,
            project_id=pid,
            fingerprint_token=fingerprint,
            lineage_parent_ids=parents,
            view_mode=mode_enum.value,
            render_primitives=primitives,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Export: SVG
    # ------------------------------------------------------------------

    def export_svg(
        self,
        artifact: DetailArtifact,
        width_mm: float = 400.0,
        height_mm: float = 300.0,
        margin_mm: float = 20.0,
    ) -> str:
        """
        Render an artifact's primitives to an SVG string.

        This is the primary export format.  The SVG uses millimeter units
        with a viewBox matching the specified dimensions.
        """
        vb_w = width_mm
        vb_h = height_mm
        lines: list[str] = []

        lines.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{vb_w}mm" height="{vb_h}mm" '
            f'viewBox="0 0 {vb_w} {vb_h}">'
        )
        lines.append(f'  <!-- Artifact: {xml_escape(artifact.artifact_id)} -->')
        lines.append(f'  <!-- Fingerprint: {artifact.fingerprint_token} -->')
        lines.append(f'  <!-- Engine: {artifact.engine_version} -->')

        # Background
        mode_cfg = get_view_mode(artifact.view_mode)
        bg = mode_cfg.visual_rules.get("background", "#FFFFFF")
        lines.append(f'  <rect width="{vb_w}" height="{vb_h}" fill="{bg}" />')

        # Render group with margin offset
        lines.append(f'  <g transform="translate({margin_mm},{margin_mm})">')

        for prim in artifact.render_primitives:
            svg_el = self._primitive_to_svg(prim)
            if svg_el:
                lines.append(f"    {svg_el}")

        lines.append("  </g>")
        lines.append("</svg>")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Export: PDF (via SVG)
    # ------------------------------------------------------------------

    def export_pdf(
        self,
        artifact: DetailArtifact,
        width_mm: float = 400.0,
        height_mm: float = 300.0,
    ) -> bytes:
        """
        Export artifact as PDF.

        Requires the ``cairosvg`` library.  Falls back to returning the SVG
        wrapped in a minimal PDF comment if cairosvg is unavailable.
        """
        svg_str = self.export_svg(artifact, width_mm, height_mm)
        try:
            import cairosvg  # type: ignore[import-untyped]
            return cairosvg.svg2pdf(bytestring=svg_str.encode("utf-8"))
        except ImportError:
            # Graceful degradation: return SVG bytes with a warning header
            header = b"%PDF-1.4 (cairosvg not installed - raw SVG follows)\n"
            return header + svg_str.encode("utf-8")

    # ------------------------------------------------------------------
    # Export: DXF (placeholder)
    # ------------------------------------------------------------------

    def export_dxf(self, artifact: DetailArtifact) -> str:
        """
        Export artifact as DXF.

        This is a placeholder that outputs a minimal DXF structure.
        Full DXF export requires ``ezdxf`` integration (future work).
        """
        dxf_lines = [
            "0", "SECTION",
            "2", "HEADER",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "ENTITIES",
        ]

        for prim in artifact.render_primitives:
            if isinstance(prim, Line):
                dxf_lines.extend([
                    "0", "LINE",
                    "8", "0",  # layer 0
                    "10", str(prim.start_point.x),
                    "20", str(prim.start_point.y),
                    "11", str(prim.end_point.x),
                    "21", str(prim.end_point.y),
                ])
            elif isinstance(prim, TextLabel):
                dxf_lines.extend([
                    "0", "TEXT",
                    "8", "0",
                    "10", str(prim.position.x),
                    "20", str(prim.position.y),
                    "40", str(prim.font_size),
                    "1", prim.text,
                ])

        dxf_lines.extend(["0", "ENDSEC", "0", "EOF"])
        return "\n".join(dxf_lines)

    # ------------------------------------------------------------------
    # Internals: primitive resolution from graph nodes
    # ------------------------------------------------------------------

    def _resolve_node_primitives(
        self,
        node: Node,
        layer_index: int,
        layer_thicknesses: list[float],
        mode_cfg: ViewModeConfig,
    ) -> list[RenderPrimitive]:
        """Generate render primitives for a single graph node."""
        prims: list[RenderPrimitive] = []
        nt = node.node_type.value
        lw = self.vs.lineweight(nt)

        # Compute Y position in the stack
        y_offset = self.spacing.stack_offset(layer_index, layer_thicknesses)
        thickness = layer_thicknesses[layer_index] if layer_index < len(layer_thicknesses) else 2.0
        width = node.attrs.get("width", 200.0)

        # Layer outline rectangle
        rect = Rectangle(
            purpose=f"Section outline for {nt} layer",
            origin=Point2D(0, y_offset),
            width=width,
            height=thickness,
            lineweight=lw,
        )
        prims.append(rect)

        # Hatch fill
        if mode_cfg.visual_rules.get("show_hatches", True):
            hatch_spec = self.vs.hatch_for_node(nt)
            hatch_opacity = mode_cfg.visual_rules.get("hatch_opacity", 1.0)
            boundary = Polyline(
                points=[
                    Point2D(0, y_offset),
                    Point2D(width, y_offset),
                    Point2D(width, y_offset + thickness),
                    Point2D(0, y_offset + thickness),
                ],
                closed=True,
            )
            hatch = HatchRegion(
                purpose=f"{hatch_spec.description} for {nt}",
                boundary=boundary,
                hatch_pattern=hatch_spec.pattern,
                scale=1.0,
                rotation=hatch_spec.angle,
                color=hatch_spec.base_color,
            )
            prims.append(hatch)

        # Text label / callout
        material_name = node.attrs.get("material_name", nt.replace("_", " ").title())
        label = TextLabel(
            purpose=f"Material label for {nt}",
            position=Point2D(width + 5.0, y_offset + thickness / 2.0),
            text=material_name,
            font_size=2.5,
        )
        prims.append(label)

        # Dimension (clean detail only)
        if mode_cfg.visual_rules.get("show_dimensions", False):
            true_thickness = node.attrs.get("thickness", thickness)
            dim = DimensionLine(
                purpose=f"Thickness dimension for {nt}",
                start=Point2D(-8.0, y_offset),
                end=Point2D(-8.0, y_offset + thickness),
                offset_distance=6.0,
                text_override=f'{true_thickness}"' if isinstance(true_thickness, (int, float)) else None,
            )
            prims.append(dim)

        # X-Ray transparency mask
        if mode_cfg.visual_rules.get("transparency_enabled", False):
            importance_map = mode_cfg.visual_rules.get("importance_map", {})
            opacity_map = mode_cfg.visual_rules.get("opacity_by_importance", {})
            importance = importance_map.get(nt, "tertiary")
            opacity = opacity_map.get(importance, 0.5)

            mask_boundary = Polyline(
                points=[
                    Point2D(0, y_offset),
                    Point2D(width, y_offset),
                    Point2D(width, y_offset + thickness),
                    Point2D(0, y_offset + thickness),
                ],
                closed=True,
            )
            mask = TransparencyMask(
                purpose=f"X-ray transparency for {nt} ({importance})",
                boundary=mask_boundary,
                opacity=opacity,
                mask_purpose="xray_fade",
            )
            prims.append(mask)

        # Control layer highlights (x-ray mode)
        if mode_cfg.visual_rules.get("color_mode") == "control_layers":
            highlights = self.vs.control_highlights(nt)
            for hl in highlights:
                highlight_boundary = Polyline(
                    points=[
                        Point2D(0, y_offset),
                        Point2D(width, y_offset),
                        Point2D(width, y_offset + thickness),
                        Point2D(0, y_offset + thickness),
                    ],
                    closed=True,
                )
                fill = PatternFill(
                    purpose=f"{hl.display_name} highlight on {nt}",
                    boundary=highlight_boundary,
                    pattern="solid",
                    color=hl.color,
                    opacity=hl.fill_opacity,
                )
                prims.append(fill)

        # Installation sequence number (exploded mode)
        if mode_cfg.visual_rules.get("show_installation_sequence_numbers", False):
            seq = node.install_sequence
            if seq is not None:
                seq_label = TextLabel(
                    purpose=f"Installation sequence #{seq} for {nt}",
                    position=Point2D(-15.0, y_offset + thickness / 2.0),
                    text=str(seq),
                    font_size=3.5,
                )
                prims.append(seq_label)

        return prims

    def _resolve_edge_primitives(
        self,
        edge: Edge,
        graph: AssemblyGraph,
        mode_cfg: ViewModeConfig,
    ) -> list[RenderPrimitive]:
        """Generate render primitives from a graph edge (relationships)."""
        prims: list[RenderPrimitive] = []
        et = edge.edge_type.value

        source = graph.get_node(edge.source_id)
        target = graph.get_node(edge.target_id)
        if source is None or target is None:
            return prims

        # Overlap arrows for laps_over edges
        if et == "laps_over":
            overlap_dist = edge.metadata.get("overlap_distance", 75.0)
            source_width = source.attrs.get("width", 200.0)
            arrow = Arrow(
                purpose=f"Overlap direction: {source.node_type.value} laps over {target.node_type.value}",
                start=Point2D(source_width - overlap_dist, 0),
                end=Point2D(source_width, 0),
                arrow_purpose=ArrowPurpose.OVERLAP,
            )
            prims.append(arrow)

        # Fastener indicators for mechanical attachment
        if et in ("mechanically_attached", "fastened_to"):
            spacing = edge.metadata.get("fastener_spacing", 12.0)
            width = source.attrs.get("width", 200.0)
            count = max(1, int(width / spacing))
            for i in range(count):
                x = spacing / 2 + i * spacing
                if x > width:
                    break
                marker = SymbolMarker(
                    purpose=f"Fastener at x={x:.1f} for {et}",
                    position=Point2D(x, 0),
                    symbol_type=SymbolMarker.META.emitting_node_types and "section_cut" or "section_cut",
                    scale=0.5,
                )
                prims.append(marker)

        # Sealant bead for seals edges
        if et == "seals":
            arc = Arc(
                purpose=f"Sealant bead at {source.node_id}",
                center=Point2D(0, 0),
                radius=1.5,
                start_angle=0,
                end_angle=360,
                lineweight=Lineweight.LIGHT,
            )
            prims.append(arc)

        return prims

    # ------------------------------------------------------------------
    # Internals: view-mode filtering and transforms
    # ------------------------------------------------------------------

    def _apply_view_mode_filters(
        self,
        primitives: list[RenderPrimitive],
        mode_cfg: ViewModeConfig,
    ) -> list[RenderPrimitive]:
        """Remove primitives that belong to suppressed element categories."""
        suppressed = set(mode_cfg.suppressed_elements)
        filtered: list[RenderPrimitive] = []

        for prim in primitives:
            suppress = False

            if isinstance(prim, TransparencyMask) and "transparency_masks" in suppressed:
                suppress = True
            elif isinstance(prim, ExplodedOffsetTransform) and "exploded_offset_transforms" in suppressed:
                suppress = True
            elif isinstance(prim, DimensionLine) and "dimensions" in suppressed:
                suppress = True
            elif isinstance(prim, PatternFill) and "control_layer_highlights" in suppressed:
                if "highlight" in prim.purpose.lower():
                    suppress = True

            # Check purpose-based suppression
            if not suppress:
                purpose_lower = prim.purpose.lower()
                if "installation sequence" in purpose_lower and "installation_sequence_numbers" in suppressed:
                    suppress = True
                if "construction sequence" in purpose_lower and "construction_sequence_markers" in suppressed:
                    suppress = True

            if not suppress:
                filtered.append(prim)

        return filtered

    def _apply_exploded_transform(
        self,
        primitives: list[RenderPrimitive],
        nodes: list[Node],
        layer_thicknesses: list[float],
        mode_cfg: ViewModeConfig,
    ) -> list[RenderPrimitive]:
        """
        Rewrite Y positions to create the exploded-view separation.

        In exploded mode, each layer is offset by additional spacing
        so they appear separated vertically.
        """
        exploded_spacing = mode_cfg.visual_rules.get("layer_spacing_mm", 12.0)
        show_connectors = mode_cfg.visual_rules.get("show_connector_lines", True)
        connector_color = mode_cfg.visual_rules.get("connector_line_color", "#BDBDBD")

        result: list[RenderPrimitive] = list(primitives)

        # Add connector lines between successive layers
        if show_connectors and len(nodes) > 1:
            for i in range(len(nodes) - 1):
                y_top_of_lower = self.spacing.stack_offset(i, layer_thicknesses) + layer_thicknesses[i]
                y_bottom_of_upper = self.spacing.stack_offset(i + 1, layer_thicknesses)
                width = nodes[i].attrs.get("width", 200.0)
                mid_x = width / 2.0

                connector = Line(
                    purpose=f"Exploded connector: layer {i} to layer {i+1}",
                    start_point=Point2D(mid_x, y_top_of_lower),
                    end_point=Point2D(mid_x, y_bottom_of_upper),
                    lineweight=Lineweight.THIN,
                    line_style=LineStyle.DASHED,
                    color=connector_color,
                )
                result.append(connector)

        return result

    # ------------------------------------------------------------------
    # Internals: thickness computation
    # ------------------------------------------------------------------

    def _compute_layer_thicknesses(
        self,
        nodes: list[Node],
        mode_cfg: ViewModeConfig,
    ) -> list[float]:
        """Compute rendered thicknesses for each layer respecting diagrammatic scaling."""
        output_scale = 1.0
        min_thickness = mode_cfg.visual_rules.get("minimum_layer_thickness_mm", 2.0)

        thicknesses: list[float] = []
        for node in nodes:
            true_t = node.attrs.get("thickness", 2.0)
            if not isinstance(true_t, (int, float)):
                true_t = 2.0
            rendered = self.spacing.resolve_thickness(float(true_t), output_scale)
            rendered = max(rendered, min_thickness)
            thicknesses.append(rendered)

        return thicknesses

    # ------------------------------------------------------------------
    # Internals: SVG rendering of individual primitives
    # ------------------------------------------------------------------

    def _primitive_to_svg(self, prim: RenderPrimitive) -> str | None:
        """Convert a single render primitive to an SVG element string."""

        if isinstance(prim, Line):
            sw = prim.lineweight.mm
            dash = self._svg_dash(prim.line_style)
            return (
                f'<line x1="{prim.start_point.x}" y1="{prim.start_point.y}" '
                f'x2="{prim.end_point.x}" y2="{prim.end_point.y}" '
                f'stroke="{prim.color}" stroke-width="{sw}"{dash} />'
            )

        if isinstance(prim, Rectangle):
            sw = prim.lineweight.mm
            transform = ""
            if prim.rotation != 0:
                cx = prim.origin.x + prim.width / 2
                cy = prim.origin.y + prim.height / 2
                transform = f' transform="rotate({prim.rotation},{cx},{cy})"'
            return (
                f'<rect x="{prim.origin.x}" y="{prim.origin.y}" '
                f'width="{prim.width}" height="{prim.height}" '
                f'fill="none" stroke="#000" stroke-width="{sw}"{transform} />'
            )

        if isinstance(prim, Polyline):
            pts = " ".join(f"{p.x},{p.y}" for p in prim.points)
            sw = prim.lineweight.mm
            tag = "polygon" if prim.closed else "polyline"
            dash = self._svg_dash(prim.line_style)
            return (
                f'<{tag} points="{pts}" '
                f'fill="none" stroke="#000" stroke-width="{sw}"{dash} />'
            )

        if isinstance(prim, Arc):
            # Approximate arc with SVG path
            sw = prim.lineweight.mm
            sa = math.radians(prim.start_angle)
            ea = math.radians(prim.end_angle)
            x1 = prim.center.x + prim.radius * math.cos(sa)
            y1 = prim.center.y + prim.radius * math.sin(sa)
            x2 = prim.center.x + prim.radius * math.cos(ea)
            y2 = prim.center.y + prim.radius * math.sin(ea)
            sweep = prim.end_angle - prim.start_angle
            large_arc = 1 if abs(sweep) > 180 else 0
            return (
                f'<path d="M {x1} {y1} A {prim.radius} {prim.radius} '
                f'0 {large_arc} 1 {x2} {y2}" '
                f'fill="none" stroke="#000" stroke-width="{sw}" />'
            )

        if isinstance(prim, Polygon):
            pts = " ".join(f"{p.x},{p.y}" for p in prim.points)
            sw = prim.lineweight.mm
            return (
                f'<polygon points="{pts}" '
                f'fill="none" stroke="#000" stroke-width="{sw}" />'
            )

        if isinstance(prim, HatchRegion):
            # Simplified: render as a semi-transparent fill
            pts = " ".join(f"{p.x},{p.y}" for p in prim.boundary.points)
            return (
                f'<polygon points="{pts}" '
                f'fill="{prim.color}" fill-opacity="0.3" stroke="none" />'
            )

        if isinstance(prim, TextLabel):
            anchor_map = {"left": "start", "center": "middle", "right": "end"}
            anchor = anchor_map.get(prim.anchor.value, "start")
            transform = ""
            if prim.rotation != 0:
                transform = f' transform="rotate({prim.rotation},{prim.position.x},{prim.position.y})"'
            return (
                f'<text x="{prim.position.x}" y="{prim.position.y}" '
                f'font-size="{prim.font_size}" text-anchor="{anchor}" '
                f'font-family="monospace"{transform}>'
                f'{xml_escape(prim.text)}</text>'
            )

        if isinstance(prim, LeaderCallout):
            parts: list[str] = []
            if len(prim.leader_points) >= 2:
                pts_str = " ".join(f"{p.x},{p.y}" for p in prim.leader_points)
                parts.append(
                    f'<polyline points="{pts_str}" fill="none" '
                    f'stroke="#000" stroke-width="0.18" />'
                )
            parts.append(
                f'<text x="{prim.text_position.x}" y="{prim.text_position.y}" '
                f'font-size="2.5" font-family="monospace">'
                f'{xml_escape(prim.text)}</text>'
            )
            return "\n    ".join(parts)

        if isinstance(prim, DimensionLine):
            # Simplified dimension: two ticks and a label
            mid_y = (prim.start.y + prim.end.y) / 2.0
            length = abs(prim.end.y - prim.start.y)
            text = prim.text_override or f"{length:.1f}"
            return (
                f'<line x1="{prim.start.x}" y1="{prim.start.y}" '
                f'x2="{prim.end.x}" y2="{prim.end.y}" '
                f'stroke="#000" stroke-width="0.09" />'
                f'<text x="{prim.start.x - 3}" y="{mid_y}" '
                f'font-size="2.0" text-anchor="end" font-family="monospace">'
                f'{xml_escape(text)}</text>'
            )

        if isinstance(prim, Arrow):
            return (
                f'<line x1="{prim.start.x}" y1="{prim.start.y}" '
                f'x2="{prim.end.x}" y2="{prim.end.y}" '
                f'stroke="#000" stroke-width="0.18" marker-end="url(#arrowhead)" />'
            )

        if isinstance(prim, PatternFill):
            pts = " ".join(f"{p.x},{p.y}" for p in prim.boundary.points)
            return (
                f'<polygon points="{pts}" '
                f'fill="{prim.color}" fill-opacity="{prim.opacity}" stroke="none" />'
            )

        if isinstance(prim, TransparencyMask):
            pts = " ".join(f"{p.x},{p.y}" for p in prim.boundary.points)
            return (
                f'<polygon points="{pts}" '
                f'fill="#FFFFFF" fill-opacity="{1.0 - prim.opacity}" stroke="none" />'
            )

        if isinstance(prim, SymbolMarker):
            # Simple cross marker
            s = 1.5 * prim.scale
            x, y = prim.position.x, prim.position.y
            return (
                f'<line x1="{x - s}" y1="{y}" x2="{x + s}" y2="{y}" '
                f'stroke="#000" stroke-width="0.09" />'
                f'<line x1="{x}" y1="{y - s}" x2="{x}" y2="{y + s}" '
                f'stroke="#000" stroke-width="0.09" />'
            )

        # ExplodedOffsetTransform is a meta-instruction, not directly renderable
        if isinstance(prim, ExplodedOffsetTransform):
            return None

        return None

    @staticmethod
    def _svg_dash(style: LineStyle) -> str:
        """Return SVG stroke-dasharray attribute fragment."""
        if style == LineStyle.DASHED:
            return ' stroke-dasharray="4,2"'
        elif style == LineStyle.DOTTED:
            return ' stroke-dasharray="1,1"'
        elif style == LineStyle.CENTER:
            return ' stroke-dasharray="8,2,2,2"'
        return ""

    # ------------------------------------------------------------------
    # Internals: IDs and fingerprinting
    # ------------------------------------------------------------------

    @staticmethod
    def _deterministic_id(
        project_id: str,
        view_mode: str,
        node_ids: list[str],
        timestamp: datetime,
    ) -> str:
        """
        Build a deterministic artifact ID from its inputs.

        Format: {project_id}:artifact:{view_mode}:{short_hash}
        """
        content = f"{project_id}|{view_mode}|{'|'.join(sorted(node_ids))}|{timestamp.isoformat()}"
        short_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"{project_id}:artifact:{view_mode}:{short_hash}"

    @staticmethod
    def _compute_fingerprint(
        primitives: list[RenderPrimitive],
        node_ids: list[str],
        edge_ids: list[str],
        project_id: str,
    ) -> str:
        """Compute a SHA-256 fingerprint over content + metadata."""
        h = hashlib.sha256()
        h.update(project_id.encode())
        for nid in sorted(node_ids):
            h.update(nid.encode())
        for eid in sorted(edge_ids):
            h.update(eid.encode())
        for prim in primitives:
            h.update(prim.primitive_type().encode())
            h.update(prim.purpose.encode())
        return h.hexdigest()

    @staticmethod
    def _mode_to_artifact_type(mode: ViewMode) -> ArtifactType:
        """Map a ViewMode to the corresponding ArtifactType."""
        return {
            ViewMode.CLEAN_DETAIL: ArtifactType.CLEAN_DETAIL,
            ViewMode.XRAY: ArtifactType.XRAY_VIEW,
            ViewMode.EXPLODED: ArtifactType.EXPLODED_VIEW,
        }.get(mode, ArtifactType.SVG)
