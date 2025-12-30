import Foundation

/// Premier Voice Assistant SDK for iOS
public class PremierVoice {
    
    /// Shared instance for convenience
    public static let shared = PremierVoice()
    
    /// API base URL
    public var apiURL: String = "https://web-production-1b085.up.railway.app"
    
    /// Current user ID
    private var userId: String?
    
    /// URLSession for network requests
    private let session: URLSession
    
    public init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config)
    }
    
    // MARK: - Configuration
    
    /// Configure the SDK with user credentials
    public func configure(userId: String, apiURL: String? = nil) {
        self.userId = userId
        if let url = apiURL {
            self.apiURL = url
        }
    }
    
    // MARK: - Subscription & Usage
    
    /// Get user's current subscription
    public func getSubscription() async throws -> Subscription? {
        guard let userId = userId else {
            throw PremierVoiceError.notConfigured
        }
        
        let data = try await request(endpoint: "/subscription", userId: userId)
        let response = try JSONDecoder().decode(SubscriptionResponse.self, from: data)
        return response.subscription
    }
    
    /// Get user's current usage
    public func getUsage() async throws -> Usage {
        guard let userId = userId else {
            throw PremierVoiceError.notConfigured
        }
        
        let data = try await request(endpoint: "/usage", userId: userId)
        let response = try JSONDecoder().decode(UsageResponse.self, from: data)
        return response.usage
    }
    
    /// Get feature limits for current plan
    public func getFeatureLimits() async throws -> FeatureLimits {
        guard let userId = userId else {
            throw PremierVoiceError.notConfigured
        }
        
        let data = try await request(endpoint: "/feature-limits", userId: userId)
        return try JSONDecoder().decode(FeatureLimits.self, from: data)
    }
    
    // MARK: - Discount Codes
    
    /// Redeem a discount code
    public func redeemCode(_ code: String) async throws -> RedeemResult {
        guard let userId = userId else {
            throw PremierVoiceError.notConfigured
        }
        
        let body = ["code": code]
        let data = try await request(
            endpoint: "/codes/redeem",
            method: "POST",
            body: body,
            userId: userId
        )
        return try JSONDecoder().decode(RedeemResult.self, from: data)
    }
    
    // MARK: - Payments
    
    /// Create a checkout session for plan upgrade
    public func createCheckoutSession(
        planName: String,
        successURL: String,
        cancelURL: String
    ) async throws -> CheckoutSession {
        guard let userId = userId else {
            throw PremierVoiceError.notConfigured
        }
        
        let body: [String: Any] = [
            "plan_name": planName,
            "success_url": successURL,
            "cancel_url": cancelURL
        ]
        
        let data = try await request(
            endpoint: "/payments/create-checkout",
            method: "POST",
            body: body,
            userId: userId
        )
        return try JSONDecoder().decode(CheckoutSession.self, from: data)
    }
    
    /// Create a billing portal session
    public func createPortalSession(returnURL: String) async throws -> PortalSession {
        guard let userId = userId else {
            throw PremierVoiceError.notConfigured
        }
        
        let body = ["return_url": returnURL]
        let data = try await request(
            endpoint: "/payments/create-portal",
            method: "POST",
            body: body,
            userId: userId
        )
        return try JSONDecoder().decode(PortalSession.self, from: data)
    }
    
    // MARK: - Network
    
    private func request(
        endpoint: String,
        method: String = "GET",
        body: [String: Any]? = nil,
        userId: String? = nil
    ) async throws -> Data {
        guard let url = URL(string: apiURL + endpoint) else {
            throw PremierVoiceError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let userId = userId {
            request.setValue(userId, forHTTPHeaderField: "X-User-ID")
        }
        
        if let body = body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw PremierVoiceError.invalidResponse
        }
        
        guard (200...299).contains(httpResponse.statusCode) else {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw PremierVoiceError.apiError(errorResponse.detail)
            }
            throw PremierVoiceError.httpError(httpResponse.statusCode)
        }
        
        return data
    }
}

// MARK: - Models

public struct Subscription: Codable {
    public let planName: String
    public let displayName: String
    public let priceCents: Int
    public let status: String
    public let currentPeriodStart: String
    public let currentPeriodEnd: String
    
    enum CodingKeys: String, CodingKey {
        case planName = "plan_name"
        case displayName = "display_name"
        case priceCents = "price_cents"
        case status
        case currentPeriodStart = "current_period_start"
        case currentPeriodEnd = "current_period_end"
    }
}

public struct Usage: Codable {
    public let minutesUsed: Int
    public let bonusMinutes: Int?
    public let conversationsCount: Int
    public let voiceClonesCount: Int
    public let assistantsCount: Int
    
    enum CodingKeys: String, CodingKey {
        case minutesUsed = "minutes_used"
        case bonusMinutes = "bonus_minutes"
        case conversationsCount = "conversations_count"
        case voiceClonesCount = "voice_clones_count"
        case assistantsCount = "assistants_count"
    }
}

public struct FeatureLimits: Codable {
    public let plan: String
    public let displayName: String
    public let limits: Limits
    public let currentUsage: CurrentUsage
    
    enum CodingKeys: String, CodingKey {
        case plan
        case displayName = "display_name"
        case limits
        case currentUsage = "current_usage"
    }
    
    public struct Limits: Codable {
        public let maxMinutes: Int
        public let maxAssistants: Int
        public let maxVoiceClones: Int
        public let customVoices: Bool
        public let apiAccess: Bool
        public let prioritySupport: Bool
        
        enum CodingKeys: String, CodingKey {
            case maxMinutes = "max_minutes"
            case maxAssistants = "max_assistants"
            case maxVoiceClones = "max_voice_clones"
            case customVoices = "custom_voices"
            case apiAccess = "api_access"
            case prioritySupport = "priority_support"
        }
    }
    
    public struct CurrentUsage: Codable {
        public let minutesUsed: Int
        public let assistantsCount: Int
        public let voiceClonesCount: Int
        
        enum CodingKeys: String, CodingKey {
            case minutesUsed = "minutes_used"
            case assistantsCount = "assistants_count"
            case voiceClonesCount = "voice_clones_count"
        }
    }
}

public struct RedeemResult: Codable {
    public let success: Bool
    public let message: String
    public let minutesAdded: Int?
    
    enum CodingKeys: String, CodingKey {
        case success, message
        case minutesAdded = "minutes_added"
    }
}

public struct CheckoutSession: Codable {
    public let url: String
    public let sessionId: String
    
    enum CodingKeys: String, CodingKey {
        case url
        case sessionId = "session_id"
    }
}

public struct PortalSession: Codable {
    public let url: String
}

// MARK: - Internal Response Types

struct SubscriptionResponse: Codable {
    let subscription: Subscription?
}

struct UsageResponse: Codable {
    let usage: Usage
}

struct ErrorResponse: Codable {
    let detail: String
}

// MARK: - Errors

public enum PremierVoiceError: LocalizedError {
    case notConfigured
    case invalidURL
    case invalidResponse
    case httpError(Int)
    case apiError(String)
    
    public var errorDescription: String? {
        switch self {
        case .notConfigured:
            return "SDK not configured. Call configure(userId:) first."
        case .invalidURL:
            return "Invalid API URL"
        case .invalidResponse:
            return "Invalid response from server"
        case .httpError(let code):
            return "HTTP error: \(code)"
        case .apiError(let message):
            return message
        }
    }
}
