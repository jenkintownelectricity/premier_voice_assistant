"""
Coqui XTTS LiveKit Integration - Streaming TTS for Real-Time Voice

This module provides a LiveKit-compatible TTS wrapper for Coqui XTTS,
using the StreamSmoother to convert batch audio into smooth streaming frames.

The key challenge: Coqui XTTS returns full audio, not streaming chunks.
Solution: We use a "pseudo-streaming" approach that:
1. Fetches the full audio from Coqui
2. Chunks it into 20ms frames using StreamSmoother
3. Yields frames with controlled pacing for smooth playback

For true streaming (if your Coqui endpoint supports it):
- Set stream=True in the request
- Use the streaming response directly

Usage:
    from coqui_livekit_tts import CoquiLiveKitTTS

    tts = CoquiLiveKitTTS(
        api_url="https://your-coqui-endpoint.modal.run",
        voice_id="my_cloned_voice",
    )

    # In LiveKit agent
    session = AgentSession(tts=tts, ...)
"""

import os
import asyncio
import logging
import base64
from typing import Optional, AsyncIterator, Union
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CoquiConfig:
    """Configuration for Coqui TTS client."""

    # API endpoint (Modal deployment)
    api_url: str = field(
        default_factory=lambda: os.getenv(
            "COQUI_TTS_URL",
            "https://jenkintownelectricity--premier-coqui-tts-synthesize-web.modal.run"
        )
    )

    # Audio settings - Coqui XTTS outputs 24000 Hz
    sample_rate: int = 24000
    channels: int = 1

    # Request settings
    timeout: float = 30.0
    stream_timeout: float = 60.0


class CoquiLiveKitTTS:
    """
    LiveKit-compatible TTS wrapper for Coqui XTTS.

    This class implements a streaming interface for LiveKit by:
    1. Fetching audio from Coqui endpoint
    2. Converting to 20ms frames using StreamSmoother
    3. Yielding frames at controlled rate for smooth playback

    Works with both batch and streaming Coqui endpoints.
    """

    def __init__(
        self,
        config: Optional[CoquiConfig] = None,
        voice_id: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        self.config = config or CoquiConfig()
        if api_url:
            self.config.api_url = api_url
        self.voice_id = voice_id or "default"
        self._http_client: Optional[httpx.AsyncClient] = None

        logger.info(f"Coqui LiveKit TTS initialized: {self.config.api_url}, voice={self.voice_id}")

    @property
    def sample_rate(self) -> int:
        return self.config.sample_rate

    @property
    def num_channels(self) -> int:
        return self.config.channels

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout,
                limits=httpx.Limits(max_connections=10),
            )
        return self._http_client

    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to audio bytes (full, non-streaming).

        Args:
            text: Text to synthesize

        Returns:
            Audio bytes (PCM 16-bit, 24000 Hz)
        """
        try:
            client = await self._get_client()
            response = await client.post(
                self.config.api_url,
                data={
                    "text": text,
                    "voice_name": self.voice_id,
                    "language": "en",
                },
                timeout=self.config.timeout,
            )

            if response.status_code == 200:
                # Coqui returns WAV, we need raw PCM
                audio_bytes = response.content
                # Skip WAV header (44 bytes) if present
                if audio_bytes[:4] == b'RIFF':
                    audio_bytes = audio_bytes[44:]
                return audio_bytes
            else:
                logger.error(f"Coqui synthesis failed: {response.status_code}")
                return b''

        except Exception as e:
            logger.error(f"Coqui synthesis error: {e}")
            return b''

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Stream synthesize text to audio chunks.

        This method tries streaming first, then falls back to chunked batch.

        Args:
            text: Text to synthesize

        Yields:
            Audio chunks as bytes (PCM 16-bit)
        """
        # Try streaming endpoint first
        try:
            client = await self._get_client()

            # Try streaming request
            async with client.stream(
                "POST",
                self.config.api_url,
                data={
                    "text": text,
                    "voice_name": self.voice_id,
                    "language": "en",
                    "stream": "true",
                },
                timeout=self.config.stream_timeout,
            ) as response:
                if response.status_code == 200:
                    # Check if response is streaming
                    content_type = response.headers.get("content-type", "")

                    if "chunked" in response.headers.get("transfer-encoding", ""):
                        # True streaming response
                        async for chunk in response.aiter_bytes():
                            if chunk:
                                yield chunk
                        return
                    else:
                        # Batch response - read all and chunk
                        full_audio = await response.aread()
                        async for chunk in self._chunk_audio(full_audio):
                            yield chunk
                        return

        except Exception as e:
            logger.warning(f"Streaming request failed: {e}, trying batch")

        # Fall back to batch synthesis
        audio_bytes = await self.synthesize(text)
        if audio_bytes:
            async for chunk in self._chunk_audio(audio_bytes):
                yield chunk

    async def _chunk_audio(self, audio_bytes: bytes, chunk_ms: int = 100) -> AsyncIterator[bytes]:
        """
        Chunk audio bytes into smaller pieces for pseudo-streaming.

        Args:
            audio_bytes: Full audio bytes
            chunk_ms: Chunk duration in milliseconds

        Yields:
            Audio chunks
        """
        # Skip WAV header if present
        if audio_bytes[:4] == b'RIFF':
            audio_bytes = audio_bytes[44:]

        bytes_per_ms = self.config.sample_rate * self.config.channels * 2 // 1000
        chunk_size = bytes_per_ms * chunk_ms

        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i + chunk_size]
            yield chunk
            # Small delay to simulate streaming pace
            await asyncio.sleep(chunk_ms / 1000 * 0.8)  # Slightly faster than real-time


