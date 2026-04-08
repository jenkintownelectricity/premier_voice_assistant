# ValidKernel Command Execution Flow

**Specification v0.1**

This specification defines the exact sequence of stages that every governed command must traverse from issuance to completion within a Governed Environment. The canonical runtime flow is: Command → Runtime Gate → Execution → Receipt → Registry Update. Each stage is mandatory and must produce its defined output before the next stage begins. The Runtime Gate determines whether execution is permitted; if it returns FAIL, execution is blocked. Every execution produces a receipt, and receipts are recorded in the Command Registry. The flow enforces FAIL_CLOSED semantics throughout: if any stage fails, no downstream stages execute.

---

## 1. Purpose

This specification defines the exact sequence of stages that every governed command must traverse from issuance to completion within a Governed Environment. It ensures that command execution is deterministic, auditable, and reproducible.

The execution flow is the runtime backbone of VKG. Without it, commands are definitions without behavior. Git repositories are the reference implementation of VKG in version 0.1.

---

## 2. Execution Sequence

Every governed command follows this canonical flow:

```
Command → Runtime Gate → Execution → Receipt → Registry Update
```

Each stage is mandatory. Skipping a stage is a governance violation.

---

## 3. Stage Definitions

### Stage 1: Command

A structured instruction issued under the ValidKernel Command Protocol v0.1 by a recognized Portable Authority.

**Input:** Human intent, governance context.
**Output:** A well-formed command containing L0 governance context, Ring 1 mission directive, Ring 2 deterministic commit gate, Ring 3 capability bound.

### Stage 2: Runtime Gate

The ValidKernel Runtime Gate (VKRT) evaluates the command before execution is permitted.

**Input:** A well-formed command.
**Output:** `PASS` (execution proceeds) or `FAIL` (execution blocked).

### Stage 3: Execution

An execution agent interprets the command and performs the work within the capability bounds defined in Ring 3.

**Input:** A gate-passed command.
**Output:** Repository changes (files created, modified, or deleted).

### Stage 4: Receipt

A Command Receipt is produced recording the execution outcome.

**Input:** Execution results, command metadata, commit hash.
**Output:** A receipt JSON file stored in `.validkernel/receipts/`.

### Stage 5: Registry Update

The Command Registry is updated to reflect the command's current lifecycle state.

**Input:** Receipt data, commit hash, execution status.
**Output:** Updated entry in `.validkernel/registry/command-registry.json`.

---

## 4. Canonical Flow Rules

1. **Sequential execution.** Stages must execute in order: command → gate → execution → receipt → registry.
2. **No stage skipping.** Every stage must produce its defined output before the next stage begins.
3. **Fail-closed.** If any stage fails, the flow halts. No downstream stages execute.
4. **Single authority.** Each flow instance is bound to exactly one command from one Portable Authority.
5. **Immutable receipts.** Once a receipt is created, it must not be modified. Corrections require a new command.
6. **Registry reflects truth.** The registry entry must match the receipt. Discrepancies are governance violations.

---

## 5. State Machine

Commands transition through lifecycle states as they progress through the flow:

```
           ┌──────────┐
           │  ISSUED   │
           └─────┬─────┘
                 │ (enter gate)
           ┌─────▼─────┐
           │IN_PROGRESS │
           └─────┬─────┘
                 │
        ┌────────┼────────┐
        │        │        │
  ┌─────▼──┐ ┌──▼───┐ ┌──▼─────┐
  │BLOCKED │ │PARTIAL│ │EXECUTED│
  └────────┘ └───────┘ └────────┘
                              │
                        ┌─────▼─────┐
                        │SUPERSEDED │ (if replaced)
                        └───────────┘
                              │
                        ┌─────▼─────┐
                        │ ARCHIVED  │ (if retired)
                        └───────────┘
```

**State transitions:**

| From | To | Trigger |
|------|----|---------|
| ISSUED | IN_PROGRESS | Execution agent begins work |
| IN_PROGRESS | EXECUTED | All gate checks pass, receipt created |
| IN_PROGRESS | BLOCKED | VKRT rejects or gate check fails |
| IN_PROGRESS | PARTIAL | Some outcomes achieved, others blocked |
| EXECUTED | SUPERSEDED | A newer command replaces this one |
| SUPERSEDED | ARCHIVED | Command retired from active governance |

---

## 6. Stage Inputs and Outputs

| Stage | Input | Output | Stored At |
|-------|-------|--------|-----------|
| Command | Human intent | Well-formed command document | Inline or `docs/` |
| Runtime Gate | Command document | PASS/FAIL decision | Evaluated in-agent |
| Execution | Gate-passed command | Repository changes | Working tree + commit |
| Receipt | Execution results | Receipt JSON | `.validkernel/receipts/` |
| Registry Update | Receipt data | Updated registry entry | `.validkernel/registry/command-registry.json` |

---

## 7. Runtime Gate Evaluation

The VKRT evaluation at Stage 2 must check:

1. **Authority verification.** Is the command issuer a recognized Portable Authority?
2. **Command structure.** Does the command contain all required sections (L0, Ring 1, Ring 2, Ring 3)?
3. **Capability bounds.** Are TOUCH-ALLOWED and NO-TOUCH lists defined and non-contradictory?
4. **Gate preconditions.** Are Ring 2 checklist items evaluable?
5. **Repository safety.** Is the working tree clean? Is the correct branch checked out?

