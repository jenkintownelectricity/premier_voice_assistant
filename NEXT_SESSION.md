# Next Session: Medium & Long-Term Feature Implementation

**Last Updated:** November 28, 2025
**Previous Session:** Completed all "Easy Wins" (sentiment display, latency monitoring, templates, quality scoring, IVR killer marketing)
**Next Goals:** Human handoff, voice upgrade, appointment scheduling, and more

---

## Current State

### Completed Features (Production Ready)

- Real-time sentiment display during calls
- Real-time latency monitoring (STT/LLM/TTS breakdown)
- Call quality scoring system (0-100 with A-F grades)
- 9 industry quick-start templates
- IVR Killer marketing positioning
- Token usage & cost tracking
- Error rate monitoring
- Budget tracking with alerts
- Twilio phone integration (live)

### Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 14, React Native (Expo) |
| Backend | FastAPI (Python) on Railway |
| Database | Supabase (PostgreSQL) |
| AI | Claude 3.5 Sonnet Latest |
| STT | Whisper (Modal) |
| TTS | Kokoro (Modal) |
| Payments | Stripe |
| Telephony | Twilio |

---

## Medium Effort Features (1-2 weeks each)

### Priority 1: Human Handoff System

**Impact:** Critical for complex issues
**Effort:** 1 week

**What It Does:**
When AI detects it can't resolve an issue or caller requests a human, seamlessly transfer to a live person with full context.

**Implementation Steps:**

1. **Backend - Handoff Detection**
```python
# backend/main.py - Add to VoiceCallSession class

HANDOFF_TRIGGERS = [
    'speak to a human', 'talk to someone', 'real person',
    'transfer me', 'manager', 'supervisor', 'representative',
    'this isn\'t working', 'you\'re not understanding'
]

def detect_handoff_request(self, text: str) -> bool:
    """Detect if caller wants human handoff."""
    text_lower = text.lower()
    return any(trigger in text_lower for trigger in self.HANDOFF_TRIGGERS)

async def initiate_handoff(self, reason: str = 'user_requested'):
    """Initiate transfer to human agent."""
    # Create handoff record with full context
    handoff_data = {
        'call_id': self.call_id,
        'transcript': self.transcript,
        'sentiment': self.current_sentiment,
        'urgency': self.urgency_level,
        'reason': reason,
        'caller_summary': self._generate_caller_summary()
    }

    # Notify human agents (via webhook, SMS, or real-time dashboard)
    await self.notify_available_agents(handoff_data)

    # Send handoff message to caller
    await self.websocket.send_json({
        "type": "handoff_initiated",
        "message": "I'm connecting you with a team member now. One moment please.",
        "estimated_wait": "under 2 minutes"
    })
```

2. **Frontend - Handoff UI**
```typescript
// Add to VoiceCall.tsx
case 'handoff_initiated':
  setHandoffStatus({
    active: true,
    message: data.message,
    estimatedWait: data.estimated_wait
  });
  break;
```

3. **Database Schema**
```sql
CREATE TABLE va_handoffs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  call_id UUID REFERENCES va_calls(id),
  user_id UUID REFERENCES auth.users(id),
  reason TEXT NOT NULL,
  transcript JSONB,
  sentiment TEXT,
  urgency TEXT,
  status TEXT DEFAULT 'pending', -- pending, accepted, completed, missed
  accepted_by UUID REFERENCES auth.users(id),
  accepted_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

4. **Agent Dashboard**
- Real-time queue of pending handoffs
- One-click accept
- Full transcript and context visible
- Call transfer via Twilio

**Files to Modify:**
- `backend/main.py` - Handoff detection and initiation
- `web/src/components/VoiceCall.tsx` - Handoff UI
- `web/src/app/dashboard/handoffs/page.tsx` - NEW: Agent queue
- Supabase migration for handoffs table

---

### Priority 2: Voice Upgrade (Cartesia/ElevenLabs)

**Impact:** Premium voice quality = premium perception
**Effort:** 1 week

**What It Does:**
Replace Kokoro TTS with Cartesia Sonic or ElevenLabs for more natural, expressive voices.

**Implementation Steps:**

1. **Add Cartesia Integration**
```python
# modal_deployment/cartesia_tts.py

import modal
import httpx

app = modal.App("cartesia-tts")

@app.function(secrets=[modal.Secret.from_name("cartesia-api-key")])
async def synthesize_cartesia(
    text: str,
    voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091",  # Sonic default
    model: str = "sonic-english",
    output_format: str = "mp3"
) -> bytes:
    """Synthesize speech using Cartesia Sonic."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.cartesia.ai/tts/bytes",
            headers={
                "X-API-Key": os.environ["CARTESIA_API_KEY"],
                "Cartesia-Version": "2024-06-10"
            },
            json={
                "model_id": model,
                "transcript": text,
                "voice": {"mode": "id", "id": voice_id},
                "output_format": {
                    "container": output_format,
                    "sample_rate": 44100
                }
            }
        )
        return response.content
```

2. **Add ElevenLabs Integration**
```python
# modal_deployment/elevenlabs_tts.py

@app.function(secrets=[modal.Secret.from_name("elevenlabs-api-key")])
async def synthesize_elevenlabs(
    text: str,
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel
    model: str = "eleven_turbo_v2"
) -> bytes:
    """Synthesize speech using ElevenLabs."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            json={
                "text": text,
                "model_id": model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
        )
        return response.content
