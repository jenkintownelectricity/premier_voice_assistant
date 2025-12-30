# Premier Voice Android SDK

Kotlin SDK for integrating Premier Voice Assistant into your Android apps.

## Installation

### Gradle

Add to your `build.gradle.kts`:

```kotlin
dependencies {
    implementation("com.hive215:premiervoice:1.0.0")
}
```

Or if using `build.gradle`:

```groovy
dependencies {
    implementation 'com.hive215:premiervoice:1.0.0'
}
```

## Quick Start

```kotlin
import com.hive215.premiervoice.PremierVoice

// Configure the SDK
val sdk = PremierVoice.getInstance()
sdk.configure(userId = "user-id-from-auth")

// Get subscription info
lifecycleScope.launch {
    try {
        val subscription = sdk.getSubscription()
        println("Plan: ${subscription?.displayName ?: "Free"}")
        
        val usage = sdk.getUsage()
        println("Minutes used: ${usage.minutesUsed}")
    } catch (e: Exception) {
        println("Error: ${e.message}")
    }
}
```

## API Reference

### Configuration

```kotlin
val sdk = PremierVoice.getInstance()

// Configure with user ID
sdk.configure(userId = "your-user-id")

// Configure with custom API URL
sdk.configure(
    userId = "your-user-id",
    apiURL = "https://your-api.com"
)
```

### Subscription & Usage

```kotlin
// Get subscription
val subscription = sdk.getSubscription()

// Get usage stats
val usage = sdk.getUsage()

// Get feature limits
val limits = sdk.getFeatureLimits()
```

### Discount Codes

```kotlin
// Redeem a code
val result = sdk.redeemCode("WELCOME2024")
if (result.success) {
    println("Added ${result.minutesAdded ?: 0} minutes!")
}
```

### Payments

```kotlin
// Create checkout session
val checkout = sdk.createCheckoutSession(
    planName = "pro",
    successURL = "myapp://success",
    cancelURL = "myapp://cancel"
)
// Open checkout.url in Chrome Custom Tabs or WebView

// Create billing portal
val portal = sdk.createPortalSession(
    returnURL = "myapp://billing"
)
```

## Error Handling

```kotlin
try {
    val usage = sdk.getUsage()
} catch (e: PremierVoiceException.NotConfigured) {
    println("Call configure() first")
} catch (e: PremierVoiceException.ApiError) {
    println("API error: ${e.message}")
} catch (e: Exception) {
    println("Error: ${e.message}")
}
```

## Permissions

Add to your `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

## Requirements

- Android SDK 24+
- Kotlin 1.8+

## Dependencies

- OkHttp 4.12.0
- Gson 2.10.1
- Kotlin Coroutines 1.7.3

## License

MIT License - See LICENSE file
