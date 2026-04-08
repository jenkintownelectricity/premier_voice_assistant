# ValidKernel Command Receipts v0.1

**Authority:** Lefebvre Design Solutions LLC
**Version:** 0.1
**Date:** 2026-03-05
**Status:** Active
**Parent:** ValidKernel Command Protocol v0.1

Command Receipts provide the auditable record layer of ValidKernel Governance (VKG). Every governed command execution produces a receipt that captures what was commanded, what happened, what changed, and what should happen next. Receipts are stored as JSON files in `.validkernel/receipts/` and are indexed by the Command Registry. Together, receipts and the registry form a complete, verifiable execution history for a Governed Environment. Git repositories are the reference implementation of VKG in version 0.1.

---

## Purpose

Command Receipts provide a deterministic, structured record of every governance command execution. Each receipt captures:

- **What** was commanded (command identity and authority)
- **What happened** (execution status, gate result)
- **What changed** (branch, commit, files)
- **What's next** (follow-up actions or blockers)

Receipts make command execution auditable, verifiable, and reproducible. They are the verification layer on top of the ValidKernel Command Protocol.

---

## Receipt Structure

Every receipt is a JSON file stored at:

```
.validkernel/receipts/{command_id}.receipt.json
```

**Naming convention:**
- Use the exact `command_id` from the governance command
- Replace spaces with hyphens, preserve case
- File extension: `.receipt.json`

**Examples:**
```
.validkernel/receipts/L0-CMD-SHOPDRAWINGS-FINAL-HARDENING-001.receipt.json
.validkernel/receipts/L0-CMD-VALIDKERNEL-PROTOCOL-INTEGRATION-001.receipt.json
```

---

## Required Receipt Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `receipt_version` | string | Yes | Receipt spec version (currently `"0.1"`) |
| `command_id` | string | Yes | Unique command identifier from the governance command |
| `authority` | string | Yes | Person or entity who issued the command |
| `organization` | string | Yes | Issuing organization |
| `issued_at` | string | Yes | ISO 8601 date when the command was issued |
| `executed_at` | string | Yes | ISO 8601 datetime when execution completed |
| `repository` | string | Yes | Repository name |
| `branch` | string | Yes | Git branch where work was committed |
| `commit_hash` | string | Yes | Git commit hash of the final commit |
| `status` | string | Yes | Execution status (see Status Model) |
| `gate_result` | string | Yes | Ring 2 gate outcome (see Gate Results) |
| `files_changed` | array | Yes | List of files created or modified |
| `summary` | string | Yes | One-paragraph summary of what was executed |
| `blocked_reason` | string | Yes | Empty string if not blocked; explanation if BLOCKED or PARTIAL |
| `next_action` | string | Yes | Recommended next step after this command |
| `signer` | string | Yes | Entity that created the receipt |
| `signature_status` | string | Yes | Signature verification state (see Signing) |

---

## Status Model

### Execution Status

| Status | Meaning |
|--------|---------|
| `EXECUTED` | Command completed successfully. All required outcomes met. |
| `BLOCKED` | Command could not execute. Blocker identified and recorded. |
| `PARTIAL` | Some outcomes completed, others blocked or deferred. |
| `SUPERSEDED` | Command replaced by a newer command. No longer active. |

### Gate Result

| Result | Meaning |
|--------|---------|
| `PASS` | All Ring 2 checklist items satisfied. |
| `FAIL` | One or more Ring 2 checklist items failed. Blocker recorded. |
| `NOT_EVALUATED` | Ring 2 gate was not evaluated (e.g., command was BLOCKED before reaching gate). |

---

## Receipt Lifecycle

```
1. Command Issued
   └─ Authority creates governance command (ValidKernel Command Protocol)

2. Command Executed
   └─ Executor performs work on designated branch

3. Gate Evaluated
   └─ Ring 2 checklist verified (PASS or FAIL)

4. Receipt Created
   └─ JSON receipt generated with all required fields
   └─ Stored in .validkernel/receipts/{command_id}.receipt.json

5. Receipt Committed
   └─ Receipt file committed to repository alongside work

6. Receipt Verified (future)
   └─ Automated validation of receipt completeness and correctness
```

---

## Blocked Execution Handling

When a command cannot complete:

1. Set `status` to `BLOCKED` or `PARTIAL`
2. Set `gate_result` to `FAIL` or `NOT_EVALUATED`
3. Fill `blocked_reason` with the exact blocker description
4. Fill `next_action` with what must happen to unblock
5. Set `commit_hash` to the last commit before blocking (or empty if no work was done)
6. Set `files_changed` to any files that were modified before blocking

**Example blocked receipt:**
```json
{
  "status": "BLOCKED",
  "gate_result": "FAIL",
  "blocked_reason": "PostgreSQL connection unavailable. Cannot run Alembic migrations.",
  "next_action": "Restore database access and re-execute command."
}
```

---

## Branch/Commit Capture

Receipts must accurately record the repository state at execution time:

- `branch`: The exact branch name where work was committed
- `commit_hash`: The full or short hash of the final commit
- `files_changed`: Complete list of files created, modified, or deleted

If multiple commits were made during execution, `commit_hash` should reference the final commit. Individual commit hashes may be listed in the `summary` field.

---

## Signing Compatibility

### v0.1 Signing

In v0.1, cryptographic signing is not required. The `signature_status` field documents the current verification state:

| Value | Meaning |
|-------|---------|
| `UNSIGNED` | No verification applied. Receipt is informational only. |
| `REPO_VERIFIED` | Receipt is committed to the repository. Git history provides integrity. |
| `FUTURE_CRYPTO_REQUIRED` | Placeholder for commands that will require cryptographic signing in future versions. |

### v0.1 Signer Values

The `signer` field identifies who created the receipt:

| Value | Meaning |
|-------|---------|
| `repository` | Receipt generated as part of repository workflow |
| `L0` | Receipt created by L0 authority |
| `CI` | Receipt generated by CI/CD system |
| `manual` | Receipt created manually by an operator |
| `agent` | Receipt created by an AI agent during command execution |

### Future Signing (v0.2+)

Future versions may introduce:
- GPG/SSH commit signing verification
- Content-addressable receipt hashing
- Chain-of-custody linking between dependent commands
- External notarization services

The receipt schema is designed to accommodate these additions without breaking v0.1 compatibility.

---

## Execution Rule

> After any governed command completes, a receipt **should** be created recording the gate result, branch, commit, files changed, and completion or blocker state.

Receipts are strongly recommended for all commands executed under the ValidKernel Command Protocol. For v0.1, receipt creation is advisory (SHOULD) rather than mandatory (MUST). Future versions may make receipts mandatory.

---

## Git Integration Pattern

Standard operating procedure for command execution with receipts:

```
1. Receive governance command
2. Create or switch to designated branch
3. Execute required outcomes
4. Evaluate Ring 2 gate checklist
5. Commit work
6. Generate receipt JSON
7. Store receipt in .validkernel/receipts/{command_id}.receipt.json
8. Commit receipt (may be same commit or follow-up)
9. Push branch to origin
10. Verify working tree is clean
```

---

## Receipt Template

A template file is provided at:

```
docs/validkernel/templates/command-receipt.template.json
```

Use this template as a starting point for new receipts. Replace all placeholder values with actual execution data.

---

## Versioning

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-03-05 | Initial receipt specification |

Future versions will be tracked in this file. The `receipt_version` field in each receipt declares which spec version it follows.

---

*ValidKernel Command Receipts v0.1 -- Lefebvre Design Solutions LLC*
