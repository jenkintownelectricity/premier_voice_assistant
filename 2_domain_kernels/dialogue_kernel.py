"""
HIVE215 Dialogue Kernel

Manages dialogue flow including turn management, context windowing,
and routing decisions between System 1 (Groq Fast Brain) and
System 2 (Claude Deep Brain).

Trust model:
    - Transcript input: TRUSTED (already normalized by transcript kernel)
    - LLM routing decision: Internal (TRUSTED)
    - LLM response: PARTIALLY TRUSTED (must be typed before execution)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TurnRole(Enum):
    """Speaker role in a dialogue turn."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FILLER = "filler"  # Filler phrase while System 2 processes


class RoutingDecision(Enum):
    """Which LLM system handles the query."""
    SYSTEM_1_FAST = "system_1_fast"    # Groq + Llama 3.3 70B (~80ms)
    SYSTEM_2_DEEP = "system_2_deep"    # Claude (~2000ms)
    FALLBACK_DIRECT = "fallback_direct"  # Direct Groq when Fast Brain unavailable


class QueryComplexity(Enum):
    """Estimated complexity of a user query."""
    SIMPLE = "simple"          # Greetings, FAQs, yes/no
    MODERATE = "moderate"      # Follow-ups, clarifications
    COMPLEX = "complex"        # Analysis, calculations, multi-step reasoning


@dataclass(frozen=True)
class DialogueTurn:
    """A single turn in the dialogue history."""
    turn_id: str
    role: TurnRole
    text: str
    timestamp_utc: str
    transcript_id: Optional[str]  # Links to TranscriptNormalized if from user
    confidence: Optional[float]
    routing_decision: Optional[RoutingDecision]
    latency_ms: Optional[int]


@dataclass
class DialogueContext:
    """Windowed dialogue context for LLM input construction."""
    session_id: str
    skill_id: Optional[str]
    turns: list[DialogueTurn] = field(default_factory=list)
    max_turns: int = 20
    max_tokens_estimate: int = 4000

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def user_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.role == TurnRole.USER)

    @property
    def last_user_text(self) -> Optional[str]:
        for turn in reversed(self.turns):
            if turn.role == TurnRole.USER:
                return turn.text
        return None


@dataclass(frozen=True)
class RoutingReceipt:
    """Receipt for a routing decision."""
    receipt_id: str
    session_id: str
    turn_id: str
    query_text: str
    estimated_complexity: QueryComplexity
    routing_decision: RoutingDecision
    reason: str
    timestamp_utc: str


# Complexity detection heuristics
_COMPLEX_KEYWORDS = frozenset([
    "calculate", "analyze", "compare", "explain why", "break down",
    "how much would", "what if", "estimate", "pros and cons",
    "step by step", "detailed", "specification", "code compliance",
    "warranty", "ANSI", "SPRI", "ASCE", "load calculation",
])

_SIMPLE_PATTERNS = frozenset([
    "hello", "hi", "hey", "good morning", "good afternoon",
    "yes", "no", "yeah", "nah", "sure", "okay", "ok",
    "thanks", "thank you", "bye", "goodbye",
    "what time", "who are you", "what can you do",
])


def _estimate_complexity(text: str) -> QueryComplexity:
    """Estimate query complexity from text content."""
    text_lower = text.lower().strip()

    # Check simple patterns first
    for pattern in _SIMPLE_PATTERNS:
        if text_lower == pattern or text_lower.startswith(pattern + " ") or text_lower.startswith(pattern + ","):
            return QueryComplexity.SIMPLE

    # Short utterances are generally simple
    word_count = len(text_lower.split())
    if word_count <= 5:
        return QueryComplexity.SIMPLE

    # Check for complex keywords
    for keyword in _COMPLEX_KEYWORDS:
        if keyword in text_lower:
            return QueryComplexity.COMPLEX

    # Long queries with questions tend to be moderate or complex
    if word_count > 20 and "?" in text:
        return QueryComplexity.COMPLEX

    return QueryComplexity.MODERATE


def _decide_routing(complexity: QueryComplexity) -> tuple[RoutingDecision, str]:
    """Decide routing based on complexity."""
    if complexity == QueryComplexity.SIMPLE:
        return RoutingDecision.SYSTEM_1_FAST, "simple query routed to System 1 Fast Brain for low-latency response"
    elif complexity == QueryComplexity.COMPLEX:
        return RoutingDecision.SYSTEM_2_DEEP, "complex query routed to System 2 Deep Brain for thorough analysis"
    else:
        return RoutingDecision.SYSTEM_1_FAST, "moderate query routed to System 1 Fast Brain (default path)"


