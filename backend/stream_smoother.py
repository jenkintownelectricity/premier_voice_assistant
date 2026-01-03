"""
Stream Smoother - Jitter Buffer for Smooth Audio Playback

This module provides a jitter buffer that converts jagged network chunks
into smooth, consistent audio frames for LiveKit playback.

The StreamSmoother accumulates audio data and yields perfect 20ms frames,
eliminating the choppy audio that can occur with direct streaming.

Usage:
    smoother = StreamSmoother(sample_rate=24000, pre_buffer_count=3)

    async for chunk in tts_stream:
        async for frame in smoother.add_chunk_and_yield(chunk):
            await audio_source.capture_frame(frame)

    # Flush remaining audio
    final_frame = smoother.flush()
    if final_frame:
        await audio_source.capture_frame(final_frame)
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

# Try to import LiveKit AudioFrame
try:
    from livekit.rtc import AudioFrame
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    # Create a simple AudioFrame placeholder for testing
    class AudioFrame:
        def __init__(self, data: bytes, sample_rate: int, num_channels: int, samples_per_channel: int):
            self.data = data
            self.sample_rate = sample_rate
            self.num_channels = num_channels
            self.samples_per_channel = samples_per_channel


class StreamSmoother:
    """
    A 'Jitter Buffer' that swallows jagged network chunks and
    spits out perfect, smooth audio frames for LiveKit.

    How it works:
    1. Incoming chunks are accumulated in a buffer
    2. Once we have enough data (pre_buffer_count frames), we start emitting
    3. Each emitted frame is exactly frame_duration_ms milliseconds
    4. Any remaining audio is flushed at the end (padded with silence)

    Args:
        sample_rate: Audio sample rate (e.g., 24000, 44100)
        channels: Number of audio channels (1 for mono, 2 for stereo)
        pre_buffer_count: Number of frames to buffer before starting playback
        frame_duration_ms: Duration of each output frame in milliseconds
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        pre_buffer_count: int = 3,
        frame_duration_ms: int = 20,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.bytes_per_sample = 2  # 16-bit PCM
        self.frame_duration_ms = frame_duration_ms

        # Calculate frame size in bytes
        # frame_size = sample_rate * (duration_ms / 1000) * channels * bytes_per_sample
        self.frame_size = int(
            sample_rate * (self.frame_duration_ms / 1000.0) * channels * self.bytes_per_sample
        )

        self.buffer = bytearray()
        self.pre_buffer_count = pre_buffer_count
        self.has_started = False
        self.total_frames_yielded = 0
        self.total_bytes_received = 0

        logger.debug(
            f"StreamSmoother initialized: sample_rate={sample_rate}, "
            f"channels={channels}, frame_size={self.frame_size} bytes, "
            f"pre_buffer={pre_buffer_count} frames"
        )

    async def add_chunk_and_yield(self, chunk: bytes) -> AsyncIterator[AudioFrame]:
        """
        Ingest a raw chunk and yield as many perfect frames as possible.

        Args:
            chunk: Raw audio bytes from the TTS stream

        Yields:
            AudioFrame objects ready for LiveKit playback
        """
        self.buffer.extend(chunk)
        self.total_bytes_received += len(chunk)

        # Determine how much data we need before yielding
        required_size = (
            self.frame_size * self.pre_buffer_count
            if not self.has_started
            else self.frame_size
        )

        # Yield frames while we have enough data
        while len(self.buffer) >= required_size:
            self.has_started = True

            # Extract one frame worth of data
            frame_data = bytes(self.buffer[:self.frame_size])
            del self.buffer[:self.frame_size]

            self.total_frames_yielded += 1

            yield AudioFrame(
                data=frame_data,
                sample_rate=self.sample_rate,
                num_channels=self.channels,
                samples_per_channel=self.frame_size // (self.channels * self.bytes_per_sample)
            )

            # After first batch, only require one frame
            required_size = self.frame_size

    def flush(self) -> Optional[AudioFrame]:
        """
        Yield any remaining audio in buffer (pad with silence if needed).

        Call this at the end of the stream to ensure all audio is played.

        Returns:
            Final AudioFrame with remaining audio (padded), or None if empty
        """
        if not self.buffer:
            logger.debug(
                f"StreamSmoother flush: no remaining data. "
                f"Total frames yielded: {self.total_frames_yielded}, "
                f"Total bytes received: {self.total_bytes_received}"
            )
            return None

        # Get remaining audio
        remaining = bytes(self.buffer)

        # Pad to frame size with silence
        padding_needed = self.frame_size - len(remaining)
        if padding_needed > 0:
            remaining += b'\x00' * padding_needed
            logger.debug(f"StreamSmoother flush: padded {padding_needed} bytes of silence")

        self.buffer.clear()
        self.total_frames_yielded += 1

        logger.debug(
            f"StreamSmoother flush complete. "
            f"Total frames: {self.total_frames_yielded}, "
            f"Total bytes: {self.total_bytes_received}"
        )

        return AudioFrame(
            data=remaining,
            sample_rate=self.sample_rate,
            num_channels=self.channels,
            samples_per_channel=self.frame_size // (self.channels * self.bytes_per_sample)
        )

    def reset(self):
        """Reset the smoother for reuse."""
        self.buffer.clear()
        self.has_started = False
        self.total_frames_yielded = 0
        self.total_bytes_received = 0

    @property
    def buffered_duration_ms(self) -> float:
        """Get the current buffered audio duration in milliseconds."""
        bytes_buffered = len(self.buffer)
        samples_buffered = bytes_buffered / (self.channels * self.bytes_per_sample)
        return (samples_buffered / self.sample_rate) * 1000


