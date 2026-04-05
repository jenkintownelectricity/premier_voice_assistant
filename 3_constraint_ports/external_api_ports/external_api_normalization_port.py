"""
HIVE215 External API Normalization Port

Constraint port for normalizing external API responses.
External APIs are UNTRUSTED -- responses may be malformed, delayed, or adversarial.
Fail closed on any unexpected response.

Trust level: UNTRUSTED
Schema: external_response_normalized.schema.json
Halt conditions: HTTP error, timeout, malformed body, oversized, unexpected content type
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ExternalAPIVerdict(Enum):
    ACCEPTED = "accepted"
    REJECTED_HTTP_ERROR = "rejected_http_error"
    REJECTED_TIMEOUT = "rejected_timeout"
    REJECTED_MALFORMED = "rejected_malformed"
    REJECTED_TOO_LARGE = "rejected_too_large"
    REJECTED_UNEXPECTED_TYPE = "rejected_unexpected_type"


MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10MB
ACCEPTED_CONTENT_TYPES = frozenset({
    "application/json",
    "application/json; charset=utf-8",
    "text/plain",
    "text/plain; charset=utf-8",
})


@dataclass(frozen=True)
class NormalizedExternalResponse:
    """Typed, normalized external API response."""
    response_id: str
    api_name: str
    http_status: int
    content_type: Optional[str]
    response_size_bytes: Optional[int]
    latency_ms: Optional[int]
    normalization_verdict: ExternalAPIVerdict
    normalized_payload: Optional[dict[str, Any]]
    error_message: Optional[str]
    timestamp_utc: str


@dataclass(frozen=True)
class ExternalAPIReceipt:
    """Receipt for external API normalization."""
    receipt_id: str
    adapter_name: str
    operation: str
    source_trust_level: str
    output_trust_level: str
    success: bool
    api_name: str
    http_status: int
    timestamp_utc: str
    error_message: Optional[str] = None


class ExternalAPINormalizationPort:
    """
    Port for normalizing external API responses.

    All external API data enters through this port. Fail closed on:
    - HTTP error status codes (4xx, 5xx)
    - Timeouts
    - Malformed response bodies
    - Oversized responses
    - Unexpected content types
    """

    def __init__(self, max_response_bytes: int = MAX_RESPONSE_BYTES) -> None:
        self.max_response_bytes = max_response_bytes

    def normalize_response(
        self,
        api_name: str,
        http_status: int,
        content_type: Optional[str],
        response_body: Optional[bytes],
        latency_ms: Optional[int] = None,
        timed_out: bool = False,
    ) -> tuple[NormalizedExternalResponse, ExternalAPIReceipt]:
        """
        Normalize an external API response.

        Returns (NormalizedExternalResponse, ExternalAPIReceipt).
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        response_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())

        # Check timeout
        if timed_out:
            return self._reject(
                response_id, receipt_id, api_name, http_status, content_type,
                0, latency_ms, now_utc,
                ExternalAPIVerdict.REJECTED_TIMEOUT,
                "request timed out",
            )

        # Check HTTP status
        if http_status < 200 or http_status >= 300:
            return self._reject(
                response_id, receipt_id, api_name, http_status, content_type,
                len(response_body) if response_body else 0, latency_ms, now_utc,
                ExternalAPIVerdict.REJECTED_HTTP_ERROR,
                f"HTTP status {http_status} is not 2xx",
            )

        # Check response body exists
        if response_body is None:
            return self._reject(
                response_id, receipt_id, api_name, http_status, content_type,
                0, latency_ms, now_utc,
                ExternalAPIVerdict.REJECTED_MALFORMED,
                "response body is None",
            )

        # Check size
        response_size = len(response_body)
        if response_size > self.max_response_bytes:
            return self._reject(
                response_id, receipt_id, api_name, http_status, content_type,
                response_size, latency_ms, now_utc,
                ExternalAPIVerdict.REJECTED_TOO_LARGE,
                f"response size {response_size} exceeds maximum {self.max_response_bytes}",
            )

        # Check content type
        ct_normalized = (content_type or "").lower().strip()
        ct_accepted = any(ct_normalized.startswith(allowed.split(";")[0]) for allowed in ACCEPTED_CONTENT_TYPES)
        if not ct_accepted:
            return self._reject(
                response_id, receipt_id, api_name, http_status, content_type,
                response_size, latency_ms, now_utc,
                ExternalAPIVerdict.REJECTED_UNEXPECTED_TYPE,
                f"content type '{content_type}' is not accepted",
            )

        # Try to parse JSON
        normalized_payload: Optional[dict[str, Any]] = None
        if ct_normalized.startswith("application/json"):
            try:
                parsed = json.loads(response_body)
                if isinstance(parsed, dict):
                    normalized_payload = parsed
                else:
                    normalized_payload = {"data": parsed}
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                return self._reject(
                    response_id, receipt_id, api_name, http_status, content_type,
                    response_size, latency_ms, now_utc,
                    ExternalAPIVerdict.REJECTED_MALFORMED,
                    f"JSON parse error: {e}",
                )
        else:
            # Plain text
            try:
                text = response_body.decode("utf-8")
                normalized_payload = {"text": text}
            except UnicodeDecodeError as e:
                return self._reject(
                    response_id, receipt_id, api_name, http_status, content_type,
                    response_size, latency_ms, now_utc,
                    ExternalAPIVerdict.REJECTED_MALFORMED,
                    f"text decode error: {e}",
                )

        response = NormalizedExternalResponse(
            response_id=response_id,
            api_name=api_name,
            http_status=http_status,
            content_type=content_type,
            response_size_bytes=response_size,
            latency_ms=latency_ms,
            normalization_verdict=ExternalAPIVerdict.ACCEPTED,
            normalized_payload=normalized_payload,
            error_message=None,
            timestamp_utc=now_utc,
        )

        receipt = ExternalAPIReceipt(
            receipt_id=receipt_id,
            adapter_name="external_api_normalization",
            operation="normalize_response",
            source_trust_level="UNTRUSTED",
            output_trust_level="TRUSTED",
            success=True,
            api_name=api_name,
            http_status=http_status,
            timestamp_utc=now_utc,
        )

        return response, receipt

    def _reject(
        self,
        response_id: str,
        receipt_id: str,
        api_name: str,
        http_status: int,
        content_type: Optional[str],
        response_size: int,
        latency_ms: Optional[int],
        timestamp_utc: str,
        verdict: ExternalAPIVerdict,
        error_message: str,
    ) -> tuple[NormalizedExternalResponse, ExternalAPIReceipt]:
        """Create rejected response and receipt."""
        response = NormalizedExternalResponse(
            response_id=response_id,
            api_name=api_name,
            http_status=http_status,
            content_type=content_type,
            response_size_bytes=response_size,
            latency_ms=latency_ms,
            normalization_verdict=verdict,
            normalized_payload=None,
            error_message=error_message,
            timestamp_utc=timestamp_utc,
        )

        receipt = ExternalAPIReceipt(
            receipt_id=receipt_id,
            adapter_name="external_api_normalization",
            operation="normalize_response",
            source_trust_level="UNTRUSTED",
            output_trust_level="REJECTED",
            success=False,
            api_name=api_name,
            http_status=http_status,
            timestamp_utc=timestamp_utc,
            error_message=error_message,
        )

        return response, receipt
