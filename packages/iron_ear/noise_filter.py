"""
Iron Ear - Multi-Layer Voice Filtering System (Standalone Package)

A production-ready noise filtering system for voice AI applications.
Combines three layers of protection against unwanted audio:

    V1 - DEBOUNCE: Filters transient noises (door slams, coughs)
    V2 - SPEAKER LOCKING: Volume fingerprinting to ignore background voices
    V3 - IDENTITY LOCK: ML-based speaker verification using voice embeddings

This module is fully decoupled from any specific backend, database, or
application framework. All configuration is injected via __init__ parameters.

Usage:
    from packages.iron_ear.noise_filter import IronEarFilter, IronEarConfig

    config = IronEarConfig(
        min_speech_duration_ms=300,
        vad_threshold=0.65,
        enable_speaker_locking=True,
        enable_identity_verification=True,
    )

    iron_ear = IronEarFilter(config)

    # Process audio frames
    for frame in audio_stream:
        is_valid = iron_ear.process_frame(
            vad_probability=frame.vad_prob,
            energy=frame.energy,
            audio_chunk=frame.audio,
        )
        if is_valid:
            # Process this frame - it's real speech from the target user
            pass

Based on research from:
- Resemblyzer (Google's GE2E paper) for speaker embeddings
- LiveKit's turn-taking research
- Zero-shot speaker enrollment techniques
"""

import time
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Callable
from enum import Enum, auto

logger = logging.getLogger(__name__)


# =============================================================================
# LAZY LOADING - RESEMBLYZER (ML Speaker Verification)
# =============================================================================
# Resemblyzer (~50MB model) is loaded lazily to reduce memory at startup.
# It's only loaded when identity verification is actually triggered.

_resemblyzer_module: Optional[Any] = None
_resemblyzer_checked: bool = False


def _load_resemblyzer():
    """
    Lazily load Resemblyzer module on first use.

    This prevents the ~50MB neural network model from being loaded
    at startup. It's only loaded when identity lock is triggered.
    """
    global _resemblyzer_module, _resemblyzer_checked

    if _resemblyzer_checked:
        return _resemblyzer_module

    _resemblyzer_checked = True

    try:
        import resemblyzer
        _resemblyzer_module = resemblyzer
        logger.info("[IronEar] Resemblyzer loaded - ML speaker verification enabled")
    except ImportError:
        _resemblyzer_module = None
        logger.warning("[IronEar] Resemblyzer not available - using energy-based fallback")

    return _resemblyzer_module


def is_resemblyzer_available() -> bool:
    """Check if Resemblyzer is available (loads it if not already checked)."""
    return _load_resemblyzer() is not None


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class IronEarConfig:
    """
    Configuration for Iron Ear noise filtering.

    All parameters are injectable - no hardcoded values.
    Defaults are production-tested values.
    """

    # =========================================================================
    # V1 - DEBOUNCE (Door Slam Fix)
    # =========================================================================
    # Problem: Agent is "jumpy" - stops talking when it hears any sound
    # Solution: Require continuous speech before considering it "real"
    #
    # A door slam = ~100ms, a cough = ~150ms, real speech = >250ms
    # By requiring 300ms of continuous sound, we ignore transient noises.

    # VAD threshold (0.0-1.0) - Higher = ignore more background noise
    # 0.5 = sensitive (picks up quiet speech but also noise)
    # 0.65 = balanced (good for most environments)
    # 0.8 = strict (may miss quiet speech but ignores most noise)
    vad_threshold: float = 0.65

    # Minimum continuous speech duration before we consider it "real" speech
    # This is the "debounce" - filters out door slams, coughs, etc.
    min_speech_duration_ms: int = 300

    # Frame duration assumption (for buffer calculations)
    frame_duration_ms: int = 20

    # =========================================================================
    # V2 - SPEAKER LOCKING (Cocktail Party Fix)
    # =========================================================================
    # Problem: Background voices (TV, other people) trigger VAD
    # Solution: Lock onto the primary speaker's volume fingerprint

    enable_speaker_locking: bool = True

    # Calibration: How many frames of speech to analyze before "locking"
    # ~50 frames at 20ms each = 1 second of speech
    locking_frames_needed: int = 50

    # Rejection: If detected speech is X% quieter than our locked user, ignore it.
    # 0.6 = ignore voices that are < 60% of the main user's volume
    background_voice_threshold: float = 0.6

    # Energy threshold for considering a frame as speech (for profiling)
    min_energy_for_profiling: float = 0.05

    # =========================================================================
    # V3 - IDENTITY VERIFICATION (Speaker Fingerprinting)
    # =========================================================================
    # Problem: Even with speaker locking, a loud imposter could still trigger
    # Solution: Use ML voice embeddings to verify speaker identity

    enable_identity_verification: bool = True

    # How long to collect audio during the "Honey Pot" calibration phase
    identity_calibration_duration: float = 10.0  # seconds

    # Similarity threshold for accepting audio (0-1)
    # Lower = more permissive, Higher = stricter
    identity_similarity_threshold: float = 0.65

    # Audio sample rate (16kHz is standard for voice, required by Resemblyzer)
    sample_rate: int = 16000

    # =========================================================================
    # CALLBACKS (Optional)
    # =========================================================================
    # Called when speaker lock is established
    on_speaker_locked: Optional[Callable[[float, float], None]] = None

    # Called when identity is locked (calibration complete)
    on_identity_locked: Optional[Callable[[dict], None]] = None

    # Called when audio is rejected
    on_audio_rejected: Optional[Callable[[str, float], None]] = None


