"""
HIVE215 Transcript Normalization Kernel

Normalizes raw STT transcripts into typed TranscriptNormalized records.
Validates, cleans, and types all transcript data before it enters the
governance boundary. Rejects malformed input with fail-closed behavior.

Trust model:
    - Raw STT output (Deepgram): PARTIALLY TRUSTED
    - Output (TranscriptNormalized): TRUSTED after validation
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TranscriptConfidence(Enum):
    """Confidence classification for transcript segments."""
    HIGH = "high"        # >= 0.85
    MEDIUM = "medium"    # >= 0.60
    LOW = "low"          # >= 0.30
    REJECTED = "rejected"  # < 0.30


class TranscriptSource(Enum):
    """Known STT sources."""
    DEEPGRAM_NOVA3 = "deepgram_nova3"
    WHISPER = "whisper"
    UNKNOWN = "unknown"


class NormalizationVerdict(Enum):
    """Result of the normalization process."""
    ACCEPTED = "accepted"
    REJECTED_EMPTY = "rejected_empty"
    REJECTED_LOW_CONFIDENCE = "rejected_low_confidence"
    REJECTED_MALFORMED = "rejected_malformed"
    REJECTED_TOO_SHORT = "rejected_too_short"
    REJECTED_TOO_LONG = "rejected_too_long"


@dataclass(frozen=True)
class TranscriptNormalized:
    """Typed, validated transcript record. Immutable once created."""
    transcript_id: str
    text: str
    text_cleaned: str
    confidence: float
    confidence_level: TranscriptConfidence
    source: TranscriptSource
    language: str
    duration_ms: int
    is_final: bool
    speaker_id: Optional[str]
    timestamp_utc: str
    normalization_verdict: NormalizationVerdict
    word_count: int


@dataclass(frozen=True)
class NormalizationReceipt:
    """Receipt emitted for every normalization attempt."""
    receipt_id: str
    transcript_id: str
    verdict: NormalizationVerdict
    source_trust_level: str
    output_trust_level: str
    confidence_raw: float
    confidence_level: TranscriptConfidence
    text_length_raw: int
    text_length_cleaned: int
    timestamp_utc: str
    rejection_reason: Optional[str] = None


# Constraints
MIN_TRANSCRIPT_LENGTH = 1
MAX_TRANSCRIPT_LENGTH = 10000
MIN_CONFIDENCE_THRESHOLD = 0.30
MIN_DURATION_MS = 50
MAX_DURATION_MS = 300000  # 5 minutes

# Cleaning patterns
_WHITESPACE_COLLAPSE = re.compile(r"\s+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _classify_confidence(confidence: float) -> TranscriptConfidence:
    """Classify raw confidence score into a trust level."""
    if confidence >= 0.85:
        return TranscriptConfidence.HIGH
    elif confidence >= 0.60:
        return TranscriptConfidence.MEDIUM
    elif confidence >= 0.30:
        return TranscriptConfidence.LOW
    else:
        return TranscriptConfidence.REJECTED


def _clean_text(raw_text: str) -> str:
    """Remove control characters, collapse whitespace, strip edges."""
    cleaned = _CONTROL_CHARS.sub("", raw_text)
    cleaned = _WHITESPACE_COLLAPSE.sub(" ", cleaned)
    cleaned = cleaned.strip()
    return cleaned


def _resolve_source(source_str: Optional[str]) -> TranscriptSource:
    """Resolve a source string to a known TranscriptSource."""
    if source_str is None:
        return TranscriptSource.UNKNOWN
    source_lower = source_str.lower()
    if "deepgram" in source_lower or "nova" in source_lower:
        return TranscriptSource.DEEPGRAM_NOVA3
    elif "whisper" in source_lower:
        return TranscriptSource.WHISPER
    return TranscriptSource.UNKNOWN


class TranscriptNormalizationKernel:
    """
    Normalizes raw STT output into typed TranscriptNormalized records.

    Every call to normalize() returns both a TranscriptNormalized record
    (which may have a REJECTED verdict) and a NormalizationReceipt.
    """

    def __init__(
        self,
        min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
        min_length: int = MIN_TRANSCRIPT_LENGTH,
        max_length: int = MAX_TRANSCRIPT_LENGTH,
        min_duration_ms: int = MIN_DURATION_MS,
        max_duration_ms: int = MAX_DURATION_MS,
    ):
        self._min_confidence = min_confidence
        self._min_length = min_length
        self._max_length = max_length
        self._min_duration_ms = min_duration_ms
        self._max_duration_ms = max_duration_ms

    def normalize(
        self,
        raw_text: Optional[str],
        confidence: float,
        source: Optional[str] = None,
        language: str = "en",
        duration_ms: int = 0,
        is_final: bool = True,
        speaker_id: Optional[str] = None,
    ) -> tuple[TranscriptNormalized, NormalizationReceipt]:
        """
        Normalize a raw transcript into a typed record.

        Returns a tuple of (TranscriptNormalized, NormalizationReceipt).
        The TranscriptNormalized may have a REJECTED verdict -- callers
        must check the verdict before using the text.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        transcript_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())
        resolved_source = _resolve_source(source)

        # Validate raw_text exists
        if raw_text is None or not isinstance(raw_text, str):
            return self._reject(
                transcript_id, receipt_id, "", 0.0,
                NormalizationVerdict.REJECTED_MALFORMED,
                resolved_source, language, duration_ms, is_final,
                speaker_id, now_utc, "raw_text is None or not a string",
            )

        cleaned = _clean_text(raw_text)

        # Validate not empty after cleaning
        if len(cleaned) < self._min_length:
            return self._reject(
                transcript_id, receipt_id, cleaned, confidence,
                NormalizationVerdict.REJECTED_EMPTY if len(cleaned) == 0
                else NormalizationVerdict.REJECTED_TOO_SHORT,
                resolved_source, language, duration_ms, is_final,
                speaker_id, now_utc,
                f"cleaned text length {len(cleaned)} below minimum {self._min_length}",
            )

        # Validate not too long
        if len(cleaned) > self._max_length:
            return self._reject(
                transcript_id, receipt_id, cleaned[:100] + "...", confidence,
                NormalizationVerdict.REJECTED_TOO_LONG,
                resolved_source, language, duration_ms, is_final,
                speaker_id, now_utc,
                f"cleaned text length {len(cleaned)} exceeds maximum {self._max_length}",
            )

        # Validate confidence
        confidence_level = _classify_confidence(confidence)
        if confidence_level == TranscriptConfidence.REJECTED:
            return self._reject(
                transcript_id, receipt_id, cleaned, confidence,
                NormalizationVerdict.REJECTED_LOW_CONFIDENCE,
                resolved_source, language, duration_ms, is_final,
                speaker_id, now_utc,
                f"confidence {confidence:.3f} below threshold {self._min_confidence}",
            )

        # Clamp duration
        clamped_duration = max(0, min(duration_ms, self._max_duration_ms))

        word_count = len(cleaned.split())

        normalized = TranscriptNormalized(
            transcript_id=transcript_id,
            text=raw_text,
            text_cleaned=cleaned,
            confidence=confidence,
            confidence_level=confidence_level,
            source=resolved_source,
            language=language,
            duration_ms=clamped_duration,
            is_final=is_final,
            speaker_id=speaker_id,
            timestamp_utc=now_utc,
            normalization_verdict=NormalizationVerdict.ACCEPTED,
            word_count=word_count,
        )

        receipt = NormalizationReceipt(
            receipt_id=receipt_id,
            transcript_id=transcript_id,
            verdict=NormalizationVerdict.ACCEPTED,
            source_trust_level="PARTIALLY_TRUSTED",
            output_trust_level="TRUSTED",
            confidence_raw=confidence,
            confidence_level=confidence_level,
            text_length_raw=len(raw_text),
            text_length_cleaned=len(cleaned),
            timestamp_utc=now_utc,
        )

        return normalized, receipt

    def _reject(
        self,
        transcript_id: str,
        receipt_id: str,
        text: str,
        confidence: float,
        verdict: NormalizationVerdict,
        source: TranscriptSource,
        language: str,
        duration_ms: int,
        is_final: bool,
        speaker_id: Optional[str],
        timestamp_utc: str,
        reason: str,
    ) -> tuple[TranscriptNormalized, NormalizationReceipt]:
        """Create a rejected TranscriptNormalized and its receipt."""
        confidence_level = _classify_confidence(confidence)

        normalized = TranscriptNormalized(
            transcript_id=transcript_id,
            text=text,
            text_cleaned=text,
            confidence=confidence,
            confidence_level=confidence_level,
            source=source,
            language=language,
            duration_ms=max(0, duration_ms),
            is_final=is_final,
            speaker_id=speaker_id,
            timestamp_utc=timestamp_utc,
            normalization_verdict=verdict,
            word_count=0,
        )

        receipt = NormalizationReceipt(
            receipt_id=receipt_id,
            transcript_id=transcript_id,
            verdict=verdict,
            source_trust_level="PARTIALLY_TRUSTED",
            output_trust_level="REJECTED",
            confidence_raw=confidence,
            confidence_level=confidence_level,
            text_length_raw=len(text),
            text_length_cleaned=len(text),
            timestamp_utc=timestamp_utc,
            rejection_reason=reason,
        )

        return normalized, receipt
