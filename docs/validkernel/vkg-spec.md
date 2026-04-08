# ValidKernel Governance (VKG)

**Specification v0.1**

ValidKernel Governance (VKG) is a deterministic governance system in which commands are validated by a Runtime Gate, executed within defined capability bounds, recorded through receipts, and indexed in the Command Registry to produce an auditable execution history. VKG provides a structured command protocol, a pre-execution runtime gate, execution receipts, a command registry, and validation tooling so that governed work can be tracked and verified consistently. This specification defines the governance model, components, and rules that apply to all Governed Environments operating under VKG. Git repositories are the reference implementation of VKG in version 0.1.

---

## 1. Overview

ValidKernel Governance (VKG) is a deterministic governance system designed to control AI-assisted and human-assisted execution through governed commands and verifiable outcomes within Governed Environments.

VKG provides a governance layer that ensures:

- Authority traceability
- Bounded AI execution
- Deterministic commit gates
- Auditable execution records
- Reproducible state within Governed Environments
- Portable governance identity
- Runtime command enforcement

VKG replaces unstructured prompts or instructions with governed commands that produce verifiable receipts and are indexed in the Command Registry.

Every governed action must follow the canonical VKG governance loop:

```
Authority → Command → Runtime Gate → Execution → Receipt → Command Registry → Verification
```

No governed action may execute without passing the Runtime Gate.

---

## 2. Governed Environment

A Governed Environment is a system in which commands may be issued, validated, executed, recorded, and verified under VKG governance rules.

Examples of Governed Environments include:

- Git repositories
- CI/CD pipelines
- infrastructure management systems
- databases
- AI execution environments

These examples are illustrative and do not imply runtime support in VKG v0.1.

Git repositories are the reference implementation of VKG in version 0.1. All runtime tooling, registry structures, and receipt storage described in this specification operate within Git repository Governed Environments.

---

## 3. Core Governance Model

VKG is built around the canonical governance loop:

```
Authority → Command → Runtime Gate → Execution → Receipt → Command Registry → Verification
```

Each stage is represented by a VKG component. The Runtime Gate ensures commands are validated and permitted before execution occurs. Governance behavior must be deterministic and auditable. FAIL_CLOSED semantics are preserved throughout: if validation fails or system state is uncertain, execution must not proceed.

---

## 4. VKG Components

### 4.1 Authority Layer

The Authority Layer defines the trusted source of commands.

Authority is defined by L0 — Governance Context.

Example:

```
Authority: Armand Lefebvre
Organization: Lefebvre Design Solutions LLC
```

The authority layer establishes:

- Command ownership
- Governance responsibility
- Root trust for the Governed Environment

### 4.2 Portable Authority

Portable Authority extends the Authority Layer by allowing governance identity to be portable across multiple Governed Environments.

Instead of authority being tied to a single Governed Environment, VKG defines a Portable Authority identity that can issue commands across multiple Governed Environments.

Portable Authority enables:

- Cross-environment governance
- Multi-system authority delegation
- Portable governance identities
- Distributed command issuance

A Portable Authority identity may include:

- `authority_id`
- `authority_name`
- `organization`
- `contact`
- `governance_scope`
- `authority_version`

Example:

```
authority_id: VKG-AUTH-001
authority_name: Armand Lefebvre
organization: Lefebvre Design Solutions LLC
governance_scope: construction-ai-systems
```

Portable Authority identities may be stored in:

```
.validkernel/authority/
```

Example file:

```
.validkernel/authority/authority.json
```

Portable Authority allows VKG systems to recognize the same governance authority across multiple Governed Environments, including:

- Multiple repositories
- Distributed infrastructure
- CI/CD systems
- External partner systems

### Relationship to AuthorityLedger

Portable Authority and the MetaKernel's AuthorityLedger are complementary constructs with distinct ownership. VKG owns Portable Authority — the governance identity. The MetaKernel owns AuthorityLedger — the transferable authority chain that records what governance power a Portable Authority identity holds over specific resources.

- **Portable Authority** answers: *Who is this governance participant?* It defines identity fields (authority_id, authority_name, organization, contact, governance_scope, authority_version).
- **AuthorityLedger** answers: *What authority does this participant hold?* It records resource-specific grants (governed_resource_type, governed_resource_id, authority_level, delegation_scope, delegation_expiry, authority_status).

A Portable Authority identity without an AuthorityLedger entry is a recognized identity with no delegated governance power. An AuthorityLedger entry must reference a valid Portable Authority identity through its authority_holder field. Neither construct subsumes or replaces the other.

