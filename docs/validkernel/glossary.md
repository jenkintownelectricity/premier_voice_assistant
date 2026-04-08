# VKG Glossary

**Version:** 0.1
**Authority:** Lefebvre Design Solutions LLC
**Status:** Active

This glossary is the canonical source of terminology for ValidKernel Governance (VKG). All definitions in other VKG documents must be consistent with the definitions provided here. Additional terms may be added but must not contradict existing definitions.

---

## Terms

### Authority

The person or entity responsible for issuing governed commands. Authority establishes command ownership, governance responsibility, and root trust within a Governed Environment.

### Portable Authority

An Authority identity that persists across multiple Governed Environments. Portable Authority allows the same governance identity to issue commands in different repositories, systems, or organizations without re-establishing trust in each environment.

### AuthorityLedger

A MetaKernel-owned governance object that records the transferable authority chain for a specific resource. The AuthorityLedger establishes who holds governance authority over a kernel, object type, governance rule, or command — at what level (L0, L1, L2), with what delegation scope, and under what expiration constraints. AuthorityLedger entries reference Portable Authority identities through the authority_holder field. Portable Authority identifies who the participant is; AuthorityLedger records what governance power that participant holds. See the MetaKernel Specification §6.2 for the canonical definition.

### Governed Environment

A Governed Environment is a system in which commands may be issued, validated, executed, recorded, and verified under VKG governance rules.

Examples of Governed Environments include:

- Git repositories
- CI/CD pipelines
- infrastructure management systems
- databases
- AI execution environments

These examples are illustrative. Git repositories are the reference implementation of VKG in version 0.1.

### Command

A structured instruction issued under the ValidKernel Command Protocol by a recognized Authority. Commands are the only authorized mechanism for initiating governed actions. Each command contains governance context (L0), a mission directive (L1), a deterministic commit gate (L2), and a capability bound (L3).

### Command Protocol

The ValidKernel Command Protocol defines the structured, deterministic format for issuing governance commands. It specifies the required sections (L0, L1, L2, L3), their fields, and the enforcement rules that govern command execution.

### Runtime Gate

The enforcement checkpoint that evaluates a command before execution is permitted. The Runtime Gate determines whether execution may proceed by validating authority, command structure, capability bounds, gate preconditions, and environment safety. If any check fails, execution is blocked.

### Execution

The stage in which an execution agent interprets and performs the work specified by a command that has passed the Runtime Gate. Execution must occur only within the bounds defined by L3 — Capability Bound.

### Receipt

A structured record produced after command execution that captures the execution outcome. Receipts record command identity, authority, execution timestamp, branch, commit, files changed, gate result, and execution status. Receipts are stored in `.validkernel/receipts/`.

### Command Registry

The canonical index of all governed commands and their lifecycle states within a Governed Environment. The Command Registry links commands to their receipts and tracks execution state, supersession relationships, and follow-up actions. Command Registry state reflects execution outcomes.

### Risk Class

A classification indicating the risk level of a governed command. Risk Classes use the format "Risk Class N (RCN)" where N ranges from 0 (lowest risk) to 4 (highest risk). Risk Class is a mandatory field in the L0 — Governance Context section of every command document. See `risk-classes.md` for detailed definitions.

### Execution Warrant

A narrow authorization permitting execution of a single governed command within defined capability bounds. In VKG v0.1, Runtime Gate PASS functions as the effective execution warrant. The execution warrant in VKG v0.1 is a logical authorization produced by Runtime Gate PASS and does not require a separate artifact file.

### Capability Bound

The permission model defined in L3 of a command that restricts what an execution agent may modify. Capability bounds consist of TOUCH-ALLOWED (what may be modified) and NO-TOUCH (what must not be modified) lists, enforced under FAIL_CLOSED semantics.

### Validation

The process of evaluating whether a command satisfies governance rules before execution. Validation is performed by the Runtime Gate and includes authority verification, command structure checks, capability boundary checks, and gate preconditions.

### Verification

The process of confirming that execution followed governance rules after completion. Verification is performed by existing receipt validation and Command Registry consistency validation tooling. Verification does not introduce a new runtime stage, lifecycle state, or execution step.

### State

The current condition of a command within its lifecycle, as recorded in the Command Registry. Valid lifecycle states are: ISSUED, IN_PROGRESS, EXECUTED, BLOCKED, PARTIAL, SUPERSEDED, and ARCHIVED.

### FAIL_CLOSED

If validation fails or system state is uncertain, execution must not proceed.

---

*VKG Glossary v0.1 — Lefebvre Design Solutions LLC*
