# Premier Voice Assistant

Production-ready voice AI system with subscription-based feature gates and usage tracking. Built with open-source models and serverless infrastructure for predictable costs and scalable monetization.

## 🚀 Features

- ✅ **Voice Pipeline**: Whisper STT → Claude LLM → Coqui TTS
- ✅ **Subscription System**: Free, Starter, Pro, Enterprise plans
- ✅ **Feature Gates**: Usage limits enforced at API level
- ✅ **Usage Tracking**: Real-time monitoring and billing
- ✅ **Mobile Ready**: Supabase backend for iOS/Android apps
- ✅ **Voice Cloning**: Custom voices with Coqui XTTS-v2

## 💰 Subscription Plans

| Plan | Price | Minutes/mo | Assistants | Custom Voices | Economics |
|------|-------|------------|------------|---------------|-----------|
| **Free** | $0 | 100 | 1 | ❌ | -$1.15/user (acquisition) |
| **Starter** | $99/mo | 2,000 | 3 | ✅ 2 max | +$76/user (77% margin) |
| **Pro** | $299/mo | 10,000 | Unlimited | Unlimited | +$184/user (62% margin) |
| **Enterprise** | Custom | Unlimited | Unlimited | Unlimited | Custom pricing |

### Cost Breakdown
- **STT**: Whisper on Modal T4 GPU (~$0.0002/min)
- **LLM**: Claude API with caching (~$0.003/min)
- **TTS**: Coqui on Modal T4 GPU (~$0.0002/min)
- **Total**: ~$0.0115/minute at scale

## 🎯 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Supabase

See [`supabase/README.md`](supabase/README.md) for complete setup:

1. **Run base schema**: `supabase/schema.sql`
2. **Run subscription migration**: `supabase/migrations/001_add_subscription_system.sql`
3. **Seed plan features**: `python scripts/seed_plan_features.py`
4. **Get API keys** from Supabase dashboard

### 3. Configure Environment

```bash
# Copy example and edit
cp .env.example .env

# Required variables:
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
ANTHROPIC_API_KEY=sk-ant-your-key
ADMIN_API_KEY=your-admin-key  # For admin endpoints
```

### 4. Deploy Modal Endpoints

```bash
modal deploy modal_deployment/whisper_stt.py
modal deploy modal_deployment/coqui_tts.py
```

### 5. Run Backend

```bash
# Development
python -m backend.main

# Production
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## 🗂️ Project Structure

```
premier_voice_assistant/
├── backend/
│   ├── main.py                  # FastAPI app with feature gates
│   ├── supabase_client.py       # Database operations
│   └── feature_gates.py         # Subscription enforcement
│
├── modal_deployment/            # Serverless GPU functions
│   ├── whisper_stt.py          # Speech-to-text
│   ├── coqui_tts.py            # Text-to-speech with cloning
│   └── voice_cloner.py         # Voice management
│
├── supabase/
│   ├── schema.sql              # Base database schema
│   └── migrations/             # Subscription system migration
│       ├── 001_add_subscription_system.sql
│       └── README.md
│
├── scripts/
│   ├── seed_plan_features.py   # Populate subscription plans
│   └── test_feature_gates.py   # Test subscription limits
│
├── voices/                      # Voice samples for cloning
├── agent/                       # Voice agent logic (future)
├── telephony/                   # VoIP integration (future)
└── knowledge/                   # Business logic (future)
```

## 🔐 API Endpoints

### Core Voice Pipeline

- `POST /transcribe` - Audio → Text (Whisper)
- `POST /speak` - Text → Audio (Coqui)
- `POST /chat` - Full conversation (STT → LLM → TTS) **[PROTECTED]**

### Voice Cloning

- `POST /clone-voice` - Clone custom voice **[PROTECTED]**
- `GET /voice-clones` - List user's voices

### Conversations

- `GET /conversations` - List user conversations
- `GET /conversations/{id}/messages` - Get messages
- `GET /profile` - User profile & preferences
- `PATCH /profile` - Update preferences

### Subscription & Usage

- `GET /subscription` - Current subscription plan
- `GET /usage` - Monthly usage statistics
- `GET /feature-limits` - All feature limits
- `POST /admin/upgrade-user` - Admin: Upgrade user plan

### Health

- `GET /health` - Service health check

## 🛡️ Feature Gate Enforcement

### Protected Endpoints

**`POST /chat`**
- ✅ Checks `max_minutes` before processing
- ✅ Tracks actual usage after completion
- ❌ Blocks with `402 Payment Required` if limit reached

**`POST /clone-voice`**
- ✅ Checks `custom_voices` capability
- ✅ Checks `max_voice_clones` limit
- ❌ Blocks if plan doesn't support custom voices

### Example: Free Plan Limit

```bash
# User on Free plan makes 100 chat calls
curl -X POST http://api.example.com/chat \
  -H "X-User-ID: user-123" \
  -F "audio=@test.wav"

# Response: 200 OK (for calls 1-100)

# 101st call
curl -X POST http://api.example.com/chat \
  -H "X-User-ID: user-123" \
  -F "audio=@test.wav"

