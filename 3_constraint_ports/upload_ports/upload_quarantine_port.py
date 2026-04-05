"""
HIVE215 Upload Quarantine Port

Constraint port for quarantining and validating user uploads.
All uploads are UNTRUSTED and must be typed, size-checked, and
content-validated before any processing.

Trust level: UNTRUSTED
Schema: upload_evidence.schema.json
Halt conditions: oversized, type mismatch, dangerous extension, empty
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class QuarantineVerdict(Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED_SIZE = "rejected_size"
    REJECTED_TYPE = "rejected_type"
    REJECTED_CONTENT = "rejected_content"


DANGEROUS_EXTENSIONS = frozenset({
    ".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".pif",
    ".sh", ".bash", ".csh", ".ksh",
    ".ps1", ".psm1", ".psd1",
    ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".dll", ".sys", ".drv",
})

ALLOWED_MIME_PREFIXES = frozenset({
    "text/", "application/pdf", "application/json",
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "audio/wav", "audio/mpeg", "audio/ogg", "audio/webm",
    "video/mp4", "video/webm",
})

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


@dataclass(frozen=True)
class UploadEvidence:
    """Typed evidence record for a quarantined upload."""
    upload_id: str
    original_filename: str
    declared_mime_type: str
    detected_mime_type: Optional[str]
    size_bytes: int
    sha256_hash: Optional[str]
    quarantine_status: QuarantineVerdict
    validation_errors: list[str]
    timestamp_utc: str


@dataclass(frozen=True)
class UploadReceipt:
    """Receipt for upload quarantine processing."""
    receipt_id: str
    adapter_name: str
    operation: str
    source_trust_level: str
    output_trust_level: str
    success: bool
    upload_id: str
    timestamp_utc: str
    error_message: Optional[str] = None


class UploadQuarantinePort:
    """
    Port for quarantining and validating user uploads.

    All uploads are UNTRUSTED. This port checks:
    1. File is not empty
    2. File size is within limits
    3. Filename does not have a dangerous extension
    4. Declared MIME type matches detected MIME type
    5. MIME type is in the allowed set
    """

    def __init__(self, max_size_bytes: int = MAX_UPLOAD_SIZE_BYTES) -> None:
        self.max_size_bytes = max_size_bytes

    def quarantine(
        self,
        filename: str,
        declared_mime_type: str,
        content_bytes: bytes,
        detected_mime_type: Optional[str] = None,
    ) -> tuple[UploadEvidence, UploadReceipt]:
        """
        Quarantine and validate an upload.

        Returns (UploadEvidence, UploadReceipt).
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        upload_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())
        errors: list[str] = []

        # Compute hash
        sha256_hash = hashlib.sha256(content_bytes).hexdigest() if content_bytes else None
        size_bytes = len(content_bytes) if content_bytes else 0

        # Check empty
        if size_bytes == 0:
            errors.append("file is empty")
            return self._build(
                upload_id, receipt_id, filename, declared_mime_type,
                detected_mime_type, size_bytes, sha256_hash,
                QuarantineVerdict.REJECTED_SIZE, errors, now_utc,
            )

        # Check size
        if size_bytes > self.max_size_bytes:
            errors.append(f"file size {size_bytes} exceeds maximum {self.max_size_bytes}")
            return self._build(
                upload_id, receipt_id, filename, declared_mime_type,
                detected_mime_type, size_bytes, sha256_hash,
                QuarantineVerdict.REJECTED_SIZE, errors, now_utc,
            )

        # Check filename
        if not filename or not filename.strip():
            errors.append("filename is empty")
            return self._build(
                upload_id, receipt_id, filename, declared_mime_type,
                detected_mime_type, size_bytes, sha256_hash,
                QuarantineVerdict.REJECTED_TYPE, errors, now_utc,
            )

        # Check dangerous extension
        filename_lower = filename.lower()
        for ext in DANGEROUS_EXTENSIONS:
            if filename_lower.endswith(ext):
                errors.append(f"dangerous file extension: {ext}")
                return self._build(
                    upload_id, receipt_id, filename, declared_mime_type,
                    detected_mime_type, size_bytes, sha256_hash,
                    QuarantineVerdict.REJECTED_TYPE, errors, now_utc,
                )

        # Check MIME type match
        if detected_mime_type and declared_mime_type != detected_mime_type:
            errors.append(
                f"MIME type mismatch: declared={declared_mime_type}, detected={detected_mime_type}"
            )
            return self._build(
                upload_id, receipt_id, filename, declared_mime_type,
                detected_mime_type, size_bytes, sha256_hash,
                QuarantineVerdict.REJECTED_TYPE, errors, now_utc,
            )

        # Check MIME type is allowed
        mime_allowed = any(
            declared_mime_type.startswith(prefix) if prefix.endswith("/")
            else declared_mime_type == prefix
            for prefix in ALLOWED_MIME_PREFIXES
        )
        if not mime_allowed:
            errors.append(f"MIME type {declared_mime_type} is not in allowed set")
            return self._build(
                upload_id, receipt_id, filename, declared_mime_type,
                detected_mime_type, size_bytes, sha256_hash,
                QuarantineVerdict.REJECTED_TYPE, errors, now_utc,
            )

        # All checks passed
        return self._build(
            upload_id, receipt_id, filename, declared_mime_type,
            detected_mime_type, size_bytes, sha256_hash,
            QuarantineVerdict.VALIDATED, errors, now_utc,
        )

    def _build(
        self,
        upload_id: str,
        receipt_id: str,
        filename: str,
        declared_mime_type: str,
        detected_mime_type: Optional[str],
        size_bytes: int,
        sha256_hash: Optional[str],
        verdict: QuarantineVerdict,
        errors: list[str],
        timestamp_utc: str,
    ) -> tuple[UploadEvidence, UploadReceipt]:
        """Build evidence and receipt."""
        evidence = UploadEvidence(
            upload_id=upload_id,
            original_filename=filename,
            declared_mime_type=declared_mime_type,
            detected_mime_type=detected_mime_type,
            size_bytes=size_bytes,
            sha256_hash=sha256_hash,
            quarantine_status=verdict,
            validation_errors=errors,
            timestamp_utc=timestamp_utc,
        )

        success = verdict == QuarantineVerdict.VALIDATED
        receipt = UploadReceipt(
            receipt_id=receipt_id,
            adapter_name="upload_quarantine",
            operation="quarantine",
            source_trust_level="UNTRUSTED",
            output_trust_level="TRUSTED" if success else "REJECTED",
            success=success,
            upload_id=upload_id,
            timestamp_utc=timestamp_utc,
            error_message="; ".join(errors) if errors else None,
        )

        return evidence, receipt
