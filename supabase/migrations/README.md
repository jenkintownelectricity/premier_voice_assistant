# Database Migrations for Feature Gates & Subscriptions

This directory contains SQL migrations to add subscription plans, feature gates, and usage tracking to the Premier Voice Assistant.

## 📋 Overview

The migration adds:
- ✅ Subscription plans (Free, Starter, Pro, Enterprise)
- ✅ Plan features with configurable limits
- ✅ User subscription management
- ✅ Usage tracking and enforcement
- ✅ Automatic subscription creation for new users
- ✅ Admin functions for user management
- ✅ Helper views for easy querying

## 🚀 Quick Start

### 1. Run the Migration

In your Supabase dashboard:

1. Go to **SQL Editor**
2. Click "New query"
3. Copy and paste the contents of `001_add_subscription_system.sql`
4. Click "Run"

The migration will:
- Create all necessary tables
- Set up Row Level Security (RLS) policies
- Create helper functions and triggers
- Insert default subscription plans
- Create views for easy querying

### 2. Seed Plan Features

After running the migration, seed the plan features:

```bash
cd /home/user/premier_voice_assistant
python scripts/seed_plan_features.py
```

This will populate the `va_plan_features` table with limits for each plan:

**Free Plan:**
- 100 minutes/month
- 1 assistant
- 0 custom voices
- No API access

**Starter Plan ($99/month):**
- 2,000 minutes/month
- 3 assistants
- 2 custom voices
- API access

**Pro Plan ($299/month):**
- 10,000 minutes/month
- Unlimited assistants
- Unlimited custom voices
- Full API access
- Priority support

**Enterprise Plan (Custom):**
- Unlimited everything
- Dedicated support

### 3. Set Admin API Key

Add an admin API key to your environment variables:

```bash
# In your .env file or Supabase dashboard
ADMIN_API_KEY=your-secure-random-key-here
```

This key is required for the `/admin/upgrade-user` endpoint.

## 📊 Database Schema

### Tables

#### va_subscription_plans
Stores available subscription plans.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| plan_name | VARCHAR(50) | Plan identifier ('free', 'starter', etc.) |
| display_name | VARCHAR(100) | Display name |
| price_cents | INTEGER | Price in cents |
| billing_interval | VARCHAR(20) | 'monthly' or 'yearly' |

#### va_plan_features
Feature limits for each plan.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| plan_id | UUID | References va_subscription_plans |
| feature_key | VARCHAR(100) | Feature name |
| feature_value | JSONB | Feature value (limit or boolean) |
| description | TEXT | Feature description |

#### va_user_subscriptions
User subscription status and billing info.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | References auth.users |
| plan_id | UUID | References va_subscription_plans |
| status | VARCHAR(20) | 'active', 'cancelled', 'expired' |
| current_period_start | TIMESTAMP | Billing period start |
| current_period_end | TIMESTAMP | Billing period end |
| stripe_customer_id | VARCHAR(100) | Optional Stripe customer ID |
| stripe_subscription_id | VARCHAR(100) | Optional Stripe subscription ID |

#### va_usage_tracking
Monthly usage tracking for enforcing limits.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | References auth.users |
| period_start | TIMESTAMP | Tracking period start |
| period_end | TIMESTAMP | Tracking period end |
| minutes_used | INTEGER | Minutes consumed |
| minutes_limit | INTEGER | Minutes limit |
| assistants_count | INTEGER | Number of assistants |
| voice_clones_count | INTEGER | Number of voice clones |
| overage_minutes | INTEGER | Minutes beyond limit |
| overage_cost_cents | INTEGER | Cost for overages |

### Functions

#### va_get_user_plan(user_id UUID)
Get user's active subscription plan.

```sql
SELECT * FROM va_get_user_plan('user-id-here');
```

#### va_get_feature_limit(user_id UUID, feature_key VARCHAR)
Get feature limit value for a user.

```sql
SELECT va_get_feature_limit('user-id-here', 'max_minutes');
```

#### va_check_feature_gate(user_id UUID, feature_key VARCHAR, requested_amount INTEGER)
Check if user can perform an action.

```sql
SELECT * FROM va_check_feature_gate('user-id-here', 'max_minutes', 1);
```

Returns:
- `allowed` (boolean): Whether action is allowed
- `current_usage` (integer): Current usage
- `limit_value` (integer): Plan limit (-1 = unlimited)
- `remaining` (integer): Remaining quota

#### va_increment_usage(user_id UUID, minutes INTEGER, metadata JSONB)
Increment usage counters.

```sql
SELECT va_increment_usage('user-id-here', 5, '{"conversation_id": "123"}'::jsonb);
```

#### va_admin_upgrade_user(user_id UUID, plan_name VARCHAR)
Admin function to upgrade user subscription.

```sql
SELECT va_admin_upgrade_user('user-id-here', 'pro');
```

### Views

#### va_user_subscription_details
User subscription with plan details (easier querying).

