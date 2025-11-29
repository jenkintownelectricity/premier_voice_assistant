"""
Advanced Turn-Taking Model for Natural Conversation Flow

This module implements a state-of-the-art turn-taking system inspired by
research from Stanford, Krisp, LiveKit, Hume AI, and Rilla Voice.

Features:
1. Prosody Analysis - Pitch contour and energy level detection
2. Semantic EOU Model - End-of-utterance prediction from text
3. Dynamic Silence Thresholds - Confidence-based threshold adjustment
4. False Interruption Recovery - Resume speech after false positives
5. Emotional Matching - Match user's emotional tone
6. Talk-Time Ratio Tracking - Rilla-style conversation analytics

Based on research:
- Kyutai Moshi: Full-duplex speech-to-speech
- Krisp: Audio-only turn-taking (6M params)
- LiveKit EOU: Semantic turn detection (135M transformer)
- Hume EVI: Prosody-based turn detection with empathy
- Rilla Voice: Talk-time ratio analytics (45-65% optimal)
"""

import asyncio
import time
import re
import math
import logging
import random
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any, Tuple
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class TurnState(Enum):
    """Current state of the turn-taking system."""
    USER_SPEAKING = "user_speaking"
    USER_PAUSING = "user_pausing"  # Brief pause, might continue
    TURN_YIELDED = "turn_yielded"  # User finished, assistant can speak
    ASSISTANT_SPEAKING = "assistant_speaking"
    ASSISTANT_YIELDED = "assistant_yielded"
    BACKCHANNEL = "backchannel"  # Short acknowledgment
    INTERRUPTED = "interrupted"  # Assistant was interrupted
    RESUMING = "resuming"  # Resuming after false interruption


class TurnEagerness(Enum):
    """How quickly the assistant takes turns."""
    LOW = "low"        # Patient, waits longer for user
    BALANCED = "balanced"  # Default behavior
    HIGH = "high"      # Quick responses, more interruption-tolerant


class EmotionalTone(Enum):
    """Detected emotional tone of speech."""
    NEUTRAL = "neutral"
    EXCITED = "excited"
    CALM = "calm"
    FRUSTRATED = "frustrated"
    CURIOUS = "curious"
    HAPPY = "happy"
    SAD = "sad"
    URGENT = "urgent"


# Hesitation markers indicating user might continue
HESITATION_MARKERS = {
    "um", "uh", "er", "ah", "hmm", "hm",
    "like", "you know", "i mean", "well",
    "so", "and", "but", "or", "actually",
    "basically", "literally", "honestly",
    "let me think", "hold on", "wait"
}

# Strong turn-completion indicators
COMPLETION_INDICATORS = {
    "thank you", "thanks", "goodbye", "bye", "that's all",
    "that's it", "i'm done", "got it", "okay thanks",
    "perfect", "great", "sounds good", "alright"
}

# Question words that expect quick response
QUESTION_STARTERS = {
    "what", "when", "where", "who", "why", "how",
    "is", "are", "do", "does", "can", "could", "would", "should"
}

# Incomplete sentence indicators
INCOMPLETE_INDICATORS = {
    "the", "a", "an", "to", "for", "with", "from", "by",
    "in", "on", "at", "of", "that", "which", "who",
    "if", "when", "where", "because", "although", "while",
    "and", "but", "or", "so", "then", "also"
}

# Emotional keywords for tone detection
EMOTION_KEYWORDS = {
    EmotionalTone.EXCITED: ["amazing", "awesome", "fantastic", "great", "love", "wonderful", "excited", "!"],
    EmotionalTone.FRUSTRATED: ["frustrated", "annoying", "terrible", "hate", "stupid", "broken", "doesn't work", "problem"],
    EmotionalTone.CURIOUS: ["wonder", "curious", "interesting", "how does", "what if", "why does", "?"],
    EmotionalTone.URGENT: ["urgent", "emergency", "asap", "immediately", "hurry", "quick", "now", "help"],
    EmotionalTone.HAPPY: ["happy", "glad", "pleased", "nice", "good", "thanks", "appreciate"],
    EmotionalTone.SAD: ["sad", "unfortunately", "sorry", "disappointed", "upset", "miss"],
    EmotionalTone.CALM: ["okay", "alright", "sure", "fine", "no problem", "take your time"],
}

# Backchannel responses with emotional variants
BACKCHANNELS = {
    EmotionalTone.NEUTRAL: ["mm-hmm", "I see", "right", "okay", "got it"],
    EmotionalTone.EXCITED: ["wow!", "that's great!", "amazing!", "yes!"],
    EmotionalTone.CURIOUS: ["interesting", "oh really?", "tell me more", "I see"],
    EmotionalTone.FRUSTRATED: ["I understand", "I'm sorry to hear that", "let me help"],
    EmotionalTone.CALM: ["mm-hmm", "sure", "okay", "I understand"],
}

