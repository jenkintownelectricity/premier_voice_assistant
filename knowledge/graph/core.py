"""
Assembly Knowledge Graph - Core Engine
=======================================

A typed, deterministic graph engine for modeling construction assemblies.

Design principles:
- Fail-closed: rejects invalid insertions with clear error messages
- Thread-safe: simple lock on all mutations
- Deterministic: IDs follow {project_id}:{node_type}:{sequence_or_name}
- Auditable: every mutation is logged in a change log

Usage:
    graph = AssemblyGraph(project_id="PROJ-001")
    graph.add_node("PROJ-001:deck:01", node_type="deck", attrs={...})
    graph.add_edge("PROJ-001:deck:01", "PROJ-001:vr:01", edge_type="supports")
    stack = graph.get_assembly_stack()
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    """Valid node types in the assembly graph."""
    DECK = "deck"
    VAPOR_RETARDER = "vapor_retarder"
    INSULATION = "insulation"
    COVER_BOARD = "cover_board"
    MEMBRANE = "membrane"
    FLASHING = "flashing"
    TERMINATION = "termination"
    COUNTER_FLASHING = "counter_flashing"
    COPING = "coping"
    WALL_SUBSTRATE = "wall_substrate"
    WALL_SHEATHING = "wall_sheathing"
    AIR_BARRIER = "air_barrier"
    SEALANT = "sealant"
    FASTENER = "fastener"
    ADHESIVE = "adhesive"
    PARAPET_CAP = "parapet_cap"
    STRUCTURAL = "structural"
    GENERIC = "generic"


class EdgeType(str, Enum):
    """Valid edge types defining relationships between nodes."""
    SUPPORTS = "supports"           # lower layer supports upper layer
    ADHERED_TO = "adhered_to"       # component adhered to substrate
    MECHANICALLY_ATTACHED = "mechanically_attached"
    TERMINATES_AT = "terminates_at" # flashing terminates at bar/sealant
    TRANSITIONS_TO = "transitions_to"  # roof-to-wall transition
    COVERS = "covers"               # counter-flashing covers base flashing
    SEALS = "seals"                 # sealant seals a joint
    FASTENED_TO = "fastened_to"     # mechanical fastener connection
    LAPS_OVER = "laps_over"        # membrane or flashing lap
    INSTALLED_BEFORE = "installed_before"  # sequencing dependency
    INSTALLED_AFTER = "installed_after"    # sequencing dependency (reverse)
    REQUIRES = "requires"           # dependency (e.g., primer before adhesive)
    INSPECTION_POINT = "inspection_point"  # checkpoint before next layer


# Schema: which edge types are valid between which node types.
# Format: {edge_type: [(source_types, target_types), ...]}
# None in source/target means "any node type".
EDGE_SCHEMA: dict[EdgeType, list[tuple[set[NodeType] | None, set[NodeType] | None]]] = {
    EdgeType.SUPPORTS: [(None, None)],
    EdgeType.ADHERED_TO: [(None, None)],
    EdgeType.MECHANICALLY_ATTACHED: [(None, None)],
    EdgeType.TERMINATES_AT: [
        ({NodeType.FLASHING, NodeType.MEMBRANE}, {NodeType.TERMINATION, NodeType.SEALANT, NodeType.COUNTER_FLASHING}),
    ],
    EdgeType.TRANSITIONS_TO: [(None, None)],
    EdgeType.COVERS: [
        ({NodeType.COUNTER_FLASHING, NodeType.COPING, NodeType.PARAPET_CAP}, None),
    ],
    EdgeType.SEALS: [
        ({NodeType.SEALANT}, None),
    ],
    EdgeType.FASTENED_TO: [(None, None)],
    EdgeType.LAPS_OVER: [
        ({NodeType.MEMBRANE, NodeType.FLASHING}, {NodeType.MEMBRANE, NodeType.FLASHING}),
    ],
    EdgeType.INSTALLED_BEFORE: [(None, None)],
    EdgeType.INSTALLED_AFTER: [(None, None)],
    EdgeType.REQUIRES: [(None, None)],
    EdgeType.INSPECTION_POINT: [(None, None)],
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class GraphValidationError(Exception):
    """Raised when a graph mutation violates schema or integrity rules."""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        self.context = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        base = super().__str__()
        if self.context:
            details = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{base} [{details}]"
        return base


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """A component in the assembly graph."""
    node_id: str
    node_type: NodeType
    attrs: dict[str, Any] = field(default_factory=dict)
    render_hints: dict[str, Any] = field(default_factory=dict)
    install_sequence: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "attrs": self.attrs,
            "render_hints": self.render_hints,
            "install_sequence": self.install_sequence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        return cls(
            node_id=data["node_id"],
            node_type=NodeType(data["node_type"]),
            attrs=data.get("attrs", {}),
            render_hints=data.get("render_hints", {}),
            install_sequence=data.get("install_sequence"),
        )


@dataclass
class Edge:
    """A relationship between two nodes."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Edge:
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            edge_type=EdgeType(data["edge_type"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ChangeLogEntry:
    """An immutable record of a graph mutation."""
    timestamp: float
    action: str          # "add_node", "add_edge", "remove_node", "remove_edge"
    entity_id: str       # node_id or "source->target"
    details: dict[str, Any] = field(default_factory=dict)
    change_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "entity_id": self.entity_id,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# GraphQuery - Fluent query builder
# ---------------------------------------------------------------------------

class GraphQuery:
    """
    Fluent query builder for the AssemblyGraph.

    Usage:
        results = (GraphQuery(graph)
            .nodes_of_type(NodeType.INSULATION)
            .with_attr("r_value_per_inch", lambda v: v >= 5.0)
            .execute())
    """

    def __init__(self, graph: AssemblyGraph):
        self._graph = graph
        self._filters: list[callable] = []
        self._node_types: set[NodeType] | None = None

    def nodes_of_type(self, *node_types: NodeType) -> GraphQuery:
        """Filter to nodes of the given type(s)."""
        self._node_types = set(node_types)
        return self

    def with_attr(self, key: str, predicate: callable | Any = None) -> GraphQuery:
        """Filter nodes that have an attribute matching a predicate or exact value."""
        if predicate is None:
            # Just check existence
            self._filters.append(lambda n: key in n.attrs)
        elif callable(predicate):
            self._filters.append(lambda n: key in n.attrs and predicate(n.attrs[key]))
        else:
            # Exact match
            self._filters.append(lambda n: n.attrs.get(key) == predicate)
        return self

    def with_install_sequence(self, predicate: callable) -> GraphQuery:
        """Filter nodes by install_sequence using a predicate."""
        self._filters.append(
            lambda n: n.install_sequence is not None and predicate(n.install_sequence)
        )
        return self

    def connected_to(self, node_id: str, edge_type: EdgeType | None = None) -> GraphQuery:
        """Filter to nodes connected to the given node."""
        connected_ids = set()
        for edge in self._graph._edges_out.get(node_id, []):
            if edge_type is None or edge.edge_type == edge_type:
                connected_ids.add(edge.target_id)
        for edge in self._graph._edges_in.get(node_id, []):
            if edge_type is None or edge.edge_type == edge_type:
                connected_ids.add(edge.source_id)
        self._filters.append(lambda n: n.node_id in connected_ids)
        return self

    def execute(self) -> list[Node]:
        """Execute the query and return matching nodes."""
        nodes = list(self._graph._nodes.values())

        if self._node_types is not None:
            nodes = [n for n in nodes if n.node_type in self._node_types]

        for f in self._filters:
            nodes = [n for n in nodes if f(n)]

        return nodes

    def execute_ids(self) -> list[str]:
        """Execute the query and return matching node IDs."""
        return [n.node_id for n in self.execute()]

    def first(self) -> Node | None:
        """Execute and return the first match, or None."""
        results = self.execute()
        return results[0] if results else None

    def count(self) -> int:
        """Execute and return the count of matches."""
        return len(self.execute())


# ---------------------------------------------------------------------------
# AssemblyGraph - Main graph class
# ---------------------------------------------------------------------------

class AssemblyGraph:
    """
    Thread-safe, typed graph engine for construction assembly modeling.

    All mutations are validated against the edge schema and logged.
    """

    def __init__(self, project_id: str, validate_schema: bool = True):
        self.project_id = project_id
        self.validate_schema = validate_schema

        self._nodes: dict[str, Node] = {}
        self._edges_out: dict[str, list[Edge]] = {}   # source_id -> [Edge]
        self._edges_in: dict[str, list[Edge]] = {}    # target_id -> [Edge]
        self._change_log: list[ChangeLogEntry] = []
        self._lock = threading.Lock()
        self._metadata: dict[str, Any] = {
            "project_id": project_id,
            "created_at": time.time(),
        }

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        node_type: str | NodeType,
        attrs: dict[str, Any] | None = None,
        render_hints: dict[str, Any] | None = None,
        install_sequence: int | None = None,
    ) -> Node:
        """Add a node to the graph. Fails if node_id already exists."""
        if isinstance(node_type, str):
            try:
                node_type = NodeType(node_type)
            except ValueError:
                raise GraphValidationError(
                    f"Invalid node_type '{node_type}'",
                    {"valid_types": [t.value for t in NodeType]},
                )

        with self._lock:
            if node_id in self._nodes:
                raise GraphValidationError(
                    f"Node '{node_id}' already exists",
                    {"existing_type": self._nodes[node_id].node_type.value},
                )

            node = Node(
                node_id=node_id,
                node_type=node_type,
                attrs=attrs or {},
                render_hints=render_hints or {},
                install_sequence=install_sequence,
            )
            self._nodes[node_id] = node
            self._edges_out.setdefault(node_id, [])
            self._edges_in.setdefault(node_id, [])

            self._log("add_node", node_id, {
                "node_type": node_type.value,
                "install_sequence": install_sequence,
            })

        return node

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its edges."""
        with self._lock:
            if node_id not in self._nodes:
                raise GraphValidationError(f"Node '{node_id}' not found")

            # Remove all edges involving this node
            for edge in list(self._edges_out.get(node_id, [])):
                self._remove_edge_internal(edge)
            for edge in list(self._edges_in.get(node_id, [])):
                self._remove_edge_internal(edge)

            del self._nodes[node_id]
            self._edges_out.pop(node_id, None)
            self._edges_in.pop(node_id, None)

            self._log("remove_node", node_id)

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID. Returns None if not found."""
        return self._nodes.get(node_id)

    def get_node_strict(self, node_id: str) -> Node:
        """Get a node by ID. Raises if not found."""
        node = self._nodes.get(node_id)
        if node is None:
            raise GraphValidationError(f"Node '{node_id}' not found")
        return node

    @property
    def nodes(self) -> list[Node]:
        """All nodes in insertion order."""
        return list(self._nodes.values())

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str | EdgeType,
        metadata: dict[str, Any] | None = None,
    ) -> Edge:
        """
        Add an edge between two existing nodes.

        Validates:
        - Both nodes exist
        - Edge type is valid
        - Edge conforms to schema (source/target type constraints)
        - No duplicate edges
        - No self-loops
        """
        if isinstance(edge_type, str):
            try:
                edge_type = EdgeType(edge_type)
            except ValueError:
                raise GraphValidationError(
                    f"Invalid edge_type '{edge_type}'",
                    {"valid_types": [e.value for e in EdgeType]},
                )

        with self._lock:
            # Validate endpoints exist
            if source_id not in self._nodes:
                raise GraphValidationError(
                    f"Source node '{source_id}' not found",
                    {"edge_type": edge_type.value, "target": target_id},
                )
            if target_id not in self._nodes:
                raise GraphValidationError(
                    f"Target node '{target_id}' not found",
                    {"edge_type": edge_type.value, "source": source_id},
                )

            # No self-loops
            if source_id == target_id:
                raise GraphValidationError(
                    f"Self-loops are not allowed",
                    {"node_id": source_id, "edge_type": edge_type.value},
                )

            # Check for duplicate
            for existing in self._edges_out.get(source_id, []):
                if existing.target_id == target_id and existing.edge_type == edge_type:
                    raise GraphValidationError(
                        f"Duplicate edge: {source_id} --[{edge_type.value}]--> {target_id}",
                    )

            # Schema validation
            if self.validate_schema:
                self._validate_edge_schema(source_id, target_id, edge_type)

            edge = Edge(
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type,
                metadata=metadata or {},
            )
            self._edges_out[source_id].append(edge)
            self._edges_in[target_id].append(edge)

            self._log("add_edge", f"{source_id}->{target_id}", {
                "edge_type": edge_type.value,
            })

        return edge

    def remove_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str | EdgeType | None = None,
    ) -> int:
        """Remove edge(s) between source and target. Returns count removed."""
        if isinstance(edge_type, str):
            edge_type = EdgeType(edge_type)

        with self._lock:
            removed = 0
            for edge in list(self._edges_out.get(source_id, [])):
                if edge.target_id == target_id:
                    if edge_type is None or edge.edge_type == edge_type:
                        self._remove_edge_internal(edge)
                        removed += 1
            if removed:
                self._log("remove_edge", f"{source_id}->{target_id}", {
                    "count": removed,
                })
            return removed

    def get_edges_from(self, node_id: str) -> list[Edge]:
        """Get all outgoing edges from a node."""
        return list(self._edges_out.get(node_id, []))

    def get_edges_to(self, node_id: str) -> list[Edge]:
        """Get all incoming edges to a node."""
        return list(self._edges_in.get(node_id, []))

    def get_connected(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
        direction: str = "both",
    ) -> list[Node]:
        """
        Get all nodes connected to a given node.

        Args:
            node_id: The node to query from.
            edge_type: Optional filter by edge type.
            direction: "out", "in", or "both".
        """
        connected_ids: set[str] = set()

        if direction in ("out", "both"):
            for edge in self._edges_out.get(node_id, []):
                if edge_type is None or edge.edge_type == edge_type:
                    connected_ids.add(edge.target_id)

        if direction in ("in", "both"):
            for edge in self._edges_in.get(node_id, []):
                if edge_type is None or edge.edge_type == edge_type:
                    connected_ids.add(edge.source_id)

        return [self._nodes[nid] for nid in connected_ids if nid in self._nodes]

    @property
    def edges(self) -> list[Edge]:
        """All edges in the graph."""
        all_edges = []
        for edge_list in self._edges_out.values():
            all_edges.extend(edge_list)
        return all_edges

    @property
    def edge_count(self) -> int:
        return sum(len(el) for el in self._edges_out.values())

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def find_path(
        self,
        start_id: str,
        end_id: str,
        edge_types: set[EdgeType] | None = None,
    ) -> list[str] | None:
        """
        BFS shortest path from start to end, optionally filtered by edge types.
        Returns list of node IDs or None if no path exists.
        """
        if start_id not in self._nodes or end_id not in self._nodes:
            return None

        if start_id == end_id:
            return [start_id]

        visited: set[str] = {start_id}
        queue: deque[list[str]] = deque([[start_id]])

        while queue:
            path = queue.popleft()
            current = path[-1]

            for edge in self._edges_out.get(current, []):
                if edge_types and edge.edge_type not in edge_types:
                    continue
                if edge.target_id in visited:
                    continue
                new_path = path + [edge.target_id]
                if edge.target_id == end_id:
                    return new_path
                visited.add(edge.target_id)
                queue.append(new_path)

        return None

    def get_assembly_stack(self) -> list[Node]:
        """
        Return nodes ordered bottom-to-top by install_sequence.
        Only includes nodes that have an install_sequence set.
        """
        sequenced = [n for n in self._nodes.values() if n.install_sequence is not None]
        sequenced.sort(key=lambda n: n.install_sequence)
        return sequenced

    def get_subgraph(
        self,
        root_id: str,
        max_depth: int = 10,
        edge_types: set[EdgeType] | None = None,
    ) -> AssemblyGraph:
        """
        Extract a subgraph starting from root_id, traversing up to max_depth.
        Returns a new AssemblyGraph containing only reachable nodes and their edges.
        """
        if root_id not in self._nodes:
            raise GraphValidationError(f"Root node '{root_id}' not found")

        reachable: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(root_id, 0)])

        while queue:
            nid, depth = queue.popleft()
            if nid in reachable:
                continue
            reachable.add(nid)
            if depth >= max_depth:
                continue
            for edge in self._edges_out.get(nid, []):
                if edge_types and edge.edge_type not in edge_types:
                    continue
                if edge.target_id not in reachable:
                    queue.append((edge.target_id, depth + 1))
            for edge in self._edges_in.get(nid, []):
                if edge_types and edge.edge_type not in edge_types:
                    continue
                if edge.source_id not in reachable:
                    queue.append((edge.source_id, depth + 1))

        sub = AssemblyGraph(
            project_id=f"{self.project_id}:subgraph",
            validate_schema=False,  # Already validated in parent graph
        )

        for nid in reachable:
            node = self._nodes[nid]
            sub.add_node(
                node_id=node.node_id,
                node_type=node.node_type,
                attrs=dict(node.attrs),
                render_hints=dict(node.render_hints),
                install_sequence=node.install_sequence,
            )

        for nid in reachable:
            for edge in self._edges_out.get(nid, []):
                if edge.target_id in reachable:
                    sub.add_edge(
                        source_id=edge.source_id,
                        target_id=edge.target_id,
                        edge_type=edge.edge_type,
                        metadata=dict(edge.metadata),
                    )

        return sub

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self) -> GraphQuery:
        """Return a new fluent query builder."""
        return GraphQuery(self)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph to a dictionary."""
        return {
            "metadata": self._metadata,
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "change_log": [c.to_dict() for c in self._change_log],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the graph to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str | Path) -> None:
        """Save the graph to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any], validate: bool = True) -> AssemblyGraph:
        """Deserialize a graph from a dictionary."""
        metadata = data.get("metadata", {})
        project_id = metadata.get("project_id", "unknown")

        graph = cls(project_id=project_id, validate_schema=validate)
        graph._metadata = metadata

        for node_data in data.get("nodes", []):
            node = Node.from_dict(node_data)
            graph.add_node(
                node_id=node.node_id,
                node_type=node.node_type,
                attrs=node.attrs,
                render_hints=node.render_hints,
                install_sequence=node.install_sequence,
            )

        for edge_data in data.get("edges", []):
            edge = Edge.from_dict(edge_data)
            graph.add_edge(
                source_id=edge.source_id,
                target_id=edge.target_id,
                edge_type=edge.edge_type,
                metadata=edge.metadata,
            )

        return graph

    @classmethod
    def from_json(cls, json_str: str, validate: bool = True) -> AssemblyGraph:
        """Deserialize a graph from a JSON string."""
        return cls.from_dict(json.loads(json_str), validate=validate)

    @classmethod
    def load(cls, path: str | Path, validate: bool = True) -> AssemblyGraph:
        """Load a graph from a JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Graph file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data, validate=validate)

    # ------------------------------------------------------------------
    # Change log
    # ------------------------------------------------------------------

    @property
    def change_log(self) -> list[ChangeLogEntry]:
        """Immutable view of the change log."""
        return list(self._change_log)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _validate_edge_schema(
        self, source_id: str, target_id: str, edge_type: EdgeType
    ) -> None:
        """Validate an edge against the schema. Raises GraphValidationError on failure."""
        rules = EDGE_SCHEMA.get(edge_type)
        if rules is None:
            raise GraphValidationError(
                f"No schema rules defined for edge type '{edge_type.value}'",
            )

        source_type = self._nodes[source_id].node_type
        target_type = self._nodes[target_id].node_type

        for valid_sources, valid_targets in rules:
            source_ok = valid_sources is None or source_type in valid_sources
            target_ok = valid_targets is None or target_type in valid_targets
            if source_ok and target_ok:
                return  # Valid

        raise GraphValidationError(
            f"Edge schema violation: {source_type.value} --[{edge_type.value}]--> {target_type.value} is not allowed",
            {
                "source_id": source_id,
                "source_type": source_type.value,
                "target_id": target_id,
                "target_type": target_type.value,
                "edge_type": edge_type.value,
            },
        )

    def _remove_edge_internal(self, edge: Edge) -> None:
        """Remove an edge without locking (caller must hold lock)."""
        out_list = self._edges_out.get(edge.source_id, [])
        if edge in out_list:
            out_list.remove(edge)
        in_list = self._edges_in.get(edge.target_id, [])
        if edge in in_list:
            in_list.remove(edge)

    def _log(self, action: str, entity_id: str, details: dict[str, Any] | None = None) -> None:
        """Append to the change log (caller must hold lock for mutations)."""
        self._change_log.append(ChangeLogEntry(
            timestamp=time.time(),
            action=action,
            entity_id=entity_id,
            details=details or {},
        ))

    def __repr__(self) -> str:
        return (
            f"AssemblyGraph(project='{self.project_id}', "
            f"nodes={self.node_count}, edges={self.edge_count})"
        )
