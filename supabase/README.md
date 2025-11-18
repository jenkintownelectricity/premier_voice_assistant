# Supabase Setup for Premier Voice Assistant

This directory contains the complete database schema and setup instructions for the Premier Voice Assistant, including base tables and subscription system with feature gates.

## 🚀 Quick Setup

### Step 1: Create Storage Buckets

In your Supabase dashboard, go to **Storage** and create two buckets:

**Bucket 1: `va-voice-recordings`** (Private)
- For temporary voice recordings from users
- Auto-delete after 24 hours (optional)

**Bucket 2: `va-voice-clones`** (Private with public folder)
- For storing reference audio for voice cloning
- Users can only access their own clones

### Step 2: Run Base Schema

In your Supabase dashboard, go to **SQL Editor** and run the contents of `schema.sql`.

This creates:
- ✅ `va_user_profiles` - Extended user info (phone, preferences)
- ✅ `va_conversations` - Conversation sessions
- ✅ `va_messages` - Message history with audio URLs
- ✅ `va_voice_clones` - Custom voice models
- ✅ `va_usage_metrics` - Analytics and monitoring
- ✅ Row Level Security policies

### Step 3: Run Subscription Migration

Run the subscription system migration from `migrations/001_add_subscription_system.sql`.

This adds:
- ✅ `va_subscription_plans` - Plans (Free, Starter, Pro, Enterprise)
- ✅ `va_plan_features` - Feature limits for each plan
- ✅ `va_user_subscriptions` - User subscription status
- ✅ `va_usage_tracking` - Monthly usage tracking
- ✅ Helper functions for feature gates
- ✅ Views for easy querying
- ✅ Triggers for automatic subscription creation

See **[migrations/README.md](migrations/README.md)** for complete migration guide.

### Step 4: Seed Plan Features

After running both migrations, seed the plan features:

```bash
python scripts/seed_plan_features.py
```

This populates limits for all plans:

| Plan | Minutes/mo | Assistants | Custom Voices |
|------|------------|------------|---------------|
| Free | 100 | 1 | ❌ |
| Starter | 2,000 | 3 | ✅ 2 max |
| Pro | 10,000 | Unlimited | Unlimited |
| Enterprise | Unlimited | Unlimited | Unlimited |

### Step 5: Enable Authentication

Go to **Authentication > Providers** and enable:

**For Mobile Apps:**
- ✅ Email (passwordless magic links)
- ✅ Phone (SMS OTP) - Recommended for voice app
- ✅ Apple Sign-In (iOS)
- ✅ Google Sign-In (Android)

**Configure Phone Auth (Recommended):**
1. Enable "Phone" provider
2. Choose an SMS provider (Twilio recommended)
3. Add your Twilio credentials
4. Configure phone number verification

### Step 6: Get API Keys

Go to **Settings > API** and copy:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key  # For backend only!
```

Add these to your `.env` file (backend) and mobile app config.

## 📊 Complete Database Schema

### Base Tables (schema.sql)

```
┌─────────────────┐
│  auth.users     │ (Supabase managed)
│  - id           │
│  - email/phone  │
└────────┬────────┘
         │
         ├─────► va_user_profiles (preferences)
         │          ↓
         │       [Trigger: Auto-create Free subscription]
         │
         ├─────► va_conversations
         │           │
         │           └─────► va_messages (with audio URLs)
         │
         ├─────► va_voice_clones (custom voices)
         │
         └─────► va_usage_metrics (analytics)
