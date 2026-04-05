# Trust Zones

Trust zone definitions for HIVE215 system boundaries.

## Zones

| Zone | Trust Level | Components |
|------|-------------|------------|
| **Core Governance** | TRUSTED | UTK, domain kernels, constraint ports, execution spine |
| **Typed State** | TRUSTED | Session state, typed user state (after validation) |
| **Service Adapters** | PARTIALLY TRUSTED | Groq, Cartesia, Deepgram, LiveKit, Anthropic, Supabase |
| **Browser Surface** | UNTRUSTED | Web UI state, browser commands, client-side data |
| **Mobile Surface** | UNTRUSTED | Mobile app state, mobile commands |
| **Upload Zone** | UNTRUSTED | User uploads of any kind |
| **External Zone** | UNTRUSTED | Third-party API responses |

## Zone Crossing Rules

1. Every zone crossing passes through a constraint port.
2. Every zone crossing emits an adapter receipt.
3. Data trust level can only increase (UNTRUSTED -> validated -> TRUSTED), never decrease.
4. TRUSTED data that leaves the core governance zone and returns must be re-validated.
