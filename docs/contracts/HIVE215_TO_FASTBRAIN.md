# Contract: HIVE215 -> Fast Brain

Defines the typed interface for data flowing from HIVE215 to Fast Brain.

## Requests Sent by HIVE215

### Chat Request (Hybrid)

**Endpoint:** POST /v1/chat/hybrid

**Pre-conditions (enforced by HIVE215):**
1. User transcript has been normalized (TranscriptNormalized with ACCEPTED verdict)
2. Session is in ACTIVE_DIALOGUE or SKILL_ROUTING phase
3. Dialogue context has been assembled with validated turns
4. Routing decision has been made (System 1 or System 2)

**Request Schema:**
```json
{
  "messages": [
    {
      "role": "system",
      "content": "<skill system prompt - typed, from skill registry>"
    },
    {
      "role": "user",
      "content": "<normalized transcript text>"
    }
  ],
  "skill_id": "<validated skill ID from registry>",
  "max_tokens": 100,
  "temperature": 0.4
}
```

**Field Constraints:**
| Field | Constraint | Enforcement |
|-------|-----------|-------------|
| `messages` | Non-empty array, system + at least one user message | Dialogue kernel |
| `messages[].role` | Must be "system", "user", or "assistant" | Dialogue kernel |
| `messages[].content` | Non-empty string, max 4000 tokens estimated | Context window enforcement |
| `skill_id` | Must be registered in skill registry | Skill router validation |
| `max_tokens` | 50-500 range for voice, 100-2000 for text | Execution approval kernel |
| `temperature` | 0.0-1.0 range | Execution approval kernel |

### Voice Chat Request

**Endpoint:** POST /v1/chat/voice

Same schema as hybrid but response includes voice hints for TTS.

### Health Check

**Endpoint:** GET /health

No request body. Used by deployment kernel for readiness checks.

### Skills List

**Endpoint:** GET /v1/skills

No request body. Used during initialization to validate skill registry.

## Data Lineage

Every request to Fast Brain can be traced back through:
1. **Execution Receipt:** Records the approved ActionEnvelope
2. **Routing Receipt:** Records the System 1/System 2 routing decision
3. **Dialogue Turn:** Records the user turn that triggered the request
4. **Normalization Receipt:** Records the transcript validation
5. **Session State:** Records the session phase at time of request

## Rate Limiting

HIVE215 does not send more than one concurrent request per session to Fast Brain. If a request is in flight, subsequent requests for the same session are queued.