# Sentence-ending patterns
SENTENCE_END_PATTERN = re.compile(r'[.!?][\s]*$')
QUESTION_PATTERN = re.compile(r'\?[\s]*$')
EXCLAMATION_PATTERN = re.compile(r'![\s]*$')


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TurnTakingConfig:
    """Configuration for the turn-taking model."""
    # Eagerness preset
    turn_eagerness: TurnEagerness = TurnEagerness.BALANCED

    # Base silence thresholds (in ms) - dynamically adjusted
    min_silence_for_turn: int = 400
    confident_silence: int = 800
    max_wait_silence: int = 1500

    # Response timing
    response_delay_ms: int = 200

    # Prosodic features (Feature 1)
    use_pitch_detection: bool = True
    use_energy_detection: bool = True
    pitch_window_size: int = 10  # Frames for pitch contour analysis
    energy_window_size: int = 10
    falling_pitch_threshold: float = -0.15  # Normalized pitch drop
    falling_energy_threshold: float = -0.2

    # Semantic EOU Model (Feature 2)
    use_semantic_eou: bool = True
    eou_confidence_weight: float = 0.25  # Weight in final confidence

    # Dynamic Silence Thresholds (Feature 3)
    enable_dynamic_thresholds: bool = True
    min_dynamic_silence: int = 200  # Minimum possible threshold
    max_dynamic_silence: int = 2000  # Maximum possible threshold

    # False Interruption Recovery (Feature 4)
    enable_interruption_recovery: bool = True
    false_interruption_timeout_ms: int = 500  # Time to detect false interrupt
    min_speech_for_real_interrupt_ms: int = 300  # Min speech for real interrupt

    # Emotional Matching (Feature 5)
    enable_emotional_matching: bool = True
    emotion_detection_weight: float = 0.3  # Speech rate/energy influence

    # Talk-Time Ratio Tracking (Feature 6)
    enable_talk_time_tracking: bool = True
    optimal_assistant_ratio_min: float = 0.45  # Rilla: 45-65% optimal
    optimal_assistant_ratio_max: float = 0.65
    ratio_adjustment_factor: float = 0.1  # How much to adjust response length

    # Text features
    use_sentence_completion: bool = True
    use_question_detection: bool = True
    use_hesitation_detection: bool = True

    # Backchanneling
    enable_backchannels: bool = True
    backchannel_interval_ms: int = 3000
    backchannel_probability: float = 0.3

    # Turn prediction
    prediction_threshold: float = 0.7

    # Barge-in
    allow_barge_in: bool = True
    barge_in_threshold_ms: int = 200


@dataclass
class ProsodyFeatures:
    """Prosodic features extracted from audio."""
    # Pitch (F0) features
    pitch_mean: float = 0.0
    pitch_std: float = 0.0
    pitch_trend: float = 0.0  # Slope: positive=rising, negative=falling
    pitch_final_contour: str = "flat"  # "rising", "falling", "flat"

    # Energy features
    energy_mean: float = 0.0
    energy_std: float = 0.0
    energy_trend: float = 0.0
    energy_final_drop: bool = False  # Sharp drop at end

    # Speaking rate
    speech_rate: float = 1.0  # Words per second
    speech_rate_trend: float = 0.0  # Slowing down = positive

    # Pause features
    pause_count: int = 0
    avg_pause_duration_ms: float = 0.0
    final_pause_ms: float = 0.0


@dataclass
class SemanticEOUFeatures:
    """Semantic end-of-utterance features from text."""
    is_complete_sentence: bool = False
    ends_with_question: bool = False
    ends_with_exclamation: bool = False
    has_hesitation: bool = False
    has_completion_phrase: bool = False
    ends_with_incomplete: bool = False
    word_count: int = 0
    eou_probability: float = 0.0  # Model's EOU prediction


@dataclass
class EmotionalState:
    """Detected emotional state of the user."""
    primary_emotion: EmotionalTone = EmotionalTone.NEUTRAL
    confidence: float = 0.5
    speech_energy_level: float = 0.5  # 0=low, 1=high
    speech_rate_level: float = 0.5  # 0=slow, 1=fast
    recommended_response_tone: EmotionalTone = EmotionalTone.NEUTRAL


