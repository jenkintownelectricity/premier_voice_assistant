# Premier Voice iOS SDK

Swift SDK for integrating Premier Voice Assistant into your iOS apps.

## Installation

### Swift Package Manager

Add this package to your `Package.swift`:

```swift
dependencies: [
    .package(url: "https://github.com/hive215/premier-voice-ios.git", from: "1.0.0")
]
```

Or in Xcode: File > Add Packages > Enter the repository URL.

## Quick Start

```swift
import PremierVoice

// Configure the SDK
PremierVoice.shared.configure(userId: "user-id-from-auth")

// Get subscription info
Task {
    do {
        let subscription = try await PremierVoice.shared.getSubscription()
        print("Plan: \(subscription?.displayName ?? "Free")")
        
        let usage = try await PremierVoice.shared.getUsage()
        print("Minutes used: \(usage.minutesUsed)")
    } catch {
        print("Error: \(error.localizedDescription)")
    }
}
```

## API Reference

### Configuration

```swift
// Configure with user ID
PremierVoice.shared.configure(userId: "your-user-id")

// Configure with custom API URL
PremierVoice.shared.configure(
    userId: "your-user-id",
    apiURL: "https://your-api.com"
)
```

### Subscription & Usage

```swift
// Get subscription
let subscription = try await PremierVoice.shared.getSubscription()

// Get usage stats
let usage = try await PremierVoice.shared.getUsage()

// Get feature limits
let limits = try await PremierVoice.shared.getFeatureLimits()
```

### Discount Codes

```swift
// Redeem a code
let result = try await PremierVoice.shared.redeemCode("WELCOME2024")
if result.success {
    print("Added \(result.minutesAdded ?? 0) minutes!")
}
```

### Payments

```swift
// Create checkout session
let checkout = try await PremierVoice.shared.createCheckoutSession(
    planName: "pro",
    successURL: "myapp://success",
    cancelURL: "myapp://cancel"
)
// Open checkout.url in Safari or WKWebView

// Create billing portal
let portal = try await PremierVoice.shared.createPortalSession(
    returnURL: "myapp://billing"
)
```

## Error Handling

```swift
do {
    let usage = try await PremierVoice.shared.getUsage()
} catch PremierVoiceError.notConfigured {
    print("Call configure() first")
} catch PremierVoiceError.apiError(let message) {
    print("API error: \(message)")
} catch {
    print("Error: \(error)")
}
```

## Requirements

- iOS 14.0+
- macOS 11.0+
- Swift 5.7+

## License

MIT License - See LICENSE file
