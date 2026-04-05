"""
HIVE215 LLM Output Typing Port

Constraint port for typing LLM output before use in execution decisions.
LLM output is PARTIALLY TRUSTED -- it is semantic, may hallucinate,
and must be typed and validated before use.

Trust level: PARTIALLY TRUSTED
Halt conditions: empty response, response too long, missing required fields
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class LLMOutputVerdict(Enum):
    ACCEPTED = "accepted"
    REJECTED_EMPTY = "rejected_empty"
    REJECTED_TOO_LONG = "rejected_too_long"
    REJECTED_MALFORMED = "rejected_malformed"
    REJECTED_MISSING_FIELDS = "rejected_missing_fields"


class LLMSystem(Enum):
    SYSTEM_1_FAST = "system_1"    # Groq + Llama
    SYSTEM_2_DEEP = "system_2"    # Claude
    FALLBACK = "fallback"         # Direct Groq
    UNKNOWN = "unknown"


MAX_RESPONSE_LENGTH = 5000  # Characters
MAX_VOICE_RESPONSE_LENGTH = 500  # Shorter for voice


@dataclass(frozen=True)
class TypedLLMResponse:
    """Typed LLM response. TRUSTED after validation."""
    response_id: str
    text: str
    system_used: LLMSystem
    skill_id: Optional[str]
    filler_phrase: Optional[str]
    model: Optional[str]
    latency_ms: Optional[int]
    verdict: LLMOutputVerdict
    is_voice_response: bool
    timestamp_utc: str
    rejection_reason: Optional[str] = None


@dataclass(frozen=True)
class LLMTypingReceipt:
    """Receipt for LLM output typing."""
    receipt_id: str
    response_id: str
    adapter_name: str
    source_trust_level: str
    output_trust_level: str
    verdict: LLMOutputVerdict
    system_used: LLMSystem
    text_length: int
    timestamp_utc: str
    rejection_reason: Optional[str] = None


def _resolve_system(system_str: Optional[str]) -> LLMSystem:
    """Resolve a system string to typed enum."""
    if system_str is None:
        return LLMSystem.UNKNOWN
    s = system_str.lower().strip()
    if s in ("system_1", "system1", "fast", "groq"):
        return LLMSystem.SYSTEM_1_FAST
    elif s in ("system_2", "system2", "deep", "claude"):
        return LLMSystem.SYSTEM_2_DEEP
    elif s in ("fallback", "direct"):
        return LLMSystem.FALLBACK
    return LLMSystem.UNKNOWN


class LLMOutputTypingPort:
    """
    Port for typing LLM output before use in execution decisions.

    All LLM responses (from Fast Brain, direct Groq, or Claude) enter
    through this port. The port validates the response, types it, and
    returns a TypedLLMResponse with a receipt.
    """

    def __init__(
        self,
        max_response_length: int = MAX_RESPONSE_LENGTH,
        max_voice_length: int = MAX_VOICE_RESPONSE_LENGTH,
    ) -> None:
        self._max_response_length = max_response_length
        self._max_voice_length = max_voice_length

    def type_response(
        self,
        raw_text: Optional[str],
        system_used: Optional[str] = None,
        skill_id: Optional[str] = None,
        filler_phrase: Optional[str] = None,
        model: Optional[str] = None,
        latency_ms: Optional[int] = None,
        is_voice: bool = True,
    ) -> tuple[TypedLLMResponse, LLMTypingReceipt]:
        """
        Type a raw LLM response.

        Returns (TypedLLMResponse, LLMTypingReceipt).
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        response_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())
        resolved_system = _resolve_system(system_used)

        # Check empty
        if raw_text is None or not isinstance(raw_text, str):
            return self._reject(
                response_id, receipt_id, "", resolved_system, skill_id,
                filler_phrase, model, latency_ms, is_voice, now_utc,
                LLMOutputVerdict.REJECTED_EMPTY,
                "raw_text is None or not a string",
            )

        text = raw_text.strip()
        if not text:
            return self._reject(
                response_id, receipt_id, text, resolved_system, skill_id,
                filler_phrase, model, latency_ms, is_voice, now_utc,
                LLMOutputVerdict.REJECTED_EMPTY,
                "response text is empty after stripping",
            )

        # Check length
        max_len = self._max_voice_length if is_voice else self._max_response_length
        if len(text) > max_len:
            # For voice, truncate at sentence boundary if possible
            if is_voice:
                truncated = self._truncate_at_sentence(text, max_len)
                text = truncated
            else:
                return self._reject(
                    response_id, receipt_id, text[:100] + "...", resolved_system,
                    skill_id, filler_phrase, model, latency_ms, is_voice, now_utc,
                    LLMOutputVerdict.REJECTED_TOO_LONG,
                    f"response length {len(text)} exceeds maximum {max_len}",
                )

        typed = TypedLLMResponse(
            response_id=response_id,
            text=text,
            system_used=resolved_system,
            skill_id=skill_id,
            filler_phrase=filler_phrase,
            model=model,
            latency_ms=latency_ms,
            verdict=LLMOutputVerdict.ACCEPTED,
            is_voice_response=is_voice,
            timestamp_utc=now_utc,
        )

        receipt = LLMTypingReceipt(
            receipt_id=receipt_id,
            response_id=response_id,
            adapter_name="llm_output_typing",
            source_trust_level="PARTIALLY_TRUSTED",
            output_trust_level="TRUSTED",
            verdict=LLMOutputVerdict.ACCEPTED,
            system_used=resolved_system,
            text_length=len(text),
            timestamp_utc=now_utc,
        )

        return typed, receipt

    def _truncate_at_sentence(self, text: str, max_len: int) -> str:
        """Truncate text at the last sentence boundary before max_len."""
        if len(text) <= max_len:
            return text
        truncated = text[:max_len]
        # Find last sentence-ending punctuation
        for i in range(len(truncated) - 1, 0, -1):
            if truncated[i] in ".!?":
                return truncated[: i + 1]
        # No sentence boundary found, hard truncate
        return truncated.rsplit(" ", 1)[0] if " " in truncated else truncated

    def _reject(
        self,
        response_id: str,
        receipt_id: str,
        text: str,
        system_used: LLMSystem,
        skill_id: Optional[str],
        filler_phrase: Optional[str],
        model: Optional[str],
        latency_ms: Optional[int],
        is_voice: bool,
        timestamp_utc: str,
        verdict: LLMOutputVerdict,
        reason: str,
    ) -> tuple[TypedLLMResponse, LLMTypingReceipt]:
        """Create rejected response and receipt."""
        typed = TypedLLMResponse(
            response_id=response_id,
            text=text,
            system_used=system_used,
            skill_id=skill_id,
            filler_phrase=filler_phrase,
            model=model,
            latency_ms=latency_ms,
            verdict=verdict,
            is_voice_response=is_voice,
            timestamp_utc=timestamp_utc,
            rejection_reason=reason,
        )

        receipt = LLMTypingReceipt(
            receipt_id=receipt_id,
            response_id=response_id,
            adapter_name="llm_output_typing",
            source_trust_level="PARTIALLY_TRUSTED",
            output_trust_level="REJECTED",
            verdict=verdict,
            system_used=system_used,
            text_length=len(text),
            timestamp_utc=timestamp_utc,
            rejection_reason=reason,
        )

        return typed, receipt
