# ValidKernel Command Protocol v0.1

**Authority:** Lefebvre Design Solutions LLC
**Version:** 0.1
**Date:** 2026-03-05
**Status:** Active

The ValidKernel Command Protocol defines the structured format used to issue governed commands within ValidKernel Governance (VKG). Every command follows a deterministic ring structure consisting of L0 — Governance Context, L1 — Mission Directive, L2 — Deterministic Commit Gate, and L3 — Capability Bound. The protocol ensures that every governed action has clear authority, explicit scope, binary validation gates, hard capability limits, and an audit trail. Commands operate under FAIL_CLOSED enforcement: if any validation check is ambiguous or incomplete, execution halts.

---

## Purpose

The ValidKernel Command Protocol defines a structured, deterministic format for issuing governance commands to AI agents and human operators within Governed Environments. It ensures that every command has:

- **Clear authority** — who is issuing the command and why
- **Explicit scope** — what must be done, what must not be touched
- **Risk classification** — the risk level of the governed action
- **Deterministic validation** — a commit gate that passes or fails with no ambiguity
- **Capability bounds** — hard limits on what the executor is allowed to modify
- **Audit trail** — every command is numbered, tracked, and logged

The protocol operates under a **FAIL_CLOSED** enforcement model: if any validation check is ambiguous or incomplete, execution halts. No silent passes. No assumed intent.

Git repositories are the reference implementation of VKG in version 0.1.

---

## Command Ring Structure

The protocol uses a layered ring model to separate concerns:

| Ring | Name | Purpose |
|------|------|---------|
| L0 | Governance Context | Identifies the authority, organization, command ID, date, risk class, and scope |
| L1 | Mission Directive | Defines the objective, required outcomes, and deliverables |
| L2 | Deterministic Commit Gate | A checklist of pass/fail conditions that must ALL be satisfied before completion |
| L3 | Capability Bound | Explicitly defines what the executor MAY and MAY NOT touch |

An optional **Execution Notes** section provides guidance, suggested language, or implementation hints.

---

## Command Document Structure

Every ValidKernel command follows this structure:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L0 — GOVERNANCE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Authority:     <Name>, <Role> — <Organization>
Document ID:   <L0-CMD-YYYY-MMDD-NNN> or <descriptive ID>
Date:          <YYYY-MM-DD>
Risk Class:    Risk Class N (RCN)
Scope:         <One-paragraph summary of what this command does>
Command Format: ValidKernel Command Protocol v0.1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L1 — MISSION DIRECTIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objective:
<What must be accomplished>

Required Outcomes:
1. <Outcome 1>
2. <Outcome 2>
...

Constraints:
- <What must NOT happen>
- <Boundaries on the work>

Non-goals:
- <Explicitly out of scope>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L2 — DETERMINISTIC COMMIT GATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Validation Checklist:
[ ] <Check 1>
[ ] <Check 2>
...

Gate Rule:
If any item fails → HALT and report exact blocker.

Gate Result:
PASS required before final response.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L3 — CAPABILITY BOUND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOUCH-ALLOWED:
- <File, directory, or system the executor may modify>

NO-TOUCH:
- <File, directory, or system the executor must NOT modify>

ENFORCEMENT MODE: FAIL_CLOSED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXECUTION NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<Optional guidance, suggested language, implementation hints>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END COMMAND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Block Definitions

### L0 — Governance Context

The header block. Establishes who, when, what, and how risky.

| Field | Required | Description |
|-------|----------|-------------|
| Authority | Yes | The person or entity issuing the command |
| Document ID | Yes | Unique identifier for tracking and audit |
| Date | Yes | ISO 8601 date of issuance |
| Risk Class | Yes | Risk classification using format "Risk Class N (RCN)" where N is 0–4 |
| Scope | Yes | One-paragraph summary of the command's purpose |
| Command Format | Recommended | Protocol version declaration |

### L1 — Mission Directive

The body of the command. Defines what must happen.

| Field | Required | Description |
|-------|----------|-------------|
| Objective | Yes | Clear statement of what the command accomplishes |
| Required Outcomes | Yes | Numbered list of deliverables with specific acceptance criteria |
| Constraints | Recommended | Boundaries on how the work is performed |
| Non-goals | Recommended | Explicitly out-of-scope items to prevent scope creep |