# =============================================================================
# LIVEKIT TTS ADAPTER (Uses StreamSmoother)
# =============================================================================

class CoquiStreamingAdapter:
    """
    Adapter that uses StreamSmoother for jitter-free LiveKit playback.

    This is the recommended approach for integrating Coqui with LiveKit.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        voice_id: str = "default",
        sample_rate: int = 24000,
        pre_buffer_frames: int = 4,
    ):
        self.api_url = api_url or os.getenv(
            "COQUI_TTS_URL",
            "https://jenkintownelectricity--premier-coqui-tts-synthesize-web.modal.run"
        )
        self.voice_id = voice_id
        self._sample_rate = sample_rate
        self.pre_buffer_frames = pre_buffer_frames

        logger.info(f"Coqui Streaming Adapter: {self.api_url}, voice={voice_id}")

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def num_channels(self) -> int:
        return 1

    async def generate_frames(self, text: str):
        """
        Generate smooth audio frames from Coqui TTS.

        Uses StreamSmoother for jitter-free playback.

        Args:
            text: Text to synthesize

        Yields:
            AudioFrame objects ready for LiveKit
        """
        from backend.stream_smoother import StreamSmoother

        smoother = StreamSmoother(
            sample_rate=self._sample_rate,
            channels=1,
            pre_buffer_count=self.pre_buffer_frames,
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Request audio from Coqui
                async with client.stream(
                    "POST",
                    self.api_url,
                    data={
                        "text": text,
                        "voice_name": self.voice_id,
                        "language": "en",
                        "stream": "true",
                    },
                ) as response:
                    if response.status_code != 200:
                        logger.error(f"Coqui TTS failed: {response.status_code}")
                        return

                    # Process audio through smoother
                    first_chunk = True
                    async for chunk in response.aiter_bytes():
                        # Skip WAV header on first chunk
                        if first_chunk and chunk[:4] == b'RIFF':
                            chunk = chunk[44:]
                            first_chunk = False
                        elif first_chunk:
                            first_chunk = False

                        # Feed to smoother and yield frames
                        async for frame in smoother.add_chunk_and_yield(chunk):
                            yield frame

                    # Flush remaining audio
                    final_frame = smoother.flush()
                    if final_frame:
                        yield final_frame

            except httpx.TimeoutException:
                logger.error("Coqui TTS timed out")
            except Exception as e:
                logger.error(f"Coqui TTS error: {e}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_coqui_tts(
    voice_id: str = "default",
    api_url: Optional[str] = None,
) -> CoquiLiveKitTTS:
    """
    Get a Coqui TTS instance for LiveKit.

    Args:
        voice_id: Voice identifier (use your cloned voice name)
        api_url: Optional custom API URL

    Returns:
        CoquiLiveKitTTS instance
    """
    config = CoquiConfig()
    if api_url:
        config.api_url = api_url
    return CoquiLiveKitTTS(config=config, voice_id=voice_id)
