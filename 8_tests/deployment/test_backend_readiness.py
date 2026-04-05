"""
Test backend readiness check.

Validates that the deployment kernel correctly assesses system readiness
based on service health.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from two_domain_kernels.deployment_kernel import (
    DeploymentKernel,
    ServiceType,
    ServiceHealth,
    ReadinessVerdict,
)


class TestBackendReadiness:
    """Backend readiness is determined by core service health."""

    def setup_method(self) -> None:
        self.kernel = DeploymentKernel()

    def test_all_healthy_is_ready(self) -> None:
        """All services healthy results in READY verdict."""
        # Register all core services as healthy
        for service in [ServiceType.WEB_API, ServiceType.VOICE_WORKER,
                       ServiceType.LIVEKIT, ServiceType.DEEPGRAM_STT]:
            self.kernel.record_health(service, ServiceHealth.HEALTHY, latency_ms=50)

        # Register all auxiliary services as healthy
        for service in [ServiceType.FAST_BRAIN, ServiceType.CARTESIA_TTS,
                       ServiceType.SUPABASE, ServiceType.MODAL_WHISPER,
                       ServiceType.MODAL_COQUI, ServiceType.MODAL_KOKORO]:
            self.kernel.record_health(service, ServiceHealth.HEALTHY, latency_ms=100)

        report, receipt = self.kernel.check_readiness()
        assert report.verdict == ReadinessVerdict.READY
        assert report.core_services_healthy == report.core_services_total

    def test_core_unhealthy_is_not_ready(self) -> None:
        """Unhealthy core service results in NOT_READY verdict."""
        self.kernel.record_health(ServiceType.WEB_API, ServiceHealth.HEALTHY)
        self.kernel.record_health(ServiceType.VOICE_WORKER, ServiceHealth.UNHEALTHY,
                                  error_message="connection refused")
        self.kernel.record_health(ServiceType.LIVEKIT, ServiceHealth.HEALTHY)
        self.kernel.record_health(ServiceType.DEEPGRAM_STT, ServiceHealth.HEALTHY)

        report, receipt = self.kernel.check_readiness()
        assert report.verdict == ReadinessVerdict.NOT_READY
        assert len(report.issues) > 0

    def test_auxiliary_down_is_degraded(self) -> None:
        """Core healthy but auxiliary down results in READY_DEGRADED."""
        for service in [ServiceType.WEB_API, ServiceType.VOICE_WORKER,
                       ServiceType.LIVEKIT, ServiceType.DEEPGRAM_STT]:
            self.kernel.record_health(service, ServiceHealth.HEALTHY)

        self.kernel.record_health(ServiceType.FAST_BRAIN, ServiceHealth.UNREACHABLE,
                                  error_message="timeout")
        self.kernel.record_health(ServiceType.CARTESIA_TTS, ServiceHealth.HEALTHY)
        self.kernel.record_health(ServiceType.SUPABASE, ServiceHealth.HEALTHY)

        report, receipt = self.kernel.check_readiness()
        assert report.verdict == ReadinessVerdict.READY_DEGRADED

    def test_unchecked_services_reported(self) -> None:
        """Services that haven't been checked are reported as issues."""
        # Only register one service
        self.kernel.record_health(ServiceType.WEB_API, ServiceHealth.HEALTHY)

        report, _ = self.kernel.check_readiness()
        assert report.verdict == ReadinessVerdict.NOT_READY
        assert any("not been checked" in issue for issue in report.issues)

    def test_readiness_emits_receipt(self) -> None:
        """Readiness check emits a deployment receipt."""
        self.kernel.record_health(ServiceType.WEB_API, ServiceHealth.HEALTHY)

        _, receipt = self.kernel.check_readiness()
        assert receipt.receipt_id is not None
        assert receipt.report_id is not None
        assert receipt.services_checked >= 1

    def test_is_core_healthy_shortcut(self) -> None:
        """Quick core health check works correctly."""
        assert self.kernel.is_core_healthy() is False

        for service in [ServiceType.WEB_API, ServiceType.VOICE_WORKER,
                       ServiceType.LIVEKIT, ServiceType.DEEPGRAM_STT]:
            self.kernel.record_health(service, ServiceHealth.HEALTHY)

        assert self.kernel.is_core_healthy() is True