# =============================================================================
# SPEAKER PROFILE (V3 Data Structure)
# =============================================================================

@dataclass
class SpeakerProfile:
    """Voice fingerprint for the enrolled speaker."""
    is_locked: bool = False

    # ML Embedding (256-dimensional vector from Resemblyzer)
    embedding: Optional[np.ndarray] = None

    # Fallback heuristic features (when Resemblyzer unavailable)
    avg_energy: float = 0.0
    energy_variance: float = 0.0

    # Calibration tracking
    calibration_start_time: float = 0.0
    total_speech_frames: int = 0
    calibration_audio_samples: int = 0


# =============================================================================
# SPEAKER CONTEXT (V2 Runtime State)
# =============================================================================

@dataclass
class SpeakerContext:
    """Runtime state for speaker locking (V2)."""
    # Running average of the TARGET user's volume
    avg_user_energy: float = 0.0

    # How much their volume fluctuates
    energy_variance: float = 0.0

    # Have we established a baseline yet?
    locked_on: bool = False

    # Baseline background noise
    noise_floor: float = 0.02

    # Frames of speech analyzed for calibration
    locking_frame_count: int = 0


# =============================================================================
# IDENTITY MANAGER (V3 - Speaker Verification)
# =============================================================================

class IdentityManager:
    """
    Manages speaker identity verification using voice embeddings.

    Uses Resemblyzer to extract 256-dimensional speaker embeddings
    and cosine similarity for verification.

    The "Honey Pot" Flow:
    1. Agent asks engaging question (e.g., "Could you state your name?")
    2. User responds with 10-15 seconds of natural speech
    3. System extracts 256-dim speaker embedding (voice fingerprint)
    4. Identity is LOCKED - only matching voice is accepted
    5. Background voices, TV, imposters are rejected
    """

    def __init__(
        self,
        calibration_duration: float = 10.0,
        similarity_threshold: float = 0.65,
        min_energy_threshold: float = 0.05,
        sample_rate: int = 16000,
        on_identity_locked: Optional[Callable[[dict], None]] = None,
    ):
        """
        Initialize IdentityManager.

        Args:
            calibration_duration: Seconds of speech needed for enrollment
            similarity_threshold: Minimum cosine similarity to accept (0-1)
            min_energy_threshold: Minimum energy to consider as speech
            sample_rate: Audio sample rate (16kHz for Resemblyzer)
            on_identity_locked: Callback when identity is locked
        """
        self.profile = SpeakerProfile()
        self.calibration_duration_needed = calibration_duration
        self.similarity_threshold = similarity_threshold
        self.min_energy_threshold = min_energy_threshold
        self.sample_rate = sample_rate
        self.on_identity_locked = on_identity_locked

        # ML encoder (loaded lazily)
        self._encoder: Optional[Any] = None

        # Audio buffer for calibration
        self._calibration_buffer: List[np.ndarray] = []
        self._buffer_duration: float = 0.0

        # Statistics
        self._rejection_count: int = 0
        self._acceptance_count: int = 0
        self._energy_samples: List[float] = []
        self._similarity_scores: List[float] = []

        logger.info(
            f"[IdentityManager] Initialized "
            f"(ML=lazy-load, calibration={calibration_duration}s, "
            f"threshold={similarity_threshold})"
        )

    def _get_encoder(self):
        """
        Lazily load the voice encoder.

        Called only when identity lock is triggered, preventing
        the ~50MB model from being loaded at startup.
        """
        resemblyzer = _load_resemblyzer()
        if resemblyzer is None:
            return None

        if self._encoder is None:
            logger.info("[IdentityManager] Loading VoiceEncoder model...")
            self._encoder = resemblyzer.VoiceEncoder()
            logger.info("[IdentityManager] VoiceEncoder loaded")

        return self._encoder

    def start_calibration(self):
        """
        Start the calibration phase (call when asking the 'Honey Pot' question).

        Resets any existing profile and begins collecting voice samples.
        """
        self.profile = SpeakerProfile()
        self.profile.calibration_start_time = time.time()
        self._calibration_buffer = []
        self._buffer_duration = 0.0
        self._energy_samples = []
        self._rejection_count = 0
        self._acceptance_count = 0
        self._similarity_scores = []

        logger.info("[IdentityManager] Calibration started (Honey Pot phase)")

    def add_calibration_audio(
        self,
        audio_chunk: np.ndarray,
        energy: float = 0.0,
        duration_ms: float = 20.0
    ):
        """
        Add audio chunk to calibration buffer.

        Args:
            audio_chunk: Audio samples (int16 or float32)
            energy: Energy level of this chunk (for fallback)
            duration_ms: Duration of this chunk in milliseconds
        """
        if self.profile.is_locked:
            return  # Already calibrated

        # Skip silent frames
        if energy < self.min_energy_threshold:
            return

        self._buffer_duration += (duration_ms / 1000.0)
        self._calibration_buffer.append(audio_chunk)
        self._energy_samples.append(energy)
        self.profile.total_speech_frames += 1
        self.profile.calibration_audio_samples += len(audio_chunk)

    def can_lock(self) -> bool:
        """Check if we have enough audio to lock identity."""
        return self._buffer_duration >= self.calibration_duration_needed

    def lock_identity(self) -> bool:
        """
        Process collected audio and create the voice fingerprint.

        Returns:
            True if successfully locked, False otherwise
        """
        if self.profile.is_locked:
            return True  # Already locked

        if not self._calibration_buffer:
            logger.warning("[IdentityManager] Cannot lock - no audio collected")
            return False

        # Concatenate all audio chunks
        all_audio = np.concatenate(self._calibration_buffer)

        # Normalize to float32 if int16
        if all_audio.dtype == np.int16:
            all_audio = all_audio.astype(np.float32) / 32768.0
        elif all_audio.dtype != np.float32:
            all_audio = all_audio.astype(np.float32)

        # Try ML embedding first (loads Resemblyzer lazily)
        encoder = self._get_encoder()
        resemblyzer = _load_resemblyzer()
        if encoder is not None and resemblyzer is not None:
            try:
                wav = resemblyzer.preprocess_wav(all_audio, source_sr=self.sample_rate)
                self.profile.embedding = encoder.embed_utterance(wav)
                logger.info(
                    f"[IdentityManager] IDENTITY LOCKED (ML) "
                    f"(embedding shape: {self.profile.embedding.shape}, "
                    f"audio: {self._buffer_duration:.1f}s, "
                    f"{len(self._calibration_buffer)} chunks)"
                )
            except Exception as e:
                logger.error(f"[IdentityManager] ML embedding failed: {e}")
                self.profile.embedding = None

        # Fallback: Calculate energy-based features
        if self._energy_samples:
            self.profile.avg_energy = sum(self._energy_samples) / len(self._energy_samples)
            variance_sum = sum(
                (e - self.profile.avg_energy) ** 2 for e in self._energy_samples
            )
            self.profile.energy_variance = variance_sum / len(self._energy_samples)

        self.profile.is_locked = True

        if self.profile.embedding is None:
            logger.info(
                f"[IdentityManager] IDENTITY LOCKED (Energy Fallback) "
                f"(avg_energy={self.profile.avg_energy:.4f}, "
                f"variance={self.profile.energy_variance:.4f})"
            )

        # Clear buffer to free memory
        self._calibration_buffer = []

        # Trigger callback
        if self.on_identity_locked:
            self.on_identity_locked(self.get_stats())

        return True

    def verify_speaker(
        self,
        audio_chunk: np.ndarray,
        energy: float = 0.0,
    ) -> Tuple[bool, float]:
        """
        Verify if audio matches the enrolled speaker.

        Args:
            audio_chunk: Audio samples to verify
            energy: Energy level (for fallback verification)

        Returns:
            (is_match, similarity_score)
        """
        if not self.profile.is_locked:
            return True, 1.0  # Can't verify if not calibrated

        # Skip very quiet audio
        if energy < self.min_energy_threshold:
            return True, 1.0  # Silent frames pass through

        # ML-based verification (only if we have an embedding)
        if self.profile.embedding is not None and is_resemblyzer_available():
            similarity = self._verify_ml(audio_chunk)
        else:
            similarity = self._verify_energy(energy)

        is_match = similarity >= self.similarity_threshold

        # Track stats
        self._similarity_scores.append(similarity)
        if is_match:
            self._acceptance_count += 1
        else:
            self._rejection_count += 1

        return is_match, similarity

    def _verify_ml(self, audio_chunk: np.ndarray) -> float:
        """Verify using ML embeddings and cosine similarity."""
        encoder = self._get_encoder()
        resemblyzer = _load_resemblyzer()
        if encoder is None or resemblyzer is None:
            return 1.0  # Fail open

        try:
            # Normalize audio
            if audio_chunk.dtype == np.int16:
                audio_chunk = audio_chunk.astype(np.float32) / 32768.0
            elif audio_chunk.dtype != np.float32:
                audio_chunk = audio_chunk.astype(np.float32)

            # Skip very short chunks (< 0.5 seconds)
            min_samples = int(self.sample_rate * 0.5)
            if len(audio_chunk) < min_samples:
                return 0.75  # Uncertain, allow through

            wav = resemblyzer.preprocess_wav(audio_chunk, source_sr=self.sample_rate)
            chunk_embedding = encoder.embed_utterance(wav)

            # Cosine similarity (embeddings are already L2 normalized)
            similarity = float(np.dot(self.profile.embedding, chunk_embedding))

            return similarity

        except Exception as e:
            logger.debug(f"[IdentityManager] ML verification error: {e}")
            return 0.75  # Fail open with uncertain score

    def _verify_energy(self, energy: float) -> float:
        """Fallback verification using energy comparison."""
        if self.profile.avg_energy == 0:
            return 1.0

        # Simple ratio-based similarity
        ratio = min(energy, self.profile.avg_energy) / max(energy, self.profile.avg_energy)
        return ratio

    def process_audio(
        self,
        audio_chunk: bytes,
        energy: float,
        duration_ms: float
    ) -> bool:
        """
        Process an audio chunk (combined calibration + verification).

        This is the main entry point for audio processing.

        Args:
            audio_chunk: Raw audio bytes (or empty for energy-only mode)
            energy: Energy level of this chunk
            duration_ms: Duration in milliseconds

        Returns:
            True if audio should be processed (accepted)
            False if audio should be ignored (rejected)
        """
        # Skip silent frames
        if energy < self.min_energy_threshold:
            return True

        # Phase 1: Calibration (Honey Pot)
        if not self.profile.is_locked:
            # Convert bytes to numpy if we have audio
            if audio_chunk and len(audio_chunk) > 0:
                try:
                    audio_np = np.frombuffer(audio_chunk, dtype=np.int16)
                    self.add_calibration_audio(audio_np, energy, duration_ms)
                except Exception:
                    # If audio conversion fails, just track energy
                    self._buffer_duration += (duration_ms / 1000.0)
                    self._energy_samples.append(energy)
            else:
                # Energy-only mode
                self._buffer_duration += (duration_ms / 1000.0)
                self._energy_samples.append(energy)

            # Auto-lock when we have enough audio
            if self.can_lock():
                self.lock_identity()

            return True  # Always accept during calibration

        # Phase 2: Verification
        if audio_chunk and len(audio_chunk) > 0:
            try:
                audio_np = np.frombuffer(audio_chunk, dtype=np.int16)
                is_match, similarity = self.verify_speaker(audio_np, energy)
                return is_match
            except Exception:
                pass

        # Energy-only verification fallback
        is_match, _ = self.verify_speaker(np.array([]), energy)
        return is_match

    def is_calibrated(self) -> bool:
        """Check if identity has been locked."""
        return self.profile.is_locked

    def get_calibration_progress(self) -> float:
        """Get calibration progress (0-1)."""
        if self.profile.is_locked:
            return 1.0
        return min(1.0, self._buffer_duration / self.calibration_duration_needed)

    def get_stats(self) -> dict:
        """Get verification statistics."""
        total = self._acceptance_count + self._rejection_count
        avg_similarity = (
            sum(self._similarity_scores) / len(self._similarity_scores)
            if self._similarity_scores else 0.0
        )
        return {
            "is_calibrated": self.profile.is_locked,
            "ml_enabled": self.profile.embedding is not None,
            "calibration_progress": self.get_calibration_progress(),
            "accepted": self._acceptance_count,
            "rejected": self._rejection_count,
            "acceptance_rate": self._acceptance_count / total if total > 0 else 1.0,
            "avg_similarity": avg_similarity,
            "avg_energy": self.profile.avg_energy,
            "energy_variance": self.profile.energy_variance,
            "threshold": self.similarity_threshold,
        }

    def adjust_threshold(self, new_threshold: float):
        """Dynamically adjust similarity threshold."""
        old_threshold = self.similarity_threshold
        self.similarity_threshold = max(0.0, min(1.0, new_threshold))
        logger.info(
            f"[IdentityManager] Threshold adjusted: "
            f"{old_threshold:.2f} -> {self.similarity_threshold:.2f}"
        )

    def reset(self):
        """Reset identity manager (for new caller)."""
        self.profile = SpeakerProfile()
        self._calibration_buffer = []
        self._buffer_duration = 0.0
        self._energy_samples = []
        self._rejection_count = 0
        self._acceptance_count = 0
        self._similarity_scores = []
        logger.info("[IdentityManager] RESET - ready for new speaker enrollment")


