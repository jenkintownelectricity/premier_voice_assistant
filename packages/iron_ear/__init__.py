"""
Iron Ear - Multi-Layer Voice Filtering System

A standalone, decoupled noise filtering package for voice AI applications.

Layers:
    V1 - DEBOUNCE: Filters transient noises (door slams, coughs)
    V2 - SPEAKER LOCKING: Volume fingerprinting to ignore background voices
    V3 - IDENTITY LOCK: ML-based speaker verification (requires resemblyzer)

Usage:
    from packages.iron_ear import IronEarFilter, IronEarConfig

    config = IronEarConfig(
        min_speech_duration_ms=300,
        vad_threshold=0.65,
    )

    iron_ear = IronEarFilter(config)

    for frame in audio_stream:
        if iron_ear.process_frame(vad_probability=frame.vad, energy=frame.energy):
            # Real speech from target user
            process(frame)
"""

from .noise_filter import (
    # Main classes
    IronEarFilter,
    IronEarConfig,
    IdentityManager,
    # Data structures
    SpeakerProfile,
    SpeakerContext,
    RejectionReason,
    # Utility functions
    get_honeypot_prompt,
    get_soft_fail_prompt,
    is_resemblyzer_available,
    # Constants
    HONEYPOT_PROMPTS,
    SOFT_FAIL_PROMPTS,
)

__version__ = "1.0.0"
__all__ = [
    # Main classes
    "IronEarFilter",
    "IronEarConfig",
    "IdentityManager",
    # Data structures
    "SpeakerProfile",
    "SpeakerContext",
    "RejectionReason",
    # Utility functions
    "get_honeypot_prompt",
    "get_soft_fail_prompt",
    "is_resemblyzer_available",
    # Constants
    "HONEYPOT_PROMPTS",
    "SOFT_FAIL_PROMPTS",
]