@dataclass
class TalkTimeStats:
    """Talk-time ratio tracking (Rilla-style analytics)."""
    session_start: float = 0.0
    user_talk_time_ms: float = 0.0
    assistant_talk_time_ms: float = 0.0
    total_session_time_ms: float = 0.0

    # Turn counts
    user_turn_count: int = 0
    assistant_turn_count: int = 0

    # Interruption tracking
    user_interruptions: int = 0
    assistant_interruptions: int = 0  # When assistant interrupted user

    # Questions asked
    user_questions: int = 0
    assistant_questions: int = 0

    @property
    def assistant_ratio(self) -> float:
        """Calculate assistant talk-time ratio."""
        total = self.user_talk_time_ms + self.assistant_talk_time_ms
        if total == 0:
            return 0.5
        return self.assistant_talk_time_ms / total

    @property
    def is_ratio_optimal(self) -> bool:
        """Check if ratio is in optimal range (45-65%)."""
        return 0.45 <= self.assistant_ratio <= 0.65

    @property
    def avg_user_turn_length_ms(self) -> float:
        """Average user turn length."""
        if self.user_turn_count == 0:
            return 0
        return self.user_talk_time_ms / self.user_turn_count

    @property
    def avg_assistant_turn_length_ms(self) -> float:
        """Average assistant turn length."""
        if self.assistant_turn_count == 0:
            return 0
        return self.assistant_talk_time_ms / self.assistant_turn_count


@dataclass
class InterruptionContext:
    """Context for false interruption recovery."""
    interrupted_at_ms: float = 0.0
    interrupted_text: str = ""
    interrupted_position: int = 0  # Character position
    is_false_interruption: bool = False
    should_resume: bool = False
    resume_text: str = ""


@dataclass
class TurnSignals:
    """All signals used to predict turn boundaries."""
    # Timing
    silence_duration_ms: float = 0.0
    speech_duration_ms: float = 0.0
    time_since_last_word_ms: float = 0.0

    # Prosody (Feature 1)
    prosody: ProsodyFeatures = field(default_factory=ProsodyFeatures)

    # Semantic EOU (Feature 2)
    semantic: SemanticEOUFeatures = field(default_factory=SemanticEOUFeatures)

    # Dynamic threshold (Feature 3)
    dynamic_silence_threshold_ms: int = 800

    # Emotional state (Feature 5)
    emotion: EmotionalState = field(default_factory=EmotionalState)

    # Raw transcript
    transcript: str = ""

    # Computed confidence
    turn_end_confidence: float = 0.0


@dataclass
class TurnPrediction:
    """Result of turn-taking prediction."""
    should_take_turn: bool = False
    confidence: float = 0.0
    recommended_delay_ms: int = 200
    reason: str = ""

    # Backchannel
    should_backchannel: bool = False
    backchannel_text: Optional[str] = None

    # Emotional matching (Feature 5)
    recommended_tone: EmotionalTone = EmotionalTone.NEUTRAL
    recommended_response_energy: float = 0.5  # 0=calm, 1=energetic

    # Talk-time adjustment (Feature 6)
    response_length_adjustment: float = 1.0  # <1 = shorter, >1 = longer

    # Interruption recovery (Feature 4)
    is_resuming: bool = False
    resume_text: Optional[str] = None


# ============================================================================
# MAIN MODEL CLASS
# ============================================================================

