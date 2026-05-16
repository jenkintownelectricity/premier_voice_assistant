"""
Construction Assembly Knowledge Graph - Schema
===============================================

Exports all node types and the NODE_REGISTRY.
"""

from knowledge.schema.ontology import (
    # Enums
    MembraneType,
    InsulationType,
    DeckType,
    SubstrateType,
    FastenerType,
    AdhesiveType,
    SealantType,
    FlashingType,
    EdgeMetalProfile,
    DrainType,
    PenetrationShape,
    FireproofingType,
    StructuralMemberType,
    RenderStyleType,
    ViewModeType,
    FacerType,
    ReinforcementType,
    CoverBoardType,
    TaperDirection,
    FlashingMaterial,
    TerminationType,
    AVBType,
    WaterproofingType,
    FailureSeverity,
    # Spatial nodes
    Project,
    Building,
    Zone,
    Level,
    RoofArea,
    WallArea,
    TransitionCondition,
    # Physical nodes
    Assembly,
    Layer,
    Material,
    Membrane,
    Insulation,
    CoverBoard,
    Deck,
    Substrate,
    Fastener,
    Adhesive,
    Sealant,
    # Connection nodes
    Flashing,
    Termination,
    EdgeMetal,
    Drain,
    Scupper,
    Penetration,
    Opening,
    # Protection nodes
    AVBLayer,
    WaterproofingLayer,
    FireproofingSystem,
    # Structural nodes
    StructuralMember,
    FireRatingRequirement,
    ULDesign,
    # Compliance nodes
    CodeReference,
    ManufacturerSystem,
    ValidationRule,
    FailureMode,
    # Workflow nodes
    InstallationStep,
    # Artifact nodes
    DetailArtifact,
    ArtifactLineage,
    RenderStyle,
    ViewMode,
    # UI nodes
    UIState,
    OverlaySet,
    # Registry
    NODE_REGISTRY,
    NODE_FAMILIES,
    export_all_schemas,
)

__all__ = [
    # Enums
    "MembraneType",
    "InsulationType",
    "DeckType",
    "SubstrateType",
    "FastenerType",
    "AdhesiveType",
    "SealantType",
    "FlashingType",
    "EdgeMetalProfile",
    "DrainType",
    "PenetrationShape",
    "FireproofingType",
    "StructuralMemberType",
    "RenderStyleType",
    "ViewModeType",
    "FacerType",
    "ReinforcementType",
    "CoverBoardType",
    "TaperDirection",
    "FlashingMaterial",
    "TerminationType",
    "AVBType",
    "WaterproofingType",
    "FailureSeverity",
    # Spatial nodes
    "Project",
    "Building",
    "Zone",
    "Level",
    "RoofArea",
    "WallArea",
    "TransitionCondition",
    # Physical nodes
    "Assembly",
    "Layer",
    "Material",
    "Membrane",
    "Insulation",
    "CoverBoard",
    "Deck",
    "Substrate",
    "Fastener",
    "Adhesive",
    "Sealant",
    # Connection nodes
    "Flashing",
    "Termination",
    "EdgeMetal",
    "Drain",
    "Scupper",
    "Penetration",
    "Opening",
    # Protection nodes
    "AVBLayer",
    "WaterproofingLayer",
    "FireproofingSystem",
    # Structural nodes
    "StructuralMember",
    "FireRatingRequirement",
    "ULDesign",
    # Compliance nodes
    "CodeReference",
    "ManufacturerSystem",
    "ValidationRule",
    "FailureMode",
    # Workflow nodes
    "InstallationStep",
    # Artifact nodes
    "DetailArtifact",
    "ArtifactLineage",
    "RenderStyle",
    "ViewMode",
    # UI nodes
    "UIState",
    "OverlaySet",
    # Registry
    "NODE_REGISTRY",
    "NODE_FAMILIES",
    "export_all_schemas",
]
