# Governance Policies

Runtime policies that govern HIVE215 behavior.

## Policy Categories

- **Trust policies:** Define which components are TRUSTED, PARTIALLY TRUSTED, and UNTRUSTED.
- **Execution policies:** Define under what conditions actions may be executed.
- **Retention policies:** Define how long receipts, audit logs, and session state are retained.
- **Fallback policies:** Define fail-closed behavior for each service boundary.
- **Rate policies:** Define rate limits for external service calls.

## Rules

1. Policies are declarative and enforceable at runtime.
2. Policy violations are receipted.
3. Policies cannot be overridden by user preference or LLM output.
