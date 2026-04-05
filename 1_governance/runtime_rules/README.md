# Runtime Rules

Enforceable rules evaluated during HIVE215 execution.

## Rule Categories

- **Validation rules:** Schema validation at every trust boundary crossing.
- **Constraint rules:** Input range checks, size limits, format requirements.
- **Routing rules:** System 1 vs System 2 routing criteria.
- **Halt rules:** Conditions that trigger fail-closed behavior.
- **Receipt rules:** What must be recorded in each receipt type.

## Rules

1. Runtime rules are evaluated synchronously at the point of enforcement.
2. Rule failures are not retried -- they halt and receipt.
3. Rules are loaded from configuration, not hardcoded in business logic.
