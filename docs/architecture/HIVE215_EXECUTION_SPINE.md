# HIVE215 Execution Spine

Full execution flow for the HIVE215 governed voice runtime.

## Pipeline Flow

```
Voice Ingress (LiveKit WebRTC)
    |
    v
VAD (Silero) -- detect speech boundaries
    |
    v
Iron Ear Filtering
    |-- V1: Debounce (<300ms noise rejection)
    |-- V2: Speaker Locking (volume fingerprint, 60% threshold)
    |-- V3: Identity Lock (256-dim Resemblyzer embeddings)
    |
    v
STT (Deepgram Nova 3) -- PARTIALLY TRUSTED
    |
    v
Transcript Normalization Kernel
    |-- Clean text (control chars, whitespace)
    |-- Validate confidence (>= 0.30 threshold)
    |-- Type into TranscriptNormalized
    |-- Emit NormalizationReceipt
    |-- REJECT if malformed (fail closed)
    |
    v
Session State Kernel
    |-- Validate session exists and is not terminated
    |-- Validate transition is legal
    |-- Update typed session state
    |-- Emit TransitionReceipt
    |
    v
Dialogue Kernel
    |-- Add user turn to context window
    |-- Estimate query complexity (simple/moderate/complex)
    |-- Route: System 1 Fast (~80ms) or System 2 Deep (~2s)
    |-- Emit RoutingReceipt
    |
    v
Fast Brain Query
    |-- System 1: Groq LPU + Llama 3.3 70B (90% of queries)
    |-- System 2: Claude 3.5 Sonnet (complex analysis)
    |-- If System 2: return filler phrase first, then deep response
    |-- Fallback: Direct Groq if Fast Brain unavailable
    |
    v
LLM Output Typing Port
    |-- Type raw LLM response into structured format
    |-- Validate against schema
    |-- REJECT if untyped or malformed (fail closed)
    |
    v
Execution Approval Kernel
    |-- Create typed ActionEnvelope
    |-- Validate source is TRUSTED
    |-- Validate session is valid
    |-- Check idempotency
    |-- Emit ExecutionReceipt (approved or rejected)
    |-- REJECT if untrusted source (fail closed)
    |
    v
Action Execution
    |-- voice_response: Text -> TTS synthesis
    |-- skill_invocation: Route to skill
    |-- session_update: Update session state
    |-- supabase_mutation: Write to database
    |
    v
TTS Synthesis (Cartesia Sonic 3)
    |-- Convert approved text to speech
    |-- Adapter receipt emitted
    |-- Fallback to alternative TTS if Cartesia unavailable
    |
    v
Audio Egress (LiveKit WebRTC)
    |-- Deliver synthesized audio to user
    |
    v
Execution Receipt
    |-- Record complete interaction lifecycle
    |-- Immutable audit trail
```

## Trust Boundary Crossings

Each arrow crossing a trust boundary emits an adapter receipt:

1. **LiveKit -> Iron Ear**: Audio frames enter governance boundary
2. **Deepgram -> Transcript Kernel**: STT output enters as PARTIALLY TRUSTED
3. **Fast Brain -> Output Typing**: LLM output enters as PARTIALLY TRUSTED
4. **Execution Spine -> Cartesia**: Approved text exits to TTS service
5. **Execution Spine -> Supabase**: Typed mutations exit to database
6. **Cartesia -> LiveKit**: Synthesized audio exits to transport

## Fail-Closed Points

Every stage can halt the pipeline:

- Transcript normalization: reject malformed, low-confidence, or oversized text
- Session validation: reject expired, terminated, or non-existent sessions
- Execution approval: reject untyped, untrusted-source, or duplicate actions
- TTS synthesis: halt on adapter failure (no silent fallback to raw text)
