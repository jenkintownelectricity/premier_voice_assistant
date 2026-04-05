# Environment Variable Contract

## Web Service (SERVICE_TYPE=web)

### Required
| Variable | Purpose | Example |
|----------|---------|---------|
| `SERVICE_TYPE` | Service routing | `web` |
| `PORT` | Server port (Railway sets this) | `8000` |
| `LIVEKIT_URL` | LiveKit server URL | `wss://app.livekit.cloud` |
| `LIVEKIT_API_KEY` | LiveKit authentication | `APIxxxxxxxx` |
| `LIVEKIT_API_SECRET` | LiveKit authentication | `secret...` |

### Optional
| Variable | Purpose | Default |
|----------|---------|---------|
| `SUPABASE_URL` | Supabase project URL | None |
| `SUPABASE_KEY` | Supabase anon key | None |
| `STRIPE_SECRET_KEY` | Stripe payments | None |
| `TWILIO_ACCOUNT_SID` | Twilio telephony | None |
| `FAST_BRAIN_URL` | Fast Brain endpoint | None |

## Worker Service (SERVICE_TYPE=worker)

### Required
| Variable | Purpose | Example |
|----------|---------|---------|
| `SERVICE_TYPE` | Service routing | `worker` |
| `LIVEKIT_URL` | LiveKit server URL | `wss://app.livekit.cloud` |
| `LIVEKIT_API_KEY` | LiveKit authentication | `APIxxxxxxxx` |
| `LIVEKIT_API_SECRET` | LiveKit authentication | `secret...` |
| `DEEPGRAM_API_KEY` | STT service | `dg_...` |

### Required (at least one TTS)
| Variable | Purpose | Example |
|----------|---------|---------|
| `CARTESIA_API_KEY` | Cartesia TTS (primary) | `sk_...` |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS (fallback) | `el_...` |

### Optional
| Variable | Purpose | Default |
|----------|---------|---------|
| `GROQ_API_KEY` | Groq LLM (System 1) | None |
| `OPENAI_API_KEY` | OpenAI fallback | None |
| `FAST_BRAIN_URL` | Fast Brain endpoint | None |
| `DEFAULT_SKILL` | Default skill ID | `default` |

## Fail-Closed Behavior

The preflight check (`scripts/preflight_env_check.py`) verifies all required variables are set before the service starts. Missing required variables cause startup failure with a clear error message.