```

3. **Backend TTS Router**
```python
# backend/main.py

async def synthesize_speech(self, text: str, voice_config: dict) -> bytes:
    """Route TTS to appropriate provider."""
    provider = voice_config.get('provider', 'kokoro')

    if provider == 'cartesia':
        return await cartesia_tts.synthesize(text, voice_config['voice_id'])
    elif provider == 'elevenlabs':
        return await elevenlabs_tts.synthesize(text, voice_config['voice_id'])
    else:
        return await kokoro_tts.synthesize(text, voice_config['voice_id'])
```

4. **Voice Selection UI**
- Add provider selector in assistant settings
- Preview voices before selecting
- Show cost per minute for each provider

**Pricing Comparison:**
| Provider | Cost/1000 chars | Quality | Latency |
|----------|-----------------|---------|---------|
| Kokoro (current) | ~$0.0002 | Good | ~200ms |
| Cartesia Sonic | $0.015 | Excellent | ~100ms |
| ElevenLabs Turbo | $0.18 | Premium | ~150ms |

**Files to Modify:**
- `modal_deployment/cartesia_tts.py` - NEW
- `modal_deployment/elevenlabs_tts.py` - NEW
- `backend/main.py` - TTS router
- `web/src/app/dashboard/assistants/page.tsx` - Voice selector
- `.env.example` - Add API keys

---

### Priority 3: Appointment Scheduling

**Impact:** AI books appointments directly - huge value prop
**Effort:** 1 week

**What It Does:**
AI can check availability and book appointments during the call, then send confirmation.

**Implementation Steps:**

1. **Availability Slots Table**
```sql
CREATE TABLE va_availability_slots (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id),
  day_of_week INT NOT NULL, -- 0-6 (Sunday-Saturday)
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  slot_duration_minutes INT DEFAULT 30,
  is_active BOOLEAN DEFAULT true
);

CREATE TABLE va_appointments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES auth.users(id),
  call_id UUID REFERENCES va_calls(id),
  customer_name TEXT NOT NULL,
  customer_phone TEXT,
  customer_email TEXT,
  scheduled_date DATE NOT NULL,
  scheduled_time TIME NOT NULL,
  duration_minutes INT DEFAULT 30,
  service_type TEXT,
  notes TEXT,
  status TEXT DEFAULT 'confirmed', -- confirmed, cancelled, completed, no_show
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

2. **Backend Scheduling Functions**
```python
# backend/main.py

@app.get("/scheduling/availability/{date}")
async def get_availability(
    date: str,  # YYYY-MM-DD
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db)
):
    """Get available time slots for a specific date."""
    # Get user's availability rules
    # Check existing appointments
    # Return open slots
    pass

@app.post("/scheduling/book")
async def book_appointment(
    appointment: AppointmentRequest,
    user_id: str = Header(..., alias="X-User-ID"),
    db: SupabaseManager = Depends(get_db)
):
    """Book an appointment slot."""
    # Validate slot is available
    # Create appointment record
    # Send confirmation (SMS/email)
    pass
```

3. **AI Scheduling Prompt Addition**
```python
SCHEDULING_PROMPT = """
When the caller wants to schedule an appointment:
1. Ask what service they need
2. Ask for their preferred date (offer next 7 days)
3. Check availability using the check_availability function
4. Confirm the booking
5. Get their name and phone for confirmation

Available functions:
- check_availability(date) - returns open time slots
- book_appointment(date, time, name, phone, service) - books the slot
"""
```

4. **Confirmation System**
- Send SMS confirmation via Twilio
- Send email confirmation via Resend/SendGrid
- Add to user's calendar (Google Calendar API)

**Files to Modify:**
- Supabase migration for scheduling tables
- `backend/main.py` - Scheduling endpoints
- `web/src/app/dashboard/scheduling/page.tsx` - NEW: Calendar view
- `backend/twilio_integration.py` - SMS confirmations

---

### Priority 4: Multi-Language Support

**Impact:** Expand to non-English markets
**Effort:** 1 week

**What It Does:**
Whisper already supports 22 languages - expose this capability with proper TTS matching.

**Implementation Steps:**

1. **Language Detection**
```python
# Whisper already returns detected language
stt_result = voice_assistant.transcribe_audio(audio_bytes, user_id)
detected_language = stt_result.get('language', 'en')
```

2. **Language-Matched TTS**
```python
LANGUAGE_VOICE_MAP = {
    'en': {'kokoro': 'af_bella', 'elevenlabs': '21m00Tcm4TlvDq8ikWAM'},
    'es': {'kokoro': 'es_male', 'elevenlabs': 'pNInz6obpgDQGcFmaJgB'},
    'fr': {'kokoro': 'fr_female', 'elevenlabs': 'ThT5KcBeYPX3keUQqHPh'},
    'de': {'kokoro': 'de_female', 'elevenlabs': '...'},
    # ... more languages
}
```

