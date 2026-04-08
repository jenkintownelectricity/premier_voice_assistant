# VKG Governance Tools

**v0.1**

*Operational tooling for receipt validation and automated governance record updates.*

---

## 1. Purpose

VKG governance tools convert static governance documentation into executable repository behavior. They automate the final stages of the command execution flow:

```
command → runtime gate → execution → receipt → registry update → verification
                                      ^^^^^     ^^^^^^^^^^^^^^^   ^^^^^^^^^^^^
                                      update-governance-record    validate-receipt
```

| Tool | Stage | Purpose |
|------|-------|---------|
| `validate-receipt.py` | Verification | Validates receipt against VKG v0.1 |
| `update-governance-record.py` | Receipt + Registry Update | Creates/updates receipt and registry |
| `install-vkg.py` | Deployment | Installs governance kernel into target repositories |

---

## 2. File Locations

```
.validkernel/
  tools/
    validate-receipt.py            # Receipt validator
    update-governance-record.py    # Receipt/registry auto-updater
    install-vkg.py                 # VKG kernel installer
  receipts/                        # Receipt JSON storage
  registry/
    command-registry.json          # Canonical command registry

docs/
  validkernel/
    templates/
      command-receipt.template.json  # Receipt template (used by updater)
```

---

## 3. Receipt Validator

### Overview

Validates a command receipt JSON file against VKG v0.1 requirements.

### Checks Performed

1. All 17 required receipt fields are present
2. `status` is one of: `EXECUTED`, `BLOCKED`, `PARTIAL`, `SUPERSEDED`
3. `gate_result` is one of: `PASS`, `FAIL`, `NOT_EVALUATED`
4. `command_id` exists in the command registry
5. `branch` and `commit_hash` agree between receipt and registry
6. `receipt_path` in registry matches actual receipt file path
7. `files_changed` is a list

### Usage

```bash
python .validkernel/tools/validate-receipt.py <receipt-path> [--registry <registry-path>]
```

### Examples

Validate a single receipt:

```bash
python .validkernel/tools/validate-receipt.py \
  .validkernel/receipts/L0-CMD-EXAMPLE-001.receipt.json
```

Validate with a custom registry location:

```bash
python .validkernel/tools/validate-receipt.py \
  .validkernel/receipts/L0-CMD-EXAMPLE-001.receipt.json \
  --registry path/to/command-registry.json
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Valid receipt |
| 1 | Invalid receipt (errors printed) |
| 2 | Usage error |

### Output

On success:

```
PASS: .validkernel/receipts/L0-CMD-EXAMPLE-001.receipt.json
  command_id: L0-CMD-EXAMPLE-001
  status: EXECUTED
  gate_result: PASS
```

On failure:

```
FAIL: .validkernel/receipts/L0-CMD-EXAMPLE-001.receipt.json
  - Missing required field: summary
  - Invalid status 'DONE'. Must be one of: BLOCKED, EXECUTED, PARTIAL, SUPERSEDED
```

---

## 4. Governance Record Updater

### Overview

Creates or updates a VKG receipt and registry entry after a governed command completes. Automatically derives repository name, git branch, and commit hash.

### Inputs

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--command-id` | Yes | — | Command ID |
| `--title` | No | `""` | Command title |
| `--authority` | No | `"Armand Lefebvre"` | Authority name |
| `--organization` | No | `"Lefebvre Design Solutions LLC"` | Organization |
| `--date-issued` | No | `""` | Date issued (YYYY-MM-DD) |
| `--status` | No | `EXECUTED` | `EXECUTED`, `BLOCKED`, `PARTIAL`, `SUPERSEDED` |
| `--gate-result` | No | `PASS` | `PASS`, `FAIL`, `NOT_EVALUATED` |
| `--summary` | No | `""` | Execution summary |
| `--blocked-reason` | No | `""` | Reason if blocked |
| `--next-action` | No | `""` | Recommended next step |
| `--supersedes` | No | — | Command ID this supersedes |
| `--superseded-by` | No | — | Command ID that supersedes this |

### Automatically Derived

- `repository` — from `git rev-parse --show-toplevel`
- `branch` — from `git branch --show-current`
- `commit_hash` — from `git rev-parse --short HEAD`
- `receipt_path` — `.validkernel/receipts/{command_id}.receipt.json`
- `last_updated` — current UTC timestamp
- `executed_at` — current UTC timestamp

