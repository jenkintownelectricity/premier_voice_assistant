"""
Smoke test web/mobile contract.

Validates basic contract assertions for the browser and mobile surfaces.
Both are UNTRUSTED -- this test ensures the governance layer treats them as such.
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
    UNTRUSTED_SOURCES,
)
from two_domain_kernels.execution_approval_kernel import (
    ExecutionApprovalKernel,
    ActionType,
    ActionSource,
    ApprovalVerdict,
    UNTRUSTED_ACTION_SOURCES,
)
from three_constraint_ports.ui_ports.browser_intent_normalization_port import (
    BrowserIntentNormalizationPort,
    BrowserIntentVerdict,
)


class TestWebMobileContractSmoke:
    """Smoke tests for web and mobile surface contracts."""

    def test_browser_and_mobile_in_untrusted_sources(self) -> None:
        """Browser and mobile are listed as UNTRUSTED state sources."""
        assert StateSource.BROWSER_UI in UNTRUSTED_SOURCES
        assert StateSource.MOBILE_UI in UNTRUSTED_SOURCES

    def test_browser_and_mobile_in_untrusted_action_sources(self) -> None:
        """Browser and mobile are listed as UNTRUSTED action sources."""
        assert ActionSource.BROWSER_UI in UNTRUSTED_ACTION_SOURCES
        assert ActionSource.MOBILE_UI in UNTRUSTED_ACTION_SOURCES

    def test_browser_intent_normalization_exists(self) -> None:
        """Browser intent normalization port can be instantiated."""
        port = BrowserIntentNormalizationPort()
        assert port is not None

    def test_browser_start_session_normalized(self) -> None:
        """Browser start_session command is normalized (not executed directly)."""
        port = BrowserIntentNormalizationPort()
        result, receipt = port.normalize_intent(
            command_type="start_session",
            session_id="browser-claimed-session-id",
            payload={"skill_id": "receptionist"},
            client_version="1.0.0",
        )
        # The result is normalized, but the session_id is NOT trusted
        assert receipt.source_trust_level == "UNTRUSTED"
        assert receipt.receipt_id is not None

    def test_browser_invalid_command_rejected(self) -> None:
        """Invalid browser commands are rejected."""
        port = BrowserIntentNormalizationPort()
        result, receipt = port.normalize_intent(
            command_type="drop_database",
            session_id="session-id",
            payload={},
            client_version="1.0.0",
        )
        assert result.verdict == BrowserIntentVerdict.REJECTED_INVALID_COMMAND
        assert receipt.success is False

    def test_session_reject_all_ui_sources(self) -> None:
        """Session kernel rejects all UI-sourced transitions."""
        kernel = SessionKernel()
        session, _ = kernel.create_session()

        for source in UNTRUSTED_SOURCES:
            _, receipt = kernel.transition(
                session.session_id,
                SessionPhase.GREETING,
                source,
            )
            assert receipt.verdict == TransitionVerdict.REJECTED_UNTRUSTED_SOURCE

    def test_execution_reject_all_ui_sources(self) -> None:
        """Execution kernel rejects all UI-sourced actions."""
        kernel = ExecutionApprovalKernel()

        for source in UNTRUSTED_ACTION_SOURCES:
            envelope = kernel.create_envelope(
                action_type=ActionType.VOICE_RESPONSE,
                session_id="session-001",
                source=source,
                payload={"text": "injected"},
            )
            receipt = kernel.submit(envelope)
            assert receipt.verdict == ApprovalVerdict.REJECTED_UNTRUSTED_SOURCE
