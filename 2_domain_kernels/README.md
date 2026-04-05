# Domain Kernels

Typed domain logic modules for HIVE215. Each kernel owns a specific domain, enforces trust boundaries, and emits typed outputs.

## Kernels

| Kernel | File | Domain |
|--------|------|--------|
| Transcript Normalization | `transcript_normalization_kernel.py` | Raw STT output -> typed TranscriptNormalized |
| Session | `session_kernel.py` | Typed session state management and transition validation |
| Dialogue | `dialogue_kernel.py` | Dialogue flow, turn management, context windowing |
| Voice | `voice_kernel.py` | Voice pipeline governance, STT/TTS adapter management |
| Identity | `identity_kernel.py` | Identity verification and speaker locking (wraps Iron Ear) |
| User State | `user_state_kernel.py` | Typed user state from Supabase (PARTIALLY TRUSTED, normalized) |
| Execution Approval | `execution_approval_kernel.py` | Gates all execution, emits execution receipts |
| Deployment | `deployment_kernel.py` | Deployment health monitoring, service readiness |

## Rules

1. Kernels receive only typed, validated inputs.
2. Kernels emit only typed outputs.
3. Kernels enforce the trust model -- UNTRUSTED and PARTIALLY TRUSTED data is rejected unless it has passed through the appropriate constraint port.
4. Kernels do not call external services directly -- they delegate to service adapters through constraint ports.
