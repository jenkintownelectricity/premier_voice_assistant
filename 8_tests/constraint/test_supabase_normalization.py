"""
Test Supabase payload normalization.

Validates that PARTIALLY TRUSTED Supabase data is properly normalized
and that malformed payloads are rejected.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from three_constraint_ports.supabase_ports.supabase_normalization_port import (
    SupabaseNormalizationPort,
    SupabaseNormalizationVerdict,
)


class TestSupabaseNormalization:
    """Supabase payloads must be normalized before use."""

    def setup_method(self) -> None:
        self.port = SupabaseNormalizationPort()

    def test_valid_select_payload_accepted(self) -> None:
        """A well-formed select payload is normalized and accepted."""
        result, receipt = self.port.normalize_query_result(
            table_name="users",
            operation="select",
            raw_rows=[
                {"user_id": "abc-123", "email": "test@example.com", "name": "Test User"},
            ],
        )
        assert result.normalization_verdict == SupabaseNormalizationVerdict.ACCEPTED
        assert result.row_count == 1
        assert receipt.success is True

    def test_empty_result_handled(self) -> None:
        """Empty query results are accepted (not an error)."""
        result, receipt = self.port.normalize_query_result(
            table_name="users",
            operation="select",
            raw_rows=[],
        )
        assert result.normalization_verdict == SupabaseNormalizationVerdict.ACCEPTED
        assert result.row_count == 0

    def test_none_payload_rejected(self) -> None:
        """None payload is rejected as malformed."""
        result, receipt = self.port.normalize_query_result(
            table_name="users",
            operation="select",
            raw_rows=None,
        )
        assert result.normalization_verdict == SupabaseNormalizationVerdict.REJECTED_MALFORMED
        assert receipt.success is False

    def test_non_list_payload_rejected(self) -> None:
        """Non-list payload is rejected as malformed."""
        result, receipt = self.port.normalize_query_result(
            table_name="users",
            operation="select",
            raw_rows="not a list",
        )
        assert result.normalization_verdict == SupabaseNormalizationVerdict.REJECTED_MALFORMED
        assert receipt.success is False

    def test_malformed_rows_filtered(self) -> None:
        """Non-dict rows within results are filtered out."""
        result, receipt = self.port.normalize_query_result(
            table_name="users",
            operation="select",
            raw_rows=[
                {"user_id": "abc-123", "email": "test@example.com"},
                "not a dict",
                42,
                {"user_id": "def-456", "email": "other@example.com"},
            ],
        )
        assert result.normalization_verdict == SupabaseNormalizationVerdict.ACCEPTED
        assert result.row_count == 2  # Only dict rows kept

    def test_receipt_records_trust_level(self) -> None:
        """Receipt correctly records PARTIALLY_TRUSTED source level."""
        _, receipt = self.port.normalize_query_result(
            table_name="users",
            operation="select",
            raw_rows=[{"user_id": "abc"}],
        )
        assert receipt.source_trust_level == "PARTIALLY_TRUSTED"
        assert receipt.adapter_name == "supabase_normalization"

    def test_empty_table_name_rejected(self) -> None:
        """Empty table name is rejected."""
        result, receipt = self.port.normalize_query_result(
            table_name="",
            operation="select",
            raw_rows=[],
        )
        assert result.normalization_verdict == SupabaseNormalizationVerdict.REJECTED_MALFORMED
        assert receipt.success is False
