"""
Feature gate middleware for Premier Voice Assistant.
Enforces subscription plan limits and tracks usage.
"""
from typing import Optional, Dict, Any, Tuple
from functools import wraps
import logging
from datetime import datetime
from backend.supabase_client import get_supabase

logger = logging.getLogger(__name__)


class FeatureGateError(Exception):
    """Exception raised when a feature gate check fails."""
    def __init__(self, message: str, feature_key: str, limit: int, current: int):
        self.message = message
        self.feature_key = feature_key
        self.limit = limit
        self.current = current
        super().__init__(self.message)


class FeatureGate:
    """
    Feature gate enforcement for subscription-based limits.
    """

    def __init__(self):
        self.supabase = get_supabase()

    def check_feature(
        self,
        user_id: str,
        feature_key: str,
        requested_amount: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if user can perform an action based on their subscription plan.

        Args:
            user_id: User ID
            feature_key: Feature to check (e.g., 'max_minutes', 'max_assistants')
            requested_amount: Amount requested (default 1)

        Returns:
            Tuple of (allowed: bool, details: dict)

        Raises:
            FeatureGateError: If feature check fails
        """
        try:
            # Call the Supabase function to check feature gate
            result = self.supabase.client.rpc(
                "va_check_feature_gate",
                {
                    "p_user_id": user_id,
                    "p_feature_key": feature_key,
                    "p_requested_amount": requested_amount,
                }
            ).execute()

            if not result.data or len(result.data) == 0:
                logger.warning(f"No result from va_check_feature_gate for user {user_id} - failing open")
                # Fail open - allow access if no subscription data found
                return True, {
                    "allowed": True,
                    "current_usage": 0,
                    "limit_value": -1,
                    "remaining": float('inf'),
                    "error": "No subscription data - defaulting to allow",
                    "fallback": True
                }

            gate_result = result.data[0]

            # Handle -1 as unlimited - always allow
            limit_value = gate_result.get("limit_value", 0)
            if limit_value == -1:
                gate_result["allowed"] = True
                gate_result["remaining"] = float('inf')

            return gate_result["allowed"], gate_result

        except Exception as e:
            logger.error(f"Error checking feature gate: {e}")
            # Fail open for critical errors (don't block users during development)
            logger.warning(f"Failing open for user {user_id} on feature {feature_key}")
            return True, {
                "allowed": True,
                "current_usage": 0,
                "limit_value": -1,
                "remaining": float('inf'),
                "error": str(e),
                "fallback": True
            }

    def enforce_feature(
        self,
        user_id: str,
        feature_key: str,
        requested_amount: int = 1
    ) -> Dict[str, Any]:
        """
        Enforce feature gate - raises exception if not allowed.

        Args:
            user_id: User ID
            feature_key: Feature to check
            requested_amount: Amount requested

        Returns:
            Feature gate details

        Raises:
            FeatureGateError: If user doesn't have access
        """
        allowed, details = self.check_feature(user_id, feature_key, requested_amount)

        if not allowed:
            limit = details.get("limit_value", 0)
            current = details.get("current_usage", 0)

            # Generate user-friendly error message
            if feature_key == "max_minutes":
                message = (
                    f"Monthly minute limit reached. "
                    f"You've used {current} of {limit} minutes this billing period. "
                    f"Upgrade your plan for more minutes."
                )
            elif feature_key == "max_assistants":
                message = (
                    f"Assistant limit reached. "
                    f"You have {current} of {limit} assistants. "
                    f"Upgrade your plan to create more assistants."
                )
            elif feature_key == "max_voice_clones":
                message = (
                    f"Voice clone limit reached. "
                    f"You have {current} of {limit} custom voices. "
                    f"Upgrade your plan for more voice clones."
                )
            elif feature_key == "custom_voices":
                message = (
                    "Custom voices not available on your plan. "
                    "Upgrade to Starter or higher to create custom voices."
                )
            else:
                message = (
                    f"Feature '{feature_key}' not available on your plan. "
                    f"Please upgrade your subscription."
                )

            raise FeatureGateError(
                message=message,
                feature_key=feature_key,
                limit=limit,
                current=current
            )

        return details

    def increment_usage(
        self,
        user_id: str,
        minutes: int = 0,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Increment usage counters for a user.

        Args:
            user_id: User ID
            minutes: Minutes to add
            metadata: Optional metadata to store

        Returns:
            Success status
        """
        try:
            self.supabase.client.rpc(
                "va_increment_usage",
                {
                    "p_user_id": user_id,
                    "p_minutes": minutes,
                    "p_metadata": metadata or {}
                }
            ).execute()

            logger.info(f"Incremented usage for user {user_id}: +{minutes} minutes")
            return True

        except Exception as e:
            logger.error(f"Error incrementing usage: {e}")
            # Don't fail the request if usage tracking fails
            return False

    def get_user_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's current subscription plan.

        Args:
            user_id: User ID

        Returns:
            Plan details or None
        """
        try:
            result = self.supabase.client.rpc(
                "va_get_user_plan",
                {"p_user_id": user_id}
            ).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]

            return None

        except Exception as e:
            logger.error(f"Error getting user plan: {e}")
            return None

    def get_user_usage(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's current usage for the billing period.

        Args:
            user_id: User ID

        Returns:
            Usage details or None
        """
        try:
            # Get current period usage
            result = self.supabase.client.from_("va_current_usage_summary") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()

            if result.data and len(result.data) > 0:
                return result.data[0]

            return None

        except Exception as e:
            logger.error(f"Error getting user usage: {e}")
            return None


# Singleton instance
_feature_gate: Optional[FeatureGate] = None


def get_feature_gate() -> FeatureGate:
    """Get or create FeatureGate singleton."""
    global _feature_gate
    if _feature_gate is None:
        _feature_gate = FeatureGate()
    return _feature_gate


# Decorator for endpoint protection
def require_feature(feature_key: str, amount: int = 1):
    """
    Decorator to enforce feature gates on API endpoints.

    Usage:
        @require_feature('max_minutes', 1)
        def transcribe_audio(user_id: str):
            # This will only execute if user has minutes available
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract user_id from kwargs or args
            user_id = kwargs.get("user_id") or (args[0] if args else None)

            if not user_id:
                raise ValueError("user_id is required for feature gate enforcement")

            # Check feature gate
            feature_gate = get_feature_gate()
            feature_gate.enforce_feature(user_id, feature_key, amount)

            # Execute the function
            return func(*args, **kwargs)

        return wrapper
    return decorator


def track_usage(minutes_key: str = "duration_minutes"):
    """
    Decorator to track usage after endpoint execution.

    Usage:
        @track_usage(minutes_key='duration_minutes')
        def process_audio(user_id: str, duration_minutes: int):
            # After this executes, usage will be tracked
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract user_id
            user_id = kwargs.get("user_id") or (args[0] if args else None)

            if not user_id:
                logger.warning("user_id not found, skipping usage tracking")
                return func(*args, **kwargs)

            # Execute the function
            result = func(*args, **kwargs)

            # Track usage after successful execution
            minutes = kwargs.get(minutes_key, 0)
            if minutes > 0:
                feature_gate = get_feature_gate()
                feature_gate.increment_usage(
                    user_id=user_id,
                    minutes=minutes,
                    metadata={
                        "function": func.__name__,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            return result

        return wrapper
    return decorator


# Admin helper functions
def admin_upgrade_user(user_id: str, plan_name: str) -> bool:
    """
    Admin function to upgrade a user's subscription.

    Args:
        user_id: User ID
        plan_name: Plan name ('free', 'starter', 'pro', 'enterprise')

    Returns:
        Success status
    """
    try:
        supabase = get_supabase()
        supabase.client.rpc(
            "va_admin_upgrade_user",
            {
                "p_user_id": user_id,
                "p_plan_name": plan_name
            }
        ).execute()

        logger.info(f"✅ Upgraded user {user_id} to {plan_name} plan")
        return True

    except Exception as e:
        logger.error(f"❌ Error upgrading user: {e}")
        return False


def get_plan_features(plan_name: str) -> Dict[str, Any]:
    """
    Get all features for a specific plan.

    Args:
        plan_name: Plan name

    Returns:
        Dictionary of feature_key -> feature_value
    """
    try:
        supabase = get_supabase()

        # Get plan ID
        plan_result = supabase.client.table("va_subscription_plans") \
            .select("id") \
            .eq("plan_name", plan_name) \
            .execute()

        if not plan_result.data:
            return {}

        plan_id = plan_result.data[0]["id"]

        # Get all features for this plan
        features_result = supabase.client.table("va_plan_features") \
            .select("feature_key, feature_value") \
            .eq("plan_id", plan_id) \
            .execute()

        return {
            feature["feature_key"]: feature["feature_value"]
            for feature in features_result.data
        }

    except Exception as e:
        logger.error(f"Error getting plan features: {e}")
        return {}
