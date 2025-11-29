"""
Sentence Boundary Detection for Premier Voice Assistant.

Optimized for real-time voice streaming to detect natural break points
where TTS can start synthesizing without waiting for full LLM response.

Key insight: Don't wait for perfect sentences. Detect natural speech
boundaries that sound good when spoken.

Architecture:
┌─────────────────────────────────────────────────────────────┐
│  SentenceDetector                                            │
│  ├── Rule-based detection (fast, ~0.1ms)                    │
│  ├── Handles abbreviations correctly                         │
│  ├── Detects clause boundaries for long sentences           │
│  └── Streaming-optimized with buffer management             │
└─────────────────────────────────────────────────────────────┘
"""

import re
import logging
from typing import Optional, List, Generator, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class SentenceDetectorConfig:
    """Configuration for sentence detection."""
    # Minimum characters before considering a boundary
    min_sentence_length: int = 15

    # Maximum characters before forcing a break (for long rambling)
    max_sentence_length: int = 200

    # Characters that definitely end sentences
    sentence_enders: str = ".!?"

    # Characters that might be good break points in long sentences
    clause_breakers: str = ",;:"

    # Minimum chars before breaking on clause breaker
    min_clause_length: int = 30

    # Break on newlines
    break_on_newline: bool = True

    # Handle spoken patterns (numbers, etc.)
    spoken_mode: bool = True


# Common abbreviations that shouldn't end sentences
ABBREVIATIONS = {
    # Titles
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "rev", "hon",
    # Academic
    "ph.d", "m.d", "b.a", "m.a", "b.s", "m.s",
    # Common
    "vs", "etc", "eg", "ie", "e.g", "i.e", "inc", "ltd", "co",
    "corp", "llc", "avg", "approx", "dept", "est", "min", "max",
    "govt", "intl", "natl", "univ",
    # Months (abbreviated)
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec",
    # Days
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    # Measurements
    "ft", "in", "lb", "oz", "pt", "qt", "gal", "mi", "km", "cm", "mm",
    "kg", "mg", "ml", "hr", "hrs", "min", "sec", "sq", "cu",
    # Numbers
    "no", "nos", "vol", "vols", "pg", "pp", "ch", "fig", "figs",
    # Streets
    "st", "ave", "blvd", "rd", "dr", "ct", "ln", "pl",
    # States (US)
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
}

# Patterns that look like sentence ends but aren't
FALSE_POSITIVE_PATTERNS = [
    r"\d\.",           # Numbers with periods (1. 2. 3.)
    r"\.\d",           # Decimal numbers (.5, 3.14)
    r"[A-Z]\.",        # Single capital letter abbreviations (J. Smith)
    r"\w\.\w",         # Acronyms with periods (U.S.A)
]


# ============================================================================
# SENTENCE DETECTOR
# ============================================================================

