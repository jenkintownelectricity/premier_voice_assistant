# SYSTEM BOUNDARY FREEZE -- HIVE215

**Frozen:** 2026-04-05
**System:** HIVE215 -- Governed Voice Runtime Shell

## System Identity

HIVE215 is the execution shell for the Premier Voice Assistant platform. It receives voice input, normalizes transcripts, orchestrates dialogue through the Fast Brain dual-system architecture, speaks responses via TTS, and executes approved actions against backend services.

## Boundary Definition

HIVE215 executes only through typed, constrained, receipted ports. There is no code path by which raw, unvalidated external data reaches the execution spine.

### What HIVE215 Does

- Receives audio via LiveKit WebRTC transport
- Runs VAD (Silero) to detect speech boundaries
- Applies Iron Ear filtering (debounce, speaker locking, identity lock)
- Transcribes speech via Deepgram STT
- Normalizes transcripts into typed `TranscriptNormalized` records
- Manages typed session state with validated transitions
- Routes queries through Fast Brain (System 1 Groq / System 2 Claude)
- Types and validates LLM output before use
- Synthesizes speech via Cartesia TTS
- Emits execution receipts for all actions
- Persists session data to Supabase with normalization

### What HIVE215 Does NOT Do

- Trust raw browser UI state for execution decisions
- Accept unvalidated uploads into any processing pipeline
- Forward raw LLM output to execution without typing
- Use Supabase query results without normalization
- Call external APIs without fail-closed error handling
- Allow unreceipted execution of any action

## Port Categories

| Port Type | Direction | Trust Level | Examples |
|-----------|-----------|-------------|----------|
| Voice Ports | Inbound | PARTIALLY TRUSTED | Transcript normalization |
| Supabase Ports | Bidirectional | PARTIALLY TRUSTED | Payload normalization |
| LLM Ports | Outbound/Inbound | PARTIALLY TRUSTED | Output typing |
| UI Ports | Inbound | UNTRUSTED | Browser intent normalization |
| Upload Ports | Inbound | UNTRUSTED | Upload quarantine |
| External API Ports | Outbound/Inbound | UNTRUSTED | Response normalization |

## Failure Mode

All boundary violations result in fail-closed behavior. The system halts the current operation and emits a failure receipt rather than proceeding with unvalidated data.
