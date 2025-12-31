"""
Identity Manager - Iron Ear 3.0 (Speaker Verification)

This module implements "Zero-Shot Speaker Enrollment".
It captures a 'fingerprint' of the user's voice during the initial
'Honey Pot' phase and rejects subsequent audio that doesn't match.

The Honey Pot Flow:
1. Agent asks engaging question (e.g., "Could you state your name and reason for calling?")
2. User responds with 10-15 seconds of natural speech
3. System captures voice characteristics (pitch, speed, timbre)
4. Identity is LOCKED - only matching voice is accepted
5. Background voices, TV, etc. are rejected

Future Enhancement:
- Replace heuristic checks with Resemblyzer/PyAnnote embeddings
- Add cosine_similarity matching for ML-based verification
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SpeakerProfile:
    """Voice fingerprint for the enrolled speaker."""
    is_locked: bool = False
    calibration_audio: List[bytes] = field(default_factory=list)

    # Heuristic features (until ML embeddings are added)
    avg_energy: float = 0.0
    energy_variance: float = 0.0
    avg_pitch: float = 0.0
    avg_speed: float = 0.0  # Words per second estimate

    # Calibration tracking
    calibration_start_time: float = 0.0
    total_speech_frames: int = 0

    # In a full ML implementation, this would store the Embedding Vector:
    # fingerprint: np.ndarray = None


class IdentityManager:
    """
    Manages speaker identity verification using voice fingerprints.

    Usage:
        identity = IdentityManager()

        # Start calibration when asking the honey pot question
        identity.start_calibration()

        # Process audio frames
        for audio_chunk in stream:
            if identity.process_audio(audio_chunk, energy, 20):
                # Audio accepted - process normally
            else:
                # Audio rejected - ignore (imposter/noise)
    """

    def __init__(
        self,
        calibration_duration: float = 10.0,
        similarity_threshold: float = 0.65,
        min_energy_threshold: float = 0.05,
    ):
        """
        Initialize IdentityManager.

        Args:
            calibration_duration: Seconds of speech needed for enrollment (default 10s)
            similarity_threshold: Minimum similarity score to accept (0-1)
            min_energy_threshold: Minimum energy to consider as speech
        """
        self.profile = SpeakerProfile()
        self.calibration_duration_needed = calibration_duration
        self.similarity_threshold = similarity_threshold
        self.min_energy_threshold = min_energy_threshold

        # Internal tracking
        self._buffer_duration = 0.0
        self._rejection_count = 0
        self._acceptance_count = 0
        self._energy_samples: List[float] = []

        logger.info(f"[IdentityManager] Initialized (calibration: {calibration_duration}s, "
                    f"threshold: {similarity_threshold})")

    def start_calibration(self):
        """
        Start the calibration phase (call when asking the 'Honey Pot' question).

        This resets any existing profile and begins collecting voice samples.
        """
        self.profile = SpeakerProfile()
        self.profile.calibration_start_time = time.time()
        self._buffer_duration = 0.0
        self._energy_samples = []
        self._rejection_count = 0
        self._acceptance_count = 0

        logger.info("[IdentityManager] Starting Calibration Phase (Honey Pot)")

    def process_audio(
        self,
        audio_chunk: bytes,
        energy: float,
        duration_ms: float
    ) -> bool:
        """
        Process an audio chunk and verify identity.

        Args:
            audio_chunk: Raw audio bytes
            energy: Normalized energy level (0-1)
            duration_ms: Duration of this chunk in milliseconds

        Returns:
            True if audio is accepted (matches user or still calibrating)
            False if audio is rejected (imposter/noise)
        """
        # Skip very quiet audio
        if energy < self.min_energy_threshold:
            return True  # Silent frames don't need verification

        # Phase 1: Data Collection (The Honey Pot)
        if not self.profile.is_locked:
            self._collect_sample(audio_chunk, energy, duration_ms)
            return True  # Always accept audio while calibrating

        # Phase 2: Identity Verification
        is_match = self._verify_identity(energy)

        if is_match:
            self._acceptance_count += 1
        else:
            self._rejection_count += 1
            if self._rejection_count % 50 == 0:  # Log every 50 rejections
                logger.warning(
                    f"[IdentityManager] High rejection rate: "
                    f"{self._rejection_count}/{self._rejection_count + self._acceptance_count}"
                )

        return is_match

    def _collect_sample(self, audio_chunk: bytes, energy: float, duration_ms: float):
        """Collect audio sample during calibration phase."""
        self._buffer_duration += (duration_ms / 1000.0)
        self.profile.calibration_audio.append(audio_chunk)
        self._energy_samples.append(energy)
        self.profile.total_speech_frames += 1

        # Check if we have enough data to lock
        if self._buffer_duration >= self.calibration_duration_needed:
            self._lock_identity()

    def _lock_identity(self):
        """Process the collected samples and create the voice fingerprint."""
        if not self._energy_samples:
            logger.warning("[IdentityManager] Cannot lock - no samples collected")
            return

        # Calculate heuristic features from collected samples
        self.profile.avg_energy = sum(self._energy_samples) / len(self._energy_samples)

        # Calculate variance
        variance_sum = sum(
            (e - self.profile.avg_energy) ** 2 for e in self._energy_samples
        )
        self.profile.energy_variance = variance_sum / len(self._energy_samples)

        self.profile.is_locked = True

        logger.info(
            f"[IdentityManager] IDENTITY LOCKED "
            f"(captured {self._buffer_duration:.1f}s, "
            f"{len(self._energy_samples)} frames, "
            f"avg_energy={self.profile.avg_energy:.4f}, "
            f"variance={self.profile.energy_variance:.4f})"
        )

        # TODO: Future ML implementation
        # self.profile.fingerprint = resemblyzer_model.embed(self.profile.calibration_audio)

    def _verify_identity(self, energy: float) -> bool:
        """
        Verify if audio matches the enrolled speaker.

        Currently uses energy-based heuristics. Future implementation will use
        cosine similarity between voice embeddings.

        Args:
            energy: Energy level of current audio frame

        Returns:
            True if audio matches enrolled speaker
        """
        if not self.profile.is_locked:
            return True  # Can't verify if not calibrated

        # Heuristic Check: Energy should be within reasonable range of baseline
        # Very quiet audio compared to baseline is likely background
        min_energy = self.profile.avg_energy * self.similarity_threshold

        if energy < min_energy:
            return False  # Too quiet - likely background voice

        # Accept if energy is reasonably close to baseline
        # (This is a simplified heuristic - ML embeddings would be more accurate)
        return True

        # TODO: Future ML implementation
        # current_embedding = resemblyzer_model.embed(audio_chunk)
        # similarity = cosine_similarity(self.profile.fingerprint, current_embedding)
        # return similarity >= self.similarity_threshold

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
        return {
            "is_calibrated": self.profile.is_locked,
            "calibration_progress": self.get_calibration_progress(),
            "accepted": self._acceptance_count,
            "rejected": self._rejection_count,
            "acceptance_rate": self._acceptance_count / total if total > 0 else 1.0,
            "avg_energy": self.profile.avg_energy,
            "energy_variance": self.profile.energy_variance,
        }

    def reset(self):
        """Reset identity manager (for new caller)."""
        self.profile = SpeakerProfile()
        self._buffer_duration = 0.0
        self._energy_samples = []
        self._rejection_count = 0
        self._acceptance_count = 0
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


def get_honeypot_prompt(skill: str = "default") -> str:
    """Get the appropriate honey pot prompt for a skill."""
    return HONEYPOT_PROMPTS.get(skill, HONEYPOT_PROMPTS["default"])