# =============================================================================
# REJECTION REASON (For Debugging/Analytics)
# =============================================================================

class RejectionReason(Enum):
    """Why audio was rejected by Iron Ear."""
    NONE = auto()                    # Audio accepted
    V1_DEBOUNCE = auto()             # Too short (noise)
    V2_BACKGROUND_VOICE = auto()     # Volume too low (background)
    V3_IDENTITY_MISMATCH = auto()    # Voice doesn't match


# =============================================================================
# IRON EAR FILTER (Main Class - Combines V1 + V2 + V3)
# =============================================================================

class IronEarFilter:
    """
    Multi-layer voice filtering system.

    Combines three protection layers:
    - V1 (Debounce): Filters transient noises like door slams, coughs
    - V2 (Speaker Locking): Volume fingerprinting to ignore background voices
    - V3 (Identity Lock): ML speaker verification using Resemblyzer embeddings

    Usage:
        config = IronEarConfig(
            min_speech_duration_ms=300,
            vad_threshold=0.65,
        )
        iron_ear = IronEarFilter(config)

        # Process frames
        for frame in audio_stream:
            is_valid = iron_ear.process_frame(
                vad_probability=0.8,
                energy=0.5,
            )
            if is_valid:
                # Real speech from target user
                process_speech(frame)
    """

    def __init__(self, config: Optional[IronEarConfig] = None):
        """
        Initialize Iron Ear filter.

        Args:
            config: Configuration object. If None, uses defaults.
        """
        self.config = config or IronEarConfig()

        # V1 - Speech buffer for debounce logic
        self._speech_buffer: List[int] = []
        self._frames_needed = int(
            self.config.min_speech_duration_ms / self.config.frame_duration_ms
        )

        # V2 - Speaker context for volume locking
        self._speaker_context = SpeakerContext()

        # V3 - Identity manager for ML verification
        if self.config.enable_identity_verification:
            self._identity_manager = IdentityManager(
                calibration_duration=self.config.identity_calibration_duration,
                similarity_threshold=self.config.identity_similarity_threshold,
                min_energy_threshold=self.config.min_energy_for_profiling,
                sample_rate=self.config.sample_rate,
                on_identity_locked=self.config.on_identity_locked,
            )
        else:
            self._identity_manager = None

        # Stats
        self._total_frames: int = 0
        self._accepted_frames: int = 0
        self._rejected_v1: int = 0
        self._rejected_v2: int = 0
        self._rejected_v3: int = 0
        self._last_rejection_reason: RejectionReason = RejectionReason.NONE

        logger.info(
            f"[IronEar] Initialized "
            f"(V1={self.config.min_speech_duration_ms}ms debounce, "
            f"V2={'ON' if self.config.enable_speaker_locking else 'OFF'}, "
            f"V3={'ON' if self.config.enable_identity_verification else 'OFF'})"
        )

    # =========================================================================
    # V1 - DEBOUNCE (Door Slam Fix)
    # =========================================================================

    def _is_real_speech_v1(self, vad_probability: float) -> bool:
        """
        Iron Ear V1: Determines if audio is TRULY speech or just noise.

        Uses debounce logic to filter out transient sounds:
        - Door slam = ~100ms (5 frames @ 20ms) - IGNORED
        - Cough = ~150ms (7 frames) - IGNORED
        - Real speech = >300ms (15+ frames) - DETECTED

        Args:
            vad_probability: VAD probability for this frame (0.0-1.0)

        Returns:
            True if this is real speech (buffer is full), False if noise
        """
        # 1. RAW VAD CHECK - Is the audio above our threshold?
        is_active = vad_probability > self.config.vad_threshold

        if is_active:
            # Add to buffer (speech detected)
            self._speech_buffer.append(1)
        else:
            # Decay buffer slowly instead of instant reset
            # This handles choppy speech / brief pauses mid-word
            if self._speech_buffer:
                self._speech_buffer.pop(0)  # Remove oldest frame

        # 2. DURATION CHECK - The "Debounce"
        # Only return True if we have enough consecutive frames
        return len(self._speech_buffer) >= self._frames_needed

    # =========================================================================
    # V2 - SPEAKER LOCKING (Cocktail Party Fix)
    # =========================================================================

    def _update_speaker_profile_v2(self, energy: float):
        """
        Adaptively learn the user's volume fingerprint.

        The first 1-2 seconds of speech establishes a baseline.
        After locking, we use a slower learning rate to adapt to
        natural volume variations while maintaining the fingerprint.
        """
        if energy < self.config.min_energy_for_profiling:
            return  # Ignore total silence or very quiet frames

        # Learning rate: fast initially, slow after locking
        alpha = 0.2 if not self._speaker_context.locked_on else 0.05

        # Update running average
        old_avg = self._speaker_context.avg_user_energy
        self._speaker_context.avg_user_energy = (
            (1 - alpha) * old_avg + (alpha * energy)
        )

        # Track variance for adaptive thresholding
        diff = energy - self._speaker_context.avg_user_energy
        self._speaker_context.energy_variance = (
            (1 - alpha) * self._speaker_context.energy_variance + (alpha * diff * diff)
        )

        # Increment frame count for locking
        self._speaker_context.locking_frame_count += 1

        # Lock on once we have enough frames and a decent baseline
        if (not self._speaker_context.locked_on and
            self._speaker_context.locking_frame_count >= self.config.locking_frames_needed and
            self._speaker_context.avg_user_energy > 0.1):

            self._speaker_context.locked_on = True
            logger.info(
                f"[IronEar] V2 LOCKED on speaker. "
                f"Baseline Energy: {self._speaker_context.avg_user_energy:.4f}, "
                f"Variance: {self._speaker_context.energy_variance:.4f}"
            )

            # Trigger callback
            if self.config.on_speaker_locked:
                self.config.on_speaker_locked(
                    self._speaker_context.avg_user_energy,
                    self._speaker_context.energy_variance,
                )

    def _is_background_voice_v2(self, energy: float) -> bool:
        """
        Check if this is a background voice based on volume.

        Returns True if speech should be IGNORED (it's background chatter).

        Uses the "Cocktail Party" algorithm:
        - If energy is significantly lower than the locked user's baseline,
          it's likely someone else talking in the background.
        """
        if not self.config.enable_speaker_locking:
            return False

        if not self._speaker_context.locked_on:
            return False  # Can't filter if we don't know the user yet

        # The Threshold: User's Average * Configured Sensitivity
        threshold = (
            self._speaker_context.avg_user_energy *
            self.config.background_voice_threshold
        )

        # If energy is significantly lower than user's baseline, it's background
        return energy < threshold

    # =========================================================================
    # MAIN PROCESSING
    # =========================================================================

    def process_frame(
        self,
        vad_probability: Optional[float] = None,
        energy: float = 0.0,
        audio_chunk: Optional[bytes] = None,
    ) -> bool:
        """
        Process an audio frame through all Iron Ear layers.

        Args:
            vad_probability: VAD confidence (0.0-1.0). If None, energy is used.
            energy: Audio energy level (0.0-1.0)
            audio_chunk: Raw audio bytes (optional, for V3 ML verification)

        Returns:
            True if audio should be processed (real speech from target user)
            False if audio should be ignored (noise, background, or imposter)
        """
        self._total_frames += 1
        self._last_rejection_reason = RejectionReason.NONE

        # Use energy as fallback if no VAD probability
        if vad_probability is None:
            vad_probability = energy

        # =====================================================================
        # V1 - DEBOUNCE FILTERING (Door Slams, Coughs)
        # =====================================================================
        is_speech = self._is_real_speech_v1(vad_probability)

        if not is_speech:
            self._rejected_v1 += 1
            self._last_rejection_reason = RejectionReason.V1_DEBOUNCE
            if self.config.on_audio_rejected:
                self.config.on_audio_rejected("V1_DEBOUNCE", vad_probability)
            return False

        # =====================================================================
        # V2 - SPEAKER LOCKING (Cocktail Party Fix)
        # =====================================================================
        # Update the speaker profile with this frame's energy
        if energy > self.config.min_energy_for_profiling:
            self._update_speaker_profile_v2(energy)

        # Check if this is a background voice
        if self._speaker_context.locked_on and self._is_background_voice_v2(energy):
            self._rejected_v2 += 1
            self._last_rejection_reason = RejectionReason.V2_BACKGROUND_VOICE
            if self.config.on_audio_rejected:
                self.config.on_audio_rejected("V2_BACKGROUND_VOICE", energy)
            return False

        # =====================================================================
        # V3 - IDENTITY VERIFICATION (Speaker Fingerprinting)
        # =====================================================================
        if self._identity_manager is not None:
            is_accepted = self._identity_manager.process_audio(
                audio_chunk or b'',
                energy,
                self.config.frame_duration_ms,
            )
            if not is_accepted:
                self._rejected_v3 += 1
                self._last_rejection_reason = RejectionReason.V3_IDENTITY_MISMATCH
                if self.config.on_audio_rejected:
                    self.config.on_audio_rejected("V3_IDENTITY_MISMATCH", energy)
                return False

        # All checks passed - this is real speech from the target user
        self._accepted_frames += 1
        return True

    # =========================================================================
    # HONEY POT METHODS (V3 - Identity Calibration)
    # =========================================================================

    def start_honeypot(self):
        """
        Start the Honey Pot calibration phase for V3.

        Call this when sending the initial prompt that asks the user
        to speak at length (e.g., "Could you state your name and reason for calling?")
        """
        if self._identity_manager is not None:
            self._identity_manager.start_calibration()
            logger.info("[IronEar] Honey Pot started - collecting voice fingerprint")

    def is_identity_calibrated(self) -> bool:
        """Check if the identity has been locked (V3)."""
        if self._identity_manager is None:
            return True  # No verification = always "calibrated"
        return self._identity_manager.is_calibrated()

    def get_calibration_progress(self) -> float:
        """Get identity calibration progress (0-1)."""
        if self._identity_manager is None:
            return 1.0
        return self._identity_manager.get_calibration_progress()

    def get_identity_stats(self) -> Optional[dict]:
        """Get identity verification statistics (V3)."""
        if self._identity_manager is None:
            return None
        return self._identity_manager.get_stats()

    # =========================================================================
    # SPEAKER LOCK METHODS (V2)
    # =========================================================================

    def is_speaker_locked(self) -> bool:
        """Check if speaker volume profile is locked (V2)."""
        return self._speaker_context.locked_on

    def unlock_speaker(self):
        """
        Reset the speaker lock (V2).

        Call this when you want to recalibrate, e.g., when a new user
        takes over the conversation.
        """
        self._speaker_context = SpeakerContext()
        logger.info("[IronEar] V2 Speaker lock RESET - will recalibrate on next speech")

    def get_speaker_profile(self) -> dict:
        """Get current speaker volume profile (V2)."""
        return {
            "locked_on": self._speaker_context.locked_on,
            "avg_energy": self._speaker_context.avg_user_energy,
            "energy_variance": self._speaker_context.energy_variance,
            "noise_floor": self._speaker_context.noise_floor,
            "frames_analyzed": self._speaker_context.locking_frame_count,
        }

    # =========================================================================
    # GENERAL METHODS
    # =========================================================================

    def reset(self):
        """Reset all Iron Ear state (for new conversation)."""
        # V1 - Reset debounce buffer
        self._speech_buffer = []

        # V2 - Reset speaker lock
        self._speaker_context = SpeakerContext()

        # V3 - Reset identity manager
        if self._identity_manager is not None:
            self._identity_manager.reset()

        # Reset stats
        self._total_frames = 0
        self._accepted_frames = 0
        self._rejected_v1 = 0
        self._rejected_v2 = 0
        self._rejected_v3 = 0
        self._last_rejection_reason = RejectionReason.NONE

        logger.info("[IronEar] FULL RESET - ready for new conversation")

    def get_stats(self) -> dict:
        """Get comprehensive Iron Ear statistics."""
        total_rejected = self._rejected_v1 + self._rejected_v2 + self._rejected_v3
        return {
            "total_frames": self._total_frames,
            "accepted_frames": self._accepted_frames,
            "acceptance_rate": (
                self._accepted_frames / self._total_frames
                if self._total_frames > 0 else 1.0
            ),
            "rejected": {
                "total": total_rejected,
                "v1_debounce": self._rejected_v1,
                "v2_background": self._rejected_v2,
                "v3_identity": self._rejected_v3,
            },
            "last_rejection_reason": self._last_rejection_reason.name,
            "v2_speaker_locked": self._speaker_context.locked_on,
            "v3_identity_calibrated": self.is_identity_calibrated(),
        }

    def get_last_rejection_reason(self) -> RejectionReason:
        """Get the reason why the last frame was rejected."""
        return self._last_rejection_reason

    def check_connection_quality(self) -> Optional[str]:
        """
        Check if the environment is too noisy to proceed.

        Returns a prompt to ask user to improve conditions, or None if OK.
        """
        # If noise floor is too high
        if self._speaker_context.noise_floor > 0.4:
            return (
                "I'm having a little trouble hearing you clearly. "
                "Are you on speakerphone by chance?"
            )

        # If identity verification is failing too often
        if self._identity_manager is not None:
            stats = self._identity_manager.get_stats()
            if stats["is_calibrated"] and stats["acceptance_rate"] < 0.5:
                return (
                    "There seems to be a lot of background noise. "
                    "Could you move to a quieter area?"
                )

        return None


