# V2 Migration Blueprint: HIVE215 Voice AI Platform

> **Generated**: January 6, 2026
> **Purpose**: Multi-tenant, white-label SaaS refactoring specification
> **Status**: READ-ONLY AUDIT (No code changes made)

---

## Table of Contents

1. [Golden Logic Inventory](#1-golden-logic-inventory)
2. [Dependency Graph](#2-dependency-graph)
3. [Refactor Strategy (Multi-Tenancy)](#3-refactor-strategy-multi-tenancy)
4. [Spaghetti Removal List](#4-spaghetti-removal-list)

---

## 1. Golden Logic Inventory

### 🎯 CRITICAL FILES - MUST PRESERVE

These files contain battle-tested logic that forms the core of the voice AI system.

---

### 1.1 Iron Ear Stack (Noise Filtering & Turn-Taking)

The "Iron Ear" is a multi-layer audio filtering system that handles real-world conversation challenges.

| File | Lines | Purpose | Complexity |
|------|-------|---------|------------|
| `worker/voice_agent.py` | 328 | Main VoiceAgent class with latency masking | ⭐⭐⭐ |
| `worker/turn_taking.py` | 896 | TurnManager, SemanticTurnDetector, Iron Ear V1/V2 | ⭐⭐⭐⭐⭐ |
| `worker/identity_manager.py` | 520 | IdentityManager with Resemblyzer ML embeddings | ⭐⭐⭐⭐ |
| `worker/latency_manager.py` | ~200 | LatencyMasker for filler generation | ⭐⭐⭐ |

**Key Classes to Preserve:**

```python
# worker/turn_taking.py
class TurnManager:
    """
    Iron Ear V1: Debounce (filters door slams, coughs)
    Iron Ear V2: Speaker Locking (volume fingerprinting)
    Iron Ear V3: Identity Lock (ML speaker verification)
    """
    def is_real_speech(frame_probability: float) -> bool  # V1 debounce
    def is_background_voice(energy: float) -> bool        # V2 volume filter
    def process(...) -> TurnState                          # Main state machine

class SemanticTurnDetector:
    """Predicts turn-end using regex patterns + context"""
    TURN_END_PATTERNS = [...]      # Lines 207-216
    TURN_CONTINUE_PATTERNS = [...]  # Lines 219-226

# worker/identity_manager.py
class IdentityManager:
    """Zero-shot speaker enrollment using Resemblyzer"""
    def lock_identity() -> bool           # Creates 256-dim embedding
    def verify_speaker(...) -> Tuple[bool, float]  # Cosine similarity check
```

**Iron Ear Flow:**
```
Audio Frame → V1 Debounce (300ms) → V2 Speaker Lock (volume) → V3 Identity (ML) → Process
              ↓ reject noise         ↓ reject quiet voices     ↓ reject imposters
```

---

### 1.2 Fast Brain (Dual-System LLM Routing)

Kahneman-inspired System 1 (fast) / System 2 (deep) architecture.

| File | Lines | Purpose | Complexity |
|------|-------|---------|------------|
| `backend/brain_client.py` | 1090 | FastBrainClient with hybrid routing | ⭐⭐⭐⭐ |
| `backend/groq_client.py` | ~600 | HybridLLMClient for Groq + Claude fallback | ⭐⭐⭐ |

**Key Classes:**

```python
# backend/brain_client.py
@dataclass
class HybridResponse:
    """Response with optional filler phrase for System 2 delays"""
    content: str
    filler: Optional[str]  # Play while Claude thinks
    system_used: str       # "fast" or "deep"
    fast_latency_ms: float
    deep_latency_ms: Optional[float]

class FastBrainClient:
    """Connects to Modal-hosted Fast Brain LPU"""
    async def hybrid_chat(...) -> HybridResponse  # Lines 460-531
    async def hybrid_think(...) -> HybridResponse # Lines 533-551
    async def analyze_turn(...) -> TurnResult     # Lines 737-804 (local logic)
```

**Routing Logic (preserve these decision points):**
- Simple queries → System 1 (Groq ~80ms)
- Complex analysis/calculations → System 2 (Claude ~2000ms) with filler phrase
- Fallback → Direct Groq if Fast Brain unavailable

---

### 1.3 TTS/STT Clients

Production-ready streaming clients with WebSocket management.

| File | Lines | Purpose | API |
|------|-------|---------|-----|
| `backend/cartesia_client.py` | 908 | CartesiaSonic3 streaming TTS | Cartesia |
| `backend/deepgram_client.py` | 705 | DeepgramNova3 streaming STT | Deepgram |
| `backend/coqui_streaming_tts.py` | 200 | CoquiStreamingTTS with jitter buffer | Modal/Coqui |

**Key Configurations (preserve defaults):**

```python
# backend/cartesia_client.py
@dataclass
class CartesiaConfig:
    model_id: str = "sonic-3"
    default_voice_id: str = "f786b574-daa5-4673-aa0c-cbe3e8534c02"  # Katie
    output_format: str = "pcm_s16le"
    sample_rate: int = 16000
    ws_url: str = "wss://api.cartesia.ai/tts/websocket"

# backend/deepgram_client.py
@dataclass
class DeepgramConfig:
    model: str = "nova-2"
    language: str = "en-US"
    encoding: str = "linear16"
    sample_rate: int = 16000
    utterance_end_ms: int = 1000
    endpointing: int = 300

# backend/coqui_streaming_tts.py
SAMPLE_RATE = 24000
FRAME_DURATION_MS = 20
pre_buffer_frames: int = 3  # 60ms jitter buffer
```

---

### 1.4 Skills System

Modular skill definitions with keyword routing.

| File | Purpose |
|------|---------|
| `skills/base.py` | SkillDefinition dataclass |
| `skills/registry.py` | SkillRegistry with keyword routing |
| `skills/electrician.py` | Domain-specific skill |
| `skills/plumber.py` | Domain-specific skill |
| `skills/receptionist.py` | Default skill |
| `skills/lawyer.py` | Domain-specific skill |
| `skills/solar.py` | Domain-specific skill |
| `skills/tara_sales.py` | Custom sales skill |

**Skill Structure (maintain this interface):**

```python
@dataclass
class SkillDefinition:
    skill_id: str           # "electrician"
    name: str               # "Master Electrician"
    description: str
    system_prompt: str      # Full LLM prompt
    knowledge: list[str]    # RAG items
    greeting: str           # Call opener
    voice_description: str  # TTS hint
```

---

### 1.5 LiveKit Agent Integration

| File | Lines | Purpose |
|------|-------|---------|
| `backend/livekit_agent.py` | 2070 | Full voice pipeline with LiveKit SDK |
| `backend/livekit_api.py` | ~750 | FastAPI routes for LiveKit |
| `backend/livekit_worker.py` | ~165 | Worker entry point |

**Critical Functions:**

```python
# backend/livekit_agent.py
async def entrypoint(ctx: JobContext)  # Lines 1394-1945
    """Main agent loop - DO NOT BREAK"""

@dataclass
class AgentConfig:  # Lines 382-426
    """All configurable parameters"""
```

---

## 2. Dependency Graph

### 2.1 Environment Variables

| Variable | Service | Context | Required |
|----------|---------|---------|----------|
| **LiveKit** ||||
| `LIVEKIT_URL` | LiveKit Cloud | Worker, Web | ✅ |
| `LIVEKIT_API_KEY` | LiveKit Cloud | Worker, Web | ✅ |
| `LIVEKIT_API_SECRET` | LiveKit Cloud | Worker, Web | ✅ |
| `LIVEKIT_SIP_URI` | LiveKit SIP | Telephony | ❌ |
| **STT** ||||
| `DEEPGRAM_API_KEY` | Deepgram | Worker | ✅ |
| **TTS** ||||
| `CARTESIA_API_KEY` | Cartesia | Worker | ✅ |
| `CARTESIA_VOICE_ID` | Cartesia | Worker | ❌ |
| `ELEVENLABS_API_KEY` | ElevenLabs | Worker | ❌ |
| `TTS_PROVIDER` | Config | Worker | ❌ |
| `TTS_VOICE_ID` | Config | Worker | ❌ |
| `MODAL_TTS_URL` | Modal (Kokoro) | Worker | ❌ |
| `COQUI_STREAM_URL` | Modal (Coqui) | Worker | ❌ |
| **LLM** ||||
| `GROQ_API_KEY` | Groq | Worker | ✅ |
| `GROQ_MODEL` | Groq | Worker | ❌ |
| `ANTHROPIC_API_KEY` | Anthropic | Worker, Web | ❌ |
| `OPENAI_API_KEY` | OpenAI | Worker | ❌ |
| `FAST_BRAIN_URL` | Modal | Worker, Skills | ✅ |
| `DEFAULT_SKILL` | Config | Worker | ❌ |
| `LLM_PRIMARY_PROVIDER` | Config | Settings | ❌ |
| `LLM_FALLBACK_PROVIDER` | Config | Settings | ❌ |
| **Database** ||||
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase | Web | ✅ |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase | Web | ✅ |
| **Telephony** ||||
| `TWILIO_ACCOUNT_SID` | Twilio | Telephony | ❌ |
| `TWILIO_AUTH_TOKEN` | Twilio | Telephony | ❌ |
| `TWILIO_PHONE_NUMBER` | Twilio | Telephony | ❌ |
| **Payments** ||||
| `STRIPE_SECRET_KEY` | Stripe | Web | ❌ |
| `STRIPE_WEBHOOK_SECRET` | Stripe | Web | ❌ |
| `STRIPE_PRICE_WORKER_BEE` | Stripe | Web | ❌ |
| `STRIPE_PRICE_SWARM` | Stripe | Web | ❌ |
| `STRIPE_PRICE_QUEEN_BEE` | Stripe | Web | ❌ |
| `STRIPE_PRICE_HIVE_MIND` | Stripe | Web | ❌ |
| **Other** ||||
| `MODAL_TOKEN_ID` | Modal | Deployment | ❌ |
| `MODAL_TOKEN_SECRET` | Modal | Deployment | ❌ |
| `DEBUG` | Config | All | ❌ |
| `API_URL` | Config | Web | ❌ |
| `SERVICE_TYPE` | Railway | Deployment | ✅ |

### 2.2 External Service Dependencies

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HIVE215 Voice AI                              │
├─────────────────────────────────────────────────────────────────────┤
│  Real-time Media       │ LiveKit Cloud (WebRTC)                     │
│  Speech-to-Text        │ Deepgram Nova-2/3                          │
│  Text-to-Speech        │ Cartesia Sonic-3 / ElevenLabs / Coqui      │
│  LLM (Fast)            │ Groq (Llama 3.3 70B)                       │
│  LLM (Deep)            │ Anthropic (Claude Sonnet)                   │
│  GPU Functions         │ Modal (Fast Brain, Coqui, Kokoro)          │
│  Database              │ Supabase (PostgreSQL)                       │
│  Payments              │ Stripe                                      │
│  Telephony             │ Twilio / Plivo / Telnyx / Vonage / VoIP.ms │
│  Hosting               │ Railway (Web + Worker)                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Refactor Strategy (Multi-Tenancy)

### 3.1 Current State

```python
# Current: Single-tenant VoiceAgent
agent = VoiceAgent(skill_type="electrician")
```

### 3.2 Target State

```python
# Target: Multi-tenant with org config injection
agent = VoiceAgent(
    org_id="org_123",
    branding_config=OrgBrandingConfig(...),
    user_id="user_456",
    skill_type="electrician"
)
```

### 3.3 Proposed OrganizationConfig

```python
@dataclass
class OrgBrandingConfig:
    """White-label configuration per organization."""
    org_id: str
    org_name: str

    # Voice Branding
    greeting_template: str = "Hi! This is {org_name}, how can I help?"
    tts_voice_id: Optional[str] = None  # Custom voice per org

    # LLM Branding
    system_prompt_prefix: str = ""  # Prepended to all skills
    company_knowledge: List[str] = field(default_factory=list)

    # Iron Ear Settings (per org thresholds)
    vad_threshold: float = 0.65
    identity_verification_enabled: bool = True

    # Feature Flags
    enable_call_recording: bool = False
    enable_sentiment_analysis: bool = True
    max_call_duration_minutes: int = 30

    # Styling (for white-label UI)
    primary_color: str = "#F59E0B"  # Amber
    logo_url: Optional[str] = None

    @classmethod
    def from_supabase(cls, org_id: str) -> "OrgBrandingConfig":
        """Load config from database."""
        # Query organizations table
        pass
```

### 3.4 VoiceAgent Multi-Tenant Wrapper

```python
# Proposed: worker/multi_tenant_agent.py

from worker.voice_agent import VoiceAgent
from worker.turn_taking import TurnConfig

class MultiTenantVoiceAgent(VoiceAgent):
    """
    Multi-tenant wrapper that preserves core VoiceAgent logic.
    Injects org-specific configuration without modifying golden logic.
    """

    def __init__(
        self,
        org_id: str,
        branding_config: OrgBrandingConfig,
        user_id: Optional[str] = None,
        skill_type: Optional[str] = None,
    ):
        # Build org-specific TurnConfig
        turn_config = TurnConfig(
            vad_threshold=branding_config.vad_threshold,
            enable_identity_verification=branding_config.identity_verification_enabled,
        )

        # Initialize parent with org-specific config
        super().__init__(
            skill_type=skill_type,
            turn_config=turn_config,
        )

        # Store org context
        self.org_id = org_id
        self.branding = branding_config
        self.user_id = user_id

        # Override greeting
        self._custom_greeting = branding_config.greeting_template.format(
            org_name=branding_config.org_name
        )

    def get_greeting(self) -> str:
        """Return org-branded greeting."""
        return self._custom_greeting

    def get_system_prompt_prefix(self) -> str:
        """Return org-specific prompt prefix."""
        return self.branding.system_prompt_prefix
```

### 3.5 Database Schema Extension

```sql
-- Add to Supabase migrations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,

    -- Branding
    greeting_template TEXT DEFAULT 'Hi! How can I help you today?',
    tts_voice_id TEXT,
    system_prompt_prefix TEXT,
    primary_color TEXT DEFAULT '#F59E0B',
    logo_url TEXT,

    -- Settings
    vad_threshold FLOAT DEFAULT 0.65,
    identity_verification_enabled BOOLEAN DEFAULT true,
    max_call_duration_minutes INT DEFAULT 30,

    -- Billing
    stripe_customer_id TEXT,
    plan_id TEXT REFERENCES plans(id),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Link users to organizations
ALTER TABLE profiles ADD COLUMN org_id UUID REFERENCES organizations(id);
```

---

## 4. Spaghetti Removal List

### 4.1 Hardcoded Styles (12 files)

Files with hardcoded hex colors that should use CSS variables:

| File | Issue |
|------|-------|
| `mobile/src/screens/AssistantsScreen.tsx` | Inline colors |
| `mobile/src/screens/CallsScreen.tsx` | Inline colors |
| `mobile/src/screens/DashboardScreen.tsx` | Inline colors |
| `mobile/src/screens/LoginScreen.tsx` | Inline colors |
| `mobile/src/screens/RedeemScreen.tsx` | Inline colors |
| `mobile/src/screens/SettingsScreen.tsx` | Inline colors |
| `mobile/src/screens/SignupScreen.tsx` | Inline colors |
| `web/src/app/dashboard/calls/page.tsx` | Inline colors |
| `web/src/app/dashboard/insights/page.tsx` | Inline colors |
| `web/src/app/dashboard/observability/page.tsx` | Inline colors |
| `web/src/app/dashboard/teams/page.tsx` | Inline colors |
| `web/src/components/HoneycombButton.tsx` | Inline colors |

**Fix:** Create `theme.css` with CSS variables:
```css
:root {
  --color-primary: #F59E0B;
  --color-primary-hover: #D97706;
  --color-bg-dark: #18181B;
  --color-border: #27272A;
}
```

### 4.2 Hardcoded URLs

| File | Line | Issue |
|------|------|-------|
| `web/src/components/VoiceCallWrapper.tsx` | 51 | `'https://web-production-1b085.up.railway.app'` |
| `web/src/lib/api.ts` | 1 | Same hardcoded URL |
| `backend/livekit_agent.py` | 418 | Modal TTS URL |
| `backend/coqui_streaming_tts.py` | 29 | Modal Coqui URL |

**Fix:** Move all to environment variables.

### 4.3 Duplicate Functions

| Function | Locations | Action |
|----------|-----------|--------|
| `normalize_livekit_url()` | `livekit_worker.py:74`, `livekit_agent.py:125` | Consolidate to `livekit_utils.py` |
| `get_*_client()` singletons | Multiple files | Create unified `clients/` module |
| `get_supported_languages()` | `cartesia_client.py`, `deepgram_client.py` | Keep separate (different APIs) |

### 4.4 TODOs and Incomplete Code

| File | Line | Issue |
|------|------|-------|
| `skills/tara_sales.py` | 20 | `TARA_VOICE_ID = "" # TODO: Set after cloning` |
| `backend/brain_client.py` | 709 | `# TODO: Implement true SSE streaming` |
| `backend/brain_client.py` | 930 | `# TODO: Implement when Fast Brain has feedback endpoint` |
| `backend/main.py` | 6129 | `# TODO: Actually send via Twilio` |
| `backend/main.py` | 6713 | `# TODO: Actually send email/SMS based on share_type` |
| `backend/main.py` | 6959 | `# TODO: Send email invitation` |

### 4.5 Dead Code Candidates

Check for usage before removing:

| Pattern | Files to Audit |
|---------|----------------|
| `lightning_pipeline.py` | May be superseded by `livekit_agent.py` |
| `streaming_manager.py` | Check if still used with WebSocket mode |
| `backend/turn_taking_model.py` | ~1155 lines, check overlap with `worker/turn_taking.py` |

### 4.6 Large Files Needing Decomposition

| File | Lines | Recommendation |
|------|-------|----------------|
| `backend/main.py` | 7000+ | Split into routers: `auth.py`, `calls.py`, `assistants.py` |
| `backend/livekit_agent.py` | 2070 | Extract: `sentiment.py`, `transcript.py`, `quality.py` |

---

## Migration Priority

### Phase 1: Foundation (No Breaking Changes)
1. Create `OrgBrandingConfig` dataclass
2. Add `organizations` table to Supabase
3. Create CSS variables theme system
4. Consolidate duplicate functions

### Phase 2: Multi-Tenant Wrapper
1. Create `MultiTenantVoiceAgent` wrapper
2. Update `entrypoint()` to load org config
3. Add org_id to call logs

### Phase 3: White-Label UI
1. Replace hardcoded colors with CSS variables
2. Add org logo/branding support
3. Custom domain support (optional)

### Phase 4: Cleanup
1. Remove dead code
2. Decompose large files
3. Complete all TODOs or remove them

---

## Files to NEVER Modify Without Tests

These files are critical and any changes must be tested:

1. `worker/turn_taking.py` - Core conversation flow
2. `worker/identity_manager.py` - Security-critical
3. `backend/brain_client.py` - LLM orchestration
4. `backend/livekit_agent.py:entrypoint()` - Main loop

---

*Generated by Claude Code audit - January 6, 2026*