async def generate_smooth_stream(
    text: str,
    voice_id: str,
    url: str,
    sample_rate: int = 24000,
    pre_buffer_count: int = 4,
) -> AsyncIterator[AudioFrame]:
    """
    Generate smooth audio frames from a streaming TTS endpoint.

    This is a convenience function that wraps StreamSmoother for common use cases.

    Args:
        text: Text to synthesize
        voice_id: Voice identifier
        url: TTS streaming endpoint URL
        sample_rate: Audio sample rate
        pre_buffer_count: Number of frames to buffer before playback

    Yields:
        Smooth AudioFrame objects ready for LiveKit
    """
    import httpx

    smoother = StreamSmoother(
        sample_rate=sample_rate,
        pre_buffer_count=pre_buffer_count
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            async with client.stream("POST", url, json={
                "text": text,
                "voice_name": voice_id,
                "language": "en",
                "stream": True,
                "format": "pcm",
                "sample_rate": sample_rate,
            }) as response:
                if response.status_code != 200:
                    logger.error(f"TTS streaming failed: {response.status_code}")
                    return

                async for chunk in response.aiter_bytes():
                    async for frame in smoother.add_chunk_and_yield(chunk):
                        yield frame

            # Flush any remaining audio
            final_frame = smoother.flush()
            if final_frame:
                yield final_frame

        except httpx.TimeoutException:
            logger.error("TTS streaming timed out")
        except Exception as e:
            logger.error(f"TTS streaming error: {e}")


class AdaptiveStreamSmoother(StreamSmoother):
    """
    An adaptive version of StreamSmoother that adjusts buffering based on network conditions.

    If the buffer runs dry frequently, it increases the pre-buffer count.
    If the buffer is consistently full, it decreases the pre-buffer count.
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        min_pre_buffer: int = 2,
        max_pre_buffer: int = 8,
        initial_pre_buffer: int = 4,
        frame_duration_ms: int = 20,
    ):
        super().__init__(
            sample_rate=sample_rate,
            channels=channels,
            pre_buffer_count=initial_pre_buffer,
            frame_duration_ms=frame_duration_ms,
        )
        self.min_pre_buffer = min_pre_buffer
        self.max_pre_buffer = max_pre_buffer
        self.underrun_count = 0
        self.overrun_count = 0
        self.adjustment_interval = 50  # Adjust every N frames

    async def add_chunk_and_yield(self, chunk: bytes) -> AsyncIterator[AudioFrame]:
        """Add chunk and yield frames, with adaptive buffering."""
        # Check for underrun (buffer ran dry)
        if self.has_started and len(self.buffer) < self.frame_size:
            self.underrun_count += 1

        # Check for overrun (buffer too full)
        if len(self.buffer) > self.frame_size * self.max_pre_buffer * 2:
            self.overrun_count += 1

        # Yield frames from parent
        async for frame in super().add_chunk_and_yield(chunk):
            yield frame

            # Adjust buffering periodically
            if self.total_frames_yielded % self.adjustment_interval == 0:
                self._adjust_buffering()

    def _adjust_buffering(self):
        """Adjust pre-buffer count based on network performance."""
        if self.underrun_count > 5 and self.pre_buffer_count < self.max_pre_buffer:
            self.pre_buffer_count += 1
            logger.info(f"Increased pre-buffer to {self.pre_buffer_count} (underruns: {self.underrun_count})")
            self.underrun_count = 0
        elif self.overrun_count > 5 and self.pre_buffer_count > self.min_pre_buffer:
            self.pre_buffer_count -= 1
            logger.info(f"Decreased pre-buffer to {self.pre_buffer_count} (overruns: {self.overrun_count})")
            self.overrun_count = 0