If all checks pass:

```
gate_result = PASS
status = IN_PROGRESS
```

If any check fails:

```
gate_result = FAIL
status = BLOCKED
blocked_reason = <specific failure>
```

---

## 8. Receipt Creation

After execution completes, a receipt must be created containing:

| Field | Required | Description |
|-------|----------|-------------|
| command_id | Yes | The command being executed |
| authority | Yes | Portable Authority identity |
| organization | Yes | Authority's organization |
| execution_timestamp | Yes | ISO 8601 timestamp |
| branch | Yes | Git branch where work occurred |
| commit_hash | Yes | Final commit hash |
| files_changed | Yes | List of files created/modified/deleted |
| gate_result | Yes | PASS or FAIL |
| execution_status | Yes | EXECUTED, BLOCKED, or PARTIAL |
| notes | No | Additional context |

Receipt files are stored at:

```
.validkernel/receipts/<command_id>.receipt.json
```

---

## 9. Registry Update

After the receipt is created, the registry must be updated:

1. Locate the command entry in `.validkernel/registry/command-registry.json`.
2. If no entry exists, create one.
3. Update the following fields: `status`, `gate_result`, `commit_hash`, `receipt_path`, `receipt_status`, `last_updated`.
4. If this command supersedes another, update both entries (`supersedes` and `superseded_by`).
5. Set `next_action` to reflect what follows this command.

---

## 10. Example Execution Flows

### Successful Execution

```
1. Command L0-CMD-EXAMPLE-001 issued by Portable Authority VKG-AUTH-001
2. VKRT evaluates: authority ✓, structure ✓, bounds ✓, preconditions ✓, repo clean ✓
   → gate_result = PASS
3. Execution agent performs work, creates/modifies files
   → commit abc1234
4. Receipt created: .validkernel/receipts/L0-CMD-EXAMPLE-001.receipt.json
   → execution_status = EXECUTED
5. Registry updated: status = EXECUTED, commit_hash = abc1234
```

### Blocked Execution

```
1. Command L0-CMD-EXAMPLE-002 issued by Portable Authority VKG-AUTH-001
2. VKRT evaluates: authority ✓, structure ✓, bounds ✓, preconditions ✗ (dirty working tree)
   → gate_result = FAIL
3. Execution does not proceed
4. Receipt created: .validkernel/receipts/L0-CMD-EXAMPLE-002.receipt.json
   → execution_status = BLOCKED, blocked_reason = "Working tree not clean"
5. Registry updated: status = BLOCKED, next_action = "Clean working tree and re-issue"
```

### Partial Execution

```
1. Command L0-CMD-EXAMPLE-003 issued (5 required outcomes)
2. VKRT evaluates: all checks pass → gate_result = PASS
3. Execution agent completes 3 of 5 outcomes, 2 blocked by external dependency
4. Receipt created: execution_status = PARTIAL, completed = [1,2,3], blocked = [4,5]
5. Registry updated: status = PARTIAL, next_action = "Resolve dependency and continue"
```

---

## 11. Failure Semantics

| Failure Point | Behavior | Recovery |
|---------------|----------|----------|
| Malformed command | Flow does not start | Fix command structure, re-issue |
| VKRT rejection | Execution blocked | Address rejection reason, re-issue |
| Execution error | Receipt records failure | Fix issue, issue new command |
| Receipt creation fails | Registry not updated | Create receipt manually, update registry |
| Registry update fails | Receipt exists but unindexed | Update registry manually |

**Principle:** The flow never silently fails. Every failure produces a record.

---

## 12. Verification Model

After a flow completes, verification confirms governance compliance:

1. **Command exists** — A well-formed command was issued.
2. **Gate evaluated** — VKRT produced a PASS/FAIL decision.
3. **Execution bounded** — Changes stayed within Ring 3 capability bounds.
4. **Receipt exists** — A receipt JSON file records the outcome.
5. **Registry consistent** — The registry entry matches the receipt.
6. **Commit traceable** — The commit hash in the receipt matches a real commit.

Verification can be performed manually or by future automated tooling.

---

## 13. Design Principles

**Determinism** — Given the same command and repository state, the flow produces the same outcome.

**Traceability** — Every stage produces evidence that can be audited.

**Fail-closed** — Ambiguity or missing data halts the flow rather than proceeding with assumptions.

**Separation of concerns** — The gate evaluates, the agent executes, the receipt records, the registry indexes.

**Minimal state** — The flow carries only what each stage needs. No hidden state accumulates between stages.

---

## 14. Repository Placement

This specification should be stored at:

```
docs/validkernel/command-execution-flow.md
```

---

## 15. Relationship to VKG

The Command Execution Flow is the runtime manifestation of VKG. While VKG defines the governance model, components, and rules, this specification defines how those components interact at execution time.

| VKG Component | Execution Flow Stage |
|---------------|---------------------|
| Command Protocol | Stage 1: Command |
| VKRT | Stage 2: Runtime Gate |
| Execution Layer | Stage 3: Execution |
| Command Receipts | Stage 4: Receipt |
| Command Registry | Stage 5: Registry Update |
| Portable Authority | Validated at Stage 2 |
| Capability Boundaries | Enforced at Stage 3 |
| Deterministic Commit Gates | Evaluated at Stage 2 |

---

*ValidKernel Command Execution Flow v0.1 — Lefebvre Design Solutions LLC*
