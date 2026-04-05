"""
HIVE215 Execution Approval Kernel

Gates all execution. Only typed, constrained action envelopes may proceed.
Emits execution receipts for every approval decision (accept or reject).

Trust model:
    - Action requests: Must be typed ActionEnvelope from trusted source
    - Execution receipts: TRUSTED (immutable records of decisions)
    - Raw/untyped action requests: REJECTED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ActionType(Enum):
    """Known action types that can be executed."""
    VOICE_RESPONSE = "voice_response"
    SKILL_INVOCATION = "skill_invocation"
    SESSION_UPDATE = "session_update"
    USER_STATE_WRITE = "user_state_write"
    SUPABASE_QUERY = "supabase_query"
    SUPABASE_MUTATION = "supabase_mutation"
    EXTERNAL_API_CALL = "external_api_call"
    TTS_SYNTHESIS = "tts_synthesis"
    NOTIFICATION = "notification"


class ApprovalVerdict(Enum):
    """Result of execution approval."""
    APPROVED = "approved"
    REJECTED_UNTYPED = "rejected_untyped"
    REJECTED_MISSING_FIELDS = "rejected_missing_fields"
    REJECTED_INVALID_ACTION_TYPE = "rejected_invalid_action_type"
    REJECTED_UNTRUSTED_SOURCE = "rejected_untrusted_source"
    REJECTED_CONSTRAINT_VIOLATION = "rejected_constraint_violation"
    REJECTED_SESSION_INVALID = "rejected_session_invalid"


class ActionSource(Enum):
    """Source of an action request."""
    DIALOGUE_KERNEL = "dialogue_kernel"
    EXECUTION_SPINE = "execution_spine"
    SKILL_ROUTER = "skill_router"
    BROWSER_UI = "browser_ui"        # UNTRUSTED
    MOBILE_UI = "mobile_ui"          # UNTRUSTED
    EXTERNAL_WEBHOOK = "external_webhook"  # UNTRUSTED


UNTRUSTED_ACTION_SOURCES = {
    ActionSource.BROWSER_UI,
    ActionSource.MOBILE_UI,
    ActionSource.EXTERNAL_WEBHOOK,
}

# Required fields for a valid action envelope
REQUIRED_ENVELOPE_FIELDS = {"action_type", "session_id", "payload", "source"}


@dataclass(frozen=True)
class ActionEnvelope:
    """
    Typed action envelope. All execution must go through an envelope.
    """
    envelope_id: str
    action_type: ActionType
    session_id: str
    source: ActionSource
    payload: dict[str, Any]
    priority: int = 0  # 0 = normal, higher = more urgent
    idempotency_key: Optional[str] = None
    created_utc: str = ""


@dataclass(frozen=True)
class ExecutionReceipt:
    """Immutable receipt for an execution approval decision."""
    receipt_id: str
    envelope_id: str
    session_id: str
    action_type: ActionType
    source: ActionSource
    source_trust_level: str
    verdict: ApprovalVerdict
    timestamp_utc: str
    execution_duration_ms: Optional[int] = None
    rejection_reason: Optional[str] = None
    result_summary: Optional[str] = None


class ExecutionApprovalKernel:
    """
    Gates all execution. Every action must be submitted as a typed
    ActionEnvelope and pass approval before execution proceeds.
    """

    def __init__(self) -> None:
        self._receipts: list[ExecutionReceipt] = []
        self._seen_idempotency_keys: set[str] = set()

    def submit(self, envelope: ActionEnvelope) -> ExecutionReceipt:
        """
        Submit an action envelope for approval.
        Returns an ExecutionReceipt with the verdict.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        receipt_id = str(uuid.uuid4())

        # Check untrusted source
        if envelope.source in UNTRUSTED_ACTION_SOURCES:
            return self._reject(
                receipt_id, envelope, now_utc,
                ApprovalVerdict.REJECTED_UNTRUSTED_SOURCE,
                f"action source {envelope.source.value} is UNTRUSTED; execution requires trusted source",
            )

        # Check idempotency
        if envelope.idempotency_key and envelope.idempotency_key in self._seen_idempotency_keys:
            return self._reject(
                receipt_id, envelope, now_utc,
                ApprovalVerdict.REJECTED_CONSTRAINT_VIOLATION,
                f"idempotency key {envelope.idempotency_key} already processed",
            )

        # Validate session_id is present
        if not envelope.session_id:
            return self._reject(
                receipt_id, envelope, now_utc,
                ApprovalVerdict.REJECTED_SESSION_INVALID,
                "session_id is empty",
            )

        # Validate payload is dict
        if not isinstance(envelope.payload, dict):
            return self._reject(
                receipt_id, envelope, now_utc,
                ApprovalVerdict.REJECTED_MISSING_FIELDS,
                f"payload must be dict, got {type(envelope.payload).__name__}",
            )

        # Track idempotency key
        if envelope.idempotency_key:
            self._seen_idempotency_keys.add(envelope.idempotency_key)

        receipt = ExecutionReceipt(
            receipt_id=receipt_id,
            envelope_id=envelope.envelope_id,
            session_id=envelope.session_id,
            action_type=envelope.action_type,
            source=envelope.source,
            source_trust_level=self._trust_level_for(envelope.source),
            verdict=ApprovalVerdict.APPROVED,
            timestamp_utc=now_utc,
        )

        self._receipts.append(receipt)
        return receipt

    def create_envelope(
        self,
        action_type: ActionType,
        session_id: str,
        source: ActionSource,
        payload: dict[str, Any],
        priority: int = 0,
        idempotency_key: Optional[str] = None,
    ) -> ActionEnvelope:
        """Create a typed action envelope."""
        return ActionEnvelope(
            envelope_id=str(uuid.uuid4()),
            action_type=action_type,
            session_id=session_id,
            source=source,
            payload=payload,
            priority=priority,
            idempotency_key=idempotency_key,
            created_utc=datetime.now(timezone.utc).isoformat(),
        )

    def record_execution_result(
        self,
        receipt: ExecutionReceipt,
        duration_ms: int,
        result_summary: str,
    ) -> ExecutionReceipt:
        """
        Create an updated receipt with execution results.
        The original receipt is immutable, so this creates a new one.
        """
        return ExecutionReceipt(
            receipt_id=receipt.receipt_id,
            envelope_id=receipt.envelope_id,
            session_id=receipt.session_id,
            action_type=receipt.action_type,
            source=receipt.source,
            source_trust_level=receipt.source_trust_level,
            verdict=receipt.verdict,
            timestamp_utc=receipt.timestamp_utc,
            execution_duration_ms=duration_ms,
            result_summary=result_summary,
        )

    def get_receipts(self, session_id: Optional[str] = None) -> list[ExecutionReceipt]:
        """Get receipts, optionally filtered by session."""
        if session_id is None:
            return list(self._receipts)
        return [r for r in self._receipts if r.session_id == session_id]

    def _reject(
        self,
        receipt_id: str,
        envelope: ActionEnvelope,
        timestamp_utc: str,
        verdict: ApprovalVerdict,
        reason: str,
    ) -> ExecutionReceipt:
        """Create a rejection receipt."""
        receipt = ExecutionReceipt(
            receipt_id=receipt_id,
            envelope_id=envelope.envelope_id,
            session_id=envelope.session_id,
            action_type=envelope.action_type,
            source=envelope.source,
            source_trust_level=self._trust_level_for(envelope.source),
            verdict=verdict,
            timestamp_utc=timestamp_utc,
            rejection_reason=reason,
        )
        self._receipts.append(receipt)
        return receipt

    @staticmethod
    def _trust_level_for(source: ActionSource) -> str:
        """Map action source to trust level."""
        if source in UNTRUSTED_ACTION_SOURCES:
            return "UNTRUSTED"
        return "TRUSTED"
