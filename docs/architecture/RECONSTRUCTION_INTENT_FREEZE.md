# RECONSTRUCTION INTENT FREEZE -- HIVE215

**Frozen:** 2026-04-05
**Branch:** claude/deployment-hardening-audit-t4L2Q
**System:** HIVE215 -- Governed Voice Runtime Shell

## Intent

This reconstruction applies a governed overlay onto the active HIVE215 voice runtime. The overlay adds formal trust boundaries, typed constraint ports, execution receipts, and deployment hardening without modifying any existing production code.

## Preservation Guarantees

The following surfaces are preserved exactly as they exist. No files within these directories are modified, renamed, or removed by this reconstruction.

| Surface | Path | Role |
|---------|------|------|
| Backend API | `backend/` | FastAPI server, brain client, service clients, LiveKit worker |
| Web Frontend | `web/` | Next.js browser application |
| Mobile App | `mobile/` | React Native mobile application |
| Voice Worker | `worker/` | Voice agent, identity manager, turn taking, latency manager |
| Supabase | `supabase/` | Database migrations and schema |
| Modal Deployment | `modal_deployment/` | Whisper STT, Coqui TTS, Kokoro TTS, voice cloner |
| Skills | `skills/` | Multi-skill system (receptionist, electrician, plumber, lawyer, solar, etc.) |
| Packages | `packages/` | Iron Ear voice constraint module |
| Tests | `tests/` | Existing test suite |
| Scripts | `scripts/` | Deployment and utility scripts |
| Config | `Dockerfile`, `start.sh`, `railway.toml`, `Procfile` | Deployment configuration |

## Overlay Structure

The reconstruction creates the following new top-level directories that sit alongside (never replace) the existing codebase:

- `0_frozen_doctrine/` -- Root truth, trust model, system intent, execution and deployment posture
- `1_governance/` -- Schemas, contracts, policies, runtime rules, trust zones
- `2_domain_kernels/` -- Typed domain logic (transcript, session, dialogue, voice, identity, user state, execution approval, deployment)
- `3_constraint_ports/` -- Typed, trust-leveled ports for all I/O boundaries
- `4_execution_spine/` -- Planners, routers, executors, receipts, rollback, fail-closed
- `5_service_adapters/` -- Wrappers for external services (Supabase, LiveKit, Groq, Deepgram, Cartesia, etc.)
- `6_state/` -- Typed state, session state, runtime cache, audit log, lineage
- `7_surfaces/` -- Mapping layer connecting overlay to existing surfaces
- `8_tests/` -- Governance test suite (doctrine, contracts, trust, constraint, runtime, deployment, e2e)
- `9_receipts/` -- Audit, reconstruction, deploy, runtime, and migration receipts

## Non-Goals

- This reconstruction does NOT rewrite any existing backend, worker, web, or mobile code.
- This reconstruction does NOT change any existing deployment configuration.
- This reconstruction does NOT introduce new runtime dependencies into the production path.
- This reconstruction does NOT gate existing functionality behind new approval layers (yet -- that is a future phase).

## Rollback

If any part of this overlay causes issues, the entire overlay can be removed by deleting the numbered directories (`0_frozen_doctrine/` through `9_receipts/`) and the new docs. The original codebase remains untouched.
