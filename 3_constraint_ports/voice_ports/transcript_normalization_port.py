"""
HIVE215 Transcript Normalization Port

Constraint port for normalizing voice transcripts at the STT boundary.
Declares trust level, schema, and halt conditions.

Trust level: PARTIALLY TRUSTED (Deepgram/Whisper STT output)
Schema: transcript_normalized.schema.json
Halt conditions: malformed input, confidence below threshold, empty text
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# Re-export from kernel for convenience
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from two_domain_kernels.transcript_normalization_kernel import (
    TranscriptNormalizationKernel,
    TranscriptNormalized,
    NormalizationReceipt,
    NormalizationVerdict,
)


class PortTrustLevel(Enum):
    PARTIALLY_TRUSTED = "PARTIALLY_TRUSTED"


@dataclass(frozen=True)
class PortDeclaration:
    """Declares the contract for this port."""
    port_name: str = "transcript_normalization"
    trust_level: PortTrustLevel = PortTrustLevel.PARTIALLY_TRUSTED
    schema_ref: str = "1_governance/schemas/transcript_normalized.schema.json"
    halt_on_empty: bool = True
    halt_on_low_confidence: bool = True
    halt_on_malformed: bool = True
    min_confidence: float = 0.30
    max_text_length: int = 10000


class TranscriptNormalizationPort:
    """
    Port for normalizing voice transcripts from STT providers.

    All STT output enters through this port. The port validates the raw
    transcript, delegates to the normalization kernel, and returns typed
    output with a receipt. Halts on any validation failure.
    """

    DECLARATION = PortDeclaration()

    def __init__(self, min_confidence: float = 0.30) -> None:
        self._kernel = TranscriptNormalizationKernel(min_confidence=min_confidence)

    def process(
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
        Process raw STT output through the normalization port.

        Returns (TranscriptNormalized, NormalizationReceipt).
        Callers MUST check normalization_verdict before using the text.
        """
        return self._kernel.normalize(
            raw_text=raw_text,
            confidence=confidence,
            source=source,
            language=language,
            duration_ms=duration_ms,
            is_final=is_final,
            speaker_id=speaker_id,
        )

    def is_accepted(self, normalized: TranscriptNormalized) -> bool:
        """Check if a normalized transcript was accepted."""
        return normalized.normalization_verdict == NormalizationVerdict.ACCEPTED

    @property
    def trust_level(self) -> str:
        return self.DECLARATION.trust_level.value

    @property
    def schema_ref(self) -> str:
        return self.DECLARATION.schema_ref
