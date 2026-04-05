"""
Test worker readiness check.

Validates that the voice worker service reports correct readiness state
based on its required dependencies.
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
from two_domain_kernels.voice_kernel import (
    VoiceKernel,
    VoiceAdapterType,
    AdapterStatus,
)


class TestWorkerReadiness:
    """Worker readiness depends on voice pipeline dependencies."""

    def test_worker_needs_livekit(self) -> None:
        """Worker is not ready without LiveKit."""
        kernel = DeploymentKernel()
        kernel.record_health(ServiceType.WEB_API, ServiceHealth.HEALTHY)
        kernel.record_health(ServiceType.VOICE_WORKER, ServiceHealth.HEALTHY)
        kernel.record_health(ServiceType.DEEPGRAM_STT, ServiceHealth.HEALTHY)
        # LiveKit not registered

        report, _ = kernel.check_readiness()
        assert report.verdict == ReadinessVerdict.NOT_READY

    def test_worker_needs_stt(self) -> None:
        """Worker is not ready without STT service."""
        kernel = DeploymentKernel()
        kernel.record_health(ServiceType.WEB_API, ServiceHealth.HEALTHY)
        kernel.record_health(ServiceType.VOICE_WORKER, ServiceHealth.HEALTHY)
        kernel.record_health(ServiceType.LIVEKIT, ServiceHealth.HEALTHY)
        # Deepgram not registered

        report, _ = kernel.check_readiness()
        assert report.verdict == ReadinessVerdict.NOT_READY

    def test_worker_with_all_deps_ready(self) -> None:
        """Worker with all dependencies is ready."""
        kernel = DeploymentKernel()
        for service in [ServiceType.WEB_API, ServiceType.VOICE_WORKER,
                       ServiceType.LIVEKIT, ServiceType.DEEPGRAM_STT]:
            kernel.record_health(service, ServiceHealth.HEALTHY, latency_ms=50)

        # Auxiliary
        for service in [ServiceType.FAST_BRAIN, ServiceType.CARTESIA_TTS,
                       ServiceType.SUPABASE, ServiceType.MODAL_WHISPER,
                       ServiceType.MODAL_COQUI, ServiceType.MODAL_KOKORO]:
            kernel.record_health(service, ServiceHealth.HEALTHY, latency_ms=100)

        report, _ = kernel.check_readiness()
        assert report.verdict == ReadinessVerdict.READY

    def test_voice_adapter_health_tracked(self) -> None:
        """Voice adapter health is independently tracked."""
        voice_kernel = VoiceKernel()

        voice_kernel.update_adapter_health(
            VoiceAdapterType.STT_DEEPGRAM,
            AdapterStatus.HEALTHY,
            latency_ms=50,
        )
        voice_kernel.update_adapter_health(
            VoiceAdapterType.TTS_CARTESIA,
            AdapterStatus.DEGRADED,
            latency_ms=500,
            error_message="high latency",
        )

        stt_health = voice_kernel.get_adapter_health(VoiceAdapterType.STT_DEEPGRAM)
        tts_health = voice_kernel.get_adapter_health(VoiceAdapterType.TTS_CARTESIA)

        assert stt_health.status == AdapterStatus.HEALTHY
        assert tts_health.status == AdapterStatus.DEGRADED

    def test_tts_fallback_selection(self) -> None:
        """Voice kernel selects fallback TTS when primary is down."""
        voice_kernel = VoiceKernel()
        voice_kernel.initialize_pipeline("session-1")

        # Mark primary TTS as unavailable
        voice_kernel.update_adapter_health(
            VoiceAdapterType.TTS_CARTESIA,
            AdapterStatus.UNAVAILABLE,
        )
        # Mark a fallback as healthy
        voice_kernel.update_adapter_health(
            VoiceAdapterType.TTS_ELEVENLABS,
            AdapterStatus.HEALTHY,
            latency_ms=80,
        )

        fallback = voice_kernel.select_fallback_tts("session-1")
        assert fallback == VoiceAdapterType.TTS_ELEVENLABS
