"""
Fish Speech TTS Client - Open Source Voice Synthesis with Cloning

Fish Speech is a high-quality open-source TTS system that supports:
- Real-time streaming synthesis
- Zero-shot voice cloning from audio samples
- Multiple languages (English, Chinese, Japanese, Korean, etc.)
- High-quality audio output (44100 Hz by default)

This client provides a clean interface for HIVE215 to use Fish Speech
either locally or via Modal deployment.

API Endpoints (Modal deployment):
- POST /tts/stream - Streaming synthesis
- POST /tts/synthesize - Full synthesis
- POST /clone - Voice cloning from audio
- GET /voices - List available voices
- GET /health - Health check

Usage:
    from fish_speech_client import FishSpeechTTS, FishSpeechConfig

    config = FishSpeechConfig(
        api_url="https://your-modal-app.modal.run",
        sample_rate=44100,
    )
    tts = FishSpeechTTS(config)

    # Synthesize text
    audio = await tts.synthesize("Hello world", voice_id="default")

    # Clone a voice
    voice_id = await tts.clone_voice(audio_bytes, "custom_voice")

    # Stream synthesis
    async for chunk in tts.synthesize_stream("Hello world", voice_id):
        process_audio(chunk)
"""

import os
import logging
import asyncio
import base64
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class FishSpeechConfig:
    """Configuration for Fish Speech TTS client."""

    # API endpoint (Modal deployment or local)
    api_url: str = field(
        default_factory=lambda: os.getenv(
            "FISH_SPEECH_URL",
            "https://jenkintownelectricity--fish-speech-tts-app.modal.run"
        )
    )

    # Audio settings
    sample_rate: int = field(
        default_factory=lambda: int(os.getenv("FISH_SPEECH_SAMPLE_RATE", "44100"))
    )
    channels: int = 1  # Mono output
    format: str = "pcm"  # PCM 16-bit

    # Default voice
    default_voice: str = "default"

    # Request settings
    timeout: float = 30.0
    stream_timeout: float = 60.0
    max_retries: int = 3

    # Voice cloning settings
    min_clone_duration_sec: float = 3.0
    max_clone_duration_sec: float = 30.0


@dataclass
class FishSpeechVoice:
    """Information about a Fish Speech voice."""
    id: str
    name: str
    description: Optional[str] = None
    language: str = "en"
    is_cloned: bool = False
    sample_url: Optional[str] = None


@dataclass
class SynthesisResult:
    """Result from text-to-speech synthesis."""
    audio_bytes: bytes
    sample_rate: int
    duration_ms: float
    format: str = "pcm"