### 4.3 Command Protocol

Commands are structured instructions issued under the ValidKernel Command Protocol.

Each command contains deterministic sections:

```
L0 — Governance Context
L1 — Mission Directive
L2 — Deterministic Commit Gate
L3 — Capability Bound
Execution Notes (optional)
End Command
```

Commands define:

- Intent
- Constraints
- Validation gates
- Execution permissions

Commands are fail-closed by design. Commands are the only authorized mechanism for initiating governed actions.

### 4.4 Runtime Gate

The Runtime Gate is the enforcement layer that evaluates commands before execution is permitted.

The Runtime Gate determines whether execution may proceed by ensuring that commands satisfy governance rules and are authorized to run.

The Runtime Gate performs:

- Authority verification
- Command structure validation
- Capability boundary checks
- Commit gate preconditions
- Environment safety checks

If any rule fails, execution is blocked.

Example Runtime Gate evaluation:

```
if authority_valid
   and command_structure_valid
   and capability_bounds_respected
   and runtime_environment_safe
then
   gate_result = PASS
else
   gate_result = FAIL
   execution_blocked
```

When execution is blocked:

```
status = BLOCKED
gate_result = FAIL
blocked_reason = Runtime Gate rejection
```

In VKG v0.1, the runtime gate is implemented by `runtime-gate.py`, which performs structural validation of command documents.

### 4.5 Execution Warrant

An Execution Warrant is a narrow authorization permitting execution of a single governed command within defined capability bounds.

In VKG v0.1, Runtime Gate PASS functions as the effective execution warrant. The execution warrant is a logical authorization produced by Runtime Gate PASS and does not require a separate artifact file.

Execution may occur only after the Runtime Gate returns PASS and must occur only within the bounds defined by L3 — Capability Bound.

### 4.6 Execution Layer

Execution occurs when a command passes through the Runtime Gate and is interpreted by an execution agent.

Execution agents may include:

- Humans
- AI systems
- Automated tooling
- CI pipelines

Execution must respect the Capability Bound defined in L3.

### 4.7 Command Receipts

Every command execution produces a Command Receipt.

Receipts record:

- Command identity
- Authority
- Execution timestamp
- Branch and commit
- Files changed
- Gate result
- Execution status

Receipt storage location:

```
.validkernel/receipts/
```

Example receipt file:

```
.validkernel/receipts/L0-CMD-EXAMPLE-001.receipt.json
```

Receipts provide a verifiable record of governance execution. Receipts are recorded in the Command Registry.

### 4.8 Command Registry

The Command Registry is the canonical index of all commands and their lifecycle state within a Governed Environment.

Registry location:

```
.validkernel/registry/command-registry.json
```

The registry tracks:

- Issued commands
- Execution state
- Receipt linkage
- Supersession relationships
- Next actions

Command Registry state reflects execution outcomes.

This enables governance queries such as:

- What commands exist?
- Which commands completed?
- Which commands were blocked?
- Which commands supersede earlier work?

---

## 5. Command Ring Structure

VKG commands use a ring structure to separate concerns:

```
┌─────────────────────────────────────────┐
│  L0 — Governance Context                │
│  (Authority, ID, Date, Risk Class,      │
│   Scope, Command Format)                │
│  ┌───────────────────────────────────┐  │
│  │  L1 — Mission Directive           │  │
│  │  (Objective, Required Outcomes,   │  │
│  │   Constraints, Non-goals)         │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  L2 — Deterministic         │  │  │
│  │  │       Commit Gate           │  │  │
│  │  │  (Validation Checklist,     │  │  │
│  │  │   Gate Rule)                │  │  │
│  │  │  ┌───────────────────────┐  │  │  │
│  │  │  │  L3 — Capability      │  │  │  │
│  │  │  │       Bound           │  │  │  │
│  │  │  │  (TOUCH-ALLOWED,      │  │  │  │
│  │  │  │   NO-TOUCH,           │  │  │  │
│  │  │  │   ENFORCEMENT MODE)   │  │  │  │
│  │  │  └───────────────────────┘  │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**Ring responsibilities:**

| Ring | Role | Description |
|------|------|-------------|
| L0 | Governance Context | Identifies authority, command ID, date, risk class, and scope |
| L1 | Mission Directive | Defines objective, required outcomes, constraints, and non-goals |
| L2 | Deterministic Commit Gate | Checklist of pass/fail conditions that must all be satisfied |
| L3 | Capability Bound | Defines what the executor may and may not modify |

---

## 6. Deterministic Commit Gates

Commit Gates enforce success criteria before a command can be declared complete.

Example gate:

```
Validation Checklist
 [ ] schema normalization implemented
 [ ] validation gates enforced
 [ ] audit logging operational
 [ ] repository state clean
