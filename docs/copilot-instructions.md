<!-- Copilot instructions for contributors and AI coding agents -->
# Premier Voice Assistant — Copilot Instructions

Summary
- Focus: backend FastAPI orchestration, Supabase RPCs (feature gates), and Modal GPU workers (Whisper STT, Coqui TTS).
- Primary touchpoints: `backend/`, `modal_deployment/`, `supabase/`, and `scripts/`.

What to know (big picture)
- Voice pipeline: mobile client → `backend.main` (FastAPI) → Modal workers (`modal_deployment/*.py`) → Supabase (usage, profiles, voice-clones).
- Feature gates live in the DB (Supabase functions) and are enforced in `backend/feature_gates.py` via RPCs like `va_check_feature_gate` and `va_increment_usage`.
- Modal workers are deployed separately (Modal images defined in `modal_deployment/*.py`). Backend lazy-loads Modal clients (`assistant.initialize_modal()`).

Key files to read
- `backend/main.py` — main FastAPI app, headers used (`X-User-ID`, `X-Admin-Key`), orchestration flow (STT → LLM → TTS).
- `backend/feature_gates.py` — enforcement, decorators (`require_feature`, `track_usage`), and RPC usage.
- `backend/supabase_client.py` — DB, storage, conversation and metrics helpers; uses service role key (backend-only).
- `modal_deployment/whisper_stt.py` and `modal_deployment/coqui_tts.py` — worker contract (methods: `transcribe`, `synthesize`, `clone_voice`) and deployment hints (images, volumes).
- `scripts/seed_plan_features.py` and `FEATURE_GATES_IMPLEMENTATION.md` — canonical plan limits and how features are seeded in the DB.

Concrete developer workflows
- Run backend locally (dev): `python -m backend.main` (or `uvicorn backend.main:app --reload`).
- Run feature gate tests / seed features:
  - `python scripts/seed_plan_features.py` (populate `va_plan_features`)
  - `python scripts/test_feature_gates.py` (end-to-end gate tests)
- Deploy Modal workers: use Modal CLI pointing at `modal_deployment/*` files. Example:
  - `modal deploy modal_deployment/whisper_stt.py`
  - `modal deploy modal_deployment/coqui_tts.py`
- Environment variables (must be set for backend): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `ADMIN_API_KEY`, optional `CLAUDE_MODEL`, `PORT`.

Project-specific conventions & patterns
- Headers: endpoints expect `X-User-ID` for user identity; admin endpoints require `X-Admin-Key`.
- Supabase usage: most business logic relies on Postgres functions/RPCs (e.g., `va_check_feature_gate`, `va_increment_usage`, `va_get_user_plan`). Prefer using these RPCs rather than re-implementing logic in Python.
- Lazy initialization: Modal clients and the Claude client are initialized on-demand (`assistant.initialize_modal()` / `initialize_claude()`) — be careful when changing startup behavior.
- Metrics: latency and token usage are logged via `supabase.log_usage_metric(...)`. Keep logging calls after major operations to preserve analytics.
- Storage buckets: review calls to `SupabaseManager.upload_audio(...)` — some code uses `voice-clones` while docstrings mention `va-voice-clones`; follow existing usages in code and verify bucket names in Supabase.

Integration points & dependencies
- External APIs: Anthropic/Claude (via `ANTHROPIC_API_KEY`), Modal (Modal SDK), Supabase (client + stored procedures), and local GPU images for TTS/STT.
- Modal contract: code expects methods with `.remote` proxies (e.g., `stt.transcribe.remote(bytes)`, `tts.synthesize.remote(text, voice)` and `tts.clone_voice.remote(...)`). Keep method signatures compatible when editing workers.
- Database: migrations live in `supabase/migrations/*` and are the source of truth for feature gate functions and triggers. Do not change enforcement behavior without updating SQL migrations.

Examples (copy-paste to reproduce behavior)
- Chat call (backend enforces `max_minutes`):
  curl -X POST http://localhost:8000/chat \
    -H "X-User-ID: user-123" \
    -F "audio=@test.wav"

- Admin upgrade (requires `X-Admin-Key` = `ADMIN_API_KEY`):
  curl -X POST http://localhost:8000/admin/upgrade-user \
    -H "X-Admin-Key: your-admin-key" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"user-123","plan_name":"pro"}'

What not to change without coordination
- Stored procedures and views in `supabase/migrations/` — they implement authoritative gating and accounting. Changing them requires migration updates and re-seeding.
- Modal worker method signatures and volume names — backend calls `.remote(...)` and uses `/voice_models` volume; changes must remain backward compatible.
- Header conventions: `X-User-ID` and `X-Admin-Key` are relied on across the codebase.

If you need more context
- Read `FEATURE_GATES_IMPLEMENTATION.md` for design rationale and canonical examples.
- Inspect `scripts/seed_plan_features.py` to see exact plan limits used in tests and seeds.
- Use `backend/main.py` and `backend/supabase_client.py` as the canonical flow and DB access examples.

Questions or missing bits? Ask which area you'd like expanded (Modal deployment, DB RPCs, or client integration). 