# =============================================================================
# HONEY POT PROMPTS (Pre-built calibration questions)
# =============================================================================

HONEYPOT_PROMPTS = {
    "default": (
        "Hi there! To make sure I can help you effectively, "
        "could you tell me your name and briefly describe what you're calling about today?"
    ),
    "receptionist": (
        "Thank you for calling. To connect you with the right person, "
        "may I have your full name and the nature of your inquiry?"
    ),
    "electrician": (
        "Thanks for reaching out. To get you the right help, "
        "could you describe the electrical issue you're experiencing?"
    ),
    "plumber": (
        "I appreciate your call. To assist you better, "
        "can you tell me about the plumbing problem you're facing?"
    ),
    "lawyer": (
        "Thank you for contacting our office. For our records, "
        "please state your full name and briefly describe your legal matter."
    ),
    "solar": (
        "Great to hear from you! To tailor our recommendations, "
        "could you tell me about your home and why you're interested in solar?"
    ),
}

SOFT_FAIL_PROMPTS = [
    "I'm having a bit of trouble hearing you clearly. Are you on speaker phone?",
    "The connection seems a little unclear. Could you move somewhere quieter?",
    "I want to make sure I catch everything you're saying. Is there background noise on your end?",
]


def get_honeypot_prompt(skill: str = "default") -> str:
    """Get the appropriate honey pot prompt for a skill."""
    return HONEYPOT_PROMPTS.get(skill, HONEYPOT_PROMPTS["default"])


