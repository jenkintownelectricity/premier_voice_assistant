"""
Construction Assembly Knowledge Graph
======================================

A domain-specific knowledge graph for modeling commercial roofing and building
envelope assemblies. The graph captures spatial relationships (buildings, zones,
roof areas), physical components (membranes, insulation, fasteners), code
compliance (UL designs, fire ratings, code references), workflow sequences
(installation steps, validation rules), and visual artifacts (detail drawings,
overlays).

Node families:
    - Spatial:     Project, Building, Zone, Level, RoofArea, WallArea
    - Physical:    Assembly, Layer, Material, Membrane, Insulation, CoverBoard,
                   Deck, Substrate, Fastener, Adhesive, Sealant
    - Connection:  Flashing, Termination, EdgeMetal, Drain, Scupper,
                   Penetration, Opening, TransitionCondition
    - Protection:  AVBLayer, WaterproofingLayer, FireproofingSystem
    - Structural:  StructuralMember, FireRatingRequirement, ULDesign
    - Compliance:  CodeReference, ManufacturerSystem, ValidationRule, FailureMode
    - Workflow:    InstallationStep
    - Artifact:    DetailArtifact, ArtifactLineage, RenderStyle, ViewMode
    - UI:          UIState, OverlaySet
"""