```

If any gate fails:

```
execution_result = BLOCKED
```

This prevents premature completion.

---

## 7. Capability Boundaries

Capability boundaries restrict what execution agents can modify.

Two categories exist:

- **TOUCH-ALLOWED**
- **NO-TOUCH**

Example:

```
TOUCH-ALLOWED
- documentation
- governance files

NO-TOUCH
- application runtime code
- deployment infrastructure
```

Enforcement mode is FAIL_CLOSED: if uncertain whether something is allowed, do not touch it.

---

## 8. Command Lifecycle

Commands move through defined lifecycle states.

```
ISSUED
   ↓
IN_PROGRESS
   ↓
EXECUTED
```

Alternative paths:

- `BLOCKED`
- `PARTIAL`
- `SUPERSEDED`
- `ARCHIVED`

The lifecycle state is recorded in:

- Command receipts
- Command Registry

---

## 9. Risk Classes

Every command must declare a Risk Class in its L0 — Governance Context section using the format:

```
Risk Class N (RCN)
```

Risk Classes range from RC0 (informational, no changes) to RC4 (critical, security or irreversible changes). See `risk-classes.md` for detailed definitions of each Risk Class.

---

## 10. Governance File Structure

A VKG-enabled Governed Environment (Git repository in v0.1) typically contains:

```
docs/
  validkernel/
    vkg-spec.md
    command-protocol.md
    command-execution-flow.md
    command-receipts.md
    command-registry.md
    governance-tools.md
    glossary.md
    risk-classes.md
    templates/

.validkernel/
  authority/
  receipts/
  registry/
  tools/
  state/
```

This structure separates governance metadata from application code.

---

## 11. Governance Rules

Governed Environments using VKG must follow these principles:

1. Commands must follow the ValidKernel Command Protocol.
2. Commands must pass the Runtime Gate before execution.
3. Execution may occur only after the Runtime Gate returns PASS.
4. Execution must occur only within the bounds defined by L3 — Capability Bound.
5. Every execution produces a Command Receipt.
6. Receipts are recorded in the Command Registry.
7. Command Registry state reflects execution outcomes.
8. Governance behavior must be deterministic and auditable.
9. FAIL_CLOSED semantics must be preserved.
10. Commands that replace earlier commands should mark them `SUPERSEDED`.
11. Portable Authority identity should be defined in `.validkernel/authority/authority.json`.

---

## 12. Failure Handling

When execution cannot complete, the execution agent must produce:

```
status = BLOCKED
gate_result = FAIL
blocked_reason = explanation
next_action = remediation
```

The receipt must reflect the failure state.

FAIL_CLOSED: if validation fails or system state is uncertain, execution must not proceed.

---

## 13. Verification

Verification confirms that execution followed governance rules.

Verification is performed by existing receipt validation and Command Registry consistency validation tooling as described by the current VKG documentation and tooling model.

Verification includes:

- Receipt field completeness and validity checks
- Registry consistency checks (receipt and registry agreement)
- Command ID existence in the registry
- Branch and commit hash agreement between receipt and registry

Verification does not introduce a new runtime stage, lifecycle state, or execution step.

---

## 14. Design Principles

VKG is designed around several principles.

**Determinism** — Execution outcomes must be predictable.

**Auditability** — Every command produces traceable evidence.

**Authority Traceability** — Command authority must be explicit and portable.

**Runtime Safety** — Commands must pass the Runtime Gate before execution.

**AI Safety** — AI agents operate under bounded capability rules.

**Simplicity** — Governance structures remain human-readable.

**FAIL_CLOSED** — If validation fails or system state is uncertain, execution must not proceed.

---

## 15. Versioning

This specification defines:

> **ValidKernel Governance (VKG) v0.1**

Future revisions should maintain backward compatibility where possible.

---

## 16. Relationship to ValidKernel

VKG functions as the governance layer of ValidKernel systems.

- **ValidKernel** defines the deterministic system kernel.
- **VKG** defines the governance protocol controlling that kernel.
- **Runtime Gate** enforces governance decisions before execution occurs.

Together they form a system capable of managing complex AI-assisted development while maintaining deterministic authority and auditability.

---

### Repository Placement

This specification should be stored at:

```
docs/validkernel/vkg-spec.md
```

---

*ValidKernel Governance (VKG) v0.1 — Lefebvre Design Solutions LLC*
