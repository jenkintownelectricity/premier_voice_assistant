# EXECUTION POSTURE -- HIVE215

**Frozen:** 2026-04-05
**Classification:** Immutable Doctrine

## Posture

The execution posture of HIVE215 follows six principles, applied in order:

### 1. Preserve

The existing runtime (backend, worker, web, mobile, skills, deployment) is preserved exactly as it exists. The governance overlay does not modify, replace, or remove any existing code. Existing behavior is maintained.

### 2. Wrap

Existing components are wrapped with typed interfaces. The wrapping layer adds type declarations, validation, and receipting without changing the underlying implementation. The wrapper delegates to the original code.

### 3. Type

All data crossing system boundaries is typed. Raw strings, untyped dictionaries, and ambiguous payloads are replaced with typed dataclasses, enums, and validated schemas at the boundary. Internal code continues to use its existing types.

### 4. Constrain

Every port declares explicit constraints: what input shapes are accepted, what ranges are valid, what conditions trigger a halt. Constraints are enforced at runtime, not just documented.

### 5. Receipt

Every execution produces an immutable receipt. Receipts record the full lifecycle: request, validation, approval, execution, observation. The receipt trail is the authoritative record.

### 6. Fail Closed

When any step fails -- validation, constraint check, schema match, service call, timeout -- the system halts the current operation and emits a failure receipt. It does not:
- Fall back to unvalidated data
- Skip the failing step
- Use cached stale data without marking it as such
- Proceed with partial results without explicit acknowledgment

Fail-closed is not optional. It applies at every trust boundary crossing.
