"""
Test voice runtime contracts.

Validates that the voice pipeline enforces typed contracts at each stage.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from two_domain_kernels.transcript_normalization_kernel import (
    TranscriptNormalizationKernel,
    NormalizationVerdict,
    TranscriptConfidence,
    TranscriptSource,
)
from two_domain_kernels.dialogue_kernel import (
    DialogueKernel,
    RoutingDecision,
    QueryComplexity,
    TurnRole,
)
from two_domain_kernels.voice_kernel import (
    VoiceKernel,
    VoiceAdapterType,
    AdapterStatus,
    PipelineStage,
)


class TestTranscriptNormalizationContract:
    """Transcript normalization must type all STT output."""

    def setup_method(self) -> None:
        self.kernel = TranscriptNormalizationKernel()

    def test_valid_transcript_produces_typed_output(self) -> None:
        """Valid transcript produces TranscriptNormalized with ACCEPTED verdict."""
        normalized, receipt = self.kernel.normalize(
            raw_text="Hello, I need help with my electrical panel.",
            confidence=0.92,
            source="deepgram",
            language="en",
            duration_ms=3500,
        )
        assert normalized.normalization_verdict == NormalizationVerdict.ACCEPTED
        assert normalized.confidence_level == TranscriptConfidence.HIGH
        assert normalized.source == TranscriptSource.DEEPGRAM_NOVA3
        assert normalized.word_count > 0
        assert receipt.verdict == NormalizationVerdict.ACCEPTED

    def test_low_confidence_rejected(self) -> None:
        """Low confidence transcripts are rejected."""
        normalized, receipt = self.kernel.normalize(
            raw_text="mumble mumble",
            confidence=0.15,
            source="deepgram",
        )
        assert normalized.normalization_verdict == NormalizationVerdict.REJECTED_LOW_CONFIDENCE
        assert normalized.confidence_level == TranscriptConfidence.REJECTED

    def test_empty_text_rejected(self) -> None:
        """Empty text is rejected."""
        normalized, receipt = self.kernel.normalize(
            raw_text="   ",
            confidence=0.95,
        )
        assert normalized.normalization_verdict == NormalizationVerdict.REJECTED_EMPTY

    def test_none_text_rejected(self) -> None:
        """None text is rejected as malformed."""
        normalized, receipt = self.kernel.normalize(
            raw_text=None,
            confidence=0.95,
        )
        assert normalized.normalization_verdict == NormalizationVerdict.REJECTED_MALFORMED

    def test_text_cleaned_of_control_chars(self) -> None:
        """Control characters are removed from transcript text."""
        normalized, _ = self.kernel.normalize(
            raw_text="Hello\x00 world\x07!",
            confidence=0.90,
        )
        assert "\x00" not in normalized.text_cleaned
        assert "\x07" not in normalized.text_cleaned
        assert "Hello world!" == normalized.text_cleaned


class TestDialogueRoutingContract:
    """Dialogue routing must produce typed routing decisions."""

    def setup_method(self) -> None:
        self.kernel = DialogueKernel()

    def test_simple_query_routes_system1(self) -> None:
        """Simple greetings route to System 1 Fast Brain."""
        turn, receipt = self.kernel.add_user_turn("session-1", "Hello")
        assert receipt.routing_decision == RoutingDecision.SYSTEM_1_FAST
        assert receipt.estimated_complexity == QueryComplexity.SIMPLE

    def test_complex_query_routes_system2(self) -> None:
        """Complex analytical queries route to System 2 Deep Brain."""
        turn, receipt = self.kernel.add_user_turn(
            "session-1",
            "Can you calculate the load requirements for a 200-amp panel with ASCE 7 compliance and compare the pros and cons of copper versus aluminum wiring?"
        )
        assert receipt.routing_decision == RoutingDecision.SYSTEM_2_DEEP
        assert receipt.estimated_complexity == QueryComplexity.COMPLEX

    def test_routing_receipt_emitted(self) -> None:
        """Every routing decision emits a receipt."""
        _, receipt = self.kernel.add_user_turn("session-1", "What is your name?")
        assert receipt.receipt_id is not None
        assert receipt.session_id == "session-1"
        assert receipt.routing_decision is not None
        assert receipt.timestamp_utc is not None


class TestVoicePipelineContract:
    """Voice pipeline must track state through typed stages."""

    def setup_method(self) -> None:
        self.kernel = VoiceKernel()

    def test_pipeline_initialization(self) -> None:
        """Pipeline initializes with correct defaults."""
        pipeline = self.kernel.initialize_pipeline("session-1")
        assert pipeline.session_id == "session-1"
        assert pipeline.stt_adapter == VoiceAdapterType.STT_DEEPGRAM
        assert pipeline.tts_adapter == VoiceAdapterType.TTS_CARTESIA
        assert pipeline.vad_active is True
        assert pipeline.iron_ear_active is True

    def test_stage_events_recorded(self) -> None:
        """Pipeline stage events are recorded."""
        self.kernel.initialize_pipeline("session-1")
        event = self.kernel.record_stage_event(
            "session-1",
            PipelineStage.STT,
            success=True,
            duration_ms=150,
            adapter_type=VoiceAdapterType.STT_DEEPGRAM,
        )
        assert event is not None
        assert event.success is True
        assert event.duration_ms == 150

    def test_adapter_health_tracking(self) -> None:
        """Adapter health is tracked and retrievable."""
        self.kernel.update_adapter_health(
            VoiceAdapterType.STT_DEEPGRAM,
            AdapterStatus.HEALTHY,
            latency_ms=50,
        )
        health = self.kernel.get_adapter_health(VoiceAdapterType.STT_DEEPGRAM)
        assert health.status == AdapterStatus.HEALTHY
        assert health.latency_ms == 50

    def test_unknown_adapter_returns_unknown_status(self) -> None:
        """Unchecked adapters return UNKNOWN status."""
        health = self.kernel.get_adapter_health(VoiceAdapterType.TTS_ELEVENLABS)
        assert health.status == AdapterStatus.UNKNOWN
