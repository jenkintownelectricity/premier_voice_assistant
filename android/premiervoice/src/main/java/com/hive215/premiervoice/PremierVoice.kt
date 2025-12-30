package com.hive215.premiervoice

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * Premier Voice Assistant SDK for Android
 */
class PremierVoice private constructor() {
    
    companion object {
        @Volatile
        private var instance: PremierVoice? = null
        
        fun getInstance(): PremierVoice {
            return instance ?: synchronized(this) {
                instance ?: PremierVoice().also { instance = it }
            }
        }
    }
    
    var apiURL: String = "https://web-production-1b085.up.railway.app"
        private set
    
    private var userId: String? = null
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()
    
    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()
    
    // MARK: - Configuration
    
    /**
     * Configure the SDK with user credentials
     */
    fun configure(userId: String, apiURL: String? = null) {
        this.userId = userId
        apiURL?.let { this.apiURL = it }
    }
    
    // MARK: - Subscription & Usage
    
    /**
     * Get user's current subscription
     */
    suspend fun getSubscription(): Subscription? {
        val userId = this.userId ?: throw PremierVoiceException.NotConfigured()
        
        val response = request<SubscriptionResponse>("/subscription", userId = userId)
        return response.subscription
    }
    
    /**
     * Get user's current usage
     */
    suspend fun getUsage(): Usage {
        val userId = this.userId ?: throw PremierVoiceException.NotConfigured()
        
        val response = request<UsageResponse>("/usage", userId = userId)
        return response.usage
    }
    
    /**
     * Get feature limits for current plan
     */
    suspend fun getFeatureLimits(): FeatureLimits {
        val userId = this.userId ?: throw PremierVoiceException.NotConfigured()
        
        return request("/feature-limits", userId = userId)
    }
    
    // MARK: - Discount Codes
    
    /**
     * Redeem a discount code
     */
    suspend fun redeemCode(code: String): RedeemResult {
        val userId = this.userId ?: throw PremierVoiceException.NotConfigured()
        
        val body = mapOf("code" to code)
        return request("/codes/redeem", method = "POST", body = body, userId = userId)
    }
    
    // MARK: - Payments
    
    /**
     * Create a checkout session for plan upgrade
     */
    suspend fun createCheckoutSession(
        planName: String,
        successURL: String,
        cancelURL: String
    ): CheckoutSession {
        val userId = this.userId ?: throw PremierVoiceException.NotConfigured()
        
        val body = mapOf(
            "plan_name" to planName,
            "success_url" to successURL,
            "cancel_url" to cancelURL
        )
        
        return request("/payments/create-checkout", method = "POST", body = body, userId = userId)
    }
    
    /**
     * Create a billing portal session
     */
    suspend fun createPortalSession(returnURL: String): PortalSession {
        val userId = this.userId ?: throw PremierVoiceException.NotConfigured()
        
        val body = mapOf("return_url" to returnURL)
        return request("/payments/create-portal", method = "POST", body = body, userId = userId)
    }
    
    // MARK: - Network
    
    private suspend inline fun <reified T> request(
        endpoint: String,
        method: String = "GET",
        body: Map<String, Any>? = null,
        userId: String? = null
    ): T = withContext(Dispatchers.IO) {
        val url = apiURL + endpoint
        
        val requestBuilder = Request.Builder()
            .url(url)
            .header("Content-Type", "application/json")
        
        userId?.let {
            requestBuilder.header("X-User-ID", it)
        }
        
        when (method) {
            "POST" -> {
                val jsonBody = gson.toJson(body ?: emptyMap<String, Any>())
                requestBuilder.post(jsonBody.toRequestBody(jsonMediaType))
            }
            "PUT" -> {
                val jsonBody = gson.toJson(body ?: emptyMap<String, Any>())
                requestBuilder.put(jsonBody.toRequestBody(jsonMediaType))
            }
            "DELETE" -> requestBuilder.delete()
            else -> requestBuilder.get()
        }
        
        val response = client.newCall(requestBuilder.build()).execute()
        val responseBody = response.body?.string() ?: ""
        
        if (!response.isSuccessful) {
            val errorResponse = try {
                gson.fromJson(responseBody, ErrorResponse::class.java)
            } catch (e: Exception) {
                null
            }
            
            throw PremierVoiceException.ApiError(
                errorResponse?.detail ?: "HTTP error: ${response.code}"
            )
        }
        
        gson.fromJson(responseBody, T::class.java)
    }
}

// MARK: - Models

data class Subscription(
    @SerializedName("plan_name") val planName: String,
    @SerializedName("display_name") val displayName: String,
    @SerializedName("price_cents") val priceCents: Int,
    val status: String,
    @SerializedName("current_period_start") val currentPeriodStart: String,
    @SerializedName("current_period_end") val currentPeriodEnd: String
)

data class Usage(
    @SerializedName("minutes_used") val minutesUsed: Int,
    @SerializedName("bonus_minutes") val bonusMinutes: Int?,
    @SerializedName("conversations_count") val conversationsCount: Int,
    @SerializedName("voice_clones_count") val voiceClonesCount: Int,
    @SerializedName("assistants_count") val assistantsCount: Int
)

data class FeatureLimits(
    val plan: String,
    @SerializedName("display_name") val displayName: String,
    val limits: Limits,
    @SerializedName("current_usage") val currentUsage: CurrentUsage
) {
    data class Limits(
        @SerializedName("max_minutes") val maxMinutes: Int,
        @SerializedName("max_assistants") val maxAssistants: Int,
        @SerializedName("max_voice_clones") val maxVoiceClones: Int,
        @SerializedName("custom_voices") val customVoices: Boolean,
        @SerializedName("api_access") val apiAccess: Boolean,
        @SerializedName("priority_support") val prioritySupport: Boolean
    )
    
    data class CurrentUsage(
        @SerializedName("minutes_used") val minutesUsed: Int,
        @SerializedName("assistants_count") val assistantsCount: Int,
        @SerializedName("voice_clones_count") val voiceClonesCount: Int
    )
}

data class RedeemResult(
    val success: Boolean,
    val message: String,
    @SerializedName("minutes_added") val minutesAdded: Int?
)

data class CheckoutSession(
    val url: String,
    @SerializedName("session_id") val sessionId: String
)

data class PortalSession(
    val url: String
)

// Internal response types
internal data class SubscriptionResponse(val subscription: Subscription?)
internal data class UsageResponse(val usage: Usage)
internal data class ErrorResponse(val detail: String)

// MARK: - Exceptions

sealed class PremierVoiceException(message: String) : Exception(message) {
    class NotConfigured : PremierVoiceException("SDK not configured. Call configure(userId) first.")
    class ApiError(message: String) : PremierVoiceException(message)
}