```

### Subscription Tables (migrations/001_*.sql)

```
va_subscription_plans (Free, Starter, Pro, Enterprise)
         │
         ├─────► va_plan_features (limits for each plan)
         │
         └─────► va_user_subscriptions (user's active plan)
                     │
                     └─────► va_usage_tracking (monthly usage)
```

## 🔐 Row Level Security (RLS)

All tables have RLS enabled to ensure users can only:
- ✅ Read their own data
- ✅ Write to their own records
- ✅ Access public voice clones
- ❌ Cannot access other users' data

### Example RLS Policy

```sql
-- Users can only view their own subscription
CREATE POLICY "Users can view own subscription"
    ON va_user_subscriptions FOR SELECT
    USING (auth.uid() = user_id);
```

## 💰 Subscription System

### Plans

The system includes 4 subscription plans:

**Free ($0/month)**
- 100 minutes/month
- 1 assistant
- No custom voices
- Community support

**Starter ($99/month)**
- 2,000 minutes/month
- 3 assistants
- 2 custom voices
- Email support
- Overage: $0.10/minute

**Pro ($299/month)**
- 10,000 minutes/month
- Unlimited assistants
- Unlimited custom voices
- Priority support
- Advanced analytics
- Overage: $0.08/minute

**Enterprise (Custom)**
- Unlimited everything
- Dedicated support
- Custom integrations

### Feature Gates

Feature gates enforce subscription limits at the API level:

```python
# Example: Check if user can use a feature
from backend.feature_gates import get_feature_gate

feature_gate = get_feature_gate()
allowed, details = feature_gate.check_feature(user_id, "max_minutes", 1)

if allowed:
    # Process request
    # ...
    # Track usage
    feature_gate.increment_usage(user_id, minutes=1)
else:
    # Block request - user over limit
    return "Upgrade to continue"
```

### Usage Tracking

Usage is automatically tracked:
- Minutes used per billing period
- Assistants created
- Voice clones created
- API calls made

All tracked in `va_usage_tracking` table with automatic rollover each billing period.

## 🔧 Database Functions

### Check Feature Gate

```sql
SELECT * FROM va_check_feature_gate('user-id', 'max_minutes', 1);
```

Returns:
- `allowed` (boolean): Whether user can perform action
- `current_usage` (int): Current usage count
- `limit_value` (int): Plan limit (-1 = unlimited)
- `remaining` (int): Remaining quota

### Increment Usage

```sql
SELECT va_increment_usage('user-id', 5, '{"conversation_id": "123"}'::jsonb);
```

Tracks usage and automatically:
- Creates usage record if not exists
- Increments counters
- Calculates overages
- Updates billing info

### Get User Plan

```sql
SELECT * FROM va_get_user_plan('user-id');
```

Returns user's active subscription plan.

### Admin Upgrade User

```sql
SELECT va_admin_upgrade_user('user-id', 'pro');
```

Upgrades user to specified plan (admin only).

## 📈 Database Views

### User Subscription Details

```sql
SELECT * FROM va_user_subscription_details WHERE user_id = 'user-id';
```

Returns:
- Plan name and display name
- Price
- Status
- Billing period dates
- Cancellation status

### Current Usage Summary

```sql
SELECT * FROM va_current_usage_summary WHERE user_id = 'user-id';
```

Returns:
- Minutes used/limit
- Usage percentage
- Assistants count
- Voice clones count
- Overage charges

## 🗂️ Storage Buckets

### va-voice-recordings/
```
{user_id}/
  ├── recording_123.wav
  ├── recording_124.wav
  └── ...
```

**Purpose**: Temporary voice recordings from conversations
**Retention**: 24 hours (configure in Supabase)
**Access**: Private (user only)

### va-voice-clones/
```
{user_id}/
  ├── fabio.wav
  ├── custom_voice.wav
public/
  ├── default_male.wav
  └── default_female.wav
```

**Purpose**: Voice clone reference audio
**Retention**: Permanent
**Access**: User's own + public voices

## 🔌 API Integration

### Backend (Python)

```python
from backend.supabase_client import get_supabase
from backend.feature_gates import get_feature_gate, FeatureGateError

# Get user's plan
feature_gate = get_feature_gate()
plan = feature_gate.get_user_plan(user_id)

# Check feature before processing
try:
    feature_gate.enforce_feature(user_id, "max_minutes", 1)
except FeatureGateError as e:
    # User over limit
    return {"error": e.message}, 402

# Track usage after success
feature_gate.increment_usage(user_id, minutes=1)
```

### Mobile App (Swift)

```swift
import Supabase

let supabase = SupabaseClient(
    supabaseURL: URL(string: "https://your-project.supabase.co")!,
    supabaseKey: "your-anon-key"
)

// Sign in with phone
await supabase.auth.signIn(phone: "+1234567890")

// Check user's subscription
let subscription = try await supabase
    .from("va_user_subscription_details")
    .select()
    .eq("user_id", userId)
    .single()
    .execute()

// Check usage
let usage = try await supabase
    .from("va_current_usage_summary")
    .select()
    .eq("user_id", userId)
    .single()
    .execute()
```

### Mobile App (React Native)

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://your-project.supabase.co',
  'your-anon-key'
)

// Get user's feature limits
const { data: limits } = await supabase
  .from('va_current_usage_summary')
  .select('*')
  .eq('user_id', userId)
  .single()

// Show upgrade prompt if near limit
if (limits.usage_percentage > 80) {
  showUpgradePrompt()
}
```

## 🧪 Testing

### Test Subscription System

```bash
# Run comprehensive tests
python scripts/test_feature_gates.py
```

This tests:
1. User creation with Free plan
2. Feature limit enforcement
3. Usage tracking
4. Admin upgrade flow
5. Pro plan features

### Manual Testing

```sql
-- Create test user
INSERT INTO va_user_profiles (id, phone)
VALUES ('test-user-123', '+1234567890');
-- Subscription automatically created via trigger

-- Check subscription
SELECT * FROM va_user_subscription_details
WHERE user_id = 'test-user-123';

-- Simulate usage
SELECT va_increment_usage('test-user-123', 50, '{}'::jsonb);

-- Check usage
SELECT * FROM va_current_usage_summary
WHERE user_id = 'test-user-123';

-- Upgrade to Pro
SELECT va_admin_upgrade_user('test-user-123', 'pro');

-- Verify upgrade
SELECT * FROM va_user_subscription_details
WHERE user_id = 'test-user-123';
```

## 📋 Useful Queries

### Get conversation history

```sql
SELECT m.*, c.title
FROM va_messages m
JOIN va_conversations c ON m.conversation_id = c.id
WHERE c.user_id = auth.uid()
ORDER BY m.created_at DESC
LIMIT 50;
```

### Get user's average latency

```sql
SELECT
  AVG(total_latency_ms) as avg_latency,
  COUNT(*) as total_requests
FROM va_usage_metrics
WHERE user_id = auth.uid()
AND created_at > NOW() - INTERVAL '7 days';
```

### Find users over 80% usage (upgrade opportunities)

```sql
SELECT
    user_id,
    plan_name,
    minutes_used,
    minutes_limit,
    usage_percentage
FROM va_current_usage_summary
WHERE usage_percentage::NUMERIC > 80
AND plan_name != 'enterprise'
ORDER BY usage_percentage DESC;
```

### Calculate revenue by plan

```sql
SELECT
    sp.plan_name,
    sp.display_name,
    COUNT(us.id) as user_count,
    sp.price_cents,
    (COUNT(us.id) * sp.price_cents / 100.0) as monthly_revenue
FROM va_subscription_plans sp
LEFT JOIN va_user_subscriptions us ON sp.id = us.plan_id AND us.status = 'active'
GROUP BY sp.id, sp.plan_name, sp.display_name, sp.price_cents
ORDER BY monthly_revenue DESC;
```

## 🚨 Monitoring & Alerts

Set up alerts for:

### Usage Alerts
```sql
-- Users at 90% of limit
SELECT user_id, plan_name, usage_percentage
FROM va_current_usage_summary
WHERE usage_percentage::NUMERIC > 90;
```

### Failed Feature Gates
Check backend logs for `FeatureGateError` exceptions

### Subscription Expiring Soon
```sql
SELECT user_id, plan_name, current_period_end
FROM va_user_subscriptions
WHERE current_period_end < NOW() + INTERVAL '7 days'
AND status = 'active'
AND cancel_at_period_end = true;
```

## 🔧 Maintenance

### Reset Monthly Usage (if needed)

```sql
-- Usually handled automatically, but if needed:
DELETE FROM va_usage_tracking
WHERE period_end < NOW() - INTERVAL '3 months';
```

### Update Plan Limits

```bash
# Edit limits in scripts/seed_plan_features.py
# Then re-run:
python scripts/seed_plan_features.py
```

### Backup Database

Use Supabase Dashboard → Database → Backups or:

```bash
pg_dump -h your-project.supabase.co -U postgres -d postgres > backup.sql
```

## 📚 Additional Resources

- **[Migration Guide](migrations/README.md)** - Complete migration instructions
- **[Feature Gates Implementation](../FEATURE_GATES_IMPLEMENTATION.md)** - Implementation guide
- **[Supabase Docs](https://supabase.com/docs)** - Official documentation
- **[RLS Guide](https://supabase.com/docs/guides/auth/row-level-security)** - Security guide

## 🐛 Troubleshooting

### "Subscription not found"
- Check trigger exists: `\df va_create_default_subscription`
- Manually create: `SELECT va_admin_upgrade_user('user-id', 'free');`

### "Feature gate check failed"
- Verify migration ran: `\dt va_*`
- Check functions exist: `\df va_check_feature_gate`
- Review Supabase logs for errors

### "RLS blocking queries"
- Ensure using service role key in backend
- Check RLS policies: `\d+ va_user_subscriptions`
- Test with: `SET ROLE authenticated; SELECT ...`

## 🔐 Security Best Practices

1. **Never expose service role key** to clients
2. **Always use RLS** for user-facing tables
3. **Validate input** in database functions
4. **Audit admin operations** (log all upgrades/downgrades)
5. **Monitor unusual patterns** (sudden usage spikes)
6. **Encrypt sensitive data** (payment info, PII)
7. **Regular backups** (automated daily)
8. **Test RLS policies** before deploying changes

## 📞 Support

- **Supabase Dashboard**: Monitor logs and errors
- **Backend Logs**: Check feature gate enforcement
- **Database Logs**: Review query performance

---

**Setup Status**: ✅ Ready for Production

**Last Updated**: 2025-11-18
