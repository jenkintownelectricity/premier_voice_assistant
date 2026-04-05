# UTK ROOT TRUTH -- HIVE215

**Frozen:** 2026-04-05
**Classification:** Immutable Doctrine

## Root Truth

HIVE215 is a governed voice runtime shell. It is the execution layer of the Premier Voice Assistant platform.

## Axioms

1. **HIVE215 does not trust raw external state.** Browser UI state, user uploads, external API responses, and raw LLM semantic output are UNTRUSTED until typed, validated, and receipted.

2. **HIVE215 executes only through typed ports.** Every input enters through a constraint port with a declared trust level, a validation schema, and a halt condition. Every output exits through a constraint port with an execution receipt.

3. **HIVE215 preserves the existing runtime.** The backend, worker, web, mobile, skills, and deployment surfaces are preserved exactly as they exist. The governance overlay wraps, types, and constrains -- it does not replace.

4. **HIVE215 fails closed.** When validation fails, when schemas do not match, when trust boundaries are violated, the system halts the current operation and emits a failure receipt. It does not fall back to unvalidated data.

5. **HIVE215 receipts everything.** Every trust boundary crossing, every execution decision, every state transition emits an immutable receipt. The receipt trail is the source of truth for what happened.

6. **HIVE215 separates fast from deep.** System 1 (Groq/Llama, ~80ms) handles 90% of queries. System 2 (Claude, ~2000ms) handles complex analysis. The routing decision is typed and receipted.

7. **HIVE215 owns the voice pipeline.** From VAD through Iron Ear through STT through dialogue through TTS, the voice pipeline is governed end to end. No ungoverned audio reaches the user.

## Non-Negotiables

- The UTK cannot be overridden by any runtime configuration, user preference, or LLM output.
- The trust model cannot be relaxed without a new frozen doctrine revision.
- Execution receipts cannot be disabled or suppressed.
- Fail-closed behavior cannot be changed to fail-open.