class FishSpeechTTS:
    """
    Fish Speech TTS client for HIVE215.

    Supports both full synthesis and streaming synthesis,
    plus voice cloning from audio samples.
    """

    def __init__(self, config: Optional[FishSpeechConfig] = None):
        """
        Initialize the Fish Speech client.

        Args:
            config: FishSpeechConfig instance (uses defaults if not provided)
        """
        self.config = config or FishSpeechConfig()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._available_voices: List[FishSpeechVoice] = []
        self._is_healthy: Optional[bool] = None

        logger.info(f"Fish Speech TTS initialized: {self.config.api_url}")

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

    async def is_healthy(self) -> bool:
        """Check if Fish Speech service is healthy."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.config.api_url}/health",
                timeout=5.0,
            )
            self._is_healthy = response.status_code == 200
            return self._is_healthy
        except Exception as e:
            logger.warning(f"Fish Speech health check failed: {e}")
            self._is_healthy = False
            return False

    # =========================================================================
    # SYNTHESIS
    # =========================================================================

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en",
        speed: float = 1.0,
    ) -> SynthesisResult:
        """
        Synthesize text to audio (full, non-streaming).

        Args:
            text: Text to synthesize
            voice_id: Voice to use (defaults to config.default_voice)
            language: Language code (e.g., "en", "zh", "ja")
            speed: Speech speed multiplier (0.5 to 2.0)

        Returns:
            SynthesisResult with audio bytes and metadata
        """
        voice_id = voice_id or self.config.default_voice

        for attempt in range(self.config.max_retries):
            try:
                client = await self._get_client()
                response = await client.post(
                    f"{self.config.api_url}/tts/synthesize",
                    json={
                        "text": text,
                        "voice_id": voice_id,
                        "language": language,
                        "speed": speed,
                        "sample_rate": self.config.sample_rate,
                        "format": self.config.format,
                    },
                    timeout=self.config.timeout,
                )

                if response.status_code == 200:
                    data = response.json()
                    audio_bytes = base64.b64decode(data["audio"])
                    return SynthesisResult(
                        audio_bytes=audio_bytes,
                        sample_rate=data.get("sample_rate", self.config.sample_rate),
                        duration_ms=data.get("duration_ms", 0),
                        format=data.get("format", "pcm"),
                    )
                else:
                    logger.warning(f"Synthesis failed: {response.status_code} - {response.text}")

            except httpx.TimeoutException:
                logger.warning(f"Synthesis timeout (attempt {attempt + 1}/{self.config.max_retries})")
            except Exception as e:
                logger.error(f"Synthesis error: {e}")

        raise FishSpeechError("Synthesis failed after all retries")

    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en",
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesize text to audio chunks.

        Args:
            text: Text to synthesize
            voice_id: Voice to use
            language: Language code
            speed: Speech speed multiplier

        Yields:
            Audio chunks as bytes (PCM 16-bit)
        """
        voice_id = voice_id or self.config.default_voice

        try:
            client = await self._get_client()
            async with client.stream(
                "POST",
                f"{self.config.api_url}/tts/stream",
                json={
                    "text": text,
                    "voice_id": voice_id,
                    "language": language,
                    "speed": speed,
                    "sample_rate": self.config.sample_rate,
                    "format": self.config.format,
                    "stream": True,
                },
                timeout=self.config.stream_timeout,
            ) as response:
                if response.status_code != 200:
                    logger.error(f"Stream synthesis failed: {response.status_code}")
                    return

                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

        except httpx.TimeoutException:
            logger.error("Stream synthesis timed out")
        except Exception as e:
            logger.error(f"Stream synthesis error: {e}")

    # =========================================================================
    # VOICE CLONING
    # =========================================================================

    async def clone_voice(
        self,
        audio_bytes: bytes,
        voice_name: str,
        description: Optional[str] = None,
        language: str = "en",
    ) -> str:
        """
        Clone a voice from an audio sample.

        The audio should be:
        - 3-30 seconds of clear speech
        - Single speaker
        - Minimal background noise
        - WAV or MP3 format

        Args:
            audio_bytes: Raw audio file bytes
            voice_name: Name for the cloned voice
            description: Optional description
            language: Primary language of the voice

        Returns:
            Voice ID for the cloned voice
        """
        try:
            client = await self._get_client()

            # Encode audio as base64
            audio_b64 = base64.b64encode(audio_bytes).decode()

            response = await client.post(
                f"{self.config.api_url}/clone",
                json={
                    "audio": audio_b64,
                    "voice_name": voice_name,
                    "description": description or f"Cloned voice: {voice_name}",
                    "language": language,
                },
                timeout=60.0,  # Cloning takes longer
            )

            if response.status_code == 200:
                data = response.json()
                voice_id = data.get("voice_id")
                logger.info(f"Voice cloned successfully: {voice_name} -> {voice_id}")
                return voice_id
            else:
                error_msg = response.json().get("error", response.text)
                raise FishSpeechError(f"Voice cloning failed: {error_msg}")

        except httpx.TimeoutException:
            raise FishSpeechError("Voice cloning timed out")
        except FishSpeechError:
            raise
        except Exception as e:
            raise FishSpeechError(f"Voice cloning error: {e}")

    async def delete_voice(self, voice_id: str) -> bool:
        """
        Delete a cloned voice.

        Args:
            voice_id: ID of the voice to delete

        Returns:
            True if deleted successfully
        """
        try:
            client = await self._get_client()
            response = await client.delete(
                f"{self.config.api_url}/voices/{voice_id}",
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete voice: {e}")
            return False

    # =========================================================================
    # VOICE MANAGEMENT
    # =========================================================================

    async def list_voices(self, include_cloned: bool = True) -> List[FishSpeechVoice]:
        """
        List all available voices.

        Args:
            include_cloned: Include user-cloned voices

        Returns:
            List of FishSpeechVoice objects
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.config.api_url}/voices",
                params={"include_cloned": include_cloned},
            )

            if response.status_code == 200:
                data = response.json()
                self._available_voices = [
                    FishSpeechVoice(
                        id=v["id"],
                        name=v["name"],
                        description=v.get("description"),
                        language=v.get("language", "en"),
                        is_cloned=v.get("is_cloned", False),
                        sample_url=v.get("sample_url"),
                    )
                    for v in data.get("voices", [])
                ]
                return self._available_voices
            else:
                logger.warning(f"Failed to list voices: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []

    async def get_voice(self, voice_id: str) -> Optional[FishSpeechVoice]:
        """Get a specific voice by ID."""
        voices = await self.list_voices()
        for voice in voices:
            if voice.id == voice_id:
                return voice
        return None


class FishSpeechError(Exception):
    """Fish Speech TTS error."""
    pass


# =============================================================================
# LIVEKIT INTEGRATION
# =============================================================================

@dataclass
class TTSCapabilities:
    """TTS capabilities for LiveKit compatibility."""
    streaming: bool = True


class FishSpeechLiveKitTTS:
    """
    LiveKit-compatible TTS wrapper for Fish Speech.

    This class provides an interface compatible with LiveKit's TTS plugins,
    allowing Fish Speech to be used as a drop-in replacement.
    """

    def __init__(
        self,
        config: Optional[FishSpeechConfig] = None,
        voice_id: Optional[str] = None,
    ):
        self.config = config or FishSpeechConfig()
        self.voice_id = voice_id or self.config.default_voice
        self._client = FishSpeechTTS(self.config)
        # LiveKit requires capabilities attribute
        self.capabilities = TTSCapabilities(streaming=True)

    @property
    def sample_rate(self) -> int:
        return self.config.sample_rate

    @property
    def num_channels(self) -> int:
        return self.config.channels

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes."""
        result = await self._client.synthesize(text, voice_id=self.voice_id)
        return result.audio_bytes

    async def stream(self, text: str = None, *, conn_options=None, **kwargs) -> AsyncIterator[bytes]:
        """Stream synthesize text to audio chunks.

        Args:
            text: Text to synthesize (can also be passed via kwargs)
            conn_options: LiveKit connection options (ignored, for compatibility)
            **kwargs: Additional arguments for LiveKit compatibility
        """
        # Handle text being passed different ways
        if text is None:
            text = kwargs.get('text', '')
        async for chunk in self._client.synthesize_stream(text, voice_id=self.voice_id):
            yield chunk

    async def close(self):
        """Close the TTS client."""
        await self._client.close()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_default_client: Optional[FishSpeechTTS] = None


def get_fish_speech_client(config: Optional[FishSpeechConfig] = None) -> FishSpeechTTS:
    """Get or create a singleton Fish Speech client."""
    global _default_client
    if _default_client is None:
        _default_client = FishSpeechTTS(config)
    return _default_client


async def quick_synthesize(
    text: str,
    voice_id: str = "default",
    api_url: Optional[str] = None,
) -> bytes:
    """
    Quick one-off synthesis without managing a client.

    Args:
        text: Text to synthesize
        voice_id: Voice to use
        api_url: Optional custom API URL

    Returns:
        Audio bytes (PCM 16-bit)
    """
    config = FishSpeechConfig()
    if api_url:
        config.api_url = api_url

    client = FishSpeechTTS(config)
    try:
        result = await client.synthesize(text, voice_id=voice_id)
        return result.audio_bytes
    finally:
        await client.close()


# =============================================================================
# TESTING
# =============================================================================

async def test_client():
    """Test the Fish Speech client."""
    import os

    url = os.environ.get("FISH_SPEECH_URL")
    if not url:
        print("FISH_SPEECH_URL not set, skipping test")
        return

    print(f"Testing Fish Speech at: {url}")

    config = FishSpeechConfig(api_url=url)
    client = FishSpeechTTS(config)

    # Health check
    print("\n1. Health check...")
    healthy = await client.is_healthy()
    print(f"   Healthy: {healthy}")

    if not healthy:
        print("   Fish Speech not available")
        return

    # List voices
    print("\n2. List voices...")
    voices = await client.list_voices()
    print(f"   Found {len(voices)} voices")
    for voice in voices[:5]:
        print(f"   - {voice.name} ({voice.id})")

    # Synthesize
    print("\n3. Synthesize text...")
    result = await client.synthesize("Hello, I am Fish Speech.", voice_id="default")
    print(f"   Audio: {len(result.audio_bytes)} bytes, {result.duration_ms:.0f}ms")

    # Stream synthesize
    print("\n4. Stream synthesize...")
    chunks = []
    async for chunk in client.synthesize_stream("This is a streaming test."):
        chunks.append(chunk)
    total_bytes = sum(len(c) for c in chunks)
    print(f"   Received {len(chunks)} chunks, {total_bytes} bytes total")

    await client.close()
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_client())
