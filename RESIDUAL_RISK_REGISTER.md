# RESIDUAL RISK REGISTER

**Date:** 2026-04-05
**System:** HIVE215 (Governed Voice Runtime Shell)
**Branch:** claude/deployment-hardening-audit-t4L2Q

---

## SUMMARY

| Severity | Count |
|---|---|
| HIGH | 2 |
| MEDIUM | 3 |
| LOW | 5 |
| **Total** | **10** |

---

## RISK REGISTER

### RR-001: No Live Fast Brain Integration Test

| Field | Value |
|---|---|
| **ID** | RR-001 |
| **Severity** | MEDIUM |
| **Description** | No live integration test exists between Fast Brain and HIVE215 under the governed overlay. The cross-repo handshake is governed by typed contracts (`FASTBRAIN_TO_HIVE215.md`, `HIVE215_TO_FASTBRAIN.md`) and validated against governance schemas, but no end-to-end test exercises the full proposal-approval-execution-receipt cycle with a live Fast Brain instance. |
| **Impact** | A schema drift or contract violation between Fast Brain and HIVE215 could go undetected until production. Proposals might fail validation silently or produce unexpected execution paths. |
| **Mitigation** | Cross-repo contracts are typed and versioned. Governance schemas validate all inbound proposals. The execution approval kernel rejects any proposal that does not conform. Add a live integration test in the next hardening cycle using a Fast Brain staging instance. |
| **Status** | OPEN -- Scheduled for next hardening cycle |

---

### RR-002: Telephony Providers Untested Under Governed Overlay

| Field | Value |
|---|---|
| **ID** | RR-002 |
| **Severity** | MEDIUM |
| **Description** | Telephony providers (Twilio, Plivo, Telnyx, and others) have not been tested under the governed overlay. The voice constraint ports (`3_constraint_ports/voice_ports/`) are installed and the adapter layer (`5_service_adapters/telephony/`) wraps telephony access, but no integration test verifies that telephony calls flow correctly through the governed pipeline. |
| **Impact** | Telephony calls might fail at the constraint port boundary, produce untyped events, or bypass the governance schema validation. Voice sessions initiated via telephony could behave differently than LiveKit-originated sessions. |
| **Mitigation** | Voice ports normalize all inbound audio regardless of source. The voice event schema (`1_governance/voice_event_schema.json`) validates all voice events. Add telephony-specific integration tests with a test phone number in the next cycle. |
| **Status** | OPEN -- Requires telephony test credentials |

---

### RR-003: golden_logic/ Directory Not Mapped Into Overlay

| Field | Value |
|---|---|
| **ID** | RR-003 |
| **Severity** | LOW |
| **Description** | The `golden_logic/` directory exists in the repository but is not mapped into the governed overlay. It appears to contain archived reference logic or historical implementation patterns. No active code imports from this directory. |
| **Impact** | Minimal. If any future code imports from `golden_logic/`, it would bypass the governed overlay and execute outside constraint ports. However, no current import path exists. |
| **Mitigation** | Confirm `golden_logic/` is archived reference material. If so, document it as excluded from the overlay in `docs/architecture/SURFACE_MAPPING.md`. If any active code depends on it, map it into the appropriate domain kernel or service adapter. |
| **Status** | OPEN -- Awaiting confirmation of archive status |

---

### RR-004: certificate.pem in Repo Root

| Field | Value |
|---|---|
| **ID** | RR-004 |
| **Severity** | HIGH |
| **Description** | A `certificate.pem` file exists in the repository root. PEM certificate files should not be stored in version control as they may contain private keys or sensitive certificate material. Even if this is a public certificate, its presence in the repo creates a pattern that could lead to accidental commit of private key material. |
| **Impact** | If the PEM file contains a private key, the key is compromised for anyone with repo access. Even if it contains only a public certificate, it sets a dangerous precedent for secret storage patterns. |
| **Mitigation** | Immediately verify the contents of `certificate.pem`. If it contains a private key, rotate the key immediately and remove the file from version control (including git history). Add `*.pem` to `.gitignore`. Store certificates in the deployment platform's secret management (Railway environment variables or a secrets vault). |
| **Status** | OPEN -- Requires immediate investigation |

---

### RR-005: QUICK_DEPLOY.sh Contains Modal Tokens

| Field | Value |
|---|---|
| **ID** | RR-005 |
| **Severity** | HIGH |
| **Description** | The `QUICK_DEPLOY.sh` script contains hardcoded Modal deployment tokens. Secrets embedded in shell scripts that are committed to version control are accessible to anyone with repo access and persist in git history even after deletion. |
| **Impact** | Modal tokens could be used by unauthorized parties to deploy to the Modal account, incur costs, or access Modal-hosted resources (STT/TTS GPU workloads). Token rotation alone is insufficient if the git history is not cleaned. |
| **Mitigation** | Remove hardcoded tokens from `QUICK_DEPLOY.sh`. Replace with environment variable references (`$MODAL_TOKEN_ID`, `$MODAL_TOKEN_SECRET`). Rotate the exposed Modal tokens immediately. Consider using `git filter-branch` or `BFG Repo-Cleaner` to remove tokens from git history. Add token patterns to `.gitignore` and pre-commit hooks. |
| **Status** | OPEN -- Requires immediate token rotation |

---

### RR-006: No Automated CI/CD Pipeline

