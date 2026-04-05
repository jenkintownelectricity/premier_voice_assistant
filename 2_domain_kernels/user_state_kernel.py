"""
HIVE215 User State Kernel

Typed user state management. Supabase data is PARTIALLY TRUSTED and must
be normalized and validated before use in any execution decision.

Trust model:
    - Supabase query results: PARTIALLY TRUSTED
    - Typed user state: TRUSTED (after validation)
    - Browser-sourced user claims: UNTRUSTED (rejected)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class UserStateSource(Enum):
    """Source of user state data."""
    SUPABASE = "supabase"              # PARTIALLY TRUSTED
    SESSION_KERNEL = "session_kernel"  # TRUSTED
    BROWSER_CLAIM = "browser_claim"    # UNTRUSTED
    MOBILE_CLAIM = "mobile_claim"      # UNTRUSTED
    EXTERNAL_API = "external_api"      # UNTRUSTED


class NormalizationVerdict(Enum):
    """Result of user state normalization."""
    ACCEPTED = "accepted"
    REJECTED_UNTRUSTED_SOURCE = "rejected_untrusted_source"
    REJECTED_MISSING_REQUIRED = "rejected_missing_required"
    REJECTED_INVALID_TYPE = "rejected_invalid_type"
    REJECTED_SCHEMA_VIOLATION = "rejected_schema_violation"


class SubscriptionTier(Enum):
    """Valid subscription tiers."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


UNTRUSTED_SOURCES = {
    UserStateSource.BROWSER_CLAIM,
    UserStateSource.MOBILE_CLAIM,
    UserStateSource.EXTERNAL_API,
}

REQUIRED_USER_FIELDS = {"user_id", "email"}


@dataclass(frozen=True)
class TypedUserState:
    """Typed, validated user state record. Immutable once created."""
    user_id: str
    email: str
    display_name: Optional[str]
    subscription_tier: SubscriptionTier
    is_active: bool
    created_utc: Optional[str]
    last_seen_utc: Optional[str]
    metadata: dict[str, str] = field(default_factory=dict)
    normalization_source: UserStateSource = UserStateSource.SUPABASE
    normalization_utc: str = ""


@dataclass(frozen=True)
class UserStateReceipt:
    """Receipt for user state normalization."""
    receipt_id: str
    user_id: Optional[str]
    source: UserStateSource
    source_trust_level: str
    verdict: NormalizationVerdict
    timestamp_utc: str
    rejection_reason: Optional[str] = None


def _safe_str(value: Any, field_name: str) -> Optional[str]:
    """Safely convert a value to string, returning None if invalid."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() if value.strip() else None
    return str(value)


def _resolve_tier(raw_tier: Any) -> SubscriptionTier:
    """Resolve raw tier value to typed enum. Defaults to FREE on unrecognized."""
    if raw_tier is None:
        return SubscriptionTier.FREE
    tier_str = str(raw_tier).lower().strip()
    try:
        return SubscriptionTier(tier_str)
    except ValueError:
        return SubscriptionTier.FREE


class UserStateKernel:
    """
    Typed user state management.

    Normalizes PARTIALLY TRUSTED Supabase data into typed user state records.
    Rejects UNTRUSTED sources (browser, mobile, external API) outright.
    """

    def __init__(self) -> None:
        self._cache: dict[str, TypedUserState] = {}

    def normalize_from_supabase(
        self, raw_payload: dict[str, Any]
    ) -> tuple[Optional[TypedUserState], UserStateReceipt]:
        """
        Normalize a raw Supabase user payload into typed state.
        Returns (typed_state, receipt). typed_state is None on rejection.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        receipt_id = str(uuid.uuid4())

        if not isinstance(raw_payload, dict):
            return None, UserStateReceipt(
                receipt_id=receipt_id,
                user_id=None,
                source=UserStateSource.SUPABASE,
                source_trust_level="PARTIALLY_TRUSTED",
                verdict=NormalizationVerdict.REJECTED_INVALID_TYPE,
                timestamp_utc=now_utc,
                rejection_reason=f"expected dict, got {type(raw_payload).__name__}",
            )

        # Check required fields
        missing = REQUIRED_USER_FIELDS - set(raw_payload.keys())
        if missing:
            return None, UserStateReceipt(
                receipt_id=receipt_id,
                user_id=_safe_str(raw_payload.get("user_id"), "user_id"),
                source=UserStateSource.SUPABASE,
                source_trust_level="PARTIALLY_TRUSTED",
                verdict=NormalizationVerdict.REJECTED_MISSING_REQUIRED,
                timestamp_utc=now_utc,
                rejection_reason=f"missing required fields: {sorted(missing)}",
            )

        user_id = _safe_str(raw_payload.get("user_id"), "user_id")
        email = _safe_str(raw_payload.get("email"), "email")

        if not user_id or not email:
            return None, UserStateReceipt(
                receipt_id=receipt_id,
                user_id=user_id,
                source=UserStateSource.SUPABASE,
                source_trust_level="PARTIALLY_TRUSTED",
                verdict=NormalizationVerdict.REJECTED_MISSING_REQUIRED,
                timestamp_utc=now_utc,
                rejection_reason="user_id or email is empty after normalization",
            )

        typed_state = TypedUserState(
            user_id=user_id,
            email=email,
            display_name=_safe_str(raw_payload.get("display_name"), "display_name"),
            subscription_tier=_resolve_tier(raw_payload.get("subscription_tier")),
            is_active=bool(raw_payload.get("is_active", True)),
            created_utc=_safe_str(raw_payload.get("created_at"), "created_at"),
            last_seen_utc=_safe_str(raw_payload.get("last_seen_at"), "last_seen_at"),
            metadata={
                k: str(v)
                for k, v in raw_payload.items()
                if k not in REQUIRED_USER_FIELDS
                and k not in {"display_name", "subscription_tier", "is_active", "created_at", "last_seen_at"}
                and v is not None
            },
            normalization_source=UserStateSource.SUPABASE,
            normalization_utc=now_utc,
        )

        self._cache[user_id] = typed_state

        receipt = UserStateReceipt(
            receipt_id=receipt_id,
            user_id=user_id,
            source=UserStateSource.SUPABASE,
            source_trust_level="PARTIALLY_TRUSTED",
            verdict=NormalizationVerdict.ACCEPTED,
            timestamp_utc=now_utc,
        )

        return typed_state, receipt

    def reject_untrusted(
        self, source: UserStateSource, raw_payload: Any
    ) -> UserStateReceipt:
        """
        Explicitly reject user state from untrusted sources.
        This is the only valid response to browser/mobile/external state claims.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        user_id = None
        if isinstance(raw_payload, dict):
            user_id = _safe_str(raw_payload.get("user_id"), "user_id")

        return UserStateReceipt(
            receipt_id=str(uuid.uuid4()),
            user_id=user_id,
            source=source,
            source_trust_level="UNTRUSTED",
            verdict=NormalizationVerdict.REJECTED_UNTRUSTED_SOURCE,
            timestamp_utc=now_utc,
            rejection_reason=f"source {source.value} is UNTRUSTED; user state must come from Supabase or session kernel",
        )

    def get_cached(self, user_id: str) -> Optional[TypedUserState]:
        """Get cached typed user state. Returns None if not cached."""
        return self._cache.get(user_id)

    def invalidate(self, user_id: str) -> bool:
        """Invalidate cached user state. Returns True if was cached."""
        return self._cache.pop(user_id, None) is not None
