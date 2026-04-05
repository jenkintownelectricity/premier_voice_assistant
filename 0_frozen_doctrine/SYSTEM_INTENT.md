# SYSTEM INTENT -- HIVE215

**Frozen:** 2026-04-05
**Classification:** Immutable Doctrine

## Identity

HIVE215 is the governed voice runtime shell of the Premier Voice Assistant platform. It receives voice input, normalizes it, orchestrates dialogue through the Fast Brain dual-system architecture, speaks responses, and executes approved actions.

## Execution Model

HIVE215 executes only through typed, constrained, receipted ports.

### Typed

Every piece of data that crosses a system boundary has a declared type. Transcripts become `TranscriptNormalized`. Session updates become `SessionStateTransition`. LLM outputs become `TypedLLMResponse`. Browser commands become `NormalizedUICommand`. There is no raw string or untyped dictionary in the execution path.

### Constrained

Every port declares what it accepts, what it rejects, and under what conditions it halts. Constraints are not advisory -- they are enforced at runtime. A constraint violation is a hard stop, not a warning.

### Receipted

Every execution produces an immutable receipt. The receipt records what was requested, what was validated, what was approved, what was executed, and what was observed. Receipts are the audit trail. They cannot be suppressed or back-dated.

## Voice Pipeline Governance

The full voice pipeline is governed:

1. **Audio Ingress:** LiveKit WebRTC transport delivers audio frames
2. **VAD:** Silero voice activity detection identifies speech boundaries
3. **Iron Ear:** Multi-layer noise filtering (debounce, speaker locking, identity lock)
4. **STT:** Deepgram Nova 3 transcribes speech to text
5. **Transcript Normalization:** Raw transcript is typed into `TranscriptNormalized`
6. **Session State:** Typed session state is updated with validated transitions
7. **Dialogue Routing:** Fast Brain routes to System 1 (Groq ~80ms) or System 2 (Claude ~2s)
8. **LLM Output Typing:** Raw LLM response is typed and validated
9. **Execution Approval:** Only typed, constrained action envelopes may proceed
10. **TTS:** Cartesia synthesizes approved response text to speech
11. **Audio Egress:** LiveKit WebRTC transport delivers audio to user
12. **Receipt:** Execution receipt emitted for the complete interaction