class SentenceDetector:
    """
    Detects sentence boundaries in streaming text.

    Optimized for voice AI where we want to:
    1. Start TTS as soon as we have a speakable chunk
    2. Not break mid-thought
    3. Handle long sentences by finding clause boundaries

    Usage:
        detector = SentenceDetector()

        # Feed tokens one at a time
        for token in llm_tokens:
            sentence = detector.feed(token)
            if sentence:
                send_to_tts(sentence)

        # Get any remaining text
        final = detector.flush()
        if final:
            send_to_tts(final)
    """

    def __init__(self, config: Optional[SentenceDetectorConfig] = None):
        self.config = config or SentenceDetectorConfig()
        self._buffer = ""
        self._sentence_count = 0

    def feed(self, token: str) -> Optional[str]:
        """
        Feed a token and return a complete sentence if detected.

        Args:
            token: New text token from LLM

        Returns:
            Complete sentence if boundary detected, None otherwise
        """
        self._buffer += token

        # Check for forced break on newline
        if self.config.break_on_newline and "\n" in self._buffer:
            parts = self._buffer.split("\n", 1)
            sentence = parts[0].strip()
            self._buffer = parts[1] if len(parts) > 1 else ""

            if sentence and len(sentence) >= self.config.min_sentence_length:
                self._sentence_count += 1
                return sentence

        # Check for sentence boundary
        sentence = self._check_boundary()
        if sentence:
            self._sentence_count += 1
            return sentence

        return None

    def _check_boundary(self) -> Optional[str]:
        """Check if buffer ends at a sentence boundary."""
        text = self._buffer.rstrip()

        if len(text) < self.config.min_sentence_length:
            return None

        # Check for standard sentence enders
        for ender in self.config.sentence_enders:
            if text.endswith(ender):
                if self._is_real_sentence_end(text, ender):
                    sentence = text
                    self._buffer = ""
                    return sentence

        # Check for forced break on very long text
        if len(text) > self.config.max_sentence_length:
            return self._force_break()

        # Check for clause boundaries in moderately long text
        if len(text) > self.config.min_clause_length:
            clause = self._check_clause_boundary()
            if clause:
                return clause

        return None

    def _is_real_sentence_end(self, text: str, ender: str) -> bool:
        """
        Check if this is a real sentence end vs abbreviation/number.

        Args:
            text: Full text ending with the potential sentence ender
            ender: The punctuation character

        Returns:
            True if this is a real sentence end
        """
        # Question marks and exclamation points are always sentence ends
        if ender in "!?":
            return True

        # For periods, need to check for abbreviations
        if ender == ".":
            # Get the word before the period
            words = text[:-1].split()
            if not words:
                return False

            last_word = words[-1].lower().rstrip(".")

            # Check abbreviation list
            if last_word in ABBREVIATIONS:
                return False

            # Check for single capital letter (initials)
            if len(last_word) == 1 and last_word.isupper():
                return False

            # Check for false positive patterns
            for pattern in FALSE_POSITIVE_PATTERNS:
                if re.search(pattern + r"$", text):
                    return False

            # Check if followed by lowercase (would indicate continuation)
            # This is tricky in streaming - we don't know what comes next
            # So we're optimistic and assume it's a sentence end

            return True

        return False

    def _check_clause_boundary(self) -> Optional[str]:
        """
        Check for clause boundaries in long sentences.

        This helps break up long rambling responses at natural pause points.
        """
        text = self._buffer.rstrip()

        # Look for clause breakers from the end
        for i in range(len(text) - 1, self.config.min_clause_length - 1, -1):
            if text[i] in self.config.clause_breakers:
                # Found a potential break point
                # Make sure there's enough content after
                remaining = text[i + 1:].strip()
                if len(remaining) > 5:  # Don't break if almost done
                    continue

                # Check that the clause is meaningful
                clause = text[:i + 1].strip()
                if len(clause) >= self.config.min_clause_length:
                    self._buffer = text[i + 1:]
                    return clause

        return None

    def _force_break(self) -> Optional[str]:
        """
        Force a break in very long text by finding the best break point.
        """
        text = self._buffer.rstrip()

        # Try to find a good break point
        # Priority: sentence enders > clause breakers > space

        # Look for sentence enders
        for i in range(len(text) - 1, self.config.min_sentence_length - 1, -1):
            if text[i] in self.config.sentence_enders:
                sentence = text[:i + 1]
                self._buffer = text[i + 1:]
                return sentence

        # Look for clause breakers
        for i in range(len(text) - 1, self.config.min_clause_length - 1, -1):
            if text[i] in self.config.clause_breakers:
                clause = text[:i + 1]
                self._buffer = text[i + 1:]
                return clause

        # Last resort: break at last space
        last_space = text.rfind(" ", self.config.min_sentence_length)
        if last_space > 0:
            chunk = text[:last_space]
            self._buffer = text[last_space + 1:]
            return chunk

        # Give up and return everything
        self._buffer = ""
        return text

    def flush(self) -> Optional[str]:
        """
        Flush any remaining text in the buffer.

        Call this when the LLM is done generating.

        Returns:
            Remaining text, or None if empty
        """
        text = self._buffer.strip()
        self._buffer = ""

        if text:
            self._sentence_count += 1
            return text

        return None

    def reset(self):
        """Reset the detector state."""
        self._buffer = ""
        self._sentence_count = 0

    @property
    def buffer_length(self) -> int:
        """Current buffer length."""
        return len(self._buffer)

    @property
    def sentence_count(self) -> int:
        """Number of sentences detected."""
        return self._sentence_count


# ============================================================================
# STREAMING SENTENCE ITERATOR
# ============================================================================

