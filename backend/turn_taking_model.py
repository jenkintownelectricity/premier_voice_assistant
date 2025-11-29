"""
Custom Turn-Taking Model for Natural Conversation Flow

This module implements a sophisticated turn-taking system that mimics
human conversational patterns using multiple signals:
- Audio features (silence, energy, pitch trends)
- Text features (sentence completion, question detection)
- Prosodic cues (speech rate changes, hesitation markers)
- Predictive modeling for turn boundary detection

Inspired by research on conversational turn-taking and competitive
implementations from Vapi, ElevenLabs, and Rilla Voice.
"""

import asyncio
import time
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class TurnState(Enum):
    """Current state of the turn-taking system."""
    USER_SPEAKING = "user_speaking"
    USER_PAUSING = "user_pausing"  # Brief pause, might continue
    TURN_YIELDED = "turn_yielded"  # User finished, assistant can speak
    ASSISTANT_SPEAKING = "assistant_speaking"
    ASSISTANT_YIELDED = "assistant_yielded"
    BACKCHANNEL = "backchannel"  # Short acknowledgment


class TurnEagerness(Enum):
    """How quickly the assistant takes turns."""
    LOW = "low"        # Patient, waits longer for user
    BALANCED = "balanced"  # Default behavior
    HIGH = "high"      # Quick responses, more interruption-tolerant


@dataclass
class TurnTakingConfig:
    """Configuration for the turn-taking model."""
    # Eagerness preset
    turn_eagerness: TurnEagerness = TurnEagerness.BALANCED

    # Silence thresholds (in ms) - adjusted per eagerness
    min_silence_for_turn: int = 400   # Minimum silence to consider turn end
    confident_silence: int = 800      # High confidence turn end
    max_wait_silence: int = 1500      # Force turn after this silence

    # Response timing
    response_delay_ms: int = 200      # Base delay before responding

    # Prosodic features
    use_pitch_detection: bool = True  # Detect falling pitch as turn end
    use_energy_detection: bool = True # Detect energy drop as turn end

    # Text features
    use_sentence_completion: bool = True  # Detect complete sentences
    use_question_detection: bool = True   # Questions need quick response
    use_hesitation_detection: bool = True # "um", "uh" extend wait time

    # Backchanneling
    enable_backchannels: bool = True  # Send "mm-hmm", "I see" during user speech
    backchannel_interval_ms: int = 3000  # Min time between backchannels
    backchannel_probability: float = 0.3  # Chance of backchannel at opportunity

    # Turn prediction
    prediction_threshold: float = 0.7  # Confidence needed to predict turn end

    # Barge-in
    allow_barge_in: bool = True
    barge_in_threshold_ms: int = 200  # Min user speech to trigger barge-in


@dataclass
class TurnSignals:
    """Signals used to predict turn boundaries."""
    # Timing signals
    silence_duration_ms: float = 0.0
    speech_duration_ms: float = 0.0
    time_since_last_word_ms: float = 0.0

    # Audio signals (0.0 to 1.0)
    energy_level: float = 0.5
    energy_trend: float = 0.0  # Positive = rising, negative = falling
    pitch_trend: float = 0.0   # Positive = rising, negative = falling
    speech_rate: float = 1.0   # Relative to baseline

    # Text signals
    transcript: str = ""
    is_complete_sentence: bool = False
    ends_with_question: bool = False
    has_hesitation: bool = False
    word_count: int = 0

    # Computed confidence
    turn_end_confidence: float = 0.0


@dataclass
class TurnPrediction:
    """Result of turn-taking prediction."""
    should_take_turn: bool = False
    confidence: float = 0.0
    recommended_delay_ms: int = 200
    reason: str = ""
    should_backchannel: bool = False
    backchannel_text: Optional[str] = None


# Hesitation markers that indicate the user might continue
HESITATION_MARKERS = {
    "um", "uh", "er", "ah", "hmm", "hm",
    "like", "you know", "i mean", "well",
    "so", "and", "but", "or", "actually",
    "basically", "literally", "honestly"
}

# Sentence-ending patterns
SENTENCE_END_PATTERN = re.compile(r'[.!?][\s]*$')
QUESTION_PATTERN = re.compile(r'\?[\s]*$')

# Incomplete sentence indicators
INCOMPLETE_INDICATORS = {
    "the", "a", "an", "to", "for", "with", "from", "by",
    "in", "on", "at", "of", "that", "which", "who",
    "if", "when", "where", "because", "although", "while"
}

# Backchannel responses
BACKCHANNELS = [
    "mm-hmm",
    "I see",
    "right",
    "okay",
    "got it",
    "yes",
    "uh-huh",
]


