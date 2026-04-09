"""
Construction Assembly Knowledge Graph - Artifact System
========================================================

Generates deterministic, traceable drawing artifacts from knowledge graph
subgraphs.  Each artifact carries a SHA-256 fingerprint, full lineage, and
the resolved render primitives required to produce the output.

Modules:
    generator   - ArtifactType enum, DetailArtifact dataclass, and the
                  ArtifactGenerator engine that transforms graph data into
                  exportable drawing artifacts.
"""

from knowledge.artifacts.generator import (
    ArtifactType,
    DetailArtifact,
    ArtifactGenerator,
)

__all__ = [
    "ArtifactType",
    "DetailArtifact",
    "ArtifactGenerator",
]