3. **Assistant Language Settings**
- Default language
- Auto-detect option
- Language-specific system prompts

**Files to Modify:**
- `backend/main.py` - Language routing
- `config/settings.py` - Language voice mapping
- `web/src/app/dashboard/assistants/page.tsx` - Language selector

---

### Priority 5: Continuous Learning Feedback

**Impact:** Calls improve over time based on feedback
**Effort:** 2 weeks

**What It Does:**
Users can thumbs up/down calls, AI learns from feedback patterns.

**Implementation Steps:**

1. **Feedback Table**
```sql
CREATE TABLE va_call_feedback (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  call_id UUID REFERENCES va_calls(id),
  user_id UUID REFERENCES auth.users(id),
  rating INT CHECK (rating >= 1 AND rating <= 5),
  thumbs_up BOOLEAN,
  feedback_text TEXT,
  improvement_areas TEXT[], -- ['accuracy', 'tone', 'speed', 'relevance']
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

2. **Feedback API**
```python
@app.post("/calls/{call_id}/feedback")
async def submit_feedback(
    call_id: str,
    feedback: FeedbackRequest,
    user_id: str = Header(..., alias="X-User-ID")
):
    """Submit feedback for a call."""
    pass

@app.get("/feedback/insights")
async def get_feedback_insights(
    user_id: str = Header(..., alias="X-User-ID"),
    days: int = 30
):
    """Get aggregated feedback insights."""
    # What's working well
    # Areas for improvement
    # Trends over time
    pass
```

3. **Feedback UI**
- Post-call rating modal
- Quick thumbs up/down
- Optional detailed feedback
- Insights dashboard

**Files to Modify:**
- Supabase migration for feedback table
- `backend/main.py` - Feedback endpoints
- `web/src/components/VoiceCall.tsx` - Post-call feedback
- `web/src/app/dashboard/feedback/page.tsx` - NEW: Insights

---

## Long-Term Features (1+ month)

### Pipecat Integration (2 weeks)

**What:** Replace custom voice pipeline with Pipecat framework
**Why:** Simplify backend, easier to swap components, better maintained
**Reference:** https://github.com/pipecat-ai/pipecat

### Speech-to-Speech Integration (6-8 weeks)

**What:** Direct audio-to-audio without intermediate text
**Why:** Lower latency, more natural responses
**Wait For:** Costs to drop (currently ~$20/hour via OpenAI)

### Full CRM Integration Suite (1 month)

**What:** Deep integrations with Salesforce, HubSpot, Pipedrive
**Why:** Enterprise customers expect CRM sync
**Includes:** Auto-create leads, update records, log activities

### White-Label Platform (2 months)

**What:** Let other businesses resell HIVE215
**Why:** Massive revenue potential, network effects
**Includes:** Custom branding, API access, revenue sharing

### Outbound Calling Campaigns (1 month)

**What:** AI makes outbound calls for reminders, follow-ups, surveys
**Why:** Proactive engagement, higher conversion rates
**Includes:** Campaign builder, scheduling, compliance tools

---

## Implementation Order

### Week 1-2: Human Handoff + Appointment Scheduling
These are the highest-value features for small businesses.

### Week 3-4: Voice Upgrade + Multi-Language
Improved quality and expanded market reach.

### Week 5-6: Continuous Learning Feedback
Start building the data flywheel for improvement.

### Month 2+: Long-term features based on customer demand

---

## Quick Start for Next Session

```bash
# 1. Check current state
git status
git log --oneline -5

# 2. Create feature branch
git checkout -b feature/human-handoff

# 3. Start with database migration
# Create supabase/migrations/YYYYMMDD_add_handoffs.sql

# 4. Implement backend changes
# Edit backend/main.py

# 5. Implement frontend changes
# Edit web/src/components/VoiceCall.tsx
# Create web/src/app/dashboard/handoffs/page.tsx

# 6. Test locally
npm run dev  # Frontend
python -m backend.main  # Backend

# 7. Deploy
git add -A && git commit -m "Add human handoff system"
git push -u origin feature/human-handoff
```

---

## Environment Variables Needed

```bash
# For Voice Upgrade
CARTESIA_API_KEY=your-cartesia-key
ELEVENLABS_API_KEY=your-elevenlabs-key

# For Appointment Scheduling
GOOGLE_CALENDAR_API_KEY=your-google-key  # Optional
RESEND_API_KEY=your-resend-key  # For email confirmations

# Already configured
ANTHROPIC_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
```

---

## Success Metrics

After implementing medium features:
- Human handoff: <30 second transfer time
- Voice quality: User satisfaction >90%
- Appointment booking: 50%+ conversion on scheduling requests
- Multi-language: Support top 5 languages
- Feedback: >20% of calls receive feedback

---

**Status:** Ready to implement
**Priority:** Human Handoff > Appointment Scheduling > Voice Upgrade
**Estimated Total:** 6-8 weeks for all medium features

Good luck! You've got an excellent foundation - now make it exceptional.