```sql
SELECT * FROM va_user_subscription_details WHERE user_id = 'user-id-here';
```

#### va_current_usage_summary
Current period usage summary.

```sql
SELECT * FROM va_current_usage_summary WHERE user_id = 'user-id-here';
```

## 🧪 Testing

### Test the Feature Gates

Run the comprehensive test script:

```bash
python scripts/test_feature_gates.py
```

This will:
1. ✅ Create a test user with Free plan
2. ✅ Test Free plan limits (100 minutes)
3. ✅ Simulate exceeding limits
4. ✅ Upgrade user to Pro plan
5. ✅ Test Pro plan features (10,000 minutes)
6. ✅ Clean up test data

### Manual Testing

#### Create a test user profile

```sql
-- This will automatically create a Free plan subscription
INSERT INTO public.va_user_profiles (id, phone)
VALUES ('test-user-id', '+1234567890');
```

#### Check user's subscription

```sql
SELECT * FROM va_user_subscription_details
WHERE user_id = 'test-user-id';
```

#### Check feature limits

```sql
SELECT * FROM va_check_feature_gate('test-user-id', 'max_minutes', 1);
```

#### Simulate usage

```sql
SELECT va_increment_usage('test-user-id', 50, '{}'::jsonb);
```

#### Upgrade user

```sql
SELECT va_admin_upgrade_user('test-user-id', 'pro');
```

#### Check usage summary

```sql
SELECT * FROM va_current_usage_summary
WHERE user_id = 'test-user-id';
```

## 🔒 Security

### Row Level Security (RLS)

All tables have RLS enabled:

- ✅ Users can only view their own subscription and usage
- ✅ Service role key (backend) can insert/update everything
- ✅ Anonymous users cannot access subscription data

### Admin Operations

Admin operations require:
- Backend service role key (for database functions)
- Admin API key (for API endpoints)

Never expose these keys to clients!

## 💰 Economics

With feature gates enforced:

**Free User (100 min/mo):**
- Your cost: $1.15
- Your revenue: $0
- Loss: $1.15 (acceptable for acquisition)

**Starter User (2,000 min/mo):**
- Your cost: $23
- Your revenue: $99
- Profit: $76 (77% margin) ✅

**Pro User (10,000 min/mo):**
- Your cost: $115
- Your revenue: $299
- Profit: $184 (62% margin) ✅

### Limits Prevent Abuse

- ❌ Can't use unlimited minutes on Free plan
- ✅ Automatic overage billing at $0.10/min (Starter)
- ✅ Admin can monitor usage in real-time
- ✅ Predictable costs and revenue

## 🔄 Integration with Backend

The backend automatically enforces feature gates:

### Protected Endpoints

- `POST /chat` - Checks `max_minutes`, increments usage
- `POST /clone-voice` - Checks `custom_voices` capability and `max_voice_clones` limit

### Usage Tracking

Usage is automatically tracked on:
- Every chat conversation (based on audio duration)
- Voice clone creation (counts toward limit)

### API Endpoints

New endpoints added:
- `GET /subscription` - Get user's plan
- `GET /usage` - Get user's current usage
- `GET /feature-limits` - Get all feature limits
- `POST /admin/upgrade-user` - Admin upgrade (requires admin key)

## 📝 Customizing Plans

### Modify Plan Limits

Edit `scripts/seed_plan_features.py` and update the `plan_features` dictionary:

```python
plan_features = {
    "free": {
        "max_minutes": 100,  # Change this
        "max_assistants": 1,
        # ...
    },
    # ...
}
```

Then re-run the seed script:

```bash
python scripts/seed_plan_features.py
```

### Add New Features

1. Add feature to `plan_features` in seed script
2. Update `backend/feature_gates.py` to enforce the feature
3. Add feature check to relevant API endpoints

## 🐛 Troubleshooting

### "Failed to check feature gate"

- Check that migration ran successfully
- Verify user has a subscription (check `va_user_subscriptions`)
- Check Supabase logs for errors

### "No subscription found"

New users should get Free plan automatically. If not:

```sql
-- Manually create subscription
INSERT INTO public.va_user_subscriptions (user_id, plan_id, status)
SELECT
    'user-id-here',
    (SELECT id FROM public.va_subscription_plans WHERE plan_name = 'free'),
    'active';
```

### "Feature limits not working"

- Check that plan features are seeded: `SELECT * FROM va_plan_features;`
- Re-run seed script if empty: `python scripts/seed_plan_features.py`

## 📚 Next Steps

1. ✅ Run migration
2. ✅ Seed plan features
3. ✅ Test with test script
4. ✅ Integrate Stripe for payment processing
5. ✅ Add webhook handlers for subscription updates
6. ✅ Build user dashboard for plan management
7. ✅ Add email notifications for limit warnings

## 🆘 Support

For issues or questions:
- Check Supabase logs in dashboard
- Review migration SQL for errors
- Test with `test_feature_gates.py`
- Check backend logs for feature gate errors