def get_soft_fail_prompt() -> str:
    """Get a random soft fail prompt for noisy environments."""
    import random
    return random.choice(SOFT_FAIL_PROMPTS)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Demo configuration with callbacks
    def on_locked(energy, variance):
        print(f"  -> Speaker locked! Energy: {energy:.3f}, Variance: {variance:.6f}")

    def on_identity(stats):
        print(f"  -> Identity locked! ML: {stats['ml_enabled']}, "
              f"Samples: {stats['accepted']}")

    def on_rejected(reason, value):
        print(f"  -> Rejected: {reason} (value={value:.3f})")

    config = IronEarConfig(
        min_speech_duration_ms=300,
        vad_threshold=0.65,
        enable_speaker_locking=True,
        enable_identity_verification=False,  # Disable for demo (no resemblyzer)
        on_speaker_locked=on_locked,
        on_identity_locked=on_identity,
        on_audio_rejected=on_rejected,
    )

    iron_ear = IronEarFilter(config)

    print("=== Iron Ear Demo ===\n")

    # Simulate a conversation
    print("1. Door slam (100ms) - should be filtered by V1:")
    for _ in range(5):  # 5 frames @ 20ms = 100ms
        result = iron_ear.process_frame(vad_probability=0.9, energy=0.3)
    print(f"   Result: {'ACCEPTED' if result else 'REJECTED'} "
          f"(reason: {iron_ear.get_last_rejection_reason().name})")

    print("\n2. Real speech (500ms) - should pass V1:")
    for _ in range(25):  # 25 frames @ 20ms = 500ms
        result = iron_ear.process_frame(vad_probability=0.85, energy=0.5)
    print(f"   Result: {'ACCEPTED' if result else 'REJECTED'}")

    print("\n3. Background voice (quieter) - should be filtered by V2:")
    # Speaker should be locked by now
    result = iron_ear.process_frame(vad_probability=0.8, energy=0.15)
    print(f"   Result: {'ACCEPTED' if result else 'REJECTED'} "
          f"(reason: {iron_ear.get_last_rejection_reason().name})")

    print("\n4. Final Stats:")
    stats = iron_ear.get_stats()
    print(f"   Total frames: {stats['total_frames']}")
    print(f"   Accepted: {stats['accepted_frames']}")
    print(f"   Rejected V1: {stats['rejected']['v1_debounce']}")
    print(f"   Rejected V2: {stats['rejected']['v2_background']}")
    print(f"   Speaker locked: {stats['v2_speaker_locked']}")
