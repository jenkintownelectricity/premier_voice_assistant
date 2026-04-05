# Surface Mapping

Maps existing codebase surfaces to the HIVE215 governance overlay.

## Backend Surface

| Existing File | Overlay Mapping | Trust Handling |
|--------------|-----------------|----------------|
| `backend/main.py` | `7_surfaces/backend` | Internal -- primary execution surface |
| `backend/brain_client.py` | `5_service_adapters/groq` + `5_service_adapters/anthropic` | PARTIALLY TRUSTED -- LLM responses typed via `3_constraint_ports/llm_ports/llm_output_typing_port.py` |
| `backend/supabase_client.py` | `5_service_adapters/supabase` | PARTIALLY TRUSTED -- payloads normalized via `3_constraint_ports/supabase_ports/supabase_normalization_port.py` |
| `backend/groq_client.py` | `5_service_adapters/groq` | PARTIALLY TRUSTED -- System 1 Fast Brain adapter |
| `backend/cartesia_client.py` | `5_service_adapters/cartesia` | PARTIALLY TRUSTED -- TTS adapter with timeout and fallback |
| `backend/deepgram_client.py` | `5_service_adapters/deepgram` | PARTIALLY TRUSTED -- STT adapter with confidence thresholds |
| `backend/livekit_worker.py` | `7_surfaces/worker` | Internal -- voice worker entrypoint |
| `backend/livekit_agent.py` | `7_surfaces/worker` | Internal -- LiveKit agent implementation |
| `backend/livekit_api.py` | `7_surfaces/backend` | Internal -- LiveKit API integration |
| `backend/streaming_manager.py` | `7_surfaces/backend` | Internal -- streaming pipeline |
| `backend/lightning_pipeline.py` | `7_surfaces/backend` | Internal -- low-latency pipeline |
| `backend/model_manager.py` | `7_surfaces/backend` | Internal -- model selection and fallback |
| `backend/stripe_payments.py` | `5_service_adapters/external` | UNTRUSTED -- external payment service |
| `backend/twilio_integration.py` | `5_service_adapters/telephony` | PARTIALLY TRUSTED -- telephony adapter |

## Worker Surface

| Existing File | Overlay Mapping | Trust Handling |
|--------------|-----------------|----------------|
| `worker/voice_agent.py` | `7_surfaces/worker` | Internal -- voice agent orchestration |
| `worker/identity_manager.py` | `2_domain_kernels/identity_kernel.py` | TRUSTED -- wraps Iron Ear V3 with governance |
| `worker/turn_taking.py` | `2_domain_kernels/dialogue_kernel.py` | TRUSTED -- turn management with typed state |
| `worker/latency_manager.py` | `7_surfaces/worker` | Internal -- latency optimization |

## Frontend Surfaces

| Existing Surface | Overlay Mapping | Trust Level |
|-----------------|-----------------|-------------|
| `web/` | `7_surfaces/web` | UNTRUSTED -- browser-controlled |
| `mobile/` | `7_surfaces/mobile` | UNTRUSTED -- user-controlled app |

## Data Surfaces

| Existing Surface | Overlay Mapping | Trust Level |
|-----------------|-----------------|-------------|
| `supabase/` | `3_constraint_ports/supabase_ports` | PARTIALLY TRUSTED -- normalize all payloads |
| `supabase/migrations/` | `9_receipts/migration` | Track migration history |

## Deployment Surfaces

| Existing Surface | Overlay Mapping | Trust Level |
|-----------------|-----------------|-------------|
| `modal_deployment/` | `5_service_adapters/tts` + `7_surfaces/modal` | PARTIALLY TRUSTED -- external service |
| `Dockerfile` | `0_frozen_doctrine/DEPLOYMENT_POSTURE.md` | Canonical build definition |
| `start.sh` | `0_frozen_doctrine/DEPLOYMENT_POSTURE.md` | Canonical routing |

## Skill Surfaces

| Existing Surface | Overlay Mapping | Trust Level |
|-----------------|-----------------|-------------|
| `skills/` | Governed skill wrappers | TRUSTED -- internal skill definitions |
| `skills/router.py` | `4_execution_spine/routers` | TRUSTED -- skill routing logic |
| `skills/registry.py` | `2_domain_kernels` | TRUSTED -- skill registry |

## Package Surfaces

| Existing Surface | Overlay Mapping | Trust Level |
|-----------------|-----------------|-------------|
| `packages/iron_ear/` | `2_domain_kernels/identity_kernel.py` | TRUSTED -- voice constraint module |
