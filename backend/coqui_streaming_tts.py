"""
Coqui XTTS Streaming TTS for LiveKit

Provides smooth streaming audio from Modal-hosted Coqui XTTS-v2 with jitter buffering
for real-time voice calls.

The jitter buffer collects a small pre-buffer of audio before starting playback,
eliminating the choppy/robotic sound that occurs when streaming network audio directly.
"""

import httpx
import asyncio
import logging
from typing import AsyncIterator, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Audio constants for LiveKit compatibility
SAMPLE_RATE = 24000  # Coqui XTTS outputs 24kHz
CHANNELS = 1
BYTES_PER_SAMPLE = 2  # 16-bit PCM
FRAME_DURATION_MS = 20  # LiveKit standard frame size


@dataclass
class CoquiStreamingConfig:
    """Configuration for Coqui streaming TTS."""
    api_url: str = "https://jenkintownelectricity--premier-coqui-tts-synthesize-stream-web.modal.run"
    voice_name: str = "fabio"
    language: str = "en"
    sample_rate: int = SAMPLE_RATE
    pre_buffer_frames: int = 3  # Number of frames to buffer before playback starts


async def generate_smooth_audio(
    text: str,
    config: CoquiStreamingConfig,
) -> AsyncIterator[bytes]:
    """
    Generate smooth streaming audio from Coqui XTTS.

    Uses a jitter buffer to collect audio before starting playback,
    eliminating choppy audio caused by network latency variations.

    Args:
        text: Text to synthesize
        config: CoquiStreamingConfig with API URL and voice settings

    Yields:
        bytes: PCM audio frames (24kHz, 16-bit, mono) in 20ms chunks
    """
    # Calculate bytes per frame: 24000 * 0.02 * 1 * 2 = 960 bytes
    frame_size = int(config.sample_rate * (FRAME_DURATION_MS / 1000.0) * CHANNELS * BYTES_PER_SAMPLE)

    buffer = bytearray()
    has_started_playing = False
    frame_count = 0

    logger.info(f"Starting Coqui stream: '{text[:50]}...' voice={config.voice_name}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "text": text,
            "voice_name": config.voice_name,
            "language": config.language,
            "sample_rate": config.sample_rate,
        }

        try:
            async with client.stream("POST", config.api_url, data=payload) as response:
                if response.status_code != 200:
                    logger.error(f"Coqui TTS error: {response.status_code}")
                    return

                async for chunk in response.aiter_bytes():
                    buffer.extend(chunk)

                    # Jitter buffer logic:
                    # Only start yielding after collecting enough "safety" buffer
                    min_buffer = frame_size * config.pre_buffer_frames if not has_started_playing else frame_size

                    while len(buffer) >= min_buffer:
                        has_started_playing = True

                        # Slice off exactly one perfect frame
                        frame_data = bytes(buffer[:frame_size])
                        del buffer[:frame_size]

                        yield frame_data
                        frame_count += 1

                # Flush remaining audio
                while len(buffer) >= frame_size:
                    frame_data = bytes(buffer[:frame_size])
                    del buffer[:frame_size]
                    yield frame_data
                    frame_count += 1

                # Handle any remaining partial frame by padding with silence
                if len(buffer) > 0:
                    # Pad to frame size with zeros (silence)
                    padded = buffer + bytearray(frame_size - len(buffer))
                    yield bytes(padded)
                    frame_count += 1

                logger.info(f"Coqui stream complete: {frame_count} frames yielded")

        except httpx.TimeoutException:
            logger.error("Coqui TTS request timed out")
        except Exception as e:
            logger.error(f"Coqui TTS stream error: {e}")


class CoquiStreamingTTS:
    """
    LiveKit-compatible TTS wrapper for Coqui XTTS streaming.

    This class implements the TTS interface expected by LiveKit's AgentSession,
    allowing Coqui voice clones to be used in real-time voice calls.

    Usage:
        tts = CoquiStreamingTTS(
            api_url="https://your-modal-url.modal.run",
            voice_name="my_voice",
        )

        # In LiveKit agent:
        session = AgentSession(
            tts=tts,
            ...
        )
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        voice_name: str = "fabio",
        language: str = "en",
        pre_buffer_frames: int = 3,
    ):
        """
        Initialize Coqui streaming TTS.

        Args:
            api_url: Modal endpoint for streaming synthesis
            voice_name: Name of the cloned voice to use
            language: Language code (default: "en")
            pre_buffer_frames: Jitter buffer size (higher = smoother, more latency)
        """
        self.config = CoquiStreamingConfig(
            api_url=api_url or CoquiStreamingConfig.api_url,
            voice_name=voice_name,
            language=language,
            pre_buffer_frames=pre_buffer_frames,
        )
        self._sample_rate = SAMPLE_RATE

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """
        Synthesize text to audio using Coqui XTTS streaming.

        Args:
            text: Text to synthesize

        Yields:
            bytes: PCM audio frames
        """
        async for frame in generate_smooth_audio(text, self.config):
            yield frame

    def set_voice(self, voice_name: str):
        """Change the voice for subsequent synthesis calls."""
        self.config.voice_name = voice_name
        logger.info(f"Coqui voice changed to: {voice_name}")


# Convenience function for testing
async def test_coqui_stream():
    """Test the Coqui streaming TTS."""
    config = CoquiStreamingConfig()

    frame_count = 0
    total_bytes = 0

    async for frame in generate_smooth_audio("Hello, this is a test of the Coqui streaming TTS system.", config):
        frame_count += 1
        total_bytes += len(frame)

    print(f"Received {frame_count} frames, {total_bytes} bytes")
    print(f"Duration: ~{frame_count * FRAME_DURATION_MS / 1000:.2f}s")


if __name__ == "__main__":
    asyncio.run(test_coqui_stream())
