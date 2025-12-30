# Mobile & Web Integration Guide

Complete guide for integrating the Premier Voice Assistant with iOS, Android, and Web applications.

## 🎯 Architecture

```
Mobile/Web App
    ↓ (Supabase Client - anon key)
Supabase Auth (Phone/Email/OAuth)
    ↓ (JWT token from auth)
Direct DB Queries (Read subscription/usage)
    ↓ (API calls with X-User-ID header)
Backend API (Feature gate enforcement)
    ↓ (Service role key)
Supabase DB + Modal GPU Workers
```

## 🔐 Authentication Flow

### 1. User Signs Up/In
- Mobile app uses Supabase Auth
- Gets JWT token
- Token contains `user_id`

### 2. Auto-Profile Creation
- Trigger creates `va_user_profiles` row
- Trigger creates Free subscription automatically
- User ready to use app

### 3. Two-Tier Access
- **Direct Supabase** (read-only): Subscription status, usage stats, conversation history
- **Backend API** (protected): Chat, voice cloning, etc. (with feature gates)

---

## 📱 iOS Integration (Swift)

### Setup

```swift
import Supabase

let supabase = SupabaseClient(
    supabaseURL: URL(string: "https://your-project.supabase.co")!,
    supabaseKey: "your-anon-key"  // NOT service role key!
)
```

### Authentication

```swift
// Phone Authentication (Recommended for voice app)
func signInWithPhone(_ phoneNumber: String) async throws {
    try await supabase.auth.signInWithOTP(
        phone: phoneNumber
    )
}

// Verify OTP
func verifyOTP(phone: String, token: String) async throws {
    try await supabase.auth.verifyOTP(
        phone: phone,
        token: token,
        type: .sms
    )
}

// Get current user
var currentUser: User? {
    supabase.auth.currentUser
}

// Listen for auth changes
supabase.auth.onAuthStateChange { event, session in
    switch event {
    case .signedIn:
        print("User signed in: \(session?.user.id ?? "")")
    case .signedOut:
        print("User signed out")
    default:
        break
    }
}
```

### Check Subscription Status

```swift
func getMySubscription() async throws -> Subscription {
    let response = try await supabase
        .rpc("va_client_get_my_subscription")
        .execute()

    return try JSONDecoder().decode([Subscription].self, from: response.data).first!
}

struct Subscription: Codable {
    let planName: String
    let displayName: String
    let priceCents: Int
    let status: String
    let currentPeriodStart: Date
    let currentPeriodEnd: Date
    let daysRemaining: Int

    var formattedPrice: String {
        "$\(priceCents / 100)/mo"
    }
}
```

### Check Usage

```swift
func getMyUsage() async throws -> Usage {
    let response = try await supabase
        .rpc("va_client_get_my_usage")
        .execute()

    return try JSONDecoder().decode([Usage].self, from: response.data).first!
}

struct Usage: Codable {
    let planName: String
    let minutesUsed: Int
    let minutesLimit: Int
    let usagePercentage: String
    let assistantsCount: Int
    let assistantsLimit: Int
    let voiceClonesCount: Int
    let voiceClonesLimit: Int

    var isNearLimit: Bool {
        guard let percentage = Double(usagePercentage.replacingOccurrences(of: "%", with: "")) else {
            return false
        }
        return percentage > 80
    }
}
```

### Check Feature Before Action

```swift
func canUseFeature(_ feature: String, amount: Int = 1) async throws -> FeatureCheck {
    let response = try await supabase
        .rpc("va_client_check_feature", params: [
            "p_feature_key": feature,
            "p_requested_amount": amount
        ])
        .execute()

    return try JSONDecoder().decode([FeatureCheck].self, from: response.data).first!
}

struct FeatureCheck: Codable {
    let allowed: Bool
    let currentUsage: Int
    let limitValue: Int
    let remaining: Int
    let planName: String
    let upgradeRequired: Bool
}

// Usage
let canChat = try await canUseFeature("max_minutes", amount: 1)
if !canChat.allowed {
    // Show upgrade prompt
    showUpgradeAlert(currentPlan: canChat.planName)
}
```

### Call Backend API

