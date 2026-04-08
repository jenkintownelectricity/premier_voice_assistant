# ValidKernel V2 Doctrine

> Canonical doctrine for ValidKernel V2. Defines primary areas, growth model, birth lineage, and invariant rules.

---

## Key Phrases

- **Soft Handoff, Hard Lineage** — the V2 growth model.
- **Slow-Grown Specialization** — invariants accumulate one at a time under operational pressure.

---

## Primary Areas

Every V2 entity belongs to exactly one primary area. There are five:

| Primary Area | Governs |
|--------------|---------|
| **Truth** | Canonical facts, state ownership, provenance |
| **Governance** | Authority, commands, validation, enforcement |
| **Execution** | Bounded work, task graphs, worker dispatch |
| **Capabilities** | Declared capacities, resource envelopes, tool/model access |
| **Interfaces** | Contracts between areas, consumption rules, boundary protocols |

Assignment to a primary area is mandatory at entity creation and does not change.

---

## Growth Model: Soft Handoff, Hard Lineage

V2 entities grow through soft handoff, not forced prescription.

**Soft Handoff** means a parent entity provides context and constraints to a descendant, but does not dictate the descendant's internal structure. The descendant inherits lineage and minimum invariants, then specializes under its own operational pressure.

**Hard Lineage** means every entity's origin is permanently recorded. The `grown_from` field is frozen at creation and is never rewritten. Lineage is a fact, not a policy — it cannot be retroactively altered.

Together: entities receive what they need to begin (soft handoff) and permanently record where they came from (hard lineage).

---

## Frozen Birth Lineage

Every V2 entity has a `grown_from` field set at creation time. This field identifies the parent entity (or root, if none) from which the entity was derived.

Rules:

1. `grown_from` is set once, at creation.
2. `grown_from` is immutable after creation. No process may modify it.
3. If an entity has no parent, `grown_from` is set to a designated root sentinel.
4. Lineage chains are acyclic. An entity cannot be its own ancestor.

Frozen birth lineage enables reliable provenance reconstruction. Any entity's full ancestry can be traced by walking the `grown_from` chain to root.

---

## Slow-Grown Specialization

Invariants are not imposed in bulk. They accumulate one at a time, each added only when operational pressure demonstrates the need.

Process:

1. An entity begins with the minimum invariants required by its primary area.
2. New invariants are added individually, in response to observed operational need.
3. Each new invariant is recorded with the pressure that motivated it.
4. Invariants are not removed without explicit governance action.

This prevents speculative over-constraint and ensures every invariant is operationally justified.

---

## Minimum Area Invariants

Each primary area defines a minimum set of invariants that every entity in that area must satisfy at creation. These are the floor, not the ceiling.

| Primary Area | Minimum Invariants |
|--------------|--------------------|
| **Truth** | Must have a canonical identity. Must declare state ownership. |
| **Governance** | Must identify authority. Must be validatable by the runtime gate. |
| **Execution** | Must declare capability bounds. Must reference a governing command. |
| **Capabilities** | Must declare at least one capability. Must specify resource envelope. |
| **Interfaces** | Must name both sides of the boundary. Must declare consumption direction. |

Additional invariants are added through slow-grown specialization, not at creation.

---

## V2 Rules

These rules are normative. Violations are governance failures.

1. **Truth bounded by lineage.** An entity's truth claims are scoped by its lineage chain. No entity may assert truth outside the scope established by its ancestors.

2. **Primary area required.** Every entity must declare exactly one primary area at creation. The primary area does not change.

3. **`grown_from` frozen.** The `grown_from` field is set at creation and is immutable. No process may overwrite, clear, or redirect it.

4. **Historical architecture record.** Changes to entity structure, invariants, or area assignments are recorded as historical facts. The system maintains a tamper-evident record of architectural evolution.

5. **Soft handoff, not forced prescription.** Parent entities provide lineage and minimum invariants to descendants. They do not prescribe internal structure. Descendants specialize independently.

6. **Slow invariant growth.** Invariants are added one at a time, each motivated by demonstrated operational pressure. Bulk invariant imposition is a governance violation.

7. **Registry integration required (V2.1).** Every new entity and every material entity change must produce a registry record, a state record, and a lineage record in ValidKernel_Registry. An entity is not architecturally integrated until these records exist.

---

## V2.1 — Registry Integration Rule

Every new entity and every material entity change must produce three records
in ValidKernel_Registry:

1. **Registry record** — identity and classification (name, type, primary area, ownership).
2. **State record** — lifecycle state of the entity (active, deprecated, superseded, etc.).
3. **Lineage record** — frozen origin and inheritance (`grown_from`, creation context).

An entity is **not considered architecturally integrated** until all three records exist
in the Registry.

### Purpose

Registry integration prevents architectural drift. Without it, entities can exist in
code or governance without being visible to the system's structural memory. V2.1 closes
that gap by requiring every material entity to be cataloged, state-tracked, and
lineage-recorded at the point of creation or change.

### Scope

This rule applies to all entity types across all five primary areas:

- Kernels
- Repositories
- Domain operating systems
- Major subsystems
- Architectural entities

Primary area assignment (truth, governance, execution, capabilities, interfaces)
does not exempt an entity from registry integration.

