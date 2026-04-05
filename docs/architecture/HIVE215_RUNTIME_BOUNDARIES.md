# HIVE215 Runtime Boundaries

## Service Boundaries

```
                          Railway Platform
+---------------------------+  +---------------------------+
|        WEB SERVICE        |  |      WORKER SERVICE       |
|  (SERVICE_TYPE=web)       |  |  (SERVICE_TYPE=worker)    |
|                           |  |                           |
|  backend/main.py          |  |  backend/livekit_worker.py|
|  FastAPI REST/WebSocket   |  |  LiveKit Agent SDK        |
|  Token generation         |  |  Voice pipeline           |
|  Health checks            |  |  STT/TTS/LLM             |
|  Supabase integration     |  |  Iron Ear filtering       |
|  Stripe payments          |  |  Identity management      |
|  Twilio telephony         |  |  Turn taking              |
+---------------------------+  +---------------------------+
         |          |                    |          |
         v          v                    v          v
    [Browser]  [Supabase]          [LiveKit]   [Fast Brain]
    [Mobile]                       [Deepgram]  [Cartesia]
```

## Process Boundaries

The two Railway services run in separate containers with separate processes.

### Web Service Process
- **Entrypoint:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Framework:** FastAPI (async)
- **Imports:** supabase_client, feature_gates, stripe_payments, twilio_integration, model_manager, streaming_manager, lightning_pipeline, groq_client, cartesia_client, deepgram_client, livekit_api
- **External connections:** Supabase (PARTIALLY TRUSTED), Browser/Mobile clients (UNTRUSTED), LiveKit API (PARTIALLY TRUSTED)

### Worker Service Process
- **Entrypoint:** `python backend/livekit_worker.py start`
- **Framework:** LiveKit Agents SDK 1.3.8
- **Imports:** livekit_agent, worker/voice_agent, worker/identity_manager, worker/turn_taking, worker/latency_manager
- **External connections:** LiveKit Cloud (PARTIALLY TRUSTED), Deepgram (PARTIALLY TRUSTED), Cartesia (PARTIALLY TRUSTED), Fast Brain/Groq (PARTIALLY TRUSTED)

## Network Boundaries

| Boundary | Protocol | Authentication | Trust Level |
|----------|----------|---------------|-------------|
| Browser -> Web Service | HTTPS/WSS | Session token | UNTRUSTED |
| Mobile -> Web Service | HTTPS/WSS | Session token | UNTRUSTED |
| Web Service -> Supabase | HTTPS | Service key | PARTIALLY TRUSTED |
| Web Service -> LiveKit API | HTTPS | API key/secret | PARTIALLY TRUSTED |
| Worker -> LiveKit Cloud | WSS | API key/secret | PARTIALLY TRUSTED |
| Worker -> Deepgram | WSS | API key | PARTIALLY TRUSTED |
| Worker -> Cartesia | HTTPS | API key | PARTIALLY TRUSTED |
| Worker -> Fast Brain (Modal) | HTTPS | None (URL-based) | PARTIALLY TRUSTED |
| Worker -> Groq | HTTPS | API key | PARTIALLY TRUSTED |

## Isolation Guarantees

1. Web and Worker services share no memory or process state
2. Communication between Web and Worker happens only through LiveKit
3. Browser clients cannot reach the Worker service directly
4. Worker does not serve HTTP traffic to external clients
5. Each service has its own set of environment variables for its specific integrations