# Response: 402 Payment Required
# {
#   "detail": "Monthly minute limit reached. You've used 100 of 100 minutes..."
# }
```

## 🧪 Testing

### Test Feature Gates

```bash
# Run comprehensive test suite
python scripts/test_feature_gates.py
```

This tests:
1. ✅ Free plan creation
2. ✅ Limit enforcement (100 minutes)
3. ✅ Limit blocking after usage
4. ✅ Admin upgrade to Pro
5. ✅ Pro plan features (10,000 minutes)

### Manual Testing

```bash
# Check user's subscription
curl http://localhost:8000/subscription \
  -H "X-User-ID: user-123"

# Check usage
curl http://localhost:8000/usage \
  -H "X-User-ID: user-123"

# Upgrade user (admin only)
curl -X POST http://localhost:8000/admin/upgrade-user \
  -H "X-Admin-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"target_user_id": "user-123", "plan_name": "pro"}'
```

## 📊 Monitoring & Analytics

### Real-Time Usage Tracking

All usage is automatically tracked:
- Minutes used per billing period
- Conversations count
- Voice clones created
- API calls made

### Database Views

```sql
-- Current usage summary
SELECT * FROM va_current_usage_summary WHERE user_id = 'user-id';

-- Subscription details
SELECT * FROM va_user_subscription_details WHERE user_id = 'user-id';
```

### Usage Alerts

Consider adding alerts for:
- Users at 80% of limit (upgrade opportunity)
- Users hitting limits frequently
- Unusual usage patterns

## 🏗️ Architecture

### Voice Pipeline

```
Mobile App → FastAPI Backend → Modal GPU Workers
    ↓            ↓                    ↓
  Auth     Feature Gates         Whisper STT
           Usage Tracking        Coqui TTS
              ↓
         Supabase DB
```

### Feature Gate Flow

```
1. Request arrives at /chat endpoint
2. Check user's plan and current usage
3. Enforce feature gate (block if over limit)
4. Process request (STT → LLM → TTS)
5. Track actual usage in database
6. Return response to user
```

## 📈 Development Phases

### ✅ Phase 1: Core Voice Pipeline (Complete)
- [x] Modal environment setup
- [x] Whisper STT deployment
- [x] Coqui TTS deployment
- [x] Claude integration
- [x] Basic integration tests

### ✅ Phase 1.5: Subscription System (Complete)
- [x] Database schema for subscriptions
- [x] Feature gate enforcement
- [x] Usage tracking
- [x] Admin management endpoints
- [x] Testing suite

### 🔄 Phase 2: Pipecat Integration (Next)
- [ ] Real-time voice streaming
- [ ] Context management
- [ ] Response caching
- [ ] Barge-in / interruption handling
- [ ] Voice Activity Detection (VAD)

### Phase 3: Telephony
- [ ] VoIP.ms SIP integration
- [ ] Inbound call handling
- [ ] Call routing
- [ ] WebRTC fallback

### Phase 4: Business Logic
- [ ] Jenkintown Electricity knowledge base
- [ ] Appointment scheduling
- [ ] Emergency detection
- [ ] Pricing database

## 💡 Best Practices

### For Backend Developers

1. **Always check feature gates** before expensive operations
2. **Track usage immediately** after completion
3. **Use service role key** only in backend (never expose to clients)
4. **Implement retry logic** for database operations
5. **Log all feature gate denials** for monitoring

### For Mobile Developers

1. **Check `/feature-limits`** before showing UI options
2. **Handle `402 Payment Required`** gracefully
3. **Show usage statistics** in settings
4. **Implement upgrade flow** for premium features
5. **Cache subscription status** (revalidate periodically)

### For Product

1. **Monitor conversion rates** (Free → Starter → Pro)
2. **Track feature gate denials** (upgrade opportunities)
3. **Analyze usage patterns** by plan
4. **A/B test plan limits** to optimize revenue
5. **Send upgrade prompts** at 80% usage

## 📚 Documentation

- **[Feature Gates Implementation](FEATURE_GATES_IMPLEMENTATION.md)** - Complete guide
- **[Supabase Setup](supabase/README.md)** - Database configuration
- **[Migration Guide](supabase/migrations/README.md)** - Subscription system setup
- **[Voice Cloning](voices/README.md)** - Recording guidelines

## 🐛 Troubleshooting

### "Feature gate check failed"
- Verify migration ran successfully
- Check user has subscription: `SELECT * FROM va_user_subscriptions WHERE user_id = 'user-id'`
- Check Supabase logs for errors

### "No subscription found"
- New users should get Free plan automatically via trigger
- Manually create: `python scripts/seed_plan_features.py`

### "Usage not tracking"
- Check backend logs for errors
- Verify `va_increment_usage` function exists
- Check RLS policies on `va_usage_tracking` table

## 🔧 Configuration

### Environment Variables

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-key
CLAUDE_MODEL=claude-3-5-sonnet-20241022
MAX_TOKENS=150
TEMPERATURE=0.7

# Admin
ADMIN_API_KEY=your-secure-admin-key

# Server
PORT=8000
DEBUG=false
```

### Feature Customization

Edit plan limits in `scripts/seed_plan_features.py`:

```python
plan_features = {
    "free": {
        "max_minutes": 100,  # Change this
        "max_assistants": 1,
        # ...
    }
}
```

Then re-run: `python scripts/seed_plan_features.py`

## 🆘 Support

- **GitHub Issues**: Report bugs and feature requests
- **Supabase Logs**: Monitor database errors
- **Backend Logs**: Check feature gate denials

## 📜 License

Proprietary - BuildingSystems.ai

---

**Status**: ✅ Production Ready with Feature Gates

**Last Updated**: 2025-11-18
