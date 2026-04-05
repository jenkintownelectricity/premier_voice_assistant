"""
HIVE215 Session Kernel

Manages typed session state with validated transitions. Prevents untrusted
state injection by requiring all state changes to pass through explicit
transition validation.

Trust model:
    - LiveKit session data: PARTIALLY TRUSTED (validated before use)
    - Typed session state: TRUSTED (after validation)
    - Browser-sourced session claims: UNTRUSTED (rejected without validation)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SessionPhase(Enum):
    """Valid session phases in order of progression."""
    INITIALIZING = "initializing"
    GREETING = "greeting"
    IDENTITY_CHALLENGE = "identity_challenge"
    IDENTITY_LOCKED = "identity_locked"
    ACTIVE_DIALOGUE = "active_dialogue"
    SKILL_ROUTING = "skill_routing"
    EXECUTION_PENDING = "execution_pending"
    WRAP_UP = "wrap_up"
    TERMINATED = "terminated"
    ERROR = "error"


# Valid phase transitions (from -> set of allowed to)
VALID_TRANSITIONS: dict[SessionPhase, set[SessionPhase]] = {
    SessionPhase.INITIALIZING: {SessionPhase.GREETING, SessionPhase.ERROR, SessionPhase.TERMINATED},
    SessionPhase.GREETING: {SessionPhase.IDENTITY_CHALLENGE, SessionPhase.ACTIVE_DIALOGUE, SessionPhase.ERROR, SessionPhase.TERMINATED},
    SessionPhase.IDENTITY_CHALLENGE: {SessionPhase.IDENTITY_LOCKED, SessionPhase.GREETING, SessionPhase.ERROR, SessionPhase.TERMINATED},
    SessionPhase.IDENTITY_LOCKED: {SessionPhase.ACTIVE_DIALOGUE, SessionPhase.ERROR, SessionPhase.TERMINATED},
    SessionPhase.ACTIVE_DIALOGUE: {SessionPhase.SKILL_ROUTING, SessionPhase.EXECUTION_PENDING, SessionPhase.WRAP_UP, SessionPhase.ERROR, SessionPhase.TERMINATED},
    SessionPhase.SKILL_ROUTING: {SessionPhase.ACTIVE_DIALOGUE, SessionPhase.EXECUTION_PENDING, SessionPhase.ERROR, SessionPhase.TERMINATED},
    SessionPhase.EXECUTION_PENDING: {SessionPhase.ACTIVE_DIALOGUE, SessionPhase.WRAP_UP, SessionPhase.ERROR, SessionPhase.TERMINATED},
    SessionPhase.WRAP_UP: {SessionPhase.TERMINATED, SessionPhase.ACTIVE_DIALOGUE, SessionPhase.ERROR},
    SessionPhase.TERMINATED: set(),  # Terminal state
    SessionPhase.ERROR: {SessionPhase.TERMINATED},
}


class TransitionVerdict(Enum):
    """Result of a state transition attempt."""
    ACCEPTED = "accepted"
    REJECTED_INVALID_TRANSITION = "rejected_invalid_transition"
    REJECTED_UNTRUSTED_SOURCE = "rejected_untrusted_source"
    REJECTED_SESSION_TERMINATED = "rejected_session_terminated"
    REJECTED_SESSION_NOT_FOUND = "rejected_session_not_found"


class StateSource(Enum):
    """Source of a state transition request."""
    KERNEL_INTERNAL = "kernel_internal"
    LIVEKIT_EVENT = "livekit_event"
    VOICE_PIPELINE = "voice_pipeline"
    BROWSER_UI = "browser_ui"          # UNTRUSTED
    MOBILE_UI = "mobile_ui"            # UNTRUSTED
    EXTERNAL_API = "external_api"      # UNTRUSTED


# Sources that are rejected without further processing
UNTRUSTED_SOURCES = {StateSource.BROWSER_UI, StateSource.MOBILE_UI, StateSource.EXTERNAL_API}


@dataclass
class SessionState:
    """Typed session state. Mutable only through the session kernel."""
    session_id: str
    phase: SessionPhase
    skill_id: Optional[str]
    speaker_id: Optional[str]
    identity_locked: bool
    turn_count: int
    created_utc: str
    last_transition_utc: str
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def is_terminated(self) -> bool:
        return self.phase == SessionPhase.TERMINATED

    @property
    def is_error(self) -> bool:
        return self.phase == SessionPhase.ERROR


@dataclass(frozen=True)
class TransitionReceipt:
    """Immutable receipt for a state transition attempt."""
    receipt_id: str
    session_id: str
    from_phase: SessionPhase
    to_phase: SessionPhase
    verdict: TransitionVerdict
    source: StateSource
    source_trust_level: str
    timestamp_utc: str
    rejection_reason: Optional[str] = None


class SessionKernel:
    """
    Manages typed session state with validated transitions.

    All state changes pass through transition validation. Untrusted sources
    (browser UI, mobile UI, external API) are rejected outright.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create_session(
        self,
        skill_id: Optional[str] = None,
        speaker_id: Optional[str] = None,
    ) -> tuple[SessionState, TransitionReceipt]:
        """Create a new session in INITIALIZING phase."""
        now_utc = datetime.now(timezone.utc).isoformat()
        session_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())

        session = SessionState(
            session_id=session_id,
            phase=SessionPhase.INITIALIZING,
            skill_id=skill_id,
            speaker_id=speaker_id,
            identity_locked=False,
            turn_count=0,
            created_utc=now_utc,
            last_transition_utc=now_utc,
        )

        self._sessions[session_id] = session

        receipt = TransitionReceipt(
            receipt_id=receipt_id,
            session_id=session_id,
            from_phase=SessionPhase.INITIALIZING,
            to_phase=SessionPhase.INITIALIZING,
            verdict=TransitionVerdict.ACCEPTED,
            source=StateSource.KERNEL_INTERNAL,
            source_trust_level="TRUSTED",
            timestamp_utc=now_utc,
        )

        return session, receipt

    def transition(
        self,
        session_id: str,
        to_phase: SessionPhase,
        source: StateSource,
        metadata_updates: Optional[dict[str, str]] = None,
    ) -> tuple[Optional[SessionState], TransitionReceipt]:
        """
        Attempt a state transition. Returns (updated_session, receipt).
        If rejected, updated_session is None.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        receipt_id = str(uuid.uuid4())

        # Check session exists
        session = self._sessions.get(session_id)
        if session is None:
            return None, TransitionReceipt(
                receipt_id=receipt_id,
                session_id=session_id,
                from_phase=SessionPhase.INITIALIZING,
                to_phase=to_phase,
                verdict=TransitionVerdict.REJECTED_SESSION_NOT_FOUND,
                source=source,
                source_trust_level=self._trust_level_for(source),
                timestamp_utc=now_utc,
                rejection_reason=f"session {session_id} not found",
            )

        # Reject untrusted sources
        if source in UNTRUSTED_SOURCES:
            return None, TransitionReceipt(
                receipt_id=receipt_id,
                session_id=session_id,
                from_phase=session.phase,
                to_phase=to_phase,
                verdict=TransitionVerdict.REJECTED_UNTRUSTED_SOURCE,
                source=source,
                source_trust_level="UNTRUSTED",
                timestamp_utc=now_utc,
                rejection_reason=f"source {source.value} is untrusted; session transitions must originate from trusted sources",
            )

        # Check terminal state
        if session.is_terminated:
            return None, TransitionReceipt(
                receipt_id=receipt_id,
                session_id=session_id,
                from_phase=session.phase,
                to_phase=to_phase,
                verdict=TransitionVerdict.REJECTED_SESSION_TERMINATED,
                source=source,
                source_trust_level=self._trust_level_for(source),
                timestamp_utc=now_utc,
                rejection_reason="session is terminated; no further transitions allowed",
            )

        # Validate transition
        allowed = VALID_TRANSITIONS.get(session.phase, set())
        if to_phase not in allowed:
            return None, TransitionReceipt(
                receipt_id=receipt_id,
                session_id=session_id,
                from_phase=session.phase,
                to_phase=to_phase,
                verdict=TransitionVerdict.REJECTED_INVALID_TRANSITION,
                source=source,
                source_trust_level=self._trust_level_for(source),
                timestamp_utc=now_utc,
                rejection_reason=f"transition from {session.phase.value} to {to_phase.value} is not allowed",
            )

        # Apply transition
        session.phase = to_phase
        session.last_transition_utc = now_utc
        if to_phase == SessionPhase.IDENTITY_LOCKED:
            session.identity_locked = True
        if metadata_updates:
            session.metadata.update(metadata_updates)

        receipt = TransitionReceipt(
            receipt_id=receipt_id,
            session_id=session_id,
            from_phase=session.phase,
            to_phase=to_phase,
            verdict=TransitionVerdict.ACCEPTED,
            source=source,
            source_trust_level=self._trust_level_for(source),
            timestamp_utc=now_utc,
        )

        return session, receipt

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get a session by ID. Returns None if not found."""
        return self._sessions.get(session_id)

    def increment_turn(self, session_id: str) -> Optional[int]:
        """Increment turn count. Returns new count or None if session not found."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        session.turn_count += 1
        return session.turn_count

    def terminate_session(self, session_id: str, source: StateSource) -> tuple[Optional[SessionState], TransitionReceipt]:
        """Convenience method to terminate a session."""
        return self.transition(session_id, SessionPhase.TERMINATED, source)

    @staticmethod
    def _trust_level_for(source: StateSource) -> str:
        """Map a state source to its trust level string."""
        if source in UNTRUSTED_SOURCES:
            return "UNTRUSTED"
        if source == StateSource.LIVEKIT_EVENT:
            return "PARTIALLY_TRUSTED"
        return "TRUSTED"
