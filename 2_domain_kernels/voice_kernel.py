"""
HIVE215 Voice Kernel

Governs the voice pipeline: STT adapter management, TTS adapter management,
VAD coordination, and Iron Ear integration. Ensures all audio processing
passes through typed, constrained boundaries.

Trust model:
    - Raw audio frames: UNTRUSTED (from LiveKit transport)
    - STT output: PARTIALLY TRUSTED (Deepgram)
    - TTS input: TRUSTED (validated response text)
    - TTS output: PARTIALLY TRUSTED (Cartesia audio)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class VoiceAdapterType(Enum):
    """Known voice service adapter types."""
    STT_DEEPGRAM = "stt_deepgram"
    STT_WHISPER = "stt_whisper"
    TTS_CARTESIA = "tts_cartesia"
    TTS_COQUI = "tts_coqui"
    TTS_KOKORO = "tts_kokoro"
    TTS_ELEVENLABS = "tts_elevenlabs"
    TTS_DEEPGRAM = "tts_deepgram"
    VAD_SILERO = "vad_silero"


class AdapterStatus(Enum):
    """Health status of a voice adapter."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PipelineStage(Enum):
    """Stages of the voice pipeline."""
    AUDIO_INGRESS = "audio_ingress"
    VAD = "vad"
    IRON_EAR_FILTER = "iron_ear_filter"
    STT = "stt"
    TRANSCRIPT_NORMALIZATION = "transcript_normalization"
    DIALOGUE_ROUTING = "dialogue_routing"
    LLM_PROCESSING = "llm_processing"
    RESPONSE_TYPING = "response_typing"
    TTS = "tts"
    AUDIO_EGRESS = "audio_egress"


@dataclass(frozen=True)
class AdapterHealthRecord:
    """Health status record for a voice adapter."""
    adapter_type: VoiceAdapterType
    status: AdapterStatus
    latency_ms: Optional[int]
    last_check_utc: str
    error_message: Optional[str] = None


@dataclass(frozen=True)
class PipelineEvent:
    """Record of a pipeline stage execution."""
    event_id: str
    session_id: str
    stage: PipelineStage
    started_utc: str
    completed_utc: Optional[str]
    duration_ms: Optional[int]
    adapter_type: Optional[VoiceAdapterType]
    success: bool
    error_message: Optional[str] = None


@dataclass
class VoicePipelineState:
    """Current state of the voice pipeline for a session."""
    session_id: str
    current_stage: PipelineStage
    stt_adapter: VoiceAdapterType
    tts_adapter: VoiceAdapterType
    vad_active: bool
    iron_ear_active: bool
    identity_locked: bool
    events: list[PipelineEvent] = field(default_factory=list)

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def last_error(self) -> Optional[str]:
        for event in reversed(self.events):
            if not event.success and event.error_message:
                return event.error_message
        return None


class VoiceKernel:
    """
    Governs the voice pipeline.

    Manages STT/TTS adapter selection, tracks pipeline state per session,
    and records pipeline events for receipting.
    """

    def __init__(
        self,
        default_stt: VoiceAdapterType = VoiceAdapterType.STT_DEEPGRAM,
        default_tts: VoiceAdapterType = VoiceAdapterType.TTS_CARTESIA,
    ) -> None:
        self._default_stt = default_stt
        self._default_tts = default_tts
        self._pipelines: dict[str, VoicePipelineState] = {}
        self._adapter_health: dict[VoiceAdapterType, AdapterHealthRecord] = {}

    def initialize_pipeline(
        self,
        session_id: str,
        stt_adapter: Optional[VoiceAdapterType] = None,
        tts_adapter: Optional[VoiceAdapterType] = None,
        iron_ear_active: bool = True,
    ) -> VoicePipelineState:
        """Initialize a voice pipeline for a session."""
        pipeline = VoicePipelineState(
            session_id=session_id,
            current_stage=PipelineStage.AUDIO_INGRESS,
            stt_adapter=stt_adapter or self._default_stt,
            tts_adapter=tts_adapter or self._default_tts,
            vad_active=True,
            iron_ear_active=iron_ear_active,
            identity_locked=False,
        )
        self._pipelines[session_id] = pipeline
        return pipeline

    def record_stage_event(
        self,
        session_id: str,
        stage: PipelineStage,
        success: bool,
        duration_ms: Optional[int] = None,
        adapter_type: Optional[VoiceAdapterType] = None,
        error_message: Optional[str] = None,
    ) -> Optional[PipelineEvent]:
        """Record a pipeline stage execution event."""
        pipeline = self._pipelines.get(session_id)
        if pipeline is None:
            return None

        now_utc = datetime.now(timezone.utc).isoformat()
        event = PipelineEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            stage=stage,
            started_utc=now_utc,
            completed_utc=now_utc if success else None,
            duration_ms=duration_ms,
            adapter_type=adapter_type,
            success=success,
            error_message=error_message,
        )

        pipeline.events.append(event)
        if success:
            pipeline.current_stage = stage
        return event

    def update_adapter_health(
        self,
        adapter_type: VoiceAdapterType,
        status: AdapterStatus,
        latency_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> AdapterHealthRecord:
        """Update health status for a voice adapter."""
        record = AdapterHealthRecord(
            adapter_type=adapter_type,
            status=status,
            latency_ms=latency_ms,
            last_check_utc=datetime.now(timezone.utc).isoformat(),
            error_message=error_message,
        )
        self._adapter_health[adapter_type] = record
        return record

    def get_adapter_health(self, adapter_type: VoiceAdapterType) -> AdapterHealthRecord:
        """Get current health for an adapter. Returns UNKNOWN if never checked."""
        return self._adapter_health.get(
            adapter_type,
            AdapterHealthRecord(
                adapter_type=adapter_type,
                status=AdapterStatus.UNKNOWN,
                latency_ms=None,
                last_check_utc=datetime.now(timezone.utc).isoformat(),
            ),
        )

    def get_pipeline(self, session_id: str) -> Optional[VoicePipelineState]:
        """Get pipeline state for a session."""
        return self._pipelines.get(session_id)

    def set_identity_locked(self, session_id: str, locked: bool) -> bool:
        """Set identity lock state. Returns False if session not found."""
        pipeline = self._pipelines.get(session_id)
        if pipeline is None:
            return False
        pipeline.identity_locked = locked
        return True

    def select_fallback_tts(self, session_id: str) -> Optional[VoiceAdapterType]:
        """
        Select a fallback TTS adapter if the current one is unhealthy.
        Returns None if no healthy fallback is available.
        """
        pipeline = self._pipelines.get(session_id)
        if pipeline is None:
            return None

        tts_adapters = [
            VoiceAdapterType.TTS_CARTESIA,
            VoiceAdapterType.TTS_ELEVENLABS,
            VoiceAdapterType.TTS_DEEPGRAM,
            VoiceAdapterType.TTS_COQUI,
            VoiceAdapterType.TTS_KOKORO,
        ]

        for adapter in tts_adapters:
            if adapter == pipeline.tts_adapter:
                continue
            health = self.get_adapter_health(adapter)
            if health.status == AdapterStatus.HEALTHY:
                pipeline.tts_adapter = adapter
                return adapter

        return None

    def teardown_pipeline(self, session_id: str) -> Optional[VoicePipelineState]:
        """Remove pipeline state for a session. Returns the final state."""
        return self._pipelines.pop(session_id, None)