def stream_sentences(
    token_generator: Generator[str, None, None],
    config: Optional[SentenceDetectorConfig] = None,
) -> Generator[str, None, None]:
    """
    Generator that yields complete sentences from a token stream.

    Usage:
        tokens = llm.generate_tokens(prompt)
        for sentence in stream_sentences(tokens):
            tts.speak(sentence)
    """
    detector = SentenceDetector(config)

    for token in token_generator:
        sentence = detector.feed(token)
        if sentence:
            yield sentence

    # Flush remaining
    final = detector.flush()
    if final:
        yield final


async def stream_sentences_async(
    token_generator,  # AsyncGenerator[str, None]
    config: Optional[SentenceDetectorConfig] = None,
):
    """
    Async generator that yields complete sentences from a token stream.

    Usage:
        async for sentence in stream_sentences_async(llm.stream_tokens()):
            await tts.speak(sentence)
    """
    detector = SentenceDetector(config)

    async for token in token_generator:
        sentence = detector.feed(token)
        if sentence:
            yield sentence

    # Flush remaining
    final = detector.flush()
    if final:
        yield final


# ============================================================================
# BATCH SENTENCE SPLITTING
# ============================================================================

def split_into_sentences(
    text: str,
    config: Optional[SentenceDetectorConfig] = None,
) -> List[str]:
    """
    Split text into sentences.

    For non-streaming use cases where you have the full text.

    Args:
        text: Full text to split
        config: Optional detector configuration

    Returns:
        List of sentences
    """
    detector = SentenceDetector(config)
    sentences = []

    # Feed character by character to use the same logic
    for char in text:
        sentence = detector.feed(char)
        if sentence:
            sentences.append(sentence)

    # Flush remaining
    final = detector.flush()
    if final:
        sentences.append(final)

    return sentences


def split_for_tts(
    text: str,
    max_chunk_length: int = 150,
    min_chunk_length: int = 20,
) -> List[str]:
    """
    Split text into chunks optimized for TTS.

    Tries to create chunks of similar length while respecting
    sentence boundaries.

    Args:
        text: Text to split
        max_chunk_length: Maximum characters per chunk
        min_chunk_length: Minimum characters per chunk

    Returns:
        List of TTS-optimized chunks
    """
    config = SentenceDetectorConfig(
        min_sentence_length=min_chunk_length,
        max_sentence_length=max_chunk_length,
    )

    return split_into_sentences(text, config)


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 60)
    print("SENTENCE DETECTOR TEST")
    print("=" * 60 + "\n")

    detector = SentenceDetector()

    # Test cases
    test_texts = [
        # Standard sentences
        "Hello, how are you? I'm doing great! Thanks for asking.",

        # Abbreviations
        "Dr. Smith works at Inc. Ltd. He has a Ph.D. from MIT.",

        # Numbers and decimals
        "The price is $3.50 per unit. We sold 1,234 items.",

        # Long sentence with clauses
        "This is a very long sentence that goes on and on, with multiple clauses, and keeps talking about various things, because sometimes people ramble.",

        # Lists
        "Here are the steps: 1. First thing. 2. Second thing. 3. Third thing.",

        # Initials
        "J. K. Rowling wrote Harry Potter. George R. R. Martin wrote Game of Thrones.",

        # Mixed
        "Dr. Watson said, 'The game is afoot!' Sherlock Holmes replied with a nod. They proceeded to investigate.",
    ]

    for text in test_texts:
        print(f"Input: {text[:60]}...")
        print("Sentences:")

        detector.reset()

        # Simulate streaming token by token
        for char in text:
            sentence = detector.feed(char)
            if sentence:
                print(f"  -> {sentence}")

        # Flush remaining
        final = detector.flush()
        if final:
            print(f"  -> {final}")

        print()

    # Test batch splitting
    print("=" * 60)
    print("BATCH SPLIT TEST")
    print("=" * 60 + "\n")

    long_text = """
    Artificial intelligence is transforming the world. It's being used in healthcare,
    finance, and transportation. Dr. Smith at MIT says, "AI will change everything."
    The market is expected to reach $190.61 billion by 2025. Companies like Google,
    Microsoft, and OpenAI are leading the way. What does this mean for the future?
    Only time will tell!
    """

    sentences = split_into_sentences(long_text.strip())
    print(f"Found {len(sentences)} sentences:")
    for i, s in enumerate(sentences, 1):
        print(f"  {i}. {s}")

    print("\n" + "=" * 60 + "\n")