```swift
func sendChatMessage(audioData: Data) async throws -> Data {
    guard let userId = currentUser?.id else {
        throw AppError.notAuthenticated
    }

    // Check feature gate first
    let canUse = try await canUseFeature("max_minutes")
    guard canUse.allowed else {
        throw AppError.limitReached(canUse)
    }

    // Call backend API
    var request = URLRequest(url: URL(string: "https://your-backend.com/chat")!)
    request.httpMethod = "POST"
    request.setValue(userId.uuidString, forHTTPHeaderField: "X-User-ID")

    let boundary = UUID().uuidString
    request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

    var body = Data()
    body.append("--\(boundary)\r\n".data(using: .utf8)!)
    body.append("Content-Disposition: form-data; name=\"audio\"; filename=\"audio.wav\"\r\n".data(using: .utf8)!)
    body.append("Content-Type: audio/wav\r\n\r\n".data(using: .utf8)!)
    body.append(audioData)
    body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

    request.httpBody = body

    let (data, response) = try await URLSession.shared.data(for: request)

    guard let httpResponse = response as? HTTPURLResponse else {
        throw AppError.invalidResponse
    }

    if httpResponse.statusCode == 402 {
        throw AppError.paymentRequired("Upgrade required to continue")
    }

    guard httpResponse.statusCode == 200 else {
        throw AppError.serverError(httpResponse.statusCode)
    }

    return data
}
```

### Get Available Plans (for Upgrade Screen)

```swift
func getAvailablePlans() async throws -> [Plan] {
    let response = try await supabase
        .rpc("va_client_get_available_plans")
        .execute()

    return try JSONDecoder().decode([Plan].self, from: response.data)
}

struct Plan: Codable {
    let planName: String
    let displayName: String
    let priceCents: Int
    let billingInterval: String
    let features: [String: FeatureValue]

    struct FeatureValue: Codable {
        let value: AnyCodable
        let description: String
    }
}
```

---

## 🤖 Android Integration (Kotlin)

### Setup

```kotlin
import io.github.jan.supabase.createSupabaseClient
import io.github.jan.supabase.gotrue.Auth
import io.github.jan.supabase.postgrest.Postgrest

val supabase = createSupabaseClient(
    supabaseUrl = "https://your-project.supabase.co",
    supabaseKey = "your-anon-key"  // NOT service role key!
) {
    install(Auth)
    install(Postgrest)
}
```

### Authentication

```kotlin
// Phone Authentication
suspend fun signInWithPhone(phoneNumber: String) {
    supabase.auth.signInWith(Phone) {
        phone = phoneNumber
    }
}

// Verify OTP
suspend fun verifyOTP(phone: String, token: String) {
    supabase.auth.verifyPhoneOtp(
        type = OtpType.SMS,
        phone = phone,
        token = token
    )
}

// Get current user
val currentUser = supabase.auth.currentUserOrNull()

// Listen for auth changes
supabase.auth.onAuthStateChange { session ->
    when (session) {
        is AuthState.SignedIn -> {
            println("User signed in: ${session.user.id}")
        }
        is AuthState.SignedOut -> {
            println("User signed out")
        }
    }
}
```

### Check Subscription

```kotlin
data class Subscription(
    val planName: String,
    val displayName: String,
    val priceCents: Int,
    val status: String,
    val currentPeriodStart: String,
    val currentPeriodEnd: String,
    val daysRemaining: Int
)

suspend fun getMySubscription(): Subscription {
    return supabase.postgrest
        .rpc("va_client_get_my_subscription")
        .decodeSingleOrNull<Subscription>()
        ?: throw Exception("No subscription found")
}
```

### Check Usage

```kotlin
data class Usage(
    val planName: String,
    val minutesUsed: Int,
    val minutesLimit: Int,
    val usagePercentage: String,
    val assistantsCount: Int,
    val assistantsLimit: Int,
    val voiceClonesCount: Int,
    val voiceClonesLimit: Int
) {
    val isNearLimit: Boolean
        get() = usagePercentage.removeSuffix("%").toDoubleOrNull()?.let { it > 80 } ?: false
}

suspend fun getMyUsage(): Usage {
    return supabase.postgrest
        .rpc("va_client_get_my_usage")
        .decodeSingleOrNull<Usage>()
        ?: throw Exception("No usage data found")
}
```

### Check Feature

```kotlin
data class FeatureCheck(
    val allowed: Boolean,
    val currentUsage: Int,
    val limitValue: Int,
    val remaining: Int,
    val planName: String,
    val upgradeRequired: Boolean
)

suspend fun canUseFeature(feature: String, amount: Int = 1): FeatureCheck {
    return supabase.postgrest
        .rpc("va_client_check_feature") {
            put("p_feature_key", feature)
            put("p_requested_amount", amount)
        }
        .decodeSingleOrNull<FeatureCheck>()
        ?: throw Exception("Feature check failed")
}

// Usage
val canChat = canUseFeature("max_minutes", 1)
if (!canChat.allowed) {
    showUpgradeDialog(canChat.planName)
}
```

