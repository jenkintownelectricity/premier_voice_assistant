# Construction Truth Spine Doctrine

## 1. Purpose

The Construction Truth Spine is the governed event-history backbone for construction truth. It defines how construction truth is represented as stateful, event-based, source-linked, append-only history within the Construction domain.

This doctrine establishes the canonical rules that govern the Truth Spine. Implementation details, schemas, and runtime behavior are defined elsewhere and must comply with this doctrine.

## 2. Core Principle

- Documents are evidence surfaces. They prove that information existed at a point in time but are not the canonical truth container.
- Canonical truth lives in extracted structured records and their event history.
- Truth is stateful, not static. The truth condition of a construction object changes over time through governed state transitions.

## 3. Truth Spine Rule

Construction truth must be preserved as an append-only history of state transitions and extracted facts. The Truth Spine is the canonical ledger for this history. No construction truth may be recorded outside the spine without explicit governance authorization.

## 4. Evidence Rule

Documents — shop drawings, submittals, RFIs, inspection reports, photos, as-builts — may support truth but must not be treated as the canonical truth container. Truth is extracted from documents and recorded as structured events in the spine. The document remains an evidence surface and traceability anchor.

## 5. Immutability Rule

Truth events are immutable once recorded. No event in the Truth Spine may be modified, overwritten, or deleted after it has been committed to the ledger.

## 6. Supersession Rule

Corrections occur only through superseding events, never by silent mutation of prior truth events. A superseding event references the event it corrects and records the new truth condition. The prior event remains in the ledger as historical record.

## 7. State Rule

Truth-bearing construction objects carry explicit state. State describes the truth condition of an object at a point in time. State transitions are the mechanism through which truth evolves. No object may change state without a recorded event.

## 8. Authority Rule

State transitions require traceable authority or source context. Every truth event must identify the authority under which it was recorded and the actor who produced it. Events without traceable authority are governance violations.

## 9. Identity Dependency Rule

Durable truth continuity depends on stable object identity. If the identity of a construction object is not yet governed or resolved, truth may be recorded provisionally but must not imply final continuity. Provisional truth must be explicitly marked and must fail closed on unstated continuity assumptions.

Stable object identity is a prerequisite for durable truth claims. The Truth Spine does not itself resolve identity — it depends on a governed identity system to provide stable identifiers.

## 10. Registry / Runtime / VKBUS Relationship

| Component | Role |
|-----------|------|
| **Governance** | Defines this doctrine and the rules governing the Truth Spine |
| **Registry** | Stores structural memory — catalogs objects, relationships, and topology |
| **Truth Spine** | Stores evented truth history — the append-only ledger of state transitions and extracted facts |
| **Runtime** | Later consumes and validates against Truth Spine state and event history |
| **VKBUS** | May observe and validate the Truth Spine but does not define truth |

Governance defines doctrine. The Truth Spine records truth. Runtime consumes truth. VKBUS validates presence and compliance. No component outside Governance may redefine truth rules.

---

## Safety Note

- This document defines governance doctrine only.
- No runtime code, schemas, or implementations are modified.
- No registry structures are changed.
- The Truth Spine described here is an architectural definition, not a declaration that a live event store exists.
