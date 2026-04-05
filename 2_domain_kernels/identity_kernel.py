"""
HIVE215 Identity Kernel

Identity verification and speaker locking. Wraps the existing Iron Ear
system (packages/iron_ear/) with governance typing and receipting.

Iron Ear Stack:
    V1: Debounce -- door slams, coughs (<300ms)
    V2: Speaker Locking -- background voices (volume fingerprint, 60% threshold)
    V3: Identity Lock -- ML fingerprint (256-dim Resemblyzer embeddings)

Trust model:
    - Audio frames: UNTRUSTED (raw from LiveKit)
    - Speaker embedding: PARTIALLY TRUSTED (ML-generated, probabilistic)
    - Identity verdict: TRUSTED (after threshold validation)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class IronEarVersion(Enum):
    """Iron Ear filtering versions."""
    V1_DEBOUNCE = "v1_debounce"
    V2_SPEAKER_LOCK = "v2_speaker_lock"
    V3_IDENTITY_LOCK = "v3_identity_lock"


class IdentityState(Enum):
    """Current identity verification state for a session."""
    UNVERIFIED = "unverified"
    CHALLENGE_PENDING = "challenge_pending"  # Honeypot question asked
    ENROLLING = "enrolling"                  # Collecting voice embedding
    LOCKED = "locked"                        # Identity confirmed and locked
    REJECTED = "rejected"                    # Speaker does not match


class IdentityVerdict(Enum):
    """Result of an identity check."""
    MATCH = "match"
    NO_MATCH = "no_match"
    INSUFFICIENT_AUDIO = "insufficient_audio"
    ENROLLMENT_NEEDED = "enrollment_needed"
    ERROR = "error"


@dataclass
class SpeakerProfile:
    """Typed speaker profile. Wraps Resemblyzer embedding."""
    profile_id: str
    session_id: str
    embedding_dimensions: int  # Expected: 256 for Resemblyzer
    enrollment_duration_ms: int
    enrolled_utc: str
    confidence_threshold: float
    is_active: bool

    def validate_dimensions(self) -> bool:
        """Validate embedding dimensions match expected Resemblyzer output."""
        return self.embedding_dimensions == 256


@dataclass(frozen=True)
class IdentityCheckResult:
    """Result of an identity verification check."""
    check_id: str
    session_id: str
    profile_id: Optional[str]
    verdict: IdentityVerdict
    similarity_score: Optional[float]
    threshold: float
    iron_ear_version: IronEarVersion
    timestamp_utc: str
    rejection_reason: Optional[str] = None


@dataclass(frozen=True)
class IdentityReceipt:
    """Receipt for identity operations."""
    receipt_id: str
    session_id: str
    operation: str
    identity_state_before: IdentityState
    identity_state_after: IdentityState
    verdict: Optional[IdentityVerdict]
    timestamp_utc: str
    details: Optional[str] = None


# Default thresholds matching Iron Ear V3 implementation
DEFAULT_SIMILARITY_THRESHOLD = 0.75
MINIMUM_ENROLLMENT_DURATION_MS = 10000  # 10 seconds of speech for enrollment
RESEMBLYZER_DIMENSIONS = 256


class IdentityKernel:
    """
    Identity verification and speaker locking.

    Wraps the Iron Ear system with typed governance. All identity decisions
    are receipted. The kernel does not directly process audio -- it manages
    state and delegates to the Iron Ear adapters.
    """

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        min_enrollment_duration_ms: int = MINIMUM_ENROLLMENT_DURATION_MS,
    ) -> None:
        self._similarity_threshold = similarity_threshold
        self._min_enrollment_duration_ms = min_enrollment_duration_ms
        self._session_states: dict[str, IdentityState] = {}
        self._profiles: dict[str, SpeakerProfile] = {}

    def initialize_session(self, session_id: str) -> IdentityReceipt:
        """Initialize identity tracking for a session."""
        now_utc = datetime.now(timezone.utc).isoformat()
        self._session_states[session_id] = IdentityState.UNVERIFIED
        return IdentityReceipt(
            receipt_id=str(uuid.uuid4()),
            session_id=session_id,
            operation="initialize",
            identity_state_before=IdentityState.UNVERIFIED,
            identity_state_after=IdentityState.UNVERIFIED,
            verdict=None,
            timestamp_utc=now_utc,
        )

    def begin_challenge(self, session_id: str) -> IdentityReceipt:
        """
        Mark that the honeypot identity challenge has been issued.
        The agent has asked "Could you tell me your name and what you're calling about?"
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        before = self._session_states.get(session_id, IdentityState.UNVERIFIED)
        self._session_states[session_id] = IdentityState.CHALLENGE_PENDING
        return IdentityReceipt(
            receipt_id=str(uuid.uuid4()),
            session_id=session_id,
            operation="begin_challenge",
            identity_state_before=before,
            identity_state_after=IdentityState.CHALLENGE_PENDING,
            verdict=None,
            timestamp_utc=now_utc,
            details="honeypot identity challenge issued to speaker",
        )

    def begin_enrollment(self, session_id: str) -> IdentityReceipt:
        """Begin collecting voice embedding from speaker."""
        now_utc = datetime.now(timezone.utc).isoformat()
        before = self._session_states.get(session_id, IdentityState.UNVERIFIED)
        self._session_states[session_id] = IdentityState.ENROLLING
        return IdentityReceipt(
            receipt_id=str(uuid.uuid4()),
            session_id=session_id,
            operation="begin_enrollment",
            identity_state_before=before,
            identity_state_after=IdentityState.ENROLLING,
            verdict=None,
            timestamp_utc=now_utc,
            details=f"collecting voice embedding; minimum duration {self._min_enrollment_duration_ms}ms",
        )

    def complete_enrollment(
        self,
        session_id: str,
        embedding_dimensions: int,
        enrollment_duration_ms: int,
    ) -> tuple[IdentityReceipt, Optional[SpeakerProfile]]:
        """
        Complete enrollment with the collected embedding.
        Validates dimensions and duration before accepting.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        before = self._session_states.get(session_id, IdentityState.UNVERIFIED)

        # Validate dimensions
        if embedding_dimensions != RESEMBLYZER_DIMENSIONS:
            self._session_states[session_id] = IdentityState.UNVERIFIED
            return IdentityReceipt(
                receipt_id=str(uuid.uuid4()),
                session_id=session_id,
                operation="complete_enrollment",
                identity_state_before=before,
                identity_state_after=IdentityState.UNVERIFIED,
                verdict=IdentityVerdict.ERROR,
                timestamp_utc=now_utc,
                details=f"embedding dimensions {embedding_dimensions} != expected {RESEMBLYZER_DIMENSIONS}",
            ), None

        # Validate duration
        if enrollment_duration_ms < self._min_enrollment_duration_ms:
            return IdentityReceipt(
                receipt_id=str(uuid.uuid4()),
                session_id=session_id,
                operation="complete_enrollment",
                identity_state_before=before,
                identity_state_after=IdentityState.ENROLLING,
                verdict=IdentityVerdict.INSUFFICIENT_AUDIO,
                timestamp_utc=now_utc,
                details=f"enrollment duration {enrollment_duration_ms}ms < minimum {self._min_enrollment_duration_ms}ms",
            ), None

        # Create profile and lock identity
        profile_id = str(uuid.uuid4())
        profile = SpeakerProfile(
            profile_id=profile_id,
            session_id=session_id,
            embedding_dimensions=embedding_dimensions,
            enrollment_duration_ms=enrollment_duration_ms,
            enrolled_utc=now_utc,
            confidence_threshold=self._similarity_threshold,
            is_active=True,
        )
        self._profiles[session_id] = profile
        self._session_states[session_id] = IdentityState.LOCKED

        return IdentityReceipt(
            receipt_id=str(uuid.uuid4()),
            session_id=session_id,
            operation="complete_enrollment",
            identity_state_before=before,
            identity_state_after=IdentityState.LOCKED,
            verdict=IdentityVerdict.MATCH,
            timestamp_utc=now_utc,
            details=f"speaker enrolled with {embedding_dimensions}-dim embedding; identity LOCKED",
        ), profile

    def verify_speaker(
        self,
        session_id: str,
        similarity_score: float,
    ) -> IdentityCheckResult:
        """
        Verify a speaker against the enrolled profile.
        Returns a typed check result with verdict.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        profile = self._profiles.get(session_id)

        if profile is None:
            return IdentityCheckResult(
                check_id=str(uuid.uuid4()),
                session_id=session_id,
                profile_id=None,
                verdict=IdentityVerdict.ENROLLMENT_NEEDED,
                similarity_score=None,
                threshold=self._similarity_threshold,
                iron_ear_version=IronEarVersion.V3_IDENTITY_LOCK,
                timestamp_utc=now_utc,
                rejection_reason="no enrolled profile for session",
            )

        is_match = similarity_score >= self._similarity_threshold
        verdict = IdentityVerdict.MATCH if is_match else IdentityVerdict.NO_MATCH

        if not is_match:
            self._session_states[session_id] = IdentityState.REJECTED

        return IdentityCheckResult(
            check_id=str(uuid.uuid4()),
            session_id=session_id,
            profile_id=profile.profile_id,
            verdict=verdict,
            similarity_score=similarity_score,
            threshold=self._similarity_threshold,
            iron_ear_version=IronEarVersion.V3_IDENTITY_LOCK,
            timestamp_utc=now_utc,
            rejection_reason=None if is_match else f"similarity {similarity_score:.3f} < threshold {self._similarity_threshold}",
        )

    def get_state(self, session_id: str) -> IdentityState:
        """Get current identity state for a session."""
        return self._session_states.get(session_id, IdentityState.UNVERIFIED)

    def is_locked(self, session_id: str) -> bool:
        """Check if identity is locked for a session."""
        return self._session_states.get(session_id) == IdentityState.LOCKED

    def teardown(self, session_id: str) -> None:
        """Clean up identity state for a session."""
        self._session_states.pop(session_id, None)
        self._profiles.pop(session_id, None)