class DialogueKernel:
    """
    Manages dialogue flow, turn management, and context windowing.

    Maintains per-session dialogue contexts and provides routing decisions
    for the Fast Brain dual-system architecture.
    """

    def __init__(self, max_turns: int = 20, max_tokens_estimate: int = 4000) -> None:
        self._contexts: dict[str, DialogueContext] = {}
        self._max_turns = max_turns
        self._max_tokens_estimate = max_tokens_estimate

    def get_or_create_context(
        self, session_id: str, skill_id: Optional[str] = None
    ) -> DialogueContext:
        """Get existing context or create new one for session."""
        if session_id not in self._contexts:
            self._contexts[session_id] = DialogueContext(
                session_id=session_id,
                skill_id=skill_id,
                max_turns=self._max_turns,
                max_tokens_estimate=self._max_tokens_estimate,
            )
        return self._contexts[session_id]

    def add_user_turn(
        self,
        session_id: str,
        text: str,
        transcript_id: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> tuple[DialogueTurn, RoutingReceipt]:
        """
        Add a user turn and produce a routing decision.

        Returns the created turn and a routing receipt.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        turn_id = str(uuid.uuid4())
        receipt_id = str(uuid.uuid4())
        context = self.get_or_create_context(session_id)

        complexity = _estimate_complexity(text)
        routing_decision, reason = _decide_routing(complexity)

        turn = DialogueTurn(
            turn_id=turn_id,
            role=TurnRole.USER,
            text=text,
            timestamp_utc=now_utc,
            transcript_id=transcript_id,
            confidence=confidence,
            routing_decision=routing_decision,
            latency_ms=None,
        )

        context.turns.append(turn)
        self._enforce_window(context)

        receipt = RoutingReceipt(
            receipt_id=receipt_id,
            session_id=session_id,
            turn_id=turn_id,
            query_text=text,
            estimated_complexity=complexity,
            routing_decision=routing_decision,
            reason=reason,
            timestamp_utc=now_utc,
        )

        return turn, receipt

    def add_assistant_turn(
        self,
        session_id: str,
        text: str,
        routing_decision: Optional[RoutingDecision] = None,
        latency_ms: Optional[int] = None,
    ) -> DialogueTurn:
        """Add an assistant response turn."""
        now_utc = datetime.now(timezone.utc).isoformat()
        context = self.get_or_create_context(session_id)

        turn = DialogueTurn(
            turn_id=str(uuid.uuid4()),
            role=TurnRole.ASSISTANT,
            text=text,
            timestamp_utc=now_utc,
            transcript_id=None,
            confidence=None,
            routing_decision=routing_decision,
            latency_ms=latency_ms,
        )

        context.turns.append(turn)
        self._enforce_window(context)
        return turn

    def add_filler_turn(self, session_id: str, filler_text: str) -> DialogueTurn:
        """Add a filler phrase turn (played while System 2 processes)."""
        now_utc = datetime.now(timezone.utc).isoformat()
        context = self.get_or_create_context(session_id)

        turn = DialogueTurn(
            turn_id=str(uuid.uuid4()),
            role=TurnRole.FILLER,
            text=filler_text,
            timestamp_utc=now_utc,
            transcript_id=None,
            confidence=None,
            routing_decision=RoutingDecision.SYSTEM_2_DEEP,
            latency_ms=None,
        )

        context.turns.append(turn)
        self._enforce_window(context)
        return turn

    def get_context_window(self, session_id: str) -> list[DialogueTurn]:
        """Get the current context window for a session."""
        context = self._contexts.get(session_id)
        if context is None:
            return []
        return list(context.turns)

    def clear_session(self, session_id: str) -> None:
        """Remove session context."""
        self._contexts.pop(session_id, None)

    def _enforce_window(self, context: DialogueContext) -> None:
        """Trim context to stay within turn and token limits."""
        # Trim by turn count
        while len(context.turns) > context.max_turns:
            context.turns.pop(0)

        # Estimate tokens and trim if needed (rough: 1 token ~ 4 chars)
        total_chars = sum(len(t.text) for t in context.turns)
        estimated_tokens = total_chars // 4
        while estimated_tokens > context.max_tokens_estimate and len(context.turns) > 2:
            removed = context.turns.pop(0)
            estimated_tokens -= len(removed.text) // 4
