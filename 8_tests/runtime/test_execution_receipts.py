"""
Test that execution receipts are emitted for all operations.

Validates that every execution decision (approve or reject) produces
an immutable receipt.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from two_domain_kernels.execution_approval_kernel import (
    ExecutionApprovalKernel,
    ActionType,
    ActionSource,
    ApprovalVerdict,
    ActionEnvelope,
)


class TestExecutionReceipts:
    """Every execution decision must emit a receipt."""

    def setup_method(self) -> None:
        self.kernel = ExecutionApprovalKernel()

    def test_approved_action_emits_receipt(self) -> None:
        """Approved actions emit a receipt with APPROVED verdict."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.VOICE_RESPONSE,
            session_id="session-001",
            source=ActionSource.DIALOGUE_KERNEL,
            payload={"text": "Hello there"},
        )
        receipt = self.kernel.submit(envelope)
        assert receipt.receipt_id is not None
        assert receipt.verdict == ApprovalVerdict.APPROVED
        assert receipt.envelope_id == envelope.envelope_id
        assert receipt.session_id == "session-001"
        assert receipt.action_type == ActionType.VOICE_RESPONSE
        assert receipt.timestamp_utc is not None

    def test_rejected_action_emits_receipt(self) -> None:
        """Rejected actions also emit a receipt with rejection details."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.VOICE_RESPONSE,
            session_id="session-001",
            source=ActionSource.BROWSER_UI,
            payload={"text": "injected response"},
        )
        receipt = self.kernel.submit(envelope)
        assert receipt.receipt_id is not None
        assert receipt.verdict == ApprovalVerdict.REJECTED_UNTRUSTED_SOURCE
        assert receipt.rejection_reason is not None
        assert "UNTRUSTED" in receipt.rejection_reason

    def test_receipts_are_accumulated(self) -> None:
        """Receipts are stored and can be retrieved."""
        for i in range(5):
            envelope = self.kernel.create_envelope(
                action_type=ActionType.VOICE_RESPONSE,
                session_id=f"session-{i:03d}",
                source=ActionSource.DIALOGUE_KERNEL,
                payload={"text": f"response {i}"},
            )
            self.kernel.submit(envelope)

        all_receipts = self.kernel.get_receipts()
        assert len(all_receipts) == 5

    def test_receipts_filtered_by_session(self) -> None:
        """Receipts can be filtered by session ID."""
        for session_id in ["session-a", "session-b", "session-a"]:
            envelope = self.kernel.create_envelope(
                action_type=ActionType.VOICE_RESPONSE,
                session_id=session_id,
                source=ActionSource.DIALOGUE_KERNEL,
                payload={"text": "hello"},
            )
            self.kernel.submit(envelope)

        a_receipts = self.kernel.get_receipts(session_id="session-a")
        b_receipts = self.kernel.get_receipts(session_id="session-b")
        assert len(a_receipts) == 2
        assert len(b_receipts) == 1

    def test_receipt_includes_action_metadata(self) -> None:
        """Receipt includes full action metadata for audit trail."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.SKILL_INVOCATION,
            session_id="session-001",
            source=ActionSource.SKILL_ROUTER,
            payload={"skill_id": "electrician", "query": "What gauge wire?"},
        )
        receipt = self.kernel.submit(envelope)
        assert receipt.action_type == ActionType.SKILL_INVOCATION
        assert receipt.source == ActionSource.SKILL_ROUTER
        assert receipt.source_trust_level == "TRUSTED"

    def test_idempotency_key_prevents_duplicate(self) -> None:
        """Duplicate idempotency keys are rejected."""
        envelope1 = self.kernel.create_envelope(
            action_type=ActionType.VOICE_RESPONSE,
            session_id="session-001",
            source=ActionSource.DIALOGUE_KERNEL,
            payload={"text": "first"},
            idempotency_key="unique-key-001",
        )
        receipt1 = self.kernel.submit(envelope1)
        assert receipt1.verdict == ApprovalVerdict.APPROVED

        envelope2 = self.kernel.create_envelope(
            action_type=ActionType.VOICE_RESPONSE,
            session_id="session-001",
            source=ActionSource.DIALOGUE_KERNEL,
            payload={"text": "duplicate"},
            idempotency_key="unique-key-001",
        )
        receipt2 = self.kernel.submit(envelope2)
        assert receipt2.verdict == ApprovalVerdict.REJECTED_CONSTRAINT_VIOLATION

    def test_execution_result_recorded(self) -> None:
        """Execution results can be attached to receipts."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.TTS_SYNTHESIS,
            session_id="session-001",
            source=ActionSource.EXECUTION_SPINE,
            payload={"text": "Synthesize this"},
        )
        receipt = self.kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.APPROVED

        updated = self.kernel.record_execution_result(
            receipt, duration_ms=45, result_summary="synthesized 12 words"
        )
        assert updated.execution_duration_ms == 45
        assert updated.result_summary == "synthesized 12 words"