class TurnTakingModel:
    """
    State-of-the-art turn-taking model for natural conversation flow.

    Implements 6 key features:
    1. Prosody Analysis - Pitch/energy contour analysis
    2. Semantic EOU Model - Text-based end-of-utterance prediction
    3. Dynamic Silence Thresholds - Confidence-based adjustment
    4. False Interruption Recovery - Resume after false positives
    5. Emotional Matching - Match user's emotional tone
    6. Talk-Time Ratio Tracking - Rilla-style analytics
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

        # Audio feature history (Feature 1: Prosody)
        self._energy_history: deque = deque(maxlen=30)
        self._pitch_history: deque = deque(maxlen=30)
        self._speech_rate_history: deque = deque(maxlen=10)

        # Transcript buffer
        self._transcript_buffer: str = ""
        self._word_timestamps: List[float] = []

        # Talk-time tracking (Feature 6)
        self._talk_stats = TalkTimeStats(session_start=time.time())
        self._current_turn_start: Optional[float] = None

        # Interruption context (Feature 4)
        self._interruption_ctx = InterruptionContext()
        self._last_assistant_text: str = ""
        self._assistant_speech_position: int = 0

        # Callbacks
        self.on_turn_detected: Optional[Callable[[TurnPrediction], Any]] = None
        self.on_backchannel: Optional[Callable[[str], Any]] = None
        self.on_state_change: Optional[Callable[[TurnState], Any]] = None
        self.on_emotion_detected: Optional[Callable[[EmotionalState], Any]] = None

        logger.info(f"TurnTakingModel initialized with eagerness={self.config.turn_eagerness.value}")

    def _apply_eagerness_presets(self):
        """Apply timing presets based on turn eagerness setting."""
        if self.config.turn_eagerness == TurnEagerness.LOW:
            self.config.min_silence_for_turn = 600
            self.config.confident_silence = 1200
            self.config.max_wait_silence = 2000
            self.config.response_delay_ms = 400
            self.config.prediction_threshold = 0.8
            self.config.backchannel_probability = 0.4

        elif self.config.turn_eagerness == TurnEagerness.HIGH:
            self.config.min_silence_for_turn = 250
            self.config.confident_silence = 500
            self.config.max_wait_silence = 1000
            self.config.response_delay_ms = 100
            self.config.prediction_threshold = 0.6
            self.config.backchannel_probability = 0.2

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

    # =========================================================================
    # FEATURE 1: PROSODY ANALYSIS
    # =========================================================================

    def on_audio_features(self, energy: float, pitch: Optional[float] = None):
        """Process audio features for prosody analysis."""
        now = time.time()

        # Track energy
        self._energy_history.append((now, energy))

        # Track pitch if available
        if pitch is not None and pitch > 0:
            self._pitch_history.append((now, pitch))

        # Update prosody features
        self._update_prosody_features()

    def _update_prosody_features(self):
        """Analyze prosody features from audio history."""
        prosody = self.signals.prosody

        # Energy analysis
        if len(self._energy_history) >= 3:
            energies = [e[1] for e in self._energy_history]
            prosody.energy_mean = sum(energies) / len(energies)
            prosody.energy_std = self._std_dev(energies)

            # Calculate energy trend (linear regression slope)
            prosody.energy_trend = self._calculate_trend(energies)

            # Detect final energy drop
            if len(energies) >= 5:
                recent = energies[-5:]
                earlier = energies[-10:-5] if len(energies) >= 10 else energies[:5]
                avg_recent = sum(recent) / len(recent)
                avg_earlier = sum(earlier) / len(earlier)
                prosody.energy_final_drop = (avg_recent < avg_earlier * 0.7)

        # Pitch analysis
        if len(self._pitch_history) >= 3:
            pitches = [p[1] for p in self._pitch_history]
            prosody.pitch_mean = sum(pitches) / len(pitches)
            prosody.pitch_std = self._std_dev(pitches)

            # Calculate pitch trend
            prosody.pitch_trend = self._calculate_trend(pitches)

            # Determine final contour
            if len(pitches) >= 5:
                final_trend = self._calculate_trend(pitches[-5:])
                if final_trend < self.config.falling_pitch_threshold:
                    prosody.pitch_final_contour = "falling"
                elif final_trend > abs(self.config.falling_pitch_threshold):
                    prosody.pitch_final_contour = "rising"
                else:
                    prosody.pitch_final_contour = "flat"

        # Speech rate calculation
        if self._word_timestamps and self._speech_start_time:
            duration = time.time() - self._speech_start_time
            if duration > 0:
                rate = len(self._word_timestamps) / duration
                self._speech_rate_history.append(rate)
                prosody.speech_rate = rate

                # Calculate rate trend (slowing down suggests turn end)
                if len(self._speech_rate_history) >= 3:
                    rates = list(self._speech_rate_history)
                    prosody.speech_rate_trend = self._calculate_trend(rates)

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate linear trend (slope) of values."""
        if len(values) < 2:
            return 0.0
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0
        return numerator / denominator

    def _std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance)

    # =========================================================================
    # FEATURE 2: SEMANTIC EOU MODEL
    # =========================================================================

    def _analyze_semantic_eou(self) -> float:
        """
        Semantic End-of-Utterance prediction.

        Inspired by LiveKit's 135M transformer EOU model, but using
        rule-based heuristics for lightweight inference.

        Returns probability (0-1) that utterance is complete.
        """
        text = self._transcript_buffer.strip().lower()
        semantic = self.signals.semantic

        if not text:
            semantic.eou_probability = 0.0
            return 0.0

        words = text.split()
        semantic.word_count = len(words)

        # Check for complete sentence
        semantic.is_complete_sentence = bool(SENTENCE_END_PATTERN.search(self._transcript_buffer))
        semantic.ends_with_question = bool(QUESTION_PATTERN.search(self._transcript_buffer))
        semantic.ends_with_exclamation = bool(EXCLAMATION_PATTERN.search(self._transcript_buffer))

        # Check for completion phrases
        semantic.has_completion_phrase = any(
            phrase in text for phrase in COMPLETION_INDICATORS
        )

        # Check for hesitation (recent words)
        last_words = " ".join(words[-3:]) if len(words) >= 3 else text
        semantic.has_hesitation = any(
            marker in last_words for marker in HESITATION_MARKERS
        )

        # Check for incomplete indicators
        if words:
            last_word = words[-1].rstrip(".,!?")
            semantic.ends_with_incomplete = last_word in INCOMPLETE_INDICATORS

        # Calculate EOU probability
        probability = 0.0

        # Strong completion signals
        if semantic.is_complete_sentence:
            probability += 0.4
        if semantic.has_completion_phrase:
            probability += 0.3
        if semantic.ends_with_question:
            probability += 0.2  # Questions expect response

        # Moderate signals
        if len(words) >= 5 and not semantic.ends_with_incomplete:
            probability += 0.15
        if semantic.ends_with_exclamation:
            probability += 0.1

        # Negative signals
        if semantic.has_hesitation:
            probability -= 0.3
        if semantic.ends_with_incomplete:
            probability -= 0.25
        if len(words) < 3:
            probability -= 0.2

        # Clamp to [0, 1]
        semantic.eou_probability = max(0.0, min(1.0, probability))
        return semantic.eou_probability

    # =========================================================================
    # FEATURE 3: DYNAMIC SILENCE THRESHOLDS
    # =========================================================================

    def _calculate_dynamic_threshold(self, confidence: float) -> int:
        """
        Dynamically adjust silence threshold based on current confidence.

        High confidence -> shorter threshold (respond faster)
        Low confidence -> longer threshold (wait more)
        """
        if not self.config.enable_dynamic_thresholds:
            return self.config.confident_silence

        # Base range
        min_thresh = self.config.min_dynamic_silence
        max_thresh = self.config.max_dynamic_silence

        # Invert confidence for threshold (high confidence = low threshold)
        threshold = max_thresh - (confidence * (max_thresh - min_thresh))

        # Apply prosody adjustments
        prosody = self.signals.prosody

        # Falling pitch suggests completion -> reduce threshold
        if prosody.pitch_final_contour == "falling":
            threshold *= 0.8

        # Rising pitch suggests question or continuation -> increase threshold
        elif prosody.pitch_final_contour == "rising" and not self.signals.semantic.ends_with_question:
            threshold *= 1.2

        # Energy drop suggests completion
        if prosody.energy_final_drop:
            threshold *= 0.85

        # Speech rate slowing suggests completion
        if prosody.speech_rate_trend > 0.1:  # Slowing down
            threshold *= 0.9

        # Clamp to valid range
        threshold = max(min_thresh, min(max_thresh, threshold))

        self.signals.dynamic_silence_threshold_ms = int(threshold)
        return int(threshold)

    # =========================================================================
    # FEATURE 4: FALSE INTERRUPTION RECOVERY
    # =========================================================================

    def on_speech_start(self):
        """Called when user starts speaking."""
        now = time.time()
        self._speech_start_time = now
        self._last_word_time = now
        self._last_speech_time = now
        self.signals.silence_duration_ms = 0

        # Track user turn for talk-time stats
        if self.config.enable_talk_time_tracking:
            self._current_turn_start = now

        # Handle potential barge-in
        if self.state == TurnState.ASSISTANT_SPEAKING:
            if self.config.allow_barge_in:
                # Start interruption detection
                if self.config.enable_interruption_recovery:
                    self._interruption_ctx = InterruptionContext(
                        interrupted_at_ms=now * 1000,
                        interrupted_text=self._last_assistant_text,
                        interrupted_position=self._assistant_speech_position,
                        is_false_interruption=False,  # TBD
                        should_resume=False,
                    )

                self._set_state(TurnState.INTERRUPTED)
                logger.info("Barge-in detected - user interrupted assistant")

                # Track interruption stat
                if self.config.enable_talk_time_tracking:
                    self._talk_stats.user_interruptions += 1
        else:
            self._set_state(TurnState.USER_SPEAKING)

    def on_speech_end(self):
        """Called when VAD detects speech stopped."""
        now = time.time()
        self._last_speech_time = now

        # Update user talk time
        if self.config.enable_talk_time_tracking and self._current_turn_start:
            turn_duration = (now - self._current_turn_start) * 1000
            self._talk_stats.user_talk_time_ms += turn_duration
            self._talk_stats.user_turn_count += 1

        if self.state == TurnState.USER_SPEAKING:
            self._set_state(TurnState.USER_PAUSING)

    def check_false_interruption(self, transcribed_words: int) -> bool:
        """
        Check if an interruption was false (no actual speech).

        Called after interruption detection to determine if we should
        resume the assistant's speech.
        """
        if not self.config.enable_interruption_recovery:
            return False

        ctx = self._interruption_ctx

        # Check if enough time has passed
        elapsed_ms = (time.time() * 1000) - ctx.interrupted_at_ms
        if elapsed_ms < self.config.false_interruption_timeout_ms:
            return False  # Still waiting

        # If no words transcribed, it's likely a false interruption
        if transcribed_words == 0:
            ctx.is_false_interruption = True
            ctx.should_resume = True
            ctx.resume_text = ctx.interrupted_text[ctx.interrupted_position:]
            logger.info("False interruption detected - will resume speech")
            return True

        # If very short utterance, might be false
        if self._speech_start_time:
            speech_duration = (time.time() - self._speech_start_time) * 1000
            if speech_duration < self.config.min_speech_for_real_interrupt_ms:
                if transcribed_words <= 1:
                    ctx.is_false_interruption = True
                    ctx.should_resume = True
                    ctx.resume_text = ctx.interrupted_text[ctx.interrupted_position:]
                    return True

        return False

    def get_resume_context(self) -> Optional[str]:
        """Get text to resume after false interruption."""
        if self._interruption_ctx.should_resume:
            text = self._interruption_ctx.resume_text
            # Reset context
            self._interruption_ctx = InterruptionContext()
            return text
        return None

    # =========================================================================
    # FEATURE 5: EMOTIONAL MATCHING
    # =========================================================================

    def _detect_emotion(self) -> EmotionalState:
        """
        Detect user's emotional state from text and prosody.

        Inspired by Hume AI's empathic voice interface.
        """
        emotion_state = EmotionalState()
        text = self._transcript_buffer.lower()
        prosody = self.signals.prosody

        # Text-based emotion detection
        emotion_scores: Dict[EmotionalTone, float] = {e: 0.0 for e in EmotionalTone}

        for emotion, keywords in EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    emotion_scores[emotion] += 1.0

        # Prosody-based adjustments
        # High energy + fast speech -> excited/urgent
        if prosody.energy_mean > 0.7 and prosody.speech_rate > 3.0:
            emotion_scores[EmotionalTone.EXCITED] += 0.5
            emotion_scores[EmotionalTone.URGENT] += 0.3

        # Low energy + slow speech -> calm/sad
        if prosody.energy_mean < 0.3 and prosody.speech_rate < 2.0:
            emotion_scores[EmotionalTone.CALM] += 0.4
            emotion_scores[EmotionalTone.SAD] += 0.2

        # High pitch variability -> excited
        if prosody.pitch_std > 50:  # Hz
            emotion_scores[EmotionalTone.EXCITED] += 0.3

        # Find primary emotion
        max_score = 0.0
        primary = EmotionalTone.NEUTRAL
        for emotion, score in emotion_scores.items():
            if score > max_score:
                max_score = score
                primary = emotion

        # Calculate confidence
        total_score = sum(emotion_scores.values())
        confidence = max_score / total_score if total_score > 0 else 0.5

        emotion_state.primary_emotion = primary
        emotion_state.confidence = confidence
        emotion_state.speech_energy_level = min(1.0, prosody.energy_mean)
        emotion_state.speech_rate_level = min(1.0, prosody.speech_rate / 5.0)

        # Recommend matching response tone
        emotion_state.recommended_response_tone = self._get_matching_tone(primary)

        self.signals.emotion = emotion_state

        # Trigger callback
        if self.on_emotion_detected and confidence > 0.5:
            asyncio.create_task(self._safe_callback(self.on_emotion_detected, emotion_state))

        return emotion_state

    def _get_matching_tone(self, user_emotion: EmotionalTone) -> EmotionalTone:
        """Get appropriate response tone to match user's emotion."""
        matching = {
            EmotionalTone.EXCITED: EmotionalTone.EXCITED,
            EmotionalTone.FRUSTRATED: EmotionalTone.CALM,  # De-escalate
            EmotionalTone.CURIOUS: EmotionalTone.CURIOUS,
            EmotionalTone.URGENT: EmotionalTone.CALM,  # Stay composed
            EmotionalTone.HAPPY: EmotionalTone.HAPPY,
            EmotionalTone.SAD: EmotionalTone.CALM,  # Supportive
            EmotionalTone.CALM: EmotionalTone.CALM,
            EmotionalTone.NEUTRAL: EmotionalTone.NEUTRAL,
        }
        return matching.get(user_emotion, EmotionalTone.NEUTRAL)

    # =========================================================================
    # FEATURE 6: TALK-TIME RATIO TRACKING
    # =========================================================================

    def get_talk_time_stats(self) -> TalkTimeStats:
        """Get current talk-time statistics."""
        self._talk_stats.total_session_time_ms = (time.time() - self._talk_stats.session_start) * 1000
        return self._talk_stats

    def _calculate_response_length_adjustment(self) -> float:
        """
        Calculate how to adjust response length based on talk-time ratio.

        Based on Rilla Voice research: optimal is 45-65% assistant talk time.
        """
        if not self.config.enable_talk_time_tracking:
            return 1.0

        ratio = self._talk_stats.assistant_ratio

        # If talking too much, suggest shorter responses
        if ratio > self.config.optimal_assistant_ratio_max:
            excess = ratio - self.config.optimal_assistant_ratio_max
            return 1.0 - (excess * self.config.ratio_adjustment_factor * 5)

        # If not talking enough, suggest longer responses
        if ratio < self.config.optimal_assistant_ratio_min:
            deficit = self.config.optimal_assistant_ratio_min - ratio
            return 1.0 + (deficit * self.config.ratio_adjustment_factor * 5)

        return 1.0

    def start_assistant_turn(self, text: str = ""):
        """Called when assistant starts speaking."""
        self._set_state(TurnState.ASSISTANT_SPEAKING)
        self._current_turn_start = time.time()
        self._last_assistant_text = text
        self._assistant_speech_position = 0

    def update_assistant_position(self, position: int):
        """Update current position in assistant's speech (for recovery)."""
        self._assistant_speech_position = position

    def end_assistant_turn(self):
        """Called when assistant finishes speaking."""
        # Track assistant talk time
        if self.config.enable_talk_time_tracking and self._current_turn_start:
            turn_duration = (time.time() - self._current_turn_start) * 1000
            self._talk_stats.assistant_talk_time_ms += turn_duration
            self._talk_stats.assistant_turn_count += 1

        self._set_state(TurnState.ASSISTANT_YIELDED)
        self.reset_for_next_turn()

    # =========================================================================
    # INPUT METHODS
    # =========================================================================

    def on_transcript(self, text: str, is_final: bool = False):
        """Called with transcript updates."""
        now = time.time()
        self._last_word_time = now
        self._word_timestamps.append(now)

        self._transcript_buffer = text
        self.signals.transcript = text

        # Analyze semantic features
        self._analyze_semantic_eou()

        # Detect emotion
        if self.config.enable_emotional_matching:
            self._detect_emotion()

        # Track questions for stats
        if is_final and self.config.enable_talk_time_tracking:
            if self.signals.semantic.ends_with_question:
                self._talk_stats.user_questions += 1

    def on_silence(self, duration_ms: float):
        """Called with silence duration updates."""
        self.signals.silence_duration_ms = duration_ms

        if self.state == TurnState.USER_SPEAKING:
            self._set_state(TurnState.USER_PAUSING)

    # =========================================================================
    # MAIN PREDICTION
    # =========================================================================

    def _calculate_turn_confidence(self) -> float:
        """
        Calculate confidence that the user has finished their turn.

        Combines all signals with learned weights.
        """
        confidence = 0.0
        prosody = self.signals.prosody
        semantic = self.signals.semantic

        # 1. Silence-based confidence (0 to 0.3)
        silence = self.signals.silence_duration_ms
        dynamic_threshold = self._calculate_dynamic_threshold(confidence)

        if silence >= self.config.max_wait_silence:
            confidence += 0.3
        elif silence >= dynamic_threshold:
            confidence += 0.25
        elif silence >= self.config.min_silence_for_turn:
            confidence += 0.15 * (silence / dynamic_threshold)

        # 2. Semantic EOU confidence (0 to 0.25)
        if self.config.use_semantic_eou:
            confidence += semantic.eou_probability * self.config.eou_confidence_weight

        # 3. Prosody-based confidence (0 to 0.2)
        if self.config.use_pitch_detection:
            if prosody.pitch_final_contour == "falling":
                confidence += 0.12
            elif prosody.pitch_final_contour == "rising" and not semantic.ends_with_question:
                confidence -= 0.08  # Might continue

        if self.config.use_energy_detection:
            if prosody.energy_final_drop:
                confidence += 0.08

        # 4. Speech rate (slowing down = ending)
        if prosody.speech_rate_trend > 0.05:
            confidence += 0.05

        # 5. Question bonus (expect quick response)
        if semantic.ends_with_question:
            confidence += 0.1

        # 6. Completion phrase bonus
        if semantic.has_completion_phrase:
            confidence += 0.15

        # 7. Hesitation penalty
        if semantic.has_hesitation:
            confidence -= 0.15

        # 8. Incomplete indicator penalty
        if semantic.ends_with_incomplete:
            confidence -= 0.12

        return max(0.0, min(1.0, confidence))

    async def predict_turn(self) -> TurnPrediction:
        """
        Predict whether the assistant should take a turn.

        Returns comprehensive prediction with all features.
        """
        confidence = self._calculate_turn_confidence()
        self.signals.turn_end_confidence = confidence

        prediction = TurnPrediction()
        prediction.confidence = confidence

        # Check for false interruption recovery (Feature 4)
        if self._interruption_ctx.should_resume:
            prediction.is_resuming = True
            prediction.resume_text = self._interruption_ctx.resume_text
            prediction.should_take_turn = True
            prediction.reason = "Resuming after false interruption"
            self._interruption_ctx = InterruptionContext()
            return prediction

        # Get dynamic threshold
        dynamic_threshold = self._calculate_dynamic_threshold(confidence)

        # Check for forced turn (max silence exceeded)
        if self.signals.silence_duration_ms >= self.config.max_wait_silence:
            prediction.should_take_turn = True
            prediction.confidence = 1.0
            prediction.recommended_delay_ms = 0
            prediction.reason = "Maximum silence threshold exceeded"

        # High confidence turn detection
        elif confidence >= self.config.prediction_threshold:
            prediction.should_take_turn = True

            # Adjust delay based on context
            if self.signals.semantic.ends_with_question:
                prediction.recommended_delay_ms = int(self.config.response_delay_ms * 0.5)
                prediction.reason = "Question detected - quick response"
            elif self.signals.semantic.has_completion_phrase:
                prediction.recommended_delay_ms = int(self.config.response_delay_ms * 0.7)
                prediction.reason = "Completion phrase detected"
            elif self.signals.prosody.pitch_final_contour == "falling":
                prediction.recommended_delay_ms = self.config.response_delay_ms
                prediction.reason = "Falling pitch - statement complete"
            else:
                prediction.recommended_delay_ms = int(self.config.response_delay_ms * 1.2)
                prediction.reason = f"Turn predicted (confidence: {confidence:.2f})"

        else:
            prediction.should_take_turn = False
            prediction.reason = f"Waiting (confidence: {confidence:.2f}, threshold: {dynamic_threshold}ms)"

        # Feature 5: Emotional matching
        if self.config.enable_emotional_matching:
            emotion = self.signals.emotion
            prediction.recommended_tone = emotion.recommended_response_tone
            prediction.recommended_response_energy = emotion.speech_energy_level

        # Feature 6: Talk-time adjustment
        if self.config.enable_talk_time_tracking:
            prediction.response_length_adjustment = self._calculate_response_length_adjustment()

        # Check for backchannel opportunity
        prediction.should_backchannel, prediction.backchannel_text = self._check_backchannel()

        return prediction

    def _check_backchannel(self) -> Tuple[bool, Optional[str]]:
        """Check if we should send a backchannel response."""
        if not self.config.enable_backchannels:
            return False, None

        if self.state != TurnState.USER_SPEAKING:
            return False, None

        now = time.time()
        time_since_backchannel = (now - self._last_backchannel_time) * 1000

        if time_since_backchannel < self.config.backchannel_interval_ms:
            return False, None

        if self._speech_start_time:
            speech_duration = (now - self._speech_start_time) * 1000
            if speech_duration < 2000:
                return False, None

        if random.random() < self.config.backchannel_probability:
            self._last_backchannel_time = now

            # Select emotion-appropriate backchannel
            emotion = self.signals.emotion.primary_emotion
            options = BACKCHANNELS.get(emotion, BACKCHANNELS[EmotionalTone.NEUTRAL])
            backchannel = random.choice(options)

            return True, backchannel

        return False, None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def reset_for_next_turn(self):
        """Reset signals for the next turn."""
        self._transcript_buffer = ""
        self._word_timestamps = []
        self._energy_history.clear()
        self._pitch_history.clear()
        self._speech_rate_history.clear()
        self.signals = TurnSignals()
        self._speech_start_time = None
        self._last_word_time = None
        self._current_turn_start = None

    def get_state(self) -> TurnState:
        """Get current turn state."""
        return self.state

    def get_signals(self) -> TurnSignals:
        """Get current signal values."""
        return self.signals

    def get_debug_info(self) -> Dict[str, Any]:
        """Get comprehensive debug information."""
        return {
            "state": self.state.value,
            "eagerness": self.config.turn_eagerness.value,
            "confidence": self.signals.turn_end_confidence,
            "dynamic_threshold_ms": self.signals.dynamic_silence_threshold_ms,
            "prosody": {
                "pitch_contour": self.signals.prosody.pitch_final_contour,
                "pitch_trend": round(self.signals.prosody.pitch_trend, 3),
                "energy_trend": round(self.signals.prosody.energy_trend, 3),
                "energy_drop": self.signals.prosody.energy_final_drop,
                "speech_rate": round(self.signals.prosody.speech_rate, 2),
            },
            "semantic": {
                "complete_sentence": self.signals.semantic.is_complete_sentence,
                "question": self.signals.semantic.ends_with_question,
                "hesitation": self.signals.semantic.has_hesitation,
                "eou_probability": round(self.signals.semantic.eou_probability, 2),
            },
            "emotion": {
                "primary": self.signals.emotion.primary_emotion.value,
                "confidence": round(self.signals.emotion.confidence, 2),
                "recommended_tone": self.signals.emotion.recommended_response_tone.value,
            },
            "talk_time": {
                "assistant_ratio": round(self._talk_stats.assistant_ratio, 2),
                "is_optimal": self._talk_stats.is_ratio_optimal,
                "user_turns": self._talk_stats.user_turn_count,
                "assistant_turns": self._talk_stats.assistant_turn_count,
            },
            "transcript": self._transcript_buffer[:100] + "..." if len(self._transcript_buffer) > 100 else self._transcript_buffer,
        }


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_turn_taking_model(
    eagerness: str = "balanced",
    response_delay_ms: int = 200,
    enable_backchannels: bool = True,
    enable_emotional_matching: bool = True,
    enable_talk_time_tracking: bool = True,
    **kwargs
) -> TurnTakingModel:
    """
    Create a configured TurnTakingModel with all features enabled.

    Args:
        eagerness: "low", "balanced", or "high"
        response_delay_ms: Base response delay
        enable_backchannels: Whether to enable backchannel responses
        enable_emotional_matching: Whether to match user's emotional tone
        enable_talk_time_tracking: Whether to track talk-time ratios
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
        enable_emotional_matching=enable_emotional_matching,
        enable_talk_time_tracking=enable_talk_time_tracking,
        **kwargs
    )

    return TurnTakingModel(config)
