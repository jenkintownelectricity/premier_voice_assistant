"""
Test that uploads are quarantined until typed and validated.

Validates that the upload quarantine port rejects oversized, mistyped,
and unvalidated uploads.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from three_constraint_ports.upload_ports.upload_quarantine_port import (
    UploadQuarantinePort,
    QuarantineVerdict,
    UploadEvidence,
)


class TestUploadQuarantine:
    """All uploads must be quarantined and validated."""

    def setup_method(self) -> None:
        self.port = UploadQuarantinePort()

    def test_valid_upload_accepted(self) -> None:
        """A properly sized, correctly typed upload is accepted."""
        evidence, receipt = self.port.quarantine(
            filename="document.pdf",
            declared_mime_type="application/pdf",
            content_bytes=b"%PDF-1.4 fake pdf content here",
            detected_mime_type="application/pdf",
        )
        assert evidence.quarantine_status == QuarantineVerdict.VALIDATED
        assert receipt.success is True

    def test_oversized_upload_rejected(self) -> None:
        """Uploads exceeding size limit are rejected."""
        # Create content that exceeds the max size
        evidence, receipt = self.port.quarantine(
            filename="huge_file.bin",
            declared_mime_type="application/octet-stream",
            content_bytes=b"x" * (self.port.max_size_bytes + 1),
            detected_mime_type="application/octet-stream",
        )
        assert evidence.quarantine_status == QuarantineVerdict.REJECTED_SIZE
        assert receipt.success is False

    def test_mime_type_mismatch_rejected(self) -> None:
        """Uploads where declared MIME type does not match detected are rejected."""
        evidence, receipt = self.port.quarantine(
            filename="image.jpg",
            declared_mime_type="image/jpeg",
            content_bytes=b"#!/bin/bash\nrm -rf /",
            detected_mime_type="text/x-shellscript",
        )
        assert evidence.quarantine_status == QuarantineVerdict.REJECTED_TYPE
        assert receipt.success is False
        assert "mime type mismatch" in (receipt.error_message or "").lower()

    def test_empty_upload_rejected(self) -> None:
        """Empty uploads are rejected."""
        evidence, receipt = self.port.quarantine(
            filename="empty.txt",
            declared_mime_type="text/plain",
            content_bytes=b"",
            detected_mime_type="text/plain",
        )
        assert evidence.quarantine_status == QuarantineVerdict.REJECTED_SIZE
        assert receipt.success is False

    def test_dangerous_extension_rejected(self) -> None:
        """Files with dangerous extensions are rejected."""
        evidence, receipt = self.port.quarantine(
            filename="malware.exe",
            declared_mime_type="application/x-executable",
            content_bytes=b"MZ" + b"\x00" * 100,
            detected_mime_type="application/x-executable",
        )
        assert evidence.quarantine_status == QuarantineVerdict.REJECTED_TYPE
        assert receipt.success is False

    def test_upload_generates_receipt(self) -> None:
        """Every quarantine operation produces a receipt."""
        _, receipt = self.port.quarantine(
            filename="test.txt",
            declared_mime_type="text/plain",
            content_bytes=b"hello world",
            detected_mime_type="text/plain",
        )
        assert receipt.receipt_id is not None
        assert receipt.adapter_name == "upload_quarantine"
        assert receipt.source_trust_level == "UNTRUSTED"

    def test_null_filename_rejected(self) -> None:
        """Uploads with no filename are rejected."""
        evidence, receipt = self.port.quarantine(
            filename="",
            declared_mime_type="text/plain",
            content_bytes=b"content",
            detected_mime_type="text/plain",
        )
        assert evidence.quarantine_status == QuarantineVerdict.REJECTED_TYPE
        assert receipt.success is False
