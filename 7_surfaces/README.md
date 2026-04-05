# Surfaces

Mapping layer connecting the HIVE215 governance overlay to existing production surfaces.

## Surface Map

| Existing Surface | Overlay Role | Trust Level |
|-----------------|-------------|-------------|
| `backend/` | Primary backend execution surface. FastAPI server, brain client, service clients. | TRUSTED (internal) |
| `worker/` | Primary voice worker surface. Voice agent, identity manager, turn taking. | TRUSTED (internal) |
| `web/` | Browser surface. Next.js frontend. | UNTRUSTED (user-controlled) |
| `mobile/` | Mobile surface. React Native app. | UNTRUSTED (user-controlled) |
| `modal_deployment/` | Deployment support surface. Modal STT/TTS services. | PARTIALLY TRUSTED (external service) |
| `skills/` | Governed skill wrappers. Multi-skill system. | TRUSTED (after governance wrapping) |
| `packages/iron_ear/` | Voice constraint module. Speaker locking, identity lock. | TRUSTED (internal) |
| `supabase/` | Database boundary. Migrations and schema. | PARTIALLY TRUSTED (external data store) |
| `tests/` | Existing test suite. Preserved and extended by 8_tests/. | TRUSTED |

## Rules

1. Surfaces are not modified by the overlay. They are wrapped at the boundary.
2. Each surface has a declared trust level that determines how its data is handled.
3. New governance tests in `8_tests/` extend (never replace) existing tests in `tests/`.
