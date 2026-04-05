# Contract: Fast Brain -> HIVE215

Defines the typed interface for data flowing from Fast Brain to HIVE215.

## Endpoints Consumed by HIVE215

### POST /v1/chat/hybrid
Auto-routes between System 1 (Groq ~80ms) and System 2 (Claude ~2s).

**Request (from HIVE215):**
```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "skill_id": "receptionist",
  "max_tokens": 100,
  "temperature": 0.4
}
```

**Response (to HIVE215) -- PARTIALLY TRUSTED:**
```json
{
  "response": "The response text from the LLM",
  "system_used": "system_1" | "system_2",
  "filler_phrase": "Let me look into that for you...",
  "latency_ms": 82,
  "skill_id": "receptionist",
  "model": "llama-3.3-70b-versatile"
}
```

### POST /v1/chat/voice
Returns text with TTS hints.

**Response (to HIVE215) -- PARTIALLY TRUSTED:**
```json
{
  "response": "The response text",
  "voice_hints": {
    "speed": 1.0,
    "emotion": "friendly"
  },
  "system_used": "system_1",
  "filler_phrase": null
}
```

### GET /health
Health check.

**Response -- PARTIALLY TRUSTED:**
```json
{
  "status": "healthy",
  "architecture": "dual_system",
  "system_1": "groq_llama_3.3_70b",
  "system_2": "claude_3.5_sonnet"
}
```

### GET /v1/skills
List available skills.

**Response -- PARTIALLY TRUSTED:**
```json
[
  {
    "skill_id": "receptionist",
    "name": "Receptionist",
    "description": "General business inquiries"
  }
]
```

## Trust Handling

All Fast Brain responses enter HIVE215 as PARTIALLY TRUSTED. Before use:

1. HTTP status must be 2xx (fail closed on errors)
2. Response must be valid JSON (fail closed on parse errors)
3. `response` field must be a non-empty string
4. `system_used` must be a known value ("system_1" or "system_2")
5. Response text is passed through the LLM output typing port
6. Typed response enters the execution approval kernel as an ActionEnvelope

## Failure Modes

| Failure | HIVE215 Behavior |
|---------|-----------------|
| Fast Brain unreachable | Fall back to direct Groq (RoutingDecision.FALLBACK_DIRECT) |
| HTTP 5xx | Fail closed, emit adapter receipt with error |
| Malformed JSON | Fail closed, emit adapter receipt with parse error |
| Empty response text | Fail closed, reject as malformed |
| Timeout (> 5s for System 1, > 15s for System 2) | Fail closed, emit timeout receipt |
