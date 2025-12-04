# HIVE215 - AI Phone Assistant Platform

> **Mission**: A Vapi alternative that's 95% cheaper and easier to use. Answer calls, take orders, collect job info - all controlled from any device.

---

## Table of Contents
- [Vision](#vision)
- [How We're 95% Cheaper](#how-were-95-cheaper)
- [Platform Architecture](#platform-architecture)
- [User Tiers & Pricing](#user-tiers--pricing)
- [Core Features](#core-features)
- [Dashboard Types](#dashboard-types)
- [Database Schema Philosophy](#database-schema-philosophy)
- [Use Cases](#use-cases)
- [Referral System](#referral-system)
- [Viral Growth Features](#viral-growth-features)
- [Technical Stack](#technical-stack)
- [Roadmap](#roadmap)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)

---

## Vision

### Fire Your Robot Receptionist

**97% of callers hate "Press 1 for Sales"** - HIVE215 replaces frustrating IVR phone trees with AI that actually understands.

HIVE215 is an AI-powered phone answering service that:
- Answers business and personal calls using Claude AI
- **No more "Press 1, Press 2"** - Natural conversation from the start
- Reads user's profession/skills from their profile
- Logs all pertinent call information with quality scoring
- Works identically on iPhone, Android, and Web
- Costs 95% less than competitors like Vapi

**The Problem We Solve**:
- 67% of callers hang up on IVR systems
- $5.6B wasted yearly on outdated phone technology
- 97% of Americans frustrated with phone menus

**Target Users**:
- Small business owners (electricians, plumbers, caterers, etc.)
- Freelancers and contractors
- Teams needing shared phone lines
- Anyone who misses important calls

---

## How We're 95% Cheaper

### Claude Prompt Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    5-MINUTE CACHE WINDOW                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Call 1 (0:00)  ──► FULL COST (loads skill + user profile)  │
│  Call 2 (1:30)  ──► 95% OFF (cache hit)                     │
│  Call 3 (3:00)  ──► 95% OFF (cache hit)                     │
│  Call 4 (4:30)  ──► 95% OFF (cache hit)                     │
│  Call 5 (6:00)  ──► FULL COST (cache expired, reload)       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**The Math**:
- Vapi: ~$0.05-0.10 per minute
- HIVE215 with caching: ~$0.005 per minute (after first call in window)
- **More users = More cache hits = Lower costs for everyone**

### Shared Skill Architecture

Every user gets the SAME Claude skill (expert phone answerer). The only variable is the user's profile text file. This means:
- One optimized system prompt cached across ALL users
- User-specific data is minimal (just their profile)
- Massive economies of scale

---

## Platform Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         HIVE215 PLATFORM                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │   iPhone    │  │   Android   │  │     Web     │               │
│  │     App     │  │     App     │  │   Browser   │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         │                │                │                       │
│         └────────────────┼────────────────┘                       │
│                          │                                        │
│                          ▼                                        │
│              ┌───────────────────────┐                            │
│              │      API Gateway      │                            │
│              └───────────┬───────────┘                            │
│                          │                                        │
│         ┌────────────────┼────────────────┐                       │
│         │                │                │                       │
│         ▼                ▼                ▼                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │   Twilio    │  │   Claude    │  │  Supabase   │               │
│  │  (Phones)   │  │    (AI)     │  │    (DB)     │               │
│  └─────────────┘  └─────────────┘  └─────────────┘               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### All Platforms, All Features

| Feature | iPhone | Android | Web |
|---------|--------|---------|-----|
| Answer calls | ✅ | ✅ | ✅ |
| View call logs | ✅ | ✅ | ✅ |
| Edit profile/skills | ✅ | ✅ | ✅ |
| Share logs (text/email) | ✅ | ✅ | ✅ |
| Team management | ✅ | ✅ | ✅ |
| Webhook integrations | ✅ | ✅ | ✅ |
| Real-time notifications | ✅ | ✅ | ✅ |

---

## User Tiers & Pricing

### Transparent Pricing Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        SUBSCRIPTION TIERS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FREE TIER ($0/mo)                                               │
│  ├── 30 minutes/month                                            │
│  ├── 1 profile field (60 chars)                                  │
│  ├── Basic call logs                                             │
│  └── Web access only                                             │
│                                                                  │
│  STARTER ($9.99/mo)                                              │
│  ├── 200 minutes/month                                           │
│  ├── 2 profile fields (60 chars each)                            │
│  ├── Full call logs + sharing                                    │
│  ├── All platforms (iOS, Android, Web)                           │
│  └── Email/text sharing                                          │
│                                                                  │
│  PROFESSIONAL ($29.99/mo)                                        │
│  ├── 1000 minutes/month                                          │
│  ├── 5 profile fields (120 chars each)                           │
│  ├── Team features (3 members)                                   │
│  ├── Webhook integrations                                        │
│  ├── Priority AI responses                                       │
│  └── Custom greeting                                             │
│                                                                  │
│  BUSINESS ($79.99/mo)                                            │
│  ├── 5000 minutes/month                                          │
│  ├── 10 profile fields (unlimited chars)                         │
│  ├── Team features (10 members)                                  │
│  ├── Multiple phone lines                                        │
│  ├── Advanced analytics                                          │
│  ├── CRM integrations                                            │
│  └── Dedicated phone number                                      │
│                                                                  │
│  ENTERPRISE (Custom pricing)                                     │
│  ├── Unlimited minutes                                           │
│  ├── Unlimited profile fields                                    │
│  ├── Unlimited team members                                      │
│  ├── White-label option                                          │
│  ├── Custom integrations                                         │
│  ├── SLA guarantee                                               │
│  └── Dedicated support                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Profile Fields by Tier

| Tier | Fields | Chars/Field | Example Use |
|------|--------|-------------|-------------|
| Free | 1 | 60 | "Licensed electrician, residential" |
| Starter | 2 | 60 | Business type + Service area |
| Professional | 5 | 120 | Full business description |
| Business | 10 | Unlimited | Detailed services, pricing, FAQ |
| Enterprise | Unlimited | Unlimited | Complete business knowledge base |

---

## Core Features

### 1. AI Phone Answering

The Claude skill is trained to:
- Answer calls professionally
- Read and understand user's profile/trade info
- Collect relevant information based on context
- Handle objections and questions
- Schedule callbacks or appointments
- Transfer to team members when needed

### 2. Streaming Voice Pipeline (NEW!)

**Sub-500ms Latency Architecture**
- Full WebSocket streaming pipeline for real-time voice
- Deepgram Nova-3: Streaming STT with <300ms latency
- Anthropic Claude: Token streaming for fast first response
- Cartesia Sonic-3: 40ms time-to-first-byte TTS
- Automatic fallback to batch processing (Modal) when not configured

**Voice Activity Detection**
- Smart utterance end detection (no more cutting off "I...")
- Barge-in support (stop TTS when user interrupts)
- Configurable silence detection (UTTERANCE_END_MS=1200)

### 3. Real-Time Intelligence

**Live Sentiment Display**
- See caller mood in real-time (positive/neutral/negative)
- Emoji indicators with sentiment score (-100 to +100)
- Trend tracking (improving/stable/declining)
- Urgency detection (urgent/elevated/normal)

**Real-Time Latency Monitoring**
- Live response time display during calls
- Component breakdown (STT/LLM/TTS)
- Visual progress bar with status indicators
- Target: <500ms with streaming, <2000ms with batch

**Call Quality Scoring**
Every call gets an automatic quality score (0-100 with A-F grade):
- Sentiment (0-30 pts) - Caller satisfaction
- Flow (0-25 pts) - Conversation balance
- Duration (0-20 pts) - Optimal call length
- Resolution (0-15 pts) - Successful closure indicators
- Urgency Handling (0-10 pts) - Emergency response quality

### 3. Industry Quick Start Templates

Pre-built AI assistant configurations for instant setup:

| Template | Icon | Use Case |
|----------|------|----------|
| Custom | ✨ | Start from scratch |
| Plumber/HVAC | 🔧 | Emergency repairs, scheduling |
| Electrician | ⚡ | Safety-first electrical services |
| Law Office | ⚖️ | Legal intake, confidentiality |
| Medical Office | 🏥 | Appointments, HIPAA-aware |
| Restaurant | 🍽️ | Reservations, takeout orders |
| Real Estate | 🏠 | Property inquiries, showings |
| Auto Repair | 🚗 | Service appointments, diagnostics |
| General Business | 💼 | Professional call handling |

### 4. Call Logs System

Every call generates a structured log:

```json
{
  "call_id": "uuid",
  "timestamp": "2025-01-26T10:30:00Z",
  "duration_seconds": 180,
  "caller": {
    "phone": "+1234567890",
    "name": "John Smith",
    "contact_id": "uuid (if existing)"
  },
  "summary": "Requesting quote for electrical panel upgrade",
  "key_info": {
    "service_requested": "Panel upgrade 100A to 200A",
    "address": "123 Main St, Philadelphia",
    "timeline": "ASAP, within 2 weeks",
    "budget": "Mentioned $2000-3000 range"
  },
  "action_items": [
    "Call back with quote",
    "Schedule site visit"
  ],
  "sentiment": "positive",
  "urgency": "high"
}
```

### 3. Sharing & Export

Share call logs instantly via:
- **SMS**: One-tap text to anyone
- **Email**: Formatted summary with details
- **Webhook**: POST to any URL (Zapier, Make, custom)
- **Copy**: Clipboard for paste anywhere
- **PDF**: Downloadable report

### 4. Phone Lines & Texting

- Get a dedicated business phone number
- Forward existing number to HIVE215
- SMS/text message handling
- Transfer calls to team members
- Voicemail with AI transcription

### 5. Team Features

- Invite team members
- Assign permission levels
- Shared call logs
- Call routing rules
- Activity dashboard

---

## Dashboard Types

### 1. Developer Dashboard (Admin)

For you and your team to manage the platform:

```
┌─────────────────────────────────────────────────────────────┐
│  DEVELOPER DASHBOARD                                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  METRICS                                                     │
│  ├── Total users: 12,450                                     │
│  ├── Active calls right now: 47                              │
│  ├── API costs today: $124.50                                │
│  ├── Cache hit rate: 87%                                     │
│  └── Revenue today: $890.00                                  │
│                                                              │
│  SYSTEM HEALTH                                               │
│  ├── Twilio status: ✅ Operational                           │
│  ├── Claude API: ✅ Operational                              │
│  ├── Database: ✅ Operational                                │
│  └── Average latency: 230ms                                  │
│                                                              │
│  TOOLS                                                       │
│  ├── User management                                         │
│  ├── Subscription management                                 │
│  ├── System logs                                             │
│  ├── Feature flags                                           │
│  ├── A/B testing                                             │
│  └── Deployment controls                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2. Business Owner Dashboard

For business owners managing their account:

```
┌─────────────────────────────────────────────────────────────┐
│  BUSINESS DASHBOARD                          [Acme Electric] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  THIS MONTH                                                  │
│  ├── Calls answered: 156                                     │
│  ├── Minutes used: 487 / 1000                                │
│  ├── Leads captured: 42                                      │
│  └── Estimated value: $12,400                                │
│                                                              │
│  RECENT CALLS                           [View All] [Export]  │
│  ├── John Smith - Panel upgrade quote - 3 min ago           │
│  ├── Sarah Jones - Emergency outlet - 1 hour ago            │
│  └── Mike Brown - Lighting install - 2 hours ago            │
│                                                              │
│  QUICK ACTIONS                                               │
│  ├── [Edit Profile/Skills]                                   │
│  ├── [Manage Team]                                           │
│  ├── [Phone Settings]                                        │
│  └── [Integrations]                                          │
│                                                              │
│  TEAM (3 members)                                            │
│  ├── You (Owner) - All permissions                           │
│  ├── Tom (Tech) - View calls, receive transfers              │
│  └── Lisa (Office) - View calls, manage schedule             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3. Employee/Civilian Dashboard

For individual users or team members:

```
┌─────────────────────────────────────────────────────────────┐
│  MY DASHBOARD                                    [Tom Tech]  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  MY CALLS TODAY                                              │
│  ├── 3 calls transferred to me                               │
│  ├── 2 callbacks needed                                      │
│  └── 1 urgent flagged                                        │
│                                                              │
│  ASSIGNED TASKS                                              │
│  ├── ⚡ Call back John Smith (panel quote)                   │
│  ├── 📞 Schedule site visit - Sarah Jones                    │
│  └── ✅ Mike Brown - completed                               │
│                                                              │
│  MY SETTINGS                                                 │
│  ├── Availability: 9am - 5pm                                 │
│  ├── Transfer calls: ✅ Enabled                              │
│  └── Notifications: Push + Email                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema Philosophy

### Core Principle: Generic & Flexible

**"A contact is a contact"** - No industry-specific tables. Everything is generic with permission toggles.

```sql
-- CONTACTS (universal)
contacts (
  id, user_id, phone, email, name,
  permission_level, -- 'blocked', 'normal', 'vip', 'team'
  tags[], -- flexible categorization
  metadata JSONB, -- any extra data
  created_at, updated_at
)

-- CALLS (universal)
calls (
  id, user_id, contact_id,
  direction, -- 'inbound', 'outbound'
  duration_seconds,
  transcript TEXT,
  summary TEXT,
  key_info JSONB, -- flexible structured data
  action_items JSONB,
  sentiment, urgency,
  created_at
)

-- USERS (universal)
users (
  id, email, phone,
  tier, -- 'free', 'starter', 'professional', 'business', 'enterprise'
  profile_fields JSONB, -- their trade/skill info
  settings JSONB,
  team_id, -- null if individual
  role, -- 'owner', 'admin', 'member'
  created_at
)

-- TEAMS (for business accounts)
teams (
  id, name, owner_id,
  settings JSONB,
  created_at
)
```

### Why This Works

1. **Never needs reconfiguration** - JSONB fields handle any data type
2. **Permission levels cascade** - Owner > Admin > Member
3. **Tags for flexibility** - "lead", "customer", "vendor", etc.
4. **Same schema for all industries** - Electrician, caterer, lawyer - same tables

---

## Use Cases

### Electrician Example

**Profile Fields**:
```
Field 1: "Licensed master electrician, 20 years experience"
Field 2: "Residential & commercial, Philadelphia metro area"
Field 3: "Services: panel upgrades, rewiring, EV chargers, generators"
Field 4: "Emergency service available 24/7, $150 service call"
Field 5: "Free estimates for jobs over $500"
```

**AI Behavior**:
- Answers: "Thank you for calling Acme Electric, this is our AI assistant..."
- Collects: Address, service needed, timeline, access info
- Logs: Full job details ready for quote
- Shares: One-tap text to electrician with all info

### Caterer Example

**Profile Fields**:
```
Field 1: "Full-service catering for events 20-500 guests"
Field 2: "Cuisines: American, Italian, Mexican, BBQ"
Field 3: "Services: delivery, setup, full-service with staff"
Field 4: "Pricing: $25-75 per person depending on menu"
Field 5: "Book 2+ weeks in advance, rush orders +25%"
```

**AI Behavior**:
- Answers: "Thank you for calling Delicious Catering..."
- Collects: Event date, guest count, cuisine preference, dietary restrictions, budget
- Logs: Complete order details
- Shares: Email to catering team with full event specs

### Personal Use Example

**Profile Fields**:
```
Field 1: "Screen my calls, I'm usually busy with work"
```

**AI Behavior**:
- Answers: "Hi, you've reached [Name]'s assistant..."
- Screens: Asks who's calling and purpose
- Logs: Caller info and message
- Notifies: Push notification with summary

---

## Referral System

### Earn More Minutes

```
┌─────────────────────────────────────────────────────────────┐
│                     REFERRAL REWARDS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  YOUR REFERRAL CODE: HIVE-ABC123                             │
│                                                              │
│  REWARDS                                                     │
│  ├── Each signup: +50 minutes (you) + 50 minutes (them)      │
│  ├── Each paid conversion: +200 minutes                      │
│  ├── 5 referrals: Bronze badge + 10% bonus minutes           │
│  ├── 10 referrals: Silver badge + 20% bonus minutes          │
│  └── 25 referrals: Gold badge + 1 month free                 │
│                                                              │
│  YOUR STATS                                                  │
│  ├── Referrals sent: 12                                      │
│  ├── Signups: 8                                              │
│  ├── Paid conversions: 3                                     │
│  └── Minutes earned: 1,150                                   │
│                                                              │
│  [Share via Text] [Share via Email] [Copy Link]              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Why Referrals = Lower Costs

More users = Higher cache hit rates = Lower per-call costs = We pass savings to users

---

## Viral Growth Features

### Future Roadmap for Viral Growth

Based on market research, these features drive viral adoption:

#### 1. AI Companion Mode
- Give your assistant a personality & name
- Daily check-ins via push notification
- Remembers your preferences and context

#### 2. Voice Journaling + Sentiment Analysis
- Speak your thoughts, AI transcribes & analyzes
- Mood tracking over time
- Mental health insights

#### 3. Gamification System
- Streak counter for daily usage
- XP & levels for conversations
- Unlock new voices/personalities
- Achievements & badges

#### 4. Social Sharing
- Share AI call summaries as clips
- Create voice memos to share
- TikTok-style short voice content

#### 5. Transparent Usage Dashboard
- Real-time cost tracking
- "You saved $X vs competitors"
- Cache hit visualization

---

## Market Research

### Competitor Analysis

| Feature | Vapi | HIVE215 |
|---------|------|---------|
| Price per minute | $0.05-0.10 | $0.005 (with caching) |
| Setup complexity | High | Low |
| Mobile apps | Limited | Full iOS/Android/Web |
| Team features | Enterprise only | All paid tiers |
| Customization | Complex API | Simple UI |

### Market Opportunity
- Global voice AI market: $3.14B (2024) → $47.5B (2034)
- 34.8% CAGR
- 22% of recent YC batch = voice AI companies
- ElevenLabs: $90M → $200M ARR in 10 months

### Top Revenue Generators

| App | Downloads | Revenue | Model |
|-----|-----------|---------|-------|
| ChatGPT | 917M | $1.1B | Freemium + $20/mo |
| Ask AI | 57M | $78M | Subscriptions |
| Nova | 89M | $44M | Voice GPT |
| Parrot (Voice Clone) | 4.2M | $5M | Per-voice pricing |
| ElevenLabs | - | $200M ARR | Tiered credits |

### Why Character AI / Replika Are ADDICTIVE (Apply These)

1. **Proactive Notifications** - AI reaches out first ("I've been thinking about you")
2. **Empathy & Validation** - Never disagrees, always supportive
3. **Gamification** - XP, coins, achievements, unlockable content
4. **Memory & Personalization** - Remembers past conversations
5. **Voice + Video Calls** - More intimate than text
6. **Interactive Activities** - Games, stories, tarot, journaling

### Sources
- [a16z: AI Voice Agents 2025](https://a16z.com/ai-voice-agents-2025-update/)
- [NFX: Voice AI is Working](https://www.nfx.com/post/voice-ai-is-working)
- [ElevenLabs Revenue](https://sacra.com/c/elevenlabs/)
- [Top AI Apps 2025](https://www.blog.udonis.co/mobile-marketing/mobile-apps/top-ai-apps)
- [TechPolicy: AI Chatbot Addiction](https://www.techpolicy.press/ai-chatbots-and-addiction-what-does-the-research-say/)
- [AWS: Voice AI Startups](https://aws.amazon.com/startups/learn/ai-has-found-its-voice-and-startups-are-listening)

---

## Technical Stack

### ⚡ Lightning Stack (NEW - Sub-150ms Latency)

The ultimate voice AI pipeline for real-time conversations:

| Component | Provider | Latency | Notes |
|-----------|----------|---------|-------|
| **STT** | Deepgram Nova-3 | ~30ms | 36+ languages, code-switching |
| **LLM** | Groq Llama 3.3 70B | ~40ms TTFT | 800 tok/s, Claude fallback |
| **TTS** | Cartesia Sonic-3 | ~30ms TTFB | 42 languages, voice cloning |

**Total perceived latency: ~150ms** (human threshold is 500ms)

```
Audio In → Deepgram → Groq → Cartesia → Audio Out
              ↓          ↓        ↓
           ~30ms      ~40ms    ~30ms
                         ↓
              Sentence-level streaming
              (TTS starts on first sentence!)
```

### Full Stack
- **Frontend**: Next.js 14, React Native (Expo)
- **Backend**: FastAPI (Python)
- **Database**: Supabase (PostgreSQL)
- **Auth**: Supabase Auth
- **AI/LLM**: Groq (primary), Anthropic Claude (fallback)
- **Streaming STT**: Deepgram Nova-3 (~30ms chunks)
- **Streaming TTS**: Cartesia Sonic-3 (30ms TTFB, 42 languages)
- **Voice Cloning**: Cartesia (3-10s samples, cross-lingual)
- **Batch Voice**: Modal (Kokoro TTS, Whisper STT) - fallback
- **Phone**: Twilio
- **Payments**: Stripe
- **Hosting**: Vercel (web), Modal (AI), Railway (backend)

### Planned Integrations
- Twilio (phone lines, SMS)
- Zapier/Make (webhooks)
- Google Calendar (scheduling)
- Various CRMs (Salesforce, HubSpot, etc.)

---

## Roadmap

### Phase 1: MVP (Current)
- [x] Web dashboard
- [x] User authentication
- [x] Subscription tiers
- [x] Basic call logs
- [x] Claude AI integration
- [x] Claude AI startup modal
- [ ] Twilio phone integration
- [ ] SMS handling

### Phase 2: Mobile Apps
- [x] iOS app foundation (React Native)
- [x] Android app foundation (React Native)
- [ ] Push notifications
- [ ] Mobile call handling

### Phase 3: Team Features
- [ ] Team creation/management
- [ ] Role-based permissions
- [ ] Shared call logs
- [ ] Call transfer between team

### Phase 4: Integrations
- [ ] Webhook system
- [ ] Zapier integration
- [ ] Calendar sync
- [ ] CRM integrations

### Phase 5: Viral Features
- [ ] Referral system
- [ ] Gamification
- [ ] Social sharing
- [ ] Voice journaling

---

## Quick Start

### For Developers
```bash
# Clone the repo
git clone https://github.com/jenkintownelectricity/premier_voice_assistant.git

# Install dependencies
cd premier_voice_assistant/web && npm install
cd ../backend && pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run development servers
npm run dev  # Frontend (http://localhost:3000)
python -m backend.main  # Backend (http://localhost:8000)
```

### Environment Variables

**Vercel (frontend):**
```
NEXT_PUBLIC_API_URL=https://web-production-1b085.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://[project-id].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
NEXT_PUBLIC_STRIPE_KEY=your-stripe-publishable-key
```

**Railway (backend):**
```
SUPABASE_URL=https://[project-id].supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
ADMIN_API_KEY=your-admin-key

# Lightning Stack (Sub-150ms Voice AI)
GROQ_API_KEY=your-groq-key          # Free at console.groq.com
DEEPGRAM_API_KEY=your-deepgram-key  # $200 free at console.deepgram.com
CARTESIA_API_KEY=your-cartesia-key  # Trial at play.cartesia.ai
ANTHROPIC_API_KEY=your-claude-key   # Fallback LLM
```

### Live URLs
- **Frontend:** https://hive215.vercel.app/
- **Backend:** https://web-production-1b085.up.railway.app/

---

## API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/subscription` | GET | User's current plan |
| `/usage` | GET | Current usage stats |
| `/feature-limits` | GET | All feature limits |
| `/chat` | POST | AI conversation (STT → LLM → TTS) |
| `/transcribe` | POST | Audio → Text |
| `/speak` | POST | Text → Audio |

### Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/upgrade-user` | POST | Upgrade user plan |
| `/admin/add-minutes` | POST | Add bonus minutes |
| `/admin/codes` | POST | Create discount code |
| `/admin/reset-usage` | POST | Reset user usage |

### Webhook Events
- `call.started` - New call received
- `call.completed` - Call ended
- `call.transcribed` - Transcript ready
- `user.upgraded` - Plan upgraded
- `minutes.low` - Usage warning

---

## Project Structure

```
premier_voice_assistant/
├── web/                    # Next.js frontend (Vercel)
│   ├── src/app/           # Pages
│   ├── src/components/    # React components
│   └── src/lib/           # API client, utilities
├── mobile/                 # React Native app (Expo)
├── backend/               # FastAPI backend (Railway)
│   ├── main.py           # API routes
│   ├── supabase_client.py
│   └── feature_gates.py
├── modal_deployment/      # GPU functions (Modal)
│   ├── whisper_stt.py    # Speech-to-text
│   └── kokoro_tts.py     # Text-to-speech
├── supabase/             # Database migrations
└── sdks/                 # iOS & Android SDKs
```

---

## Contact

- **Website**: [hive215.com](https://hive215.vercel.app)
- **Support**: support@hive215.com

---

## Development History & Session Log

### Session: November 28, 2025 - Model Not Found Fix

**Issue**: 404 error when calling Anthropic API
```
Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-5-sonnet-20241022'}}
```

**Root Cause**: The model `claude-3-5-sonnet-20241022` was deprecated and no longer available via the Anthropic API.

**Fix**: Updated all model references from `claude-3-5-sonnet-20241022` to `claude-3-5-sonnet-latest` in:
- `main.py` - Backend API defaults and pricing (6 locations)
- `config/settings.py` - Configuration constant
- `web/src/app/dashboard/assistants/page.tsx` - Web frontend
- `mobile/src/screens/AssistantsScreen.tsx` - Mobile app
- `web/src/app/dashboard/admin/tests/page.tsx` - Admin tests

**Branch**: `claude/fix-model-not-found-01LSFGUqsoTPz1LbmUYz936U`

---

### Session: November 2025 - Major Bug Fixes (Previous Context)

This session addressed multiple issues to get the platform "working 100 percent".

#### 1. Build Errors Fixed
- **Card component** - Added missing `onClick` prop to `web/src/components/Card.tsx`
- **ESLint errors** - Fixed unescaped apostrophes in multiple files
- **Added** `.eslintrc.json` for Next.js configuration

#### 2. Voice Call Echo/Repetition Issue
**Problem**: Agent kept repeating itself during voice calls due to acoustic echo (assistant hearing itself through microphone).

**Fixes in `web/src/components/VoiceCall.tsx`**:
```typescript
// Added audio constraints
echoCancellation: true,
noiseSuppression: true,
autoGainControl: true

// Added speaking state tracking
isSpeakingRef to track when assistant is speaking
Skip sending audio while assistant is speaking
Duplicate transcript detection
```

**Fixes in `backend/main.py`**:
```python
# VoiceCallSession deduplication
self.last_user_text = ""
self.last_response_time = 0
self.min_response_interval = 2.0

# Echo detection (80% word similarity check)
# Rate limiting between responses
```

#### 3. AI Assistant [object Object] Error
**Problem**: Chat showing `[object Object]` in StartupModal.

**Root Cause**: Backend `/chat` endpoint expected audio file, not JSON text.

**Fix**:
- Added new `/chat/text` endpoint for text-based Claude chat
- Updated frontend API to use `/chat/text`

#### 4. Stripe Module Missing
**Problem**: `No module named 'stripe'` error.

**Fix**: Added `stripe>=8.0.0` to `requirements.txt`

#### 5. Dashboard Fixes
- **Teams page** - Fixed error handling to properly extract error message
- **Phone page** - Added error state and display
- **Calls page** - Added error handling, ensured transcript is always an array

---

### Service Connections Status

| Service | Status | Purpose |
|---------|--------|---------|
| Supabase | ✅ Connected | Database & Auth |
| Anthropic | ✅ Connected | Claude AI (claude-sonnet-4-5-20250929) |
| Deepgram | ✅ Connected | Streaming STT (<300ms latency) |
| Cartesia | ✅ Connected | Streaming TTS (40ms TTFB) |
| Modal | ✅ Connected | Batch Voice Fallback (Whisper STT, Kokoro TTS) |
| Stripe | ✅ Connected | Payments |
| Twilio | ✅ Connected | Phone/SMS |
| Vercel | ✅ Hosting | Frontend deployment |
| Railway | ✅ Hosting | Backend API |

---

### Key Files Reference

| File | Purpose |
|------|---------|
| `main.py` | Root FastAPI backend with voice processing |
| `backend/main.py` | Additional backend routes |
| `config/settings.py` | Configuration constants |
| `web/src/components/VoiceCall.tsx` | WebSocket voice streaming component |
| `web/src/app/dashboard/assistants/page.tsx` | Assistant management UI |
| `mobile/src/screens/AssistantsScreen.tsx` | Mobile assistant management |

---

## Contact

- **Website**: [hive215.com](https://hive215.vercel.app)
- **Support**: support@hive215.com

---

## Development History & Session Logs

### Session: November 28, 2025 - Voice Assistant Easy Wins

**Objective**: Implement all "Easy Win" features from market research analysis.

#### Features Implemented

**1. Real-Time Sentiment Display**
- Live sentiment indicator during calls (positive/neutral/negative with emoji)
- Sentiment score bar (-100 to +100) with visual indicator
- Trend tracking (improving/stable/declining arrows)
- Urgency detection (urgent/elevated/normal) with pulsing alerts

**2. Real-Time Latency Monitoring**
- Live latency display during calls with component breakdown
- STT (Speech-to-Text), LLM (AI), TTS (Text-to-Speech) breakdown
- Visual progress bar with color coding (green/yellow/red)
- Status indicators (good ✓ / warning / slow ⚠)

**3. Industry Quick Start Templates (9 templates)**
- Custom, Plumber/HVAC, Electrician, Law Office
- Medical Office, Restaurant, Real Estate, Auto Repair, General Business
- Each includes pre-built system prompt and first message
- One-click template application with customization

**4. Call Quality Score System**
- Automatic scoring (0-100) with A-F letter grades
- 5-factor breakdown: Sentiment, Flow, Duration, Resolution, Urgency Handling
- Beautiful post-call summary modal
- Stored in database for historical tracking

**5. IVR Killer Marketing Positioning**
- New hero section: "Fire Your Robot Receptionist"
- Problem statistics section (67% hang up, $5.6B wasted, 97% frustrated)
- Old Way vs HIVE215 Way comparison section
- Updated features grid highlighting new capabilities

#### Technical Changes

**Backend (`backend/main.py`)**:
- `VoiceCallSession` class updated with sentiment tracking
- Added `analyze_sentiment_realtime()` method with word lists
- Added `calculate_quality_score()` method with 5-factor scoring
- WebSocket now sends `sentiment`, `latency`, and `quality_score` messages
- Call end includes duration calculation and quality data persistence

**Frontend (`VoiceCall.tsx`)**:
- Added `SentimentData`, `LatencyData`, `QualityScoreData` interfaces
- Real-time sentiment display with emoji indicators
- Latency monitoring panel with breakdown
- Post-call quality summary modal with score visualization

**Assistants Page (`assistants/page.tsx`)**:
- Added `ASSISTANT_TEMPLATES` array with 9 industry templates
- Template selector grid in create form
- Auto-population of name, description, system prompt, first message

**Landing Page (`page.tsx`)**:
- IVR Killer hero section with statistics badge
- Problem Statement section with key metrics
- Old vs New comparison cards
- Updated features grid with new capabilities

**Branch**: `claude/voice-assistant-research-012oUMT9hkQfzrsHQ9PyxwWZ`

---

### Session: November 28, 2025 - Streaming Voice Pipeline Integration

**Objective**: Implement sub-500ms voice latency using streaming STT/TTS providers.

#### Problem
- Original batch processing: ~6800ms latency (Record → STT → LLM → TTS → Play)
- Aggressive endpointing causing false triggers on "I..."
- Serial processing mathematically incapable of sub-second latency

#### Solution: Full Streaming Pipeline

**Architecture**:
```
Audio In → Deepgram (streaming) → Claude (streaming) → Cartesia (streaming) → Audio Out
             ~200ms                 ~200ms               ~100ms
                                                    Total: ~500ms
```

#### Features Implemented

**1. Backend Streaming Infrastructure (`backend/streaming_manager.py`)**
- `DeepgramStreamer`: WebSocket STT with VAD, utterance end detection
- `CartesiaStreamer`: WebSocket TTS with 40ms TTFB
- `AnthropicStreamer`: Token streaming for fast first response
- `StreamingPipeline`: Full orchestrator with barge-in support

**2. WebSocket Handler Integration (`backend/main.py`)**
- Auto-detects streaming availability (Deepgram + Cartesia keys)
- Routes audio to streaming pipeline when configured
- Falls back to batch processing (Modal) when not configured
- Streaming callbacks for transcript, audio, state, latency

**3. Developer Dashboard (`web/src/app/dashboard/developer/page.tsx`)**
- New "Streaming Voice Pipeline" section
- Real-time connection status for Deepgram and Cartesia
- Target latency display (500ms streaming vs 2000ms batch)
- Setup instructions when not configured

**4. Backend Status Endpoint (`/admin/status`)**
- Deepgram connection status
- Cartesia connection status
- Streaming pipeline status with provider info

#### Environment Variables Added
```bash
DEEPGRAM_API_KEY=your_deepgram_api_key
CARTESIA_API_KEY=your_cartesia_api_key
CARTESIA_VOICE_ID=a0e99841-438c-4a64-b679-ae501e7d6091
UTTERANCE_END_MS=1200
ENABLE_BARGE_IN=true
```

#### Technical Improvements
- Automatic model versioning with fallback chains (model_manager.py)
- Feature gate fix for unlimited plans (-1 handling)
- Better LLM error logging for debugging

**Branch**: `claude/voice-assistant-research-012oUMT9hkQfzrsHQ9PyxwWZ`

---

### Session: December 4, 2025 - LiveKit WebRTC & Pricing Overhaul

**Objective**: Set up LiveKit voice agent worker and update pricing structure.

#### Issues Fixed

**1. LiveKit Worker Deployment Issues**
- `aiohttp proxy TypeError` - Resolved with proper dependency pinning
- `opentelemetry LogData import error` - Pinned to `opentelemetry-api==1.21.0`
- `pip backtracking (19+ minutes)` - Pinned `livekit-agents==1.1.7` and all plugins
- Python version compatibility - Configured Python 3.11 via `runtime.txt` and `nixpacks.toml`

**2. LIVEKIT_URL 401 Error**
- Web service was using placeholder URL
- Required adding LIVEKIT_URL to Railway web service environment

#### New Pricing Structure

| Plan | Price | Minutes | Voice Clones | Features |
|------|-------|---------|--------------|----------|
| Free | $0/mo | 30 | 0 | Web only, basic logs |
| Starter | $9.99/mo | 200 | 2 | All platforms, call sharing |
| Pro | $29.99/mo | 1,000 | 11 | Teams (3), webhooks, priority |
| Business | $79.99/mo | 5,000 | Unlimited | Teams (10), CRM, advanced analytics |

**New Feature Gates Added:**
- `all_platforms` - Multi-platform access
- `call_sharing` - Share call recordings
- `team_members` - Team member limits
- `webhooks` - Webhook integrations
- `crm_integrations` - CRM system integrations
- `advanced_analytics` - Advanced analytics dashboard

#### Developer Dashboard Enhancements
- Voice Agent LLM status card
- Shows active LLM (Fast Brain → Groq → Anthropic)
- LiveKit, Groq, Fast Brain connection status
- Fallback chain visualization

#### Files Modified
- `requirements.txt` - Pinned livekit-agents, opentelemetry versions
- `runtime.txt` - Python 3.11
- `nixpacks.toml` - Nixpacks config for Railway
- `scripts/seed_plan_features.py` - New pricing tiers and 16 features per plan
- `web/src/app/dashboard/subscription/page.tsx` - Updated frontend pricing UI
- `backend/feature_gates.py` - Error messages for new features
- `web/src/app/dashboard/developer/page.tsx` - Voice Agent LLM status section
- `backend/main.py` - Added service status checks for LiveKit, Groq, Fast Brain

**Branch**: `claude/fix-livekit-url-config-012h6fFQv12QCtacVEjWsaZe`

---

### Session: December 4, 2025 - Fast Brain LPU Integration

**Objective**: Integrate Fast Brain (Groq-powered LPU) into HIVE215 voice assistant for ~80ms TTFB.

#### What Fast Brain Is
Fast Brain is a **Groq-powered inference endpoint** deployed on Modal:
- **~80ms TTFB** (Time to First Byte)
- **200+ tokens/second** throughput
- **Built-in skills**: receptionist, electrician, plumber, lawyer, general
- **OpenAI-compatible API** at `/v1/chat/completions`

#### Changes Implemented

**1. Backend `/admin/status` Enhanced** (`backend/main.py:3134-3171`)
- Added actual HTTP health check to Fast Brain service
- Returns latency measurement, skills list, and backend type
- Shows `healthy`, `configured` (unreachable), or `not_configured` states

**2. New Skills API** (`backend/main.py:3254-3361`)
- `GET /api/skills/fast-brain` - Fetches available skills from Fast Brain
- `POST /api/skills/fast-brain` - Creates custom skills with system prompts

**3. Voice Agent Fallback Logic** (`backend/main.py:3173-3203`)
- Now checks actual Fast Brain health before selecting it as primary LLM
- Falls back to Groq → Anthropic if Fast Brain is unreachable

**4. Developer Dashboard** (`web/src/app/dashboard/developer/page.tsx`)
- Shows Fast Brain status: Online (purple pulse) / Configured (yellow) / Not Set (gray)
- Displays available skills as tags when online
- Shows health check latency

#### Already Existed (No Changes Needed)
- `backend/brain_client.py` - Full FastBrainClient implementation
- `backend/livekit_agent.py` - BrainLLM class and fallback chain
- `config/settings.py` - FAST_BRAIN_URL config support

#### Environment Variables
```bash
# Railway Backend
FAST_BRAIN_URL=https://jenkintownelectricity--fast-brain-api-fastapi-app.modal.run
```

#### Fast Brain API Reference
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with skills list |
| `/v1/skills` | GET | List all skills |
| `/v1/skills` | POST | Create custom skill |
| `/v1/chat/completions` | POST | Chat completion (OpenAI format) |

#### Skills Available
- `general` - General assistant (default)
- `receptionist` - Professional call handling
- `electrician` - Electrical service intake
- `plumber` - Plumbing service intake
- `lawyer` - Legal intake calls

**Branch**: `claude/integrate-fast-brain-lpu-01UtorJFkpFmGieoY5J2yCFZ`

---

*Built with Claude AI, designed for humans.*

**Last Updated**: 2025-12-04

---

## Next Claude Code Session Instructions

### Current Branch Status
All work is on branch: `claude/fix-livekit-url-config-012h6fFQv12QCtacVEjWsaZe`

### Pending Database Updates (REQUIRED)
Run this SQL in Supabase SQL Editor before deploying:

```sql
-- Update plan names and prices
UPDATE va_subscription_plans
SET plan_name = 'business', display_name = 'Business', price_cents = 7999
WHERE plan_name = 'enterprise';

UPDATE va_subscription_plans SET price_cents = 0 WHERE plan_name = 'free';
UPDATE va_subscription_plans SET price_cents = 999 WHERE plan_name = 'starter';
UPDATE va_subscription_plans SET price_cents = 2999 WHERE plan_name = 'pro';
```

Then run the seed script:
```bash
python scripts/seed_plan_features.py
```

### Stripe Updates Required
Create/update products in Stripe Dashboard:
- Starter: $9.99/month
- Pro: $29.99/month
- Business: $79.99/month

Update `stripe_price_id` in `va_subscription_plans` table.

### Railway Environment Variables
**Web Service** needs:
- `LIVEKIT_URL` - Your LiveKit cloud URL (wss://your-project.livekit.cloud)

**Worker Service** needs:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `GROQ_API_KEY` (for LLM fallback if Fast Brain not configured)
- `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY` (for STT/TTS)

### What's Working
- Pricing structure updated (Free/Starter/Pro/Business)
- Developer dashboard shows Voice Agent LLM status
- LiveKit worker dependencies pinned (livekit-agents==1.1.7)
- Python 3.11 configured for Railway

---

## Fast Brain Development Guide

### Overview
Fast Brain is a custom BitNet LPU (Language Processing Unit) designed for ultra-low latency voice AI responses. It serves as the primary LLM in the voice agent fallback chain:

```
Fast Brain (primary) → Groq (fallback 1) → Anthropic Claude (fallback 2)
```

### Architecture
Fast Brain runs on Modal with GPU acceleration for sub-50ms inference latency.

### Key Files to Create/Modify
```
fast_brain/
├── modal_app.py          # Modal deployment entry point
├── model.py              # BitNet model wrapper
├── inference.py          # Streaming inference handler
├── api.py                # HTTP/WebSocket endpoints
└── config.py             # Model configuration
```

### Development Steps

#### 1. Set Up Modal Project
```bash
cd premier_voice_assistant
mkdir -p fast_brain
modal setup  # Authenticate with Modal
```

#### 2. Create Modal App Structure
```python
# fast_brain/modal_app.py
import modal

app = modal.App("fast-brain")

# GPU image with model dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch",
    "transformers",
    "bitnet",  # or your BitNet implementation
    "fastapi",
    "uvicorn"
)

@app.cls(gpu="A10G", image=image, container_idle_timeout=300)
class FastBrain:
    @modal.enter()
    def load_model(self):
        # Load BitNet model into GPU memory
        pass

    @modal.method()
    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        # Streaming generation
        pass

    @modal.web_endpoint(method="POST")
    def chat(self, request: dict):
        # HTTP endpoint for voice agent
        pass
```

#### 3. Implement Streaming Response
```python
# fast_brain/inference.py
async def stream_generate(prompt: str):
    """Stream tokens for ultra-low TTFB."""
    for token in model.generate_stream(prompt):
        yield token
```

#### 4. Deploy to Modal
```bash
modal deploy fast_brain/modal_app.py
```

#### 5. Get Endpoint URL
After deployment, Modal provides a URL like:
```
https://your-username--fast-brain-fastbrain-chat.modal.run
```

#### 6. Configure in Railway Worker
Add to Railway worker environment:
```
FAST_BRAIN_URL=https://your-username--fast-brain-fastbrain-chat.modal.run
```

### Integration with Voice Agent

The LiveKit voice agent (`worker/voice_agent.py`) already checks for Fast Brain:

```python
# LLM selection priority
if os.getenv("FAST_BRAIN_URL"):
    llm = FastBrainLLM(url=os.getenv("FAST_BRAIN_URL"))
elif os.getenv("GROQ_API_KEY"):
    llm = GroqLLM(api_key=os.getenv("GROQ_API_KEY"))
else:
    llm = AnthropicLLM(api_key=os.getenv("ANTHROPIC_API_KEY"))
```

### Performance Targets
| Metric | Target | Notes |
|--------|--------|-------|
| TTFB | <50ms | Time to first token |
| Throughput | >500 tok/s | Tokens per second |
| Cold start | <5s | Container spinup |
| Warm latency | <30ms | Already loaded |

### Testing Fast Brain
```bash
# Test endpoint directly
curl -X POST https://your-fast-brain-url/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, how can I help you today?", "max_tokens": 100}'

# Monitor in Modal dashboard
modal app logs fast-brain
```

### Claude Code Session Prompt for Fast Brain
```
I'm working on the Fast Brain custom BitNet LPU for the Premier Voice Assistant.
It needs to:
1. Run on Modal with GPU (A10G or better)
2. Provide streaming inference with <50ms TTFB
3. Expose HTTP/WebSocket endpoints for the voice agent
4. Handle the system prompt for phone answering scenarios

Current files are in fast_brain/ directory.
The voice agent worker expects FAST_BRAIN_URL environment variable.

Please help me [implement/debug/optimize] the Fast Brain deployment.
```

---
