# VKG Risk Classes

**Version:** 0.1
**Authority:** Lefebvre Design Solutions LLC
**Status:** Active

Risk Classes categorize governed commands by their potential impact on a Governed Environment. Every command issued under the ValidKernel Command Protocol must declare a Risk Class in its L0 — Governance Context section. Risk Classes help authorities, execution agents, and reviewers understand the scope and consequences of a command before execution proceeds.

---

## Risk Class Format

Risk Classes use the format:

```
Risk Class N (RCN)
```

Where N is a value from 0 to 4.

---

## Risk Class Definitions

### Risk Class 0 (RC0) — Informational

Commands that produce no changes to the Governed Environment. RC0 commands are read-only operations such as queries, audits, reports, or status checks.

**Examples:**
- Generate a governance compliance report
- Query the Command Registry for command status
- Validate existing receipts against the registry

**Impact:** None. No files, state, or configuration are modified.

---

### Risk Class 1 (RC1) — Low Risk

Commands that modify documentation, comments, or non-functional metadata. RC1 commands do not affect runtime behavior, application logic, or system configuration.

**Examples:**
- Update specification documentation
- Add or revise README content
- Correct typographical errors in governance files
- Add glossary entries

**Impact:** Documentation or metadata changes only. No runtime or behavioral effect.

---

### Risk Class 2 (RC2) — Moderate Risk

Commands that modify governance configuration, tooling behavior, templates, or non-critical system files. RC2 commands may affect how governance operates but do not modify application runtime code or production infrastructure.

**Examples:**
- Update governance tooling scripts
- Modify receipt or registry templates
- Add new governance validation checks
- Revise CI workflow configurations for governance enforcement

**Impact:** Governance process or tooling changes. May affect how future commands are validated or recorded.

---

### Risk Class 3 (RC3) — High Risk

Commands that modify application code, system configuration, database schemas, or infrastructure definitions. RC3 commands produce changes that directly affect runtime behavior or system operation.

**Examples:**
- Modify application source code
- Change database migration scripts
- Update deployment configurations
- Alter API endpoints or service definitions

**Impact:** Runtime behavior changes. Requires careful review and testing before execution.

---

### Risk Class 4 (RC4) — Critical Risk

Commands that affect security boundaries, access controls, authority definitions, production data, or irreversible system operations. RC4 commands carry the highest potential for damage and require the most rigorous governance oversight.

**Examples:**
- Modify authority identity or governance scope
- Change access control rules or security policies
- Perform production data migrations
- Execute irreversible infrastructure changes
- Alter cryptographic keys or signing configurations

**Impact:** Security, authority, or irreversible system changes. Requires explicit L0 authority approval and heightened verification.

---

## Risk Class in Command Documents

The Risk Class field must appear in the L0 — Governance Context section of every command:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L0 — GOVERNANCE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Authority:     Armand Lefebvre, L0 — Lefebvre Design Solutions LLC
Document ID:   L0-CMD-EXAMPLE-001
Date:          2026-03-06
Risk Class:    Risk Class 1 (RC1)
Scope:         Update governance documentation for clarity.
Command Format: ValidKernel Command Protocol v0.1
```

---

## Relationship to the Runtime Gate

The Runtime Gate does not currently enforce Risk Class as a validation check in VKG v0.1. Risk Class serves as a structured metadata field that supports governance decision-making, audit trails, and future enforcement capabilities.

---

*VKG Risk Classes v0.1 — Lefebvre Design Solutions LLC*