### Call Backend API

```kotlin
suspend fun sendChatMessage(audioData: ByteArray): ByteArray {
    val userId = currentUser?.id ?: throw Exception("Not authenticated")

    // Check feature gate
    val canUse = canUseFeature("max_minutes")
    if (!canUse.allowed) {
        throw Exception("Limit reached: ${canUse}")
    }

    // Call backend
    val client = OkHttpClient()
    val requestBody = MultipartBody.Builder()
        .setType(MultipartBody.FORM)
        .addFormDataPart(
            "audio",
            "audio.wav",
            audioData.toRequestBody("audio/wav".toMediaType())
        )
        .build()

    val request = Request.Builder()
        .url("https://your-backend.com/chat")
        .addHeader("X-User-ID", userId)
        .post(requestBody)
        .build()

    return client.newCall(request).execute().use { response ->
        when (response.code) {
            200 -> response.body?.bytes() ?: throw Exception("Empty response")
            402 -> throw PaymentRequiredException("Upgrade required")
            else -> throw Exception("Server error: ${response.code}")
        }
    }
}
```

---

## 🌐 Web Integration (JavaScript/TypeScript)

### Setup

```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://your-project.supabase.co',
  'your-anon-key'  // NOT service role key!
)
```

### Authentication

```typescript
// Email/Password
async function signUp(email: string, password: string) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password
  })
  return { data, error }
}

async function signIn(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password
  })
  return { data, error }
}

// OAuth (Google, Apple, etc.)
async function signInWithGoogle() {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google'
  })
  return { data, error }
}

// Get current user
const { data: { user } } = await supabase.auth.getUser()

// Listen for auth changes
supabase.auth.onAuthStateChange((event, session) => {
  if (event === 'SIGNED_IN') {
    console.log('User signed in:', session?.user.id)
  } else if (event === 'SIGNED_OUT') {
    console.log('User signed out')
  }
})
```

### Check Subscription

```typescript
interface Subscription {
  plan_name: string
  display_name: string
  price_cents: number
  status: string
  current_period_start: string
  current_period_end: string
  days_remaining: number
}

async function getMySubscription(): Promise<Subscription | null> {
  const { data, error } = await supabase
    .rpc('va_client_get_my_subscription')

  if (error) throw error
  return data?.[0] || null
}
```

### Check Usage

```typescript
interface Usage {
  plan_name: string
  minutes_used: number
  minutes_limit: number
  usage_percentage: string
  assistants_count: number
  assistants_limit: number
  voice_clones_count: number
  voice_clones_limit: number
}

async function getMyUsage(): Promise<Usage | null> {
  const { data, error } = await supabase
    .rpc('va_client_get_my_usage')

  if (error) throw error
  return data?.[0] || null
}

// React Hook Example
function useUsage() {
  const [usage, setUsage] = useState<Usage | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getMyUsage()
      .then(setUsage)
      .finally(() => setLoading(false))
  }, [])

  const isNearLimit = useMemo(() => {
    if (!usage) return false
    const percentage = parseFloat(usage.usage_percentage.replace('%', ''))
    return percentage > 80
  }, [usage])

  return { usage, loading, isNearLimit }
}
```

### Check Feature