### L2 — Deterministic Commit Gate

The validation checkpoint. Binary pass/fail.

| Field | Required | Description |
|-------|----------|-------------|
| Validation Checklist | Yes | List of `[ ]` items that must all be checked before completion |
| Gate Rule | Yes | Statement of what happens on failure (always HALT) |
| Gate Result | Recommended | Final pass/fail declaration |

**Rules:**
- Every checklist item must be independently verifiable
- No subjective criteria ("looks good" is not a valid check)
- The gate is atomic: ALL items must pass, or the command fails
- Failed items must report the exact blocker, not a generic error

### L3 — Capability Bound

The permission model. Defines the blast radius.

| Field | Required | Description |
|-------|----------|-------------|
| TOUCH-ALLOWED | Yes | Explicit list of files, directories, or systems the executor may modify |
| NO-TOUCH | Yes | Explicit list of what must not be modified |
| ENFORCEMENT MODE | Yes | Always `FAIL_CLOSED` — if uncertain whether something is allowed, do not touch it |

### Execution Notes (Optional)

Non-binding guidance for the executor. May include:
- Suggested commit messages
- Recommended documentation language
- Implementation hints
- Testing guidance

---

## Enforcement Rules

1. **FAIL_CLOSED**: If any check is ambiguous, uncertain, or incomplete, the command fails. No silent passes.
2. **No fabrication**: The executor must not claim completion of work that was not performed (e.g., "tests pass" when no tests were run).
3. **No scope creep**: The executor must not perform work outside the Required Outcomes, even if it seems beneficial.
4. **Atomic gate**: The L2 checklist is all-or-nothing. Partial completion is a failure.
5. **Audit trail**: Every command execution must be logged with: command ID, branch, commit hash, files changed, and gate result.
6. **Authority chain**: Only the declared Authority (or their delegate) may issue commands. The executor must not self-authorize new commands.
7. **Capability enforcement**: L3 bounds are hard limits. Touching a NO-TOUCH item is a protocol violation, not a judgment call.

---

## Example Command

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L0 — GOVERNANCE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Authority:     Armand Lefebvre, L0 — Lefebvre Design Solutions LLC
Document ID:   L0-CMD-2026-0305-001
Date:          2026-03-05
Risk Class:    Risk Class 2 (RC2)
Scope:         Add a health check banner to the dashboard view.
Command Format: ValidKernel Command Protocol v0.1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L1 — MISSION DIRECTIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objective:
Display a green/red health check banner on the dashboard that
calls GET /health and shows API status.

Required Outcomes:
1. Dashboard chunk (05) shows a banner at the top
2. Banner calls GET /health on mount
3. Green banner if 200, red banner if error
4. No new dependencies

Constraints:
- Do not modify backend code
- Do not change other views

Non-goals:
- No retry logic
- No caching

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L2 — DETERMINISTIC COMMIT GATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Validation Checklist:
[ ] chunk 05 modified
[ ] banner renders on dashboard load
[ ] apiFetch('/health') called on mount
[ ] green state for 200 response
[ ] red state for error response
[ ] no other chunks modified
[ ] no backend files modified
[ ] commit created

Gate Rule:
If any item fails → HALT and report exact blocker.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L3 — CAPABILITY BOUND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOUCH-ALLOWED:
- ui/chunks/05-dashboard.json
- ui/shopdrawing.html (reassembly)
- ui/index.html (reassembly)

NO-TOUCH:
- server/
- other ui/chunks/
- data/
- docs/

ENFORCEMENT MODE: FAIL_CLOSED

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END COMMAND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Versioning

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-03-05 | Initial protocol specification |

Future versions will be tracked in this file. Breaking changes increment the major version. Additive changes increment the minor version.

---

## Adoption

To declare that a command follows this protocol, include the following line in the Governance Context block:

```
Command Format: ValidKernel Command Protocol v0.1
```

To declare that a repository uses this protocol, add to the README:

```
## Command Governance

This repository uses the **ValidKernel Command Protocol v0.1** for AI/human
execution governance. All commands follow the structured format defined in:
`docs/validkernel/command-protocol.md`
```

---

*ValidKernel Command Protocol v0.1 — Lefebvre Design Solutions LLC*
