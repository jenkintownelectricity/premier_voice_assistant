"""
Test external API fail-closed behavior.

Validates that external API responses are properly normalized and that
failures result in fail-closed behavior (not fallback to raw data).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from three_constraint_ports.external_api_ports.external_api_normalization_port import (
    ExternalAPINormalizationPort,
    ExternalAPIVerdict,
)


class TestExternalAPIFailClosed:
    """External API responses must fail closed on any anomaly."""

    def setup_method(self) -> None:
        self.port = ExternalAPINormalizationPort()

    def test_successful_response_accepted(self) -> None:
        """A valid 200 response with JSON body is accepted."""
        result, receipt = self.port.normalize_response(
            api_name="test_api",
            http_status=200,
            content_type="application/json",
            response_body=b'{"data": "valid"}',
            latency_ms=150,
        )
        assert result.normalization_verdict == ExternalAPIVerdict.ACCEPTED
        assert receipt.success is True

    def test_http_error_fails_closed(self) -> None:
        """HTTP error responses are rejected (fail closed)."""
        for status in [400, 401, 403, 404, 500, 502, 503]:
            result, receipt = self.port.normalize_response(
                api_name="test_api",
                http_status=status,
                content_type="application/json",
                response_body=b'{"error": "something went wrong"}',
                latency_ms=100,
            )
            assert result.normalization_verdict == ExternalAPIVerdict.REJECTED_HTTP_ERROR, (
                f"status {status} should be rejected"
            )
            assert receipt.success is False

    def test_timeout_fails_closed(self) -> None:
        """Timeout responses are rejected (fail closed)."""
        result, receipt = self.port.normalize_response(
            api_name="test_api",
            http_status=0,
            content_type=None,
            response_body=None,
            latency_ms=30000,
            timed_out=True,
        )
        assert result.normalization_verdict == ExternalAPIVerdict.REJECTED_TIMEOUT
        assert receipt.success is False

    def test_malformed_json_fails_closed(self) -> None:
        """Malformed JSON responses are rejected (fail closed)."""
        result, receipt = self.port.normalize_response(
            api_name="test_api",
            http_status=200,
            content_type="application/json",
            response_body=b'{"broken json',
            latency_ms=100,
        )
        assert result.normalization_verdict == ExternalAPIVerdict.REJECTED_MALFORMED
        assert receipt.success is False

    def test_oversized_response_fails_closed(self) -> None:
        """Oversized responses are rejected (fail closed)."""
        large_body = b"x" * (self.port.max_response_bytes + 1)
        result, receipt = self.port.normalize_response(
            api_name="test_api",
            http_status=200,
            content_type="application/json",
            response_body=large_body,
            latency_ms=100,
        )
        assert result.normalization_verdict == ExternalAPIVerdict.REJECTED_TOO_LARGE
        assert receipt.success is False

    def test_unexpected_content_type_fails_closed(self) -> None:
        """Unexpected content types are rejected (fail closed)."""
        result, receipt = self.port.normalize_response(
            api_name="test_api",
            http_status=200,
            content_type="text/html",
            response_body=b"<html><body>Not JSON</body></html>",
            latency_ms=100,
        )
        assert result.normalization_verdict == ExternalAPIVerdict.REJECTED_UNEXPECTED_TYPE
        assert receipt.success is False

    def test_receipt_always_emitted(self) -> None:
        """A receipt is emitted for every normalization attempt."""
        _, receipt = self.port.normalize_response(
            api_name="test_api",
            http_status=500,
            content_type="application/json",
            response_body=b'{"error": "internal"}',
            latency_ms=50,
        )
        assert receipt.receipt_id is not None
        assert receipt.source_trust_level == "UNTRUSTED"
        assert receipt.adapter_name == "external_api_normalization"

    def test_null_response_body_fails_closed(self) -> None:
        """Null response body fails closed."""
        result, receipt = self.port.normalize_response(
            api_name="test_api",
            http_status=200,
            content_type="application/json",
            response_body=None,
            latency_ms=100,
        )
        assert result.normalization_verdict == ExternalAPIVerdict.REJECTED_MALFORMED
        assert receipt.success is False
