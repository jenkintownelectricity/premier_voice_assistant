"""
Identity Manager - Iron Ear 3.0 (Speaker Verification)

This module implements "Zero-Shot Speaker Enrollment" using Resemblyzer
for real speaker embeddings.

It captures a voice fingerprint (256-dimensional embedding) during the
'Honey Pot' phase and rejects subsequent audio that doesn't match.

The Honey Pot Flow:
1. Agent asks engaging question (e.g., "Could you state your name and reason for calling?")
2. User responds with 10-15 seconds of natural speech
3. System extracts 256-dim speaker embedding (voice fingerprint)
4. Identity is LOCKED - only matching voice is accepted
5. Background voices, TV, imposters are rejected

Based on research from:
- Resemblyzer (Google's GE2E paper)
- ECAPA-TDNN speaker verification
- Zero-shot speaker enrollment techniques
"""

import time
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Resemblyzer is loaded lazily to reduce memory usage at startup
# The model (~50MB) is only loaded when identity lock is actually triggered
_resemblyzer_module: Optional[Any] = None
_resemblyzer_checked: bool = False


def _load_resemblyzer():
    """
    Lazily load Resemblyzer module on first use.

    This prevents the ~50MB neural network model from being loaded
    at worker startup. It's only loaded when identity lock is triggered.
    """
    global _resemblyzer_module, _resemblyzer_checked

    if _resemblyzer_checked:
        return _resemblyzer_module

    _resemblyzer_checked = True

    try:
        import resemblyzer
        _resemblyzer_module = resemblyzer
        logger.info("[IdentityManager] Resemblyzer loaded - ML speaker verification enabled")
    except ImportError:
        _resemblyzer_module = None
        logger.warning("[IdentityManager] Resemblyzer not available - using energy-based fallback")

    return _resemblyzer_module


def is_resemblyzer_available() -> bool:
    """Check if Resemblyzer is available (loads it if not already checked)."""
    return _load_resemblyzer() is not None


@dataclass
class SpeakerProfile:
    """Voice fingerprint for the enrolled speaker."""
    is_locked: bool = False

    # ML Embedding (256-dimensional vector)
    embedding: Optional[np.ndarray] = None

    # Fallback heuristic features (when Resemblyzer unavailable)
    avg_energy: float = 0.0
    energy_variance: float = 0.0

    # Calibration tracking
    calibration_start_time: float = 0.0
    total_speech_frames: int = 0
    calibration_audio_samples: int = 0


class IdentityManager:
    """
    Manages speaker identity verification using voice embeddings.

    Uses Resemblyzer to extract 256-dimensional speaker embeddings
    and cosine similarity for verification.

    Usage:
        identity = IdentityManager()

        # Start calibration when asking the honey pot question
        identity.start_calibration()

        # Collect audio during user's response
        for audio_chunk in stream:
            identity.add_calibration_audio(audio_chunk)

        # Lock identity after enough audio collected
        if identity.can_lock():
            identity.lock_identity()

        # Verify subsequent audio
        is_match, score = identity.verify_speaker(audio_chunk)
    """

    def __init__(
        self,
        calibration_duration: float = 10.0,
        similarity_threshold: float = 0.75,
        min_energy_threshold: float = 0.05,
        sample_rate: int = 16000,
    ):
        """
        Initialize IdentityManager.

        Args:
            calibration_duration: Seconds of speech needed for enrollment (default 10s)
            similarity_threshold: Minimum cosine similarity to accept (0-1)
            min_energy_threshold: Minimum energy to consider as speech
            sample_rate: Audio sample rate (default 16kHz for Resemblyzer)
        """
        self.profile = SpeakerProfile()
        self.calibration_duration_needed = calibration_duration
        self.similarity_threshold = similarity_threshold
        self.min_energy_threshold = min_energy_threshold
        self.sample_rate = sample_rate

        # ML encoder (loaded lazily)
        self._encoder: Optional['VoiceEncoder'] = None

        # Audio buffer for calibration
        self._calibration_buffer: List[np.ndarray] = []
        self._buffer_duration = 0.0

        # Statistics
        self._rejection_count = 0
        self._acceptance_count = 0
        self._energy_samples: List[float] = []
        self._similarity_scores: List[float] = []

        # Note: Resemblyzer is loaded lazily when identity lock is triggered
        logger.info(
            f"[IdentityManager] Initialized "
            f"(ML=lazy-load, calibration={calibration_duration}s, threshold={similarity_threshold})"
        )

    def _get_encoder(self):
        """
        Lazily load the voice encoder.

        This is called only when identity lock is triggered, preventing
        the ~50MB model from being loaded at worker startup.
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

        This resets any existing profile and begins collecting voice samples.
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

        This is the main entry point called by TurnManager.

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
            f"{old_threshold:.2f} → {self.similarity_threshold:.2f}"
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
# HONEY POT PROMPTS
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


# =============================================================================
# SOFT FAIL PROMPTS
# =============================================================================

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
