"""
Test that browser UI state is treated as UNTRUSTED.

Validates that session transitions from browser/mobile sources are rejected,
and that user state claims from untrusted sources are rejected.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from two_domain_kernels.session_kernel import (
    SessionKernel,
    SessionPhase,
    StateSource,
    TransitionVerdict,
)
from two_domain_kernels.user_state_kernel import (
    UserStateKernel,
    UserStateSource,
    NormalizationVerdict,
)
from two_domain_kernels.execution_approval_kernel import (
    ExecutionApprovalKernel,
    ActionType,
    ActionSource,
    ApprovalVerdict,
)


# Use module-level aliases to handle the numbered directory import
# In practice these would use importlib or proper package configuration
# For test purposes we import directly


class TestBrowserUIStateUntrusted:
    """Browser UI state must never be trusted for session transitions."""

    def test_browser_cannot_transition_session(self) -> None:
        """Session transitions from browser UI are rejected."""
        kernel = SessionKernel()
        session, _ = kernel.create_session()

        # Transition to greeting from trusted source works
        updated, receipt = kernel.transition(
            session.session_id,
            SessionPhase.GREETING,
            StateSource.KERNEL_INTERNAL,
        )
        assert updated is not None
        assert receipt.verdict == TransitionVerdict.ACCEPTED

        # Same transition from browser UI is rejected
        updated, receipt = kernel.transition(
            session.session_id,
            SessionPhase.ACTIVE_DIALOGUE,
            StateSource.BROWSER_UI,
        )
        assert updated is None
        assert receipt.verdict == TransitionVerdict.REJECTED_UNTRUSTED_SOURCE
        assert receipt.source_trust_level == "UNTRUSTED"

    def test_mobile_ui_cannot_transition_session(self) -> None:
        """Session transitions from mobile UI are rejected."""
        kernel = SessionKernel()
        session, _ = kernel.create_session()

        updated, receipt = kernel.transition(
            session.session_id,
            SessionPhase.GREETING,
            StateSource.MOBILE_UI,
        )
        assert updated is None
        assert receipt.verdict == TransitionVerdict.REJECTED_UNTRUSTED_SOURCE

    def test_external_api_cannot_transition_session(self) -> None:
        """Session transitions from external APIs are rejected."""
        kernel = SessionKernel()
        session, _ = kernel.create_session()

        updated, receipt = kernel.transition(
            session.session_id,
            SessionPhase.GREETING,
            StateSource.EXTERNAL_API,
        )
        assert updated is None
        assert receipt.verdict == TransitionVerdict.REJECTED_UNTRUSTED_SOURCE

    def test_trusted_source_can_transition(self) -> None:
        """Session transitions from trusted sources are accepted."""
        kernel = SessionKernel()
        session, _ = kernel.create_session()

        for source in [StateSource.KERNEL_INTERNAL, StateSource.VOICE_PIPELINE, StateSource.LIVEKIT_EVENT]:
            # Create fresh session for each test
            s, _ = kernel.create_session()
            updated, receipt = kernel.transition(
                s.session_id,
                SessionPhase.GREETING,
                source,
            )
            assert updated is not None, f"source {source.value} should be accepted"
            assert receipt.verdict == TransitionVerdict.ACCEPTED


class TestBrowserUserStateClaims:
    """User state claims from browser must be rejected."""

    def test_browser_user_state_rejected(self) -> None:
        """User state from browser source is rejected outright."""
        kernel = UserStateKernel()
        receipt = kernel.reject_untrusted(
            UserStateSource.BROWSER_CLAIM,
            {"user_id": "fake-id", "email": "fake@example.com"},
        )
        assert receipt.verdict == NormalizationVerdict.REJECTED_UNTRUSTED_SOURCE
        assert receipt.source_trust_level == "UNTRUSTED"

    def test_mobile_user_state_rejected(self) -> None:
        """User state from mobile source is rejected outright."""
        kernel = UserStateKernel()
        receipt = kernel.reject_untrusted(
            UserStateSource.MOBILE_CLAIM,
            {"user_id": "fake-id", "email": "fake@example.com"},
        )
        assert receipt.verdict == NormalizationVerdict.REJECTED_UNTRUSTED_SOURCE

    def test_external_api_user_state_rejected(self) -> None:
        """User state from external API is rejected."""
        kernel = UserStateKernel()
        receipt = kernel.reject_untrusted(
            UserStateSource.EXTERNAL_API,
            {"user_id": "fake-id"},
        )
        assert receipt.verdict == NormalizationVerdict.REJECTED_UNTRUSTED_SOURCE


class TestBrowserActionExecution:
    """Actions from browser UI must be rejected by execution approval."""

    def test_browser_action_rejected(self) -> None:
        """Execution requests from browser UI are rejected."""
        kernel = ExecutionApprovalKernel()
        envelope = kernel.create_envelope(
            action_type=ActionType.VOICE_RESPONSE,
            session_id="test-session-id",
            source=ActionSource.BROWSER_UI,
            payload={"text": "hello"},
        )
        receipt = kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.REJECTED_UNTRUSTED_SOURCE
        assert receipt.source_trust_level == "UNTRUSTED"

    def test_mobile_action_rejected(self) -> None:
        """Execution requests from mobile UI are rejected."""
        kernel = ExecutionApprovalKernel()
        envelope = kernel.create_envelope(
            action_type=ActionType.SESSION_UPDATE,
            session_id="test-session-id",
            source=ActionSource.MOBILE_UI,
            payload={"phase": "terminated"},
        )
        receipt = kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.REJECTED_UNTRUSTED_SOURCE

    def test_external_webhook_action_rejected(self) -> None:
        """Execution requests from external webhooks are rejected."""
        kernel = ExecutionApprovalKernel()
        envelope = kernel.create_envelope(
            action_type=ActionType.SUPABASE_MUTATION,
            session_id="test-session-id",
            source=ActionSource.EXTERNAL_WEBHOOK,
            payload={"table": "users", "data": {}},
        )
        receipt = kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.REJECTED_UNTRUSTED_SOURCE

    def test_trusted_action_approved(self) -> None:
        """Execution requests from trusted sources are approved."""
        kernel = ExecutionApprovalKernel()
        envelope = kernel.create_envelope(
            action_type=ActionType.VOICE_RESPONSE,
            session_id="test-session-id",
            source=ActionSource.DIALOGUE_KERNEL,
            payload={"text": "Hello, how can I help you?"},
        )
        receipt = kernel.submit(envelope)
        assert receipt.verdict == ApprovalVerdict.APPROVED
        assert receipt.source_trust_level == "TRUSTED"