```typescript
interface FeatureCheck {
  allowed: boolean
  current_usage: number
  limit_value: number
  remaining: number
  plan_name: string
  upgrade_required: boolean
}

async function canUseFeature(
  feature: string,
  amount: number = 1
): Promise<FeatureCheck> {
  const { data, error } = await supabase.rpc('va_client_check_feature', {
    p_feature_key: feature,
    p_requested_amount: amount
  })

  if (error) throw error
  return data[0]
}

// Usage in component
async function handleStartChat() {
  const canChat = await canUseFeature('max_minutes')

  if (!canChat.allowed) {
    showUpgradeModal({
      message: `You've used ${canChat.current_usage} of ${canChat.limit_value} minutes`,
      currentPlan: canChat.plan_name
    })
    return
  }

  // Proceed with chat
  startChatSession()
}
```

### Call Backend API

```typescript
async function sendChatMessage(audioBlob: Blob): Promise<Blob> {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error('Not authenticated')

  // Check feature gate
  const canUse = await canUseFeature('max_minutes')
  if (!canUse.allowed) {
    throw new Error('Limit reached. Please upgrade.')
  }

  // Call backend
  const formData = new FormData()
  formData.append('audio', audioBlob, 'audio.wav')

  const response = await fetch('https://your-backend.com/chat', {
    method: 'POST',
    headers: {
      'X-User-ID': user.id
    },
    body: formData
  })

  if (response.status === 402) {
    throw new Error('Payment required. Please upgrade your plan.')
  }

  if (!response.ok) {
    throw new Error(`Server error: ${response.status}`)
  }

  return await response.blob()
}
```

### Get Available Plans

```typescript
interface Plan {
  plan_name: string
  display_name: string
  price_cents: number
  billing_interval: string
  features: Record<string, {
    value: any
    description: string
  }>
}

async function getAvailablePlans(): Promise<Plan[]> {
  const { data, error } = await supabase
    .rpc('va_client_get_available_plans')

  if (error) throw error
  return data
}

// React Component Example
function PricingTable() {
  const [plans, setPlans] = useState<Plan[]>([])

  useEffect(() => {
    getAvailablePlans().then(setPlans)
  }, [])

  return (
    <div className="pricing-grid">
      {plans.map(plan => (
        <PricingCard key={plan.plan_name} plan={plan} />
      ))}
    </div>
  )
}
```

---

## 🔄 Real-time Updates

### Listen for Subscription Changes

```typescript
// Subscribe to subscription changes
const subscription = supabase
  .channel('subscription-changes')
  .on(
    'postgres_changes',
    {
      event: '*',
      schema: 'public',
      table: 'va_user_subscriptions',
      filter: `user_id=eq.${user.id}`
    },
    (payload) => {
      console.log('Subscription changed:', payload)
      // Refresh subscription data
      refreshSubscription()
    }
  )
  .subscribe()

// Clean up
subscription.unsubscribe()
```

---

## 📊 Best Practices

### 1. Check Limits Before Actions
```typescript
// ✅ Good: Check before showing UI
const canClone = await canUseFeature('max_voice_clones')
if (canClone.allowed) {
  showVoiceCloningButton()
} else {
  showUpgradePrompt()
}

// ❌ Bad: Let user try and fail
// User clicks button → API fails → poor UX
```

### 2. Cache Subscription Data
```typescript
// Cache for 5 minutes
const CACHE_TTL = 5 * 60 * 1000
let cachedSubscription: Subscription | null = null
let cacheTime = 0

async function getSubscription() {
  if (cachedSubscription && Date.now() - cacheTime < CACHE_TTL) {
    return cachedSubscription
  }

  cachedSubscription = await getMySubscription()
  cacheTime = Date.now()
  return cachedSubscription
}
```

### 3. Show Usage Warnings
```typescript
// Warn at 80% usage
const usage = await getMyUsage()
const percentage = parseFloat(usage.usage_percentage.replace('%', ''))

if (percentage > 80 && percentage < 100) {
  showWarning(`You've used ${percentage}% of your monthly minutes`)
} else if (percentage >= 100) {
  showUpgradeRequired()
}
```

### 4. Graceful Degradation
```typescript
try {
  const audioResponse = await sendChatMessage(audioBlob)
  playAudio(audioResponse)
} catch (error) {
  if (error.message.includes('Limit reached')) {
    showUpgradeModal()
  } else if (error.message.includes('Payment required')) {
    showPaymentModal()
  } else {
    showGenericError()
  }
}
```

---

## 🔒 Security Checklist

- ✅ Use **anon key** in mobile/web apps (NOT service role key)
- ✅ Authenticate users with Supabase Auth
- ✅ Let RLS protect database access
- ✅ Call backend API for protected operations
- ✅ Backend uses service role key
- ✅ Feature gates enforced server-side
- ✅ Never trust client-side checks alone

---

## 🆘 Troubleshooting

### "Access denied" error
- Check you're using **anon key** (not service role key)
- Ensure user is authenticated
- Verify RLS policies allow the operation

### "Feature check returns null"
- User might not have a subscription yet
- Check they completed sign-up
- Verify trigger created subscription

### "Backend API returns 402"
- User hit their plan limit
- Show upgrade modal
- Don't retry - they need to upgrade

---

**Last Updated**: 2025-11-18