### Material Entity Changes

A "material entity change" includes at minimum:

- Entity creation
- Primary area change
- Ownership or role change
- Lifecycle state change (e.g., active → deprecated)
- Lineage correction, supersession, or reclassification

Cosmetic changes (documentation wording, formatting) do not trigger this rule.

### Integration Definition

An entity is architecturally integrated when:

1. A registry record exists identifying the entity and its classification.
2. A state record exists reflecting the entity's current lifecycle state.
3. A lineage record exists preserving the entity's frozen origin.

Until all three exist, the entity is considered **structurally unregistered**,
regardless of whether it functions correctly at runtime.

### VKBUS Relationship

ValidKernelOS_VKBUS may observe registry integration state and may assist with
integration workflows in the future. However, the Registry is the canonical
structural memory — VKBUS is a non-canonical growth bus that references it.

### Relationship to V2.0

V2.0 is the frozen reference baseline for ValidKernel structural doctrine (primary areas,
growth model, birth lineage, slow-grown specialization, and rules 1–6 above).

V2.1 is **additive** to V2.0. It introduces one new obligation — registry integration —
without rewriting, redefining, or weakening any V2.0 rule. All V2.0 definitions,
invariants, and semantics remain in force and unchanged.

### Canonical Ownership

- **ValidKernel-Governance** is the canonical doctrine source. All doctrine rules,
  including V2.1, are authored and versioned here.
- **ValidKernel_Registry** is the canonical structural memory. It stores the registry,
  state, and lineage records that V2.1 requires.
- **ValidKernelOS_VKBUS** is a non-canonical growth bus. It may observe integration
  state but does not own doctrine or structural truth.

### Doctrine Versioning Posture

**Clarifications may edit. Obligation changes must version.**

- A documentation revision that clarifies existing meaning without adding, changing,
  or removing obligations does not require a doctrine version change.
- A revision that creates, changes, or removes obligations for upstream or canonical
  entities is an obligation change and must increment the doctrine version.
- V2.1 is an obligation change (it requires new records) and is therefore versioned.

---

## V2.2 — Lineage and Upstream Affinity Rule

Every entity must declare exactly one primary lineage parent through `grown_from`.
`grown_from` defines architectural birth lineage and remains singular and frozen.

If an entity was materially shaped by another upstream entity and a real architectural
decision had to be made about which upstream entity was the parent, that non-parent
influence may be recorded using `upstream_affinity`.

### Upstream Affinity Is Conditional

`upstream_affinity` is not required when parentage is clear.
If no ambiguity exists, `upstream_affinity` should be omitted or null.

Use `upstream_affinity` only when all of the following are true:

- More than one upstream entity could reasonably be interpreted as the parent.
- One entity was chosen as the true parent in `grown_from`.
- Another upstream entity still materially shaped the entity's posture, structure, or architectural form.
- That influence is stronger than a casual relation and worth preserving for human and machine interpretation.

Do not use `upstream_affinity` for obvious lineage, weak associations, generic dependencies,
tooling interactions, ordinary references, or broad cross-repo awareness.

### Upstream Affinity Does Not Create Multi-Parent Lineage

`upstream_affinity` does not replace lineage, does not weaken `grown_from`, and does not
create multi-parent birth. Every entity has exactly one architectural parent. `upstream_affinity`
records a conditional, non-parent structural influence — nothing more.

### Example

| Entity | `grown_from` | `upstream_affinity` |
|---|---|---|
| Construction_Assembly_Kernel | Construction_Kernel | omitted |
| Construction_Runtime | Construction_Kernel | ValidKernel_Runtime |

In the first case, parentage is obvious — no affinity needed.
In the second case, both Construction_Kernel and ValidKernel_Runtime materially shaped
the entity, and a real architectural decision selected Construction_Kernel as the parent.

### VKBUS Boundary

ValidKernelOS_VKBUS may observe lineage and upstream affinity and may later assist
registry integration or bounded write-through application of these fields. However:

- VKBUS does not define lineage doctrine.
- VKBUS is not the canonical owner of lineage truth.
- VKBUS must not interpret `upstream_affinity` as second parentage.
- VKBUS must preserve singular `grown_from` authority.

### Canonical Ownership

- **ValidKernel-Governance** is the canonical doctrine source for lineage rules.
- **ValidKernel_Registry** is the canonical structural memory that records `grown_from`
  and `upstream_affinity` fields.
- **ValidKernelOS_VKBUS** is a non-canonical observer and helper.

### Relationship to V2.0 and V2.1

V2.2 is additive. It does not rewrite or weaken V2.0 frozen birth lineage rules or
V2.1 registry integration requirements. It clarifies when `upstream_affinity` applies
and when it should be omitted.

---

## Relationship to V1

V2 does not replace V1 governance mechanics (command protocol, runtime gate, receipts, registry, FAIL_CLOSED semantics). V2 adds a structural doctrine layer — primary areas, birth lineage, and growth rules — that governs how entities are created, classified, and allowed to evolve.

V1 governs what happens. V2 governs what things are and where they came from.

---

## Canonical Location

This document is the canonical V2 doctrine reference. It lives at:

```
docs/validkernel/v2-doctrine.md
```

All V2 implementation and specification work must be consistent with this document.