### Usage

```bash
python .validkernel/tools/update-governance-record.py \
  --command-id <ID> \
  --title "Title" \
  --status EXECUTED \
  --gate-result PASS \
  --summary "What was done."
```

### Examples

Record a successful execution:

```bash
python .validkernel/tools/update-governance-record.py \
  --command-id L0-CMD-EXAMPLE-001 \
  --title "Example Command" \
  --status EXECUTED \
  --gate-result PASS \
  --summary "Example completed successfully."
```

Record a blocked execution:

```bash
python .validkernel/tools/update-governance-record.py \
  --command-id L0-CMD-EXAMPLE-002 \
  --title "Blocked Command" \
  --status BLOCKED \
  --gate-result FAIL \
  --blocked-reason "Working tree not clean" \
  --next-action "Clean working tree and re-issue"
```

Record a supersession:

```bash
python .validkernel/tools/update-governance-record.py \
  --command-id L0-CMD-EXAMPLE-003 \
  --title "Replacement Command" \
  --status EXECUTED \
  --gate-result PASS \
  --supersedes L0-CMD-EXAMPLE-001 \
  --summary "Replaces earlier command."
```

### Behavior

1. Loads the receipt template from `docs/validkernel/templates/command-receipt.template.json`
2. Creates a new receipt or updates an existing one at `.validkernel/receipts/{command_id}.receipt.json`
3. Stamps the current git branch and commit hash automatically
4. Appends or updates the matching entry in `.validkernel/registry/command-registry.json`
5. If `--supersedes` is provided, marks the superseded command as `SUPERSEDED` in the registry

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error |

---

## 5. Relationship to VKG Execution Flow

The tools operationalize the final three stages of the VKG command execution flow:

```
Stage 1: Command          — human issues command
Stage 2: Runtime Gate     — VKRT evaluates
Stage 3: Execution        — agent performs work
Stage 4: Receipt          — update-governance-record.py creates receipt
Stage 5: Registry Update  — update-governance-record.py updates registry
Verification              — validate-receipt.py confirms compliance
```

### Typical Workflow

1. L0 issues a command
2. Execution agent performs work and commits
3. Run `update-governance-record.py` to create receipt and update registry
4. Run `validate-receipt.py` to verify the receipt is well-formed
5. Commit the receipt and registry updates

---

## 6. Batch Receipt Validator

### Overview

Discovers and validates all receipt files in `.validkernel/receipts/`. Used by CI and for local pre-push checks.

### Usage

```bash
python .validkernel/tools/validate-all-receipts.py [--receipts-dir <dir>] [--registry <path>]
```

### Example

```bash
python .validkernel/tools/validate-all-receipts.py
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All receipts valid (or no receipts found) |
| 1 | One or more receipts invalid |

### Output

```
Found 3 receipt(s) to validate.

PASS: .validkernel/receipts/L0-CMD-EXAMPLE-001.receipt.json
PASS: .validkernel/receipts/L0-CMD-EXAMPLE-002.receipt.json
FAIL: .validkernel/receipts/L0-CMD-EXAMPLE-003.receipt.json
  - Missing required field: summary