class TurnTakingModel:
    """
    Advanced turn-taking model for natural conversation flow.

    Uses multiple signals to predict when the user has finished speaking
    and when the assistant should respond, mimicking human conversation
    patterns.
    """

    def __init__(self, config: Optional[TurnTakingConfig] = None):
        self.config = config or TurnTakingConfig()
        self._apply_eagerness_presets()

        self.state = TurnState.ASSISTANT_YIELDED
        self.signals = TurnSignals()

        # Timing
        self._speech_start_time: Optional[float] = None
        self._last_word_time: Optional[float] = None
        self._last_speech_time: Optional[float] = None
        self._last_backchannel_time: float = 0.0

        # Audio feature history
        self._energy_history: deque = deque(maxlen=20)
        self._pitch_history: deque = deque(maxlen=20)

        # Transcript buffer
        self._transcript_buffer: str = ""
        self._word_timestamps: List[float] = []

        # Callbacks
        self.on_turn_detected: Optional[Callable[[TurnPrediction], Any]] = None
        self.on_backchannel: Optional[Callable[[str], Any]] = None
        self.on_state_change: Optional[Callable[[TurnState], Any]] = None

        logger.info(f"TurnTakingModel initialized with eagerness={self.config.turn_eagerness.value}")

    def _apply_eagerness_presets(self):
        """Apply timing presets based on turn eagerness setting."""
        if self.config.turn_eagerness == TurnEagerness.LOW:
            # Patient - wait longer, less aggressive
            self.config.min_silence_for_turn = 600
            self.config.confident_silence = 1200
            self.config.max_wait_silence = 2000
            self.config.response_delay_ms = 400
            self.config.prediction_threshold = 0.8
            self.config.backchannel_probability = 0.4

        elif self.config.turn_eagerness == TurnEagerness.HIGH:
            # Eager - quick responses, more interruption-tolerant
            self.config.min_silence_for_turn = 250
            self.config.confident_silence = 500
            self.config.max_wait_silence = 1000
            self.config.response_delay_ms = 100
            self.config.prediction_threshold = 0.6
            self.config.backchannel_probability = 0.2

        # BALANCED uses default values

    def set_eagerness(self, eagerness: str):
        """Update turn eagerness at runtime."""
        try:
            self.config.turn_eagerness = TurnEagerness(eagerness)
            self._apply_eagerness_presets()
            logger.info(f"Turn eagerness updated to {eagerness}")
        except ValueError:
            logger.warning(f"Invalid eagerness value: {eagerness}")

    def _set_state(self, new_state: TurnState):
        """Update state and trigger callback."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.debug(f"Turn state: {old_state.value} -> {new_state.value}")
            if self.on_state_change:
                asyncio.create_task(self._safe_callback(self.on_state_change, new_state))

    async def _safe_callback(self, callback: Callable, *args):
        """Safely execute callback."""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Callback error: {e}")

    # ========== Input Methods ==========

    def on_speech_start(self):
        """Called when user starts speaking."""
        now = time.time()
        self._speech_start_time = now
        self._last_word_time = now
        self._last_speech_time = now
        self.signals.silence_duration_ms = 0

        if self.state == TurnState.ASSISTANT_SPEAKING:
            if self.config.allow_barge_in:
                self._set_state(TurnState.USER_SPEAKING)
                logger.info("Barge-in detected - user interrupted assistant")
        else:
            self._set_state(TurnState.USER_SPEAKING)

    def on_speech_end(self):
        """Called when VAD detects speech stopped."""
        self._last_speech_time = time.time()
        if self.state == TurnState.USER_SPEAKING:
            self._set_state(TurnState.USER_PAUSING)

    def on_transcript(self, text: str, is_final: bool = False):
        """Called with transcript updates (interim or final)."""
        now = time.time()
        self._last_word_time = now
        self._word_timestamps.append(now)

        if is_final:
            self._transcript_buffer = text
        else:
            # Interim - update for analysis
            self._transcript_buffer = text

        self.signals.transcript = self._transcript_buffer
        self.signals.word_count = len(self._transcript_buffer.split())

        # Analyze text features
        self._analyze_text_features()

    def on_audio_features(self, energy: float, pitch: Optional[float] = None):
        """Called with audio feature updates."""
        # Track energy
        self._energy_history.append(energy)
        self.signals.energy_level = energy

        if len(self._energy_history) >= 3:
            # Calculate trend
            recent = list(self._energy_history)[-5:]
            self.signals.energy_trend = recent[-1] - recent[0]

        # Track pitch if available
        if pitch is not None:
            self._pitch_history.append(pitch)
            if len(self._pitch_history) >= 3:
                recent = list(self._pitch_history)[-5:]
                self.signals.pitch_trend = recent[-1] - recent[0]

    def on_silence(self, duration_ms: float):
        """Called with silence duration updates."""
        self.signals.silence_duration_ms = duration_ms

        if self.state == TurnState.USER_SPEAKING:
            self._set_state(TurnState.USER_PAUSING)

    # ========== Analysis Methods ==========

    def _analyze_text_features(self):
        """Analyze transcript for turn-taking signals."""
        text = self._transcript_buffer.lower().strip()

        if not text:
            return

        # Check for complete sentence
        if self.config.use_sentence_completion:
            self.signals.is_complete_sentence = bool(SENTENCE_END_PATTERN.search(self._transcript_buffer))

        # Check for question
        if self.config.use_question_detection:
            self.signals.ends_with_question = bool(QUESTION_PATTERN.search(self._transcript_buffer))

        # Check for hesitation markers
        if self.config.use_hesitation_detection:
            words = text.split()
            last_words = " ".join(words[-3:]) if len(words) >= 3 else text
            self.signals.has_hesitation = any(
                marker in last_words for marker in HESITATION_MARKERS
            )

        # Calculate speech rate
        if self._word_timestamps and self._speech_start_time:
            duration = time.time() - self._speech_start_time
            if duration > 0:
                self.signals.speech_rate = len(self._word_timestamps) / duration

    def _calculate_turn_confidence(self) -> float:
        """
        Calculate confidence that the user has finished their turn.

        Uses a weighted combination of signals:
        - Silence duration (primary signal)
        - Sentence completion (strong signal)
        - Pitch/energy trends (supporting signals)
        - Hesitation markers (negative signal)
        """
        confidence = 0.0

        # Silence-based confidence (0 to 0.4)
        silence = self.signals.silence_duration_ms
        if silence >= self.config.max_wait_silence:
            confidence += 0.4
        elif silence >= self.config.confident_silence:
            confidence += 0.3
        elif silence >= self.config.min_silence_for_turn:
            confidence += 0.2 * (silence / self.config.confident_silence)

        # Sentence completion (0 to 0.3)
        if self.signals.is_complete_sentence:
            confidence += 0.3
        elif self.signals.word_count >= 3:
            # Partial credit for longer utterances
            confidence += 0.1

        # Question detection - boost confidence for quick response
        if self.signals.ends_with_question:
            confidence += 0.15

        # Energy trend (0 to 0.1)
        if self.config.use_energy_detection and self.signals.energy_trend < -0.1:
            # Falling energy suggests end of utterance
            confidence += 0.1

        # Pitch trend (0 to 0.1)
        if self.config.use_pitch_detection and self.signals.pitch_trend < -0.1:
            # Falling pitch suggests statement completion
            confidence += 0.1

        # Hesitation penalty (-0.2)
        if self.signals.has_hesitation:
            confidence -= 0.2

        # Check for incomplete sentence indicators
        if self._transcript_buffer:
            last_word = self._transcript_buffer.split()[-1].lower().rstrip(".,!?")
            if last_word in INCOMPLETE_INDICATORS:
                confidence -= 0.15

        return max(0.0, min(1.0, confidence))

    # ========== Prediction Methods ==========

    async def predict_turn(self) -> TurnPrediction:
        """
        Predict whether the assistant should take a turn.

        Returns a TurnPrediction with:
        - should_take_turn: Whether to start responding
        - confidence: How confident we are
        - recommended_delay_ms: Suggested wait time
        - reason: Explanation for the decision
        """
        confidence = self._calculate_turn_confidence()
        self.signals.turn_end_confidence = confidence

        prediction = TurnPrediction()
        prediction.confidence = confidence

        # Check for forced turn (max silence exceeded)
        if self.signals.silence_duration_ms >= self.config.max_wait_silence:
            prediction.should_take_turn = True
            prediction.confidence = 1.0
            prediction.recommended_delay_ms = 0
            prediction.reason = "Maximum silence threshold exceeded"

        # High confidence turn detection
        elif confidence >= self.config.prediction_threshold:
            prediction.should_take_turn = True

            # Adjust delay based on confidence and context
            if self.signals.ends_with_question:
                # Quick response to questions
                prediction.recommended_delay_ms = int(self.config.response_delay_ms * 0.5)
                prediction.reason = "Question detected - quick response"
            elif self.signals.is_complete_sentence:
                prediction.recommended_delay_ms = self.config.response_delay_ms
                prediction.reason = "Complete sentence with high confidence"
            else:
                # Slightly longer delay for uncertain cases
                prediction.recommended_delay_ms = int(self.config.response_delay_ms * 1.5)
                prediction.reason = f"Turn predicted (confidence: {confidence:.2f})"

        # Not ready to take turn
        else:
            prediction.should_take_turn = False
            prediction.reason = f"Waiting for turn signal (confidence: {confidence:.2f})"

        # Check for backchannel opportunity
        prediction.should_backchannel, prediction.backchannel_text = self._check_backchannel()

        return prediction

    def _check_backchannel(self) -> tuple[bool, Optional[str]]:
        """Check if we should send a backchannel response."""
        if not self.config.enable_backchannels:
            return False, None

        if self.state != TurnState.USER_SPEAKING:
            return False, None

        now = time.time()
        time_since_backchannel = (now - self._last_backchannel_time) * 1000

        # Check if enough time has passed
        if time_since_backchannel < self.config.backchannel_interval_ms:
            return False, None

        # Check if user has been speaking long enough
        if self._speech_start_time:
            speech_duration = (now - self._speech_start_time) * 1000
            if speech_duration < 2000:  # At least 2 seconds
                return False, None

        # Probability-based backchannel
        import random
        if random.random() < self.config.backchannel_probability:
            self._last_backchannel_time = now
            backchannel = random.choice(BACKCHANNELS)
            return True, backchannel

        return False, None

    # ========== Turn Management ==========

    async def wait_for_turn(self, timeout_ms: int = 5000) -> TurnPrediction:
        """
        Wait until it's appropriate to take a turn.

        This method continuously monitors signals and returns when
        the model predicts the user has finished speaking.
        """
        start_time = time.time()
        timeout_s = timeout_ms / 1000.0

        while True:
            # Check timeout
            if time.time() - start_time > timeout_s:
                return TurnPrediction(
                    should_take_turn=True,
                    confidence=0.5,
                    recommended_delay_ms=0,
                    reason="Timeout waiting for turn"
                )

            # Get prediction
            prediction = await self.predict_turn()

            if prediction.should_take_turn:
                # Apply recommended delay
                if prediction.recommended_delay_ms > 0:
                    await asyncio.sleep(prediction.recommended_delay_ms / 1000.0)

                    # Re-check after delay (user might have started speaking)
                    if self.state == TurnState.USER_SPEAKING:
                        continue

                self._set_state(TurnState.TURN_YIELDED)

                if self.on_turn_detected:
                    await self._safe_callback(self.on_turn_detected, prediction)

                return prediction

            # Handle backchannel
            if prediction.should_backchannel and prediction.backchannel_text:
                if self.on_backchannel:
                    await self._safe_callback(self.on_backchannel, prediction.backchannel_text)

            # Short sleep before next check
            await asyncio.sleep(0.05)  # 50ms polling

    def start_assistant_turn(self):
        """Called when assistant starts speaking."""
        self._set_state(TurnState.ASSISTANT_SPEAKING)

    def end_assistant_turn(self):
        """Called when assistant finishes speaking."""
        self._set_state(TurnState.ASSISTANT_YIELDED)
        self.reset_for_next_turn()

    def reset_for_next_turn(self):
        """Reset signals for the next turn."""
        self._transcript_buffer = ""
        self._word_timestamps = []
        self._energy_history.clear()
        self._pitch_history.clear()
        self.signals = TurnSignals()
        self._speech_start_time = None
        self._last_word_time = None

    # ========== Utility Methods ==========

    def get_state(self) -> TurnState:
        """Get current turn state."""
        return self.state

    def get_signals(self) -> TurnSignals:
        """Get current signal values."""
        return self.signals

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information for logging/monitoring."""
        return {
            "state": self.state.value,
            "eagerness": self.config.turn_eagerness.value,
            "signals": {
                "silence_ms": self.signals.silence_duration_ms,
                "speech_ms": self.signals.speech_duration_ms,
                "energy": self.signals.energy_level,
                "energy_trend": self.signals.energy_trend,
                "pitch_trend": self.signals.pitch_trend,
                "is_complete": self.signals.is_complete_sentence,
                "is_question": self.signals.ends_with_question,
                "has_hesitation": self.signals.has_hesitation,
                "word_count": self.signals.word_count,
                "confidence": self.signals.turn_end_confidence,
            },
            "transcript": self._transcript_buffer[:100] + "..." if len(self._transcript_buffer) > 100 else self._transcript_buffer,
        }


# ========== Factory Functions ==========

def create_turn_taking_model(
    eagerness: str = "balanced",
    response_delay_ms: int = 200,
    enable_backchannels: bool = True,
    **kwargs
) -> TurnTakingModel:
    """
    Create a configured TurnTakingModel.

    Args:
        eagerness: "low", "balanced", or "high"
        response_delay_ms: Base response delay
        enable_backchannels: Whether to enable backchannel responses
        **kwargs: Additional config options

    Returns:
        Configured TurnTakingModel instance
    """
    try:
        turn_eagerness = TurnEagerness(eagerness)
    except ValueError:
        turn_eagerness = TurnEagerness.BALANCED

    config = TurnTakingConfig(
        turn_eagerness=turn_eagerness,
        response_delay_ms=response_delay_ms,
        enable_backchannels=enable_backchannels,
        **kwargs
    )

    return TurnTakingModel(config)
