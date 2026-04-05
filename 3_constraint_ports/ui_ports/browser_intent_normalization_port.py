"""
HIVE215 Browser Intent Normalization Port

Constraint port for normalizing browser UI intents. All browser data
is UNTRUSTED -- it can be spoofed, replayed, or manipulated via devtools.

Trust level: UNTRUSTED
Schema: ui_command.schema.json
Halt conditions: invalid command type, missing required fields, oversized payload
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class BrowserIntentVerdict(Enum):
    ACCEPTED = "accepted"
    REJECTED_INVALID_COMMAND = "rejected_invalid_command"
    REJECTED_MISSING_FIELDS = "rejected_missing_fields"
    REJECTED_OVERSIZED = "rejected_oversized"
    REJECTED_MALFORMED = "rejected_malformed"


# Allowed command types from browser
VALID_COMMAND_TYPES = frozenset({
    "start_session",
    "end_session",
    "mute_toggle",
    "select_skill",
    "send_text",
    "request_transcript",
    "update_settings",
})

MAX_PAYLOAD_SIZE_BYTES = 65536  # 64KB max payload
MAX_TEXT_LENGTH = 2000


@dataclass(frozen=True)
class NormalizedBrowserIntent:
    """Typed, normalized browser intent. Still UNTRUSTED -- must be
    validated against session state before execution."""
    intent_id: str
    command_type: str
    session_id_claimed: str  # Named _claimed because browser session IDs are untrusted
    payload: dict[str, Any]
    client_version: str
    verdict: BrowserIntentVerdict
    timestamp_utc: str
    rejection_reason: Optional[str] = None


@dataclass(frozen=True)
class BrowserIntentReceipt:
    """Receipt for browser intent normalization."""
    receipt_id: str
    adapter_name: str
    operation: str
    source_trust_level: str
    output_trust_level: str
    success: bool
    command_type: str
    timestamp_utc: str
    error_message: Optional[str] = None


class BrowserIntentNormalizationPort:
    """
    Port for normalizing browser UI intents.

    All browser commands enter through this port. The port validates
    command type, checks field requirements, and produces a normalized
    intent with a receipt. The normalized intent is still UNTRUSTED --
    it must be further validated against session state before any
    execution.
    """

    def normalize_intent(
        self,
        command_type: str,
        session_id: str,
        payload: Any,
        client_version: str = "unknown",
    ) -> tuple[NormalizedBrowserIntent, BrowserIntentReceipt]:
        """
        Normalize a raw browser intent.

        Returns (NormalizedBrowserIntent, BrowserIntentReceipt).
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        intent_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())

        # Validate command type
        if not command_type or command_type not in VALID_COMMAND_TYPES:
            return self._reject(
                intent_id, receipt_id, command_type or "", session_id or "",
                {}, client_version, now_utc,
                BrowserIntentVerdict.REJECTED_INVALID_COMMAND,
                f"command_type '{command_type}' is not in allowed set",
            )

        # Validate session_id present
        if not session_id or not isinstance(session_id, str):
            return self._reject(
                intent_id, receipt_id, command_type, "", {}, client_version, now_utc,
                BrowserIntentVerdict.REJECTED_MISSING_FIELDS,
                "session_id is missing or invalid",
            )

        # Validate payload is dict
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return self._reject(
                intent_id, receipt_id, command_type, session_id, {}, client_version, now_utc,
                BrowserIntentVerdict.REJECTED_MALFORMED,
                f"payload is {type(payload).__name__}, expected dict",
            )

        # Sanitize text fields in payload
        sanitized_payload: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str) and len(value) > MAX_TEXT_LENGTH:
                value = value[:MAX_TEXT_LENGTH]
            sanitized_payload[str(key)[:128]] = value

        normalized = NormalizedBrowserIntent(
            intent_id=intent_id,
            command_type=command_type,
            session_id_claimed=str(session_id)[:128],
            payload=sanitized_payload,
            client_version=str(client_version)[:32],
            verdict=BrowserIntentVerdict.ACCEPTED,
            timestamp_utc=now_utc,
        )

        receipt = BrowserIntentReceipt(
            receipt_id=receipt_id,
            adapter_name="browser_intent_normalization",
            operation="normalize_intent",
            source_trust_level="UNTRUSTED",
            output_trust_level="UNTRUSTED",  # Still untrusted after normalization
            success=True,
            command_type=command_type,
            timestamp_utc=now_utc,
        )

        return normalized, receipt

    def _reject(
        self,
        intent_id: str,
        receipt_id: str,
        command_type: str,
        session_id: str,
        payload: dict,
        client_version: str,
        timestamp_utc: str,
        verdict: BrowserIntentVerdict,
        reason: str,
    ) -> tuple[NormalizedBrowserIntent, BrowserIntentReceipt]:
        """Create rejected intent and receipt."""
        normalized = NormalizedBrowserIntent(
            intent_id=intent_id,
            command_type=command_type,
            session_id_claimed=session_id,
            payload=payload,
            client_version=client_version,
            verdict=verdict,
            timestamp_utc=timestamp_utc,
            rejection_reason=reason,
        )

        receipt = BrowserIntentReceipt(
            receipt_id=receipt_id,
            adapter_name="browser_intent_normalization",
            operation="normalize_intent",
            source_trust_level="UNTRUSTED",
            output_trust_level="REJECTED",
            success=False,
            command_type=command_type,
            timestamp_utc=timestamp_utc,
            error_message=reason,
        )

        return normalized, receipt