==================================================
Results: 2 passed, 1 failed, 3 total
GOVERNANCE CHECK FAILED
```

---

## 7. CI Enforcement

### Overview

VKG governance is enforced automatically on every push and pull request via GitHub Actions. The CI workflow validates that all receipts and registry state are consistent with VKG v0.1 requirements.

### Workflow Location

```
.github/workflows/vkg-governance-check.yml
```

### What It Checks

1. **Registry parseable** — `command-registry.json` must be valid JSON
2. **All receipts valid** — every `.receipt.json` file in `.validkernel/receipts/` must pass validation (required fields, valid status/gate_result, registry agreement)

### When It Runs

- On every **push** to any branch
- On every **pull request**

### What Causes Failure

- Malformed `command-registry.json` (invalid JSON)
- A receipt missing required fields
- A receipt with an invalid `status` or `gate_result` value
- A receipt whose `command_id` is not in the registry
- A receipt whose `branch` or `commit_hash` contradicts the registry

### How to Fix Failures Locally

Before pushing, run the batch validator:

```bash
python .validkernel/tools/validate-all-receipts.py
```

To validate a single receipt:

```bash
python .validkernel/tools/validate-receipt.py .validkernel/receipts/<command-id>.receipt.json
```

To verify registry JSON is parseable:

```bash
python -c "import json; json.load(open('.validkernel/registry/command-registry.json'))"
```

Fix any reported errors, then commit and push.

---

## 8. VKRT — Runtime Gate

### Overview

The ValidKernel Runtime Gate (VKRT) is the first executable checkpoint in the VKG command execution flow. It evaluates whether a governed command is structurally valid before execution is permitted.

### What It Checks

The runtime gate performs 16 structural checks across 5 groups:

**Authority / L0 (5 checks)**
- Authority, Organization, Document ID, Date, Scope

**Ring Structure (5 checks)**
- L0 — Governance Context, Ring 1 — Mission Directive, Ring 2 — Deterministic Commit Gate, Ring 3 — Capability Bound, End Command

**Mission (2 checks)**
- Objective, Required Outcomes

**Gate (2 checks)**
- Validation Checklist, Gate Rule

**Capability (2 checks)**
- TOUCH-ALLOWED, NO-TOUCH

### Usage

```bash
python .validkernel/tools/runtime-gate.py <command-file> [--json]
```

### Examples

Evaluate a command before execution:

```bash
python .validkernel/tools/runtime-gate.py path/to/command.md
```

Output on success:

```
PASS: path/to/command.md
  command satisfies VKRT structural requirements

  Checks passed: 16/16
```

Output on failure:

```
FAIL: path/to/command.md
  command rejected by VKRT
  - missing Ring 2 — Deterministic Commit Gate (Ring Structure)
  - missing TOUCH-ALLOWED (Capability)

  Checks passed: 14/16
```

Get structured JSON output:

```bash
python .validkernel/tools/runtime-gate.py path/to/command.md --json
```

Test with the included sample command:

```bash
python .validkernel/tools/runtime-gate.py docs/validkernel/examples/sample-command.md
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | PASS — command satisfies VKRT structural requirements |
| 1 | FAIL — command rejected by VKRT |
| 2 | Usage error |

### Position in Execution Flow

```
command → runtime-gate.py → execution → receipt → registry → validator → CI
          ^^^^^^^^^^^^^^^^
          VKRT checkpoint
```

The runtime gate is the first tool in the VKG pipeline. It runs before execution begins. All other tools (updater, validator, CI) operate after execution.

---

## 9. VKG Installer

### Overview

Installs the ValidKernel Governance kernel from the ValidKernel-Governance source repository into a target repository. The installer copies governance kernel paths deterministically, preserves directory structure, and fails closed on invalid input or overwrite risk.

Intended for deploying governance into repositories such as ShopDrawing.AI, construction_dna, SUPA-SAINT, and future governed repositories.

### Required Flags

| Flag | Description |
|------|-------------|
| `--target-repo <path>` | Path to the target git repository (required) |

### Optional Flags

| Flag | Description |
|------|-------------|
| `--force` | Overwrite existing governance files in the target |
| `--initialize-authority` | Create a blank `authority.json` if none exists in target |
| `--initialize-registry` | Create an empty `command-registry.json` if none exists in target |
| `--create-install-receipt` | Create an install receipt after successful install |

### Installed Paths

The installer copies the following kernel paths into the target:

```
docs/validkernel/          — governance documentation
.validkernel/tools/        — governance tooling
.github/workflows/vkg-governance-check.yml — CI enforcement
```

It does **not** copy source-specific files (receipts, registry, authority) unless explicitly initialized via flags.

### Overwrite Behavior

Default behavior is **fail-closed**:

- Target repo does not exist → FAIL
- Target path is not a git repository → FAIL
- Required kernel source paths are missing → FAIL
- Install would overwrite existing governance files → FAIL unless `--force` is provided

### Authority Initialization

If the target does not contain `.validkernel/authority/authority.json`, the installer creates a blank template only when `--initialize-authority` is provided. Existing authority is never overwritten unless `--force` is also provided.

### Registry Initialization

If the target does not contain `.validkernel/registry/command-registry.json`, the installer creates an empty registry only when `--initialize-registry` is provided:

```json
{
  "registry_version": "0.1",
  "repository": "<target repository name>",
  "last_updated": "<install timestamp>",
  "commands": []
}
```

### Install Receipt

When `--create-install-receipt` is provided, the installer creates a receipt at:

```
.validkernel/receipts/L0-CMD-VKG-INSTALL-001.receipt.json
```

If a registry exists, the matching entry is added or updated.

### Post-Install Validation

After installation, the installer verifies that the following exist in the target:

- `docs/validkernel/vkg-spec.md`
- `docs/validkernel/command-protocol.md`
- `.validkernel/tools/runtime-gate.py`
- `.validkernel/tools/validate-receipt.py`
- `.github/workflows/vkg-governance-check.yml`

If any required artifact is missing, the install is treated as FAIL.

### Usage

```bash
python .validkernel/tools/install-vkg.py \
  --target-repo /path/to/SomeRepo \
  --initialize-authority \
  --initialize-registry
```

Windows:

```cmd
python .validkernel/tools/install-vkg.py ^
  --target-repo D:\APP_CENTRAL\SomeRepo ^
  --initialize-authority ^
  --initialize-registry ^
  --create-install-receipt
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Successful install |
| 1 | Install failed (errors printed) |

---

## 10. Continuous Governance Gate

### Overview

The Continuous Governance Gate automatically verifies that governance-critical documentation satisfies the Ring 2 deterministic checkpoint. It runs in CI on pull requests and pushes that modify governance-critical files and blocks merge when verification fails.

### What Triggers the Gate

The gate activates when any of the following governance-critical paths are changed:

- `README.md`
- `docs/validkernel/vkg-spec.md`
- `docs/validkernel/command-protocol.md`
- `docs/validkernel/command-execution-flow.md`
- `docs/validkernel/command-receipts.md`
- `docs/validkernel/command-registry.md`
- `docs/validkernel/governance-tools.md`
- `docs/validkernel/glossary.md`
- `docs/validkernel/risk-classes.md`
- `docs/validkernel/examples/`
- `docs/validkernel/templates/`

Changes outside these paths do not trigger the governance documentation gate.

### What the Gate Checks

The gate executes 21 Ring 2 checklist items covering:

- VKG defined as governing Governed Environments
- Git repositories stated as v0.1 reference implementation
- Canonical governance loop wording preserved
- Risk Class format compliance
- Required files exist (glossary.md, risk-classes.md)
- Glossary terminology consistency (all 16 required terms)
- FAIL_CLOSED definition uses required wording
- Execution warrant defined as Runtime Gate PASS
- Runtime flow wording preserved exactly
- Command Registry lifecycle states unchanged
- Verification scoped to existing tooling
- Plain-language summaries in major spec files
- README diagrams and non-technical explanation
- README canonical governance loop
- Command example with Risk Class and all required sections
- Command ring diagram with L0/L1/L2/L3
- Real diagrams (not placeholders)
- Documentation compatible with tooling
- No speculative architecture text

### PASS and FAIL Behavior

**PASS** means all 21 checklist items are satisfied. The governance documentation is consistent and aligned with VKG specification requirements.

**FAIL** means one or more checklist items failed. The output identifies which items failed and provides diagnostic evidence. Failed governance checks block merge eligibility.

### Usage

Run the verification locally before pushing:

```bash
python .validkernel/tools/verify-governance-docs.py
```

The same script runs automatically in CI via the `governance-docs-gate` job in `.github/workflows/vkg-governance-check.yml`.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks PASS |
| 1 | One or more checks FAIL |

### Position in CI

```
vkg-governance-check.yml
  ├─ vkg-check            — receipt and registry validation (existing)
  └─ governance-docs-gate — Ring 2 documentation verification (new)
```

The governance-docs-gate runs alongside the existing vkg-check job. It does not replace or weaken existing receipt and registry validation.

---

## 11. Governance State

### Overview

Governance tools may read and update live state files to track the current status of the repository and runtime tooling.

### State Files

| File | Purpose |
|------|---------|
| `.validkernel/state/repo-state.json` | Tracks whether governance is installed, authority/registry/receipts are present, and CI is enforced |
| `.validkernel/state/runtime-state.json` | Tracks readiness of runtime tools (gate, validator, installer, etc.) |

These files provide a snapshot of the governance posture of the repository at any point in time. Tools may update `last_checked` or `last_updated` timestamps and tool readiness status as part of their normal operation.

---

## 12. Requirements

- Python 3.6+
- Git (for automatic branch/commit detection)
- No external dependencies

---

*VKG Governance Tools v0.1 — Lefebvre Design Solutions LLC*