| Field | Value |
|---|---|
| **ID** | RR-006 |
| **Severity** | MEDIUM |
| **Description** | No automated CI/CD pipeline (GitHub Actions, Railway auto-deploy, etc.) is configured. Deployments are manual via the canonical deploy path (`docker build` + Railway). The test suite runs locally but is not enforced on push or pull request. |
| **Impact** | Governance regressions, test failures, and schema violations could be merged without detection. Manual deployment increases the risk of human error (wrong branch, missing env vars, skipped preflight). |
| **Mitigation** | The preflight script (`scripts/preflight_env_check.py`) catches missing environment variables at startup. The governance overlay catches schema violations at runtime. Add a GitHub Actions workflow that runs the test suite on push/PR and blocks merge on failure. Configure Railway auto-deploy from the governed branch. |
| **Status** | OPEN -- Recommended for next hardening cycle |

---

### RR-007: web/ Next.js App Not Covered by Python Overlay Tests

| Field | Value |
|---|---|
| **ID** | RR-007 |
| **Severity** | LOW |
| **Description** | The `web/` directory contains a Next.js application (browser surface) that is not covered by the Python overlay test suite. The Python tests validate that browser state is treated as UNTRUSTED at the constraint port boundary, but they do not test the Next.js application itself. |
| **Impact** | The Next.js app could send malformed state, bypass expected API contracts, or drift from the typed session state schema without detection by the overlay test suite. |
| **Mitigation** | The UI constraint port (`3_constraint_ports/ui_ports/`) validates all inbound browser state regardless of the Next.js app's behavior. The `test_web_mobile_contract_smoke.py` test validates that the contract interface exists. Add JavaScript/TypeScript tests within `web/` that validate outbound state conforms to the governance schema. |
| **Status** | OPEN -- Separate deployment, lower priority |

---

### RR-008: mobile/ React Native App at Early Stage

| Field | Value |
|---|---|
| **ID** | RR-008 |
| **Severity** | LOW |
| **Description** | The `mobile/` directory contains an early-stage React Native application. It is not included in the current production deployment scope and is not covered by the governed overlay test suite beyond contract smoke tests. |
| **Impact** | Minimal for current deployment. If the mobile app reaches production without governance integration, it could bypass trust boundaries or send untyped state to the backend. |
| **Mitigation** | The mobile app is excluded from the current canonical deploy path. When it reaches production readiness, it must be integrated with the UI constraint port (`3_constraint_ports/ui_ports/`) and validated against the session state schema. The `test_web_mobile_contract_smoke.py` test provides a baseline contract check. |
| **Status** | OPEN -- Not in current production scope |

---

### RR-009: Multiple Migration Directories

| Field | Value |
|---|---|
| **ID** | RR-009 |
| **Severity** | LOW |
| **Description** | Two migration directories exist: `migrations/` (root level) and `supabase/migrations/`. This creates potential for migration drift if changes are applied to one directory but not the other, or if the deployment process references the wrong directory. |
| **Impact** | Database schema drift between the two migration sets could cause runtime errors, data integrity issues, or constraint port failures when the Supabase port expects a schema that does not match the actual database state. |
| **Mitigation** | The Supabase constraint port (`3_constraint_ports/supabase_ports/`) normalizes all database interactions, reducing the impact of schema drift. Determine which migration directory is authoritative, archive the other, and document the canonical migration path in the deployment guide. |
| **Status** | OPEN -- Cleanup candidate |

---

### RR-010: Screenshot Files in Repo Root

| Field | Value |
|---|---|
| **ID** | RR-010 |
| **Severity** | LOW |
| **Description** | Screenshot image files exist in the repository root. These are likely development artifacts or documentation assets that were committed for convenience. They increase repo size and create clutter without serving a governed function. |
| **Impact** | Minimal. No security or governance impact. Increases clone size and creates visual clutter in the repository root. |
| **Mitigation** | Move screenshots to a `docs/images/` directory if they serve a documentation purpose, or remove them entirely. Add `*.png`, `*.jpg`, `*.jpeg` patterns to `.gitignore` for the root directory to prevent future accumulation. |
| **Status** | OPEN -- Cleanup candidate |

---

## RISK MATRIX

| ID | Severity | Category | Immediate Action Required |
|---|---|---|---|
| RR-004 | HIGH | Security | Yes -- Investigate and remove PEM file |
| RR-005 | HIGH | Security | Yes -- Rotate tokens, remove from code |
| RR-001 | MEDIUM | Testing | No -- Next hardening cycle |
| RR-002 | MEDIUM | Testing | No -- Requires test credentials |
| RR-006 | MEDIUM | Operations | No -- Next hardening cycle |
| RR-003 | LOW | Architecture | No -- Confirm archive status |
| RR-007 | LOW | Testing | No -- Separate deployment |
| RR-008 | LOW | Scope | No -- Not in production scope |
| RR-009 | LOW | Data | No -- Cleanup candidate |
| RR-010 | LOW | Hygiene | No -- Cleanup candidate |

---

## RECOMMENDED PRIORITY ORDER

1. **RR-004** and **RR-005** -- Address immediately (security: secrets in repo)
2. **RR-006** -- Add CI/CD pipeline (next hardening cycle)
3. **RR-001** -- Add live Fast Brain integration test (next hardening cycle)
4. **RR-002** -- Add telephony integration tests (when test credentials available)
5. **RR-003**, **RR-009**, **RR-010** -- Cleanup tasks (scheduled maintenance)
6. **RR-007**, **RR-008** -- Frontend governance (when apps reach production readiness)

---

*Risk register generated: 2026-04-05*
*System: HIVE215 Governed Voice Runtime Shell*
*Total risks: 10 (2 HIGH, 3 MEDIUM, 5 LOW)*
