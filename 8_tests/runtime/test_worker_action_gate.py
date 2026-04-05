"""
Test worker action gate enforcement.

Validates that the execution approval kernel correctly gates all worker
actions and that only typed, trusted envelopes proceed.
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


class TestWorkerActionGate:
    """Worker actions must pass through the execution approval gate."""

    def setup_method(self) -> None:
        self.kernel = ExecutionApprovalKernel()

    def test_voice_response_from_dialogue_approved(self) -> None:
        """Voice response from dialogue kernel is approved."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.VOICE_RESPONSE,
            session_id="session-001",
            source=ActionSource.DIALOGUE_KERNEL,
            payload={"text": "I can help you with that.", "skill_id": "receptionist"},
        )
        receipt = self.kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.APPROVED

    def test_skill_invocation_from_router_approved(self) -> None:
        """Skill invocation from skill router is approved."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.SKILL_INVOCATION,
            session_id="session-001",
            source=ActionSource.SKILL_ROUTER,
            payload={"skill_id": "electrician", "system": "system_1"},
        )
        receipt = self.kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.APPROVED

    def test_supabase_mutation_from_spine_approved(self) -> None:
        """Supabase mutation from execution spine is approved."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.SUPABASE_MUTATION,
            session_id="session-001",
            source=ActionSource.EXECUTION_SPINE,
            payload={"table": "call_logs", "operation": "insert", "data": {"duration_s": 120}},
        )
        receipt = self.kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.APPROVED

    def test_empty_session_id_rejected(self) -> None:
        """Actions with empty session ID are rejected."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.VOICE_RESPONSE,
            session_id="",
            source=ActionSource.DIALOGUE_KERNEL,
            payload={"text": "hello"},
        )
        receipt = self.kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.REJECTED_SESSION_INVALID

    def test_all_untrusted_sources_rejected(self) -> None:
        """All untrusted sources are rejected regardless of action type."""
        untrusted_sources = [
            ActionSource.BROWSER_UI,
            ActionSource.MOBILE_UI,
            ActionSource.EXTERNAL_WEBHOOK,
        ]
        for source in untrusted_sources:
            for action_type in ActionType:
                envelope = self.kernel.create_envelope(
                    action_type=action_type,
                    session_id="session-001",
                    source=source,
                    payload={"data": "test"},
                )
                receipt = self.kernel.submit(envelope)
                assert receipt.verdict == ApprovalVerdict.REJECTED_UNTRUSTED_SOURCE, (
                    f"{source.value} + {action_type.value} should be rejected"
                )

    def test_envelope_has_required_fields(self) -> None:
        """Created envelopes have all required fields populated."""
        envelope = self.kernel.create_envelope(
            action_type=ActionType.TTS_SYNTHESIS,
            session_id="session-001",
            source=ActionSource.EXECUTION_SPINE,
            payload={"text": "synthesize this"},
        )
        assert envelope.envelope_id is not None
        assert envelope.action_type == ActionType.TTS_SYNTHESIS
        assert envelope.session_id == "session-001"
        assert envelope.source == ActionSource.EXECUTION_SPINE
        assert isinstance(envelope.payload, dict)
        assert envelope.created_utc != ""

    def test_multiple_action_types_from_trusted_sources(self) -> None:
        """All action types are approved from trusted sources."""
        trusted_sources = [
            ActionSource.DIALOGUE_KERNEL,
            ActionSource.EXECUTION_SPINE,
            ActionSource.SKILL_ROUTER,
        ]
        for source in trusted_sources:
            envelope = self.kernel.create_envelope(
                action_type=ActionType.VOICE_RESPONSE,
                session_id="session-001",
                source=source,
                payload={"text": "test"},
            )
            receipt = self.kernel.submit(envelope)
            assert receipt.verdict == ApprovalVerdict.APPROVED, (
                f"{source.value} should be approved"
            )
