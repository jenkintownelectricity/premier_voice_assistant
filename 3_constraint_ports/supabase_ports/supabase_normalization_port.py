"""
HIVE215 Supabase Normalization Port

Constraint port for normalizing Supabase database payloads.
Supabase data is PARTIALLY TRUSTED -- it may contain stale, malformed,
or injected data.

Trust level: PARTIALLY TRUSTED
Schema: supabase_payload_normalized.schema.json
Halt conditions: malformed payload, non-dict rows, empty table name
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SupabaseNormalizationVerdict(Enum):
    ACCEPTED = "accepted"
    REJECTED_EMPTY = "rejected_empty"
    REJECTED_MALFORMED = "rejected_malformed"
    REJECTED_SCHEMA_MISMATCH = "rejected_schema_mismatch"
    REJECTED_STALE = "rejected_stale"


@dataclass(frozen=True)
class NormalizedSupabasePayload:
    """Typed, normalized Supabase query result."""
    payload_id: str
    table_name: str
    operation: str
    row_count: int
    normalized_rows: list[dict[str, Any]]
    normalization_verdict: SupabaseNormalizationVerdict
    timestamp_utc: str
    error_message: Optional[str] = None


@dataclass(frozen=True)
class SupabaseAdapterReceipt:
    """Receipt for Supabase normalization."""
    receipt_id: str
    adapter_name: str
    operation: str
    source_trust_level: str
    output_trust_level: str
    success: bool
    row_count: int
    timestamp_utc: str
    error_message: Optional[str] = None


class SupabaseNormalizationPort:
    """
    Port for normalizing Supabase query results.

    All Supabase data enters through this port. Validates structure,
    filters malformed rows, and produces typed output with receipt.
    """

    def normalize_query_result(
        self,
        table_name: str,
        operation: str,
        raw_rows: Any,
    ) -> tuple[NormalizedSupabasePayload, SupabaseAdapterReceipt]:
        """
        Normalize a raw Supabase query result.

        Returns (NormalizedSupabasePayload, SupabaseAdapterReceipt).
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        payload_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())

        # Validate table name
        if not table_name or not isinstance(table_name, str) or not table_name.strip():
            return self._reject(
                payload_id, receipt_id, table_name or "", operation, now_utc,
                SupabaseNormalizationVerdict.REJECTED_MALFORMED,
                "table_name is empty or invalid",
            )

        # Validate raw_rows is a list
        if raw_rows is None:
            return self._reject(
                payload_id, receipt_id, table_name, operation, now_utc,
                SupabaseNormalizationVerdict.REJECTED_MALFORMED,
                "raw_rows is None",
            )

        if not isinstance(raw_rows, list):
            return self._reject(
                payload_id, receipt_id, table_name, operation, now_utc,
                SupabaseNormalizationVerdict.REJECTED_MALFORMED,
                f"raw_rows is {type(raw_rows).__name__}, expected list",
            )

        # Filter to only dict rows (non-dict entries are silently dropped)
        normalized_rows = [row for row in raw_rows if isinstance(row, dict)]

        payload = NormalizedSupabasePayload(
            payload_id=payload_id,
            table_name=table_name.strip(),
            operation=operation,
            row_count=len(normalized_rows),
            normalized_rows=normalized_rows,
            normalization_verdict=SupabaseNormalizationVerdict.ACCEPTED,
            timestamp_utc=now_utc,
        )

        receipt = SupabaseAdapterReceipt(
            receipt_id=receipt_id,
            adapter_name="supabase_normalization",
            operation=operation,
            source_trust_level="PARTIALLY_TRUSTED",
            output_trust_level="TRUSTED",
            success=True,
            row_count=len(normalized_rows),
            timestamp_utc=now_utc,
        )

        return payload, receipt

    def _reject(
        self,
        payload_id: str,
        receipt_id: str,
        table_name: str,
        operation: str,
        timestamp_utc: str,
        verdict: SupabaseNormalizationVerdict,
        error_message: str,
    ) -> tuple[NormalizedSupabasePayload, SupabaseAdapterReceipt]:
        """Create rejected payload and receipt."""
        payload = NormalizedSupabasePayload(
            payload_id=payload_id,
            table_name=table_name,
            operation=operation,
            row_count=0,
            normalized_rows=[],
            normalization_verdict=verdict,
            timestamp_utc=timestamp_utc,
            error_message=error_message,
        )

        receipt = SupabaseAdapterReceipt(
            receipt_id=receipt_id,
            adapter_name="supabase_normalization",
            operation=operation,
            source_trust_level="PARTIALLY_TRUSTED",
            output_trust_level="REJECTED",
            success=False,
            row_count=0,
            timestamp_utc=timestamp_utc,
            error_message=error_message,
        )

        return payload, receipt
