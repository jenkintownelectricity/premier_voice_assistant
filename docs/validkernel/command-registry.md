# ValidKernel Command Registry v0.1

**Authority:** Lefebvre Design Solutions LLC
**Version:** 0.1
**Date:** 2026-03-05
**Status:** Active
**Parent:** ValidKernel Command Protocol v0.1

The Command Registry is the canonical index of all governed commands and their lifecycle states within a Governed Environment. It provides a single, machine-readable source of truth that tracks which commands have been issued, their current status, which commands supersede others, and where their receipts are stored. The registry links to receipts but does not duplicate them, maintaining a clean separation between the summary index and the detailed execution records. Command Registry state reflects execution outcomes. Git repositories are the reference implementation of VKG in version 0.1.

---

## Purpose

The Command Registry is the canonical index of all governed commands within a Governed Environment. It answers:

- **What commands have been issued?**
- **What is the current status of each command?**
- **Which commands supersede others?**
- **Where are the receipts?**

The registry is the single source of truth for command state. While PROGRESS.md and CLAUDE_LOG.md provide human-readable narrative, the registry provides machine-readable, queryable state.

---

## Role in the Governance Stack

```
ValidKernel Command Protocol v0.1
  └─ Defines command structure (rings, gates, bounds)

ValidKernel Command Receipts v0.1
  └─ Records execution outcome per command

ValidKernel Command Registry v0.1    ← this spec
  └─ Indexes all commands and links to receipts
```

The registry sits at the top of the governance stack as the master index. It does not replace receipts or the protocol -- it references them.

---

## Registry Storage

The canonical registry file lives at:

```
.validkernel/registry/command-registry.json
```

This is a single JSON file containing an array of command entries. It is updated in-place as commands are issued, executed, or superseded.

---

## Required Registry Fields

Each entry in the registry must include:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command_id` | string | Yes | Unique command identifier |
| `title` | string | Yes | Short human-readable description |
| `authority` | string | Yes | Person or entity who issued the command |
| `organization` | string | Yes | Issuing organization |
| `date_issued` | string | Yes | ISO 8601 date when the command was issued |
| `repository` | string | Yes | Repository name |
| `branch` | string | Yes | Git branch where work was committed |
| `commit_hash` | string | Yes | Git commit hash (empty if not yet executed) |
| `status` | string | Yes | Current lifecycle state (see Status Model) |
| `gate_result` | string | Yes | Ring 2 gate outcome (PASS/FAIL/NOT_EVALUATED) |
| `receipt_path` | string | Yes | Path to receipt JSON (empty if no receipt) |
| `receipt_status` | string | Yes | Receipt state (NONE/CREATED/VERIFIED) |
| `supersedes` | string | Yes | Command ID this entry replaces (empty if none) |
| `superseded_by` | string | Yes | Command ID that replaced this entry (empty if none) |
| `next_action` | string | Yes | Recommended follow-up action |
| `last_updated` | string | Yes | ISO 8601 datetime of last registry update |

---

## Status Model

### Lifecycle States

| Status | Meaning |
|--------|---------|
| `ISSUED` | Command has been created but not yet started |
| `IN_PROGRESS` | Command execution has begun but is not complete |
| `EXECUTED` | Command completed successfully |
| `BLOCKED` | Command could not execute; blocker identified |
| `PARTIAL` | Some outcomes completed, others blocked or deferred |
| `SUPERSEDED` | Command replaced by a newer command |
| `ARCHIVED` | Command is historical; no longer active or relevant |

### State Transitions

```
ISSUED → IN_PROGRESS → EXECUTED
                     → BLOCKED
                     → PARTIAL

Any state → SUPERSEDED (when superseded_by is set)
Any state → ARCHIVED (when no longer relevant)
```

---

## Update Rules

1. **On command issuance:** Create a new entry with status `ISSUED`, empty `commit_hash`, `receipt_path`, and `receipt_status: "NONE"`.

2. **On execution start:** Update status to `IN_PROGRESS`.

3. **On execution complete:** Update status to `EXECUTED`, set `commit_hash`, `gate_result`, and `last_updated`.

4. **On receipt creation:** Update `receipt_path` to the receipt file path and `receipt_status` to `"CREATED"`.

5. **On supersession:** Set `superseded_by` on the old entry and `supersedes` on the new entry. Old entry status becomes `SUPERSEDED`.

6. **On archival:** Set status to `ARCHIVED`. No other fields change.

7. **Immutability:** Once a `command_id` is assigned, it must never be reused. Command IDs are permanent.

8. **Ordering:** Entries should be ordered by `date_issued` (oldest first).

---

## Relationship to Receipts

The registry indexes receipts but does not duplicate them:

- `receipt_path` points to the receipt file (e.g., `.validkernel/receipts/L0-CMD-XXX.receipt.json`)
- `receipt_status` indicates whether a receipt exists and its verification state
- The receipt contains the detailed execution record; the registry contains the summary state

| `receipt_status` | Meaning |
|------------------|---------|
| `NONE` | No receipt has been created |
| `CREATED` | Receipt file exists at `receipt_path` |
| `VERIFIED` | Receipt has been validated (future: automated check) |

---

## Supersession Handling

When a new command replaces an old one:

1. Create the new entry with `supersedes` set to the old command ID
2. Update the old entry: set `superseded_by` to the new command ID, change `status` to `SUPERSEDED`
3. Both entries remain in the registry permanently (no deletion)

This preserves the full command history and allows tracing the evolution of governance decisions.

---

## Registry Operating Rule

> After any governed command is issued or executed, the command registry must be updated to reflect the current state. If a receipt exists, `receipt_path` must be linked. If a command is replaced, supersession fields must be set on both the old and new entries.

---

## Registry Template

A template file is provided at:

```
docs/validkernel/templates/command-registry.template.json
```

---

## Versioning

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-03-05 | Initial registry specification |

---

*ValidKernel Command Registry v0.1 -- Lefebvre Design Solutions LLC*
