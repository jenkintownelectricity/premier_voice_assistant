# Governance Confidence Score (GCS) Doctrine v0.1

## Canonical Authority

This document is the canonical definition of the Governance Confidence Score. ValidKernel-Governance is the only canonical owner of the GCS model. No other repo may redefine this model.

## Purpose

The Governance Confidence Score is an observational governance confidence indicator that summarizes how well a governed system adheres to architecture discipline, documentation standards, receipt integrity, boundary enforcement, and registry alignment.

The score is:
- Evidence-derived
- Interpretable
- Not an override of canonical authorities
- May be missing, declared, or provisional when evidence is incomplete

The score is NOT:
- A replacement for governance doctrine
- A replacement for receipts
- A replacement for registry truth
- A subjective trust score
- A hidden heuristic with unexplained output
- A runtime execution authority
- A mutation right

## Canonical Rule

The score must always remain subordinate to canonical truth, receipts, and doctrine. It may summarize confidence. It may not redefine truth.

## Scoring Model

**Range: 0–100**

### Scoring Dimensions

| Dimension | Weight | Description |
|---|---|---|
| Birth Integrity | 30% | Governed birth scaffold quality, genesis receipt completeness, doctrinal parent linkage |
| Documentation Discipline | 25% | Presence and quality of doctrine docs, boundary rules, intent truth, system model |
| Boundary Enforcement | 20% | Observer-only posture compliance, no unauthorized mutation, FAIL_CLOSED adherence |
| Receipt / Lineage Integrity | 15% | Receipt truthfulness, lineage traceability, status field accuracy |
| Registry Alignment | 10% | Alignment with ValidKernel_Registry and domain registry posture, declared relationships |

### Interpretation Bands

| Range | Interpretation |
|---|---|
| 95–100 | Fully governed / high-confidence architectural posture |
| 85–94 | Strong governance discipline |
| 70–84 | Acceptable / incomplete signal coverage |
| 50–69 | Weak governance posture |
| 0–49 | Untrusted / insufficient governance evidence |

## Signal Definitions

### governance.confidence.score.updated

A governed system's observable governance confidence score has been calculated, updated, or recorded from declared scoring inputs.

- Observational / no mutation rights.
- Declared / not executed in this pass.
- subordinate to canonical truth, receipts, and doctrine

### governance.micro_commit.execution

A governed documentation or system birth pass was executed using bounded commit phases with intermediate audits.

- Observational / no mutation rights.
- Declared / not executed in this pass.
- subordinate to canonical truth, receipts, and doctrine

## Explainability Rule

Every Governance Confidence Score must be explainable by its visible inputs. No score may be produced from hidden or undeclared evidence. An operator viewing a GCS must be able to trace each dimension’s contribution to the final score through documented, observable inputs.

## Subordination Statement

The Governance Confidence Score is subordinate to canonical truth, receipts, and doctrine. It is an observational governance confidence indicator only. It does not grant, revoke, or modify any governance authority. It does not replace receipts, registry entries, or doctrine documents as sources of truth.

Observational / no mutation rights.

## Document Execution Status

This doctrine defines the GCS model at documentation level only. No automated scoring engine, no runtime computation, and no live fabric propagation exist as a result of this document. All signals defined herein are declared for future implementation.

Declared / not executed in this pass.
