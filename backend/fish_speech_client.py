"""
Fish Speech TTS Client - Cloud API + OpenVoice Fallback

This client uses the Fish Audio Cloud API (https://fish.audio) for TTS synthesis.
Falls back to self-hosted OpenVoice (MIT licensed) on Modal if no API key is configured.

Features:
- Real-time streaming synthesis via Fish Audio Cloud
- Zero-shot voice cloning from audio samples
- Multiple languages (English, Chinese, Japanese, Korean, etc.)
- MIT licensed fallback (OpenVoice + MeloTTS) for commercial use

Configuration:
    FISH_AUDIO_API_KEY - API key from https://fish.audio (optional, for Cloud API)
    FISH_SPEECH_URL - Modal endpoint URL (default: OpenVoice Modal deployment)
    FISH_SPEECH_SAMPLE_RATE - Output sample rate (default: 24000)

Priority:
    1. Fish Audio Cloud API (if FISH_AUDIO_API_KEY is set) - Paid service
    2. OpenVoice Modal (fallback) - MIT licensed, free self-hosted

Usage:
    from fish_speech_client import FishSpeechTTS, FishSpeechConfig

    config = FishSpeechConfig()
    tts = FishSpeechTTS(config)

    # Synthesize text
    audio = await tts.synthesize("Hello world", voice_id="default")

    # Stream synthesis
    async for chunk in tts.synthesize_stream("Hello world", voice_id):
        process_audio(chunk)
"""

import os
import io
import logging
import asyncio
import base64
import struct
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# Check if fish-audio-sdk is available
FISH_AUDIO_SDK_AVAILABLE = False
try:
    from fish_audio_sdk import Session
    from fish_audio_sdk.schemas import TTSRequest
    FISH_AUDIO_SDK_AVAILABLE = True
    logger.info("Fish Audio SDK available")
except ImportError:
    logger.warning("fish-audio-sdk not installed, using HTTP API fallback")


@dataclass
class FishSpeechConfig:
    """Configuration for Fish Speech TTS client."""

    # Fish Audio Cloud API key (from https://fish.audio)
    api_key: str = field(
        default_factory=lambda: os.getenv("FISH_AUDIO_API_KEY", "")
    )

    # Fish Audio Cloud API base URL
    api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "FISH_AUDIO_API_URL",
            "https://api.fish.audio"
        )
    )

    # Fallback Modal endpoint (OpenVoice - MIT licensed)
    modal_url: str = field(
        default_factory=lambda: os.getenv(
            "FISH_SPEECH_URL",
            "https://jenkintownelectricity--openvoice-tts-fastapi-app.modal.run"
        )
    )

    # Audio settings (24000 Hz for OpenVoice compatibility)
    sample_rate: int = field(
        default_factory=lambda: int(os.getenv("FISH_SPEECH_SAMPLE_RATE", "24000"))
    )
    channels: int = 1  # Mono output
    format: str = "pcm"  # PCM 16-bit

    # Default voice ID (Fish Audio model ID)
    # "default" will use the default Fish Audio voice
    default_voice: str = field(
        default_factory=lambda: os.getenv(
            "FISH_AUDIO_DEFAULT_VOICE",
            "bf322df2096a46f18c579d0baa36f41d"  # Adrian voice
        )
    )

    # Request settings
    timeout: float = 30.0
    stream_timeout: float = 60.0
    max_retries: int = 3

    # Voice cloning settings
    min_clone_duration_sec: float = 3.0
    max_clone_duration_sec: float = 30.0

    @property
    def has_api_key(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)


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

    Priority:
    1. Fish Audio Cloud API (if FISH_AUDIO_API_KEY is set)
    2. Self-hosted Modal endpoint (fallback)
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

        if self.config.has_api_key:
            self._use_cloud = True
            self._api_base = self.config.api_base_url
            logger.info(f"Fish Audio Cloud API initialized (key: {self.config.api_key[:8]}...)")
        else:
            self._use_cloud = False
            self._api_base = self.config.modal_url
            logger.info(f"Using OpenVoice TTS (MIT licensed) via Modal: {self._api_base}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            headers = {}
            if self._use_cloud and self.config.has_api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout,
                limits=httpx.Limits(max_connections=10),
                headers=headers,
            )
        return self._http_client

    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def is_healthy(self) -> bool:
        """Check if Fish Audio service is healthy."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self._api_base}/health",
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
            voice_id: Voice/model ID to use
            language: Language code (e.g., "en", "zh", "ja")
            speed: Speech speed multiplier (0.5 to 2.0)

        Returns:
            SynthesisResult with audio bytes and metadata
        """
        voice_id = voice_id or self.config.default_voice
        if voice_id in ("default", ""):
            voice_id = self.config.default_voice

        for attempt in range(self.config.max_retries):
            try:
                client = await self._get_client()

                if self._use_cloud:
                    # Fish Audio Cloud API
                    response = await client.post(
                        f"{self._api_base}/v1/tts",
                        json={
                            "text": text,
                            "reference_id": voice_id,
                            "format": "pcm",
                            "normalize": True,
                            "latency": "normal",
                        },
                        timeout=self.config.timeout,
                    )
                else:
                    # Self-hosted Modal endpoint
                    response = await client.post(
                        f"{self._api_base}/v1/tts",
                        json={
                            "text": text,
                            "reference_id": voice_id,
                            "voice_id": voice_id,
                            "format": "pcm",
                            "language": language,
                        },
                        timeout=self.config.timeout,
                    )

                if response.status_code == 200:
                    audio_bytes = response.content
                    duration_ms = (len(audio_bytes) / 2 / self.config.sample_rate) * 1000
                    return SynthesisResult(
                        audio_bytes=audio_bytes,
                        sample_rate=self.config.sample_rate,
                        duration_ms=duration_ms,
                        format="pcm",
                    )
                else:
                    logger.warning(f"Fish Speech synthesis failed: {response.status_code} - {response.text[:200]}")

            except httpx.TimeoutException:
                logger.warning(f"Fish Speech timeout (attempt {attempt + 1}/{self.config.max_retries})")
            except Exception as e:
                logger.error(f"Fish Speech synthesis error: {e}")

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
            voice_id: Voice/model ID to use
            language: Language code
            speed: Speech speed multiplier

        Yields:
            Audio chunks as bytes (PCM 16-bit)
        """
        voice_id = voice_id or self.config.default_voice
        if voice_id in ("default", ""):
            voice_id = self.config.default_voice

        try:
            client = await self._get_client()

            if self._use_cloud:
                endpoint = f"{self._api_base}/v1/tts"
                payload = {
                    "text": text,
                    "reference_id": voice_id,
                    "format": "pcm",
                    "normalize": True,
                    "latency": "balanced",
                }
            else:
                endpoint = f"{self._api_base}/tts/stream"
                payload = {
                    "text": text,
                    "voice_id": voice_id,
                    "language": language,
                    "speed": speed,
                    "sample_rate": self.config.sample_rate,
                }

            async with client.stream(
                "POST",
                endpoint,
                json=payload,
                timeout=self.config.stream_timeout,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"Fish Speech stream failed: {response.status_code} - {error_text[:200]}")
                    return

                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

        except httpx.TimeoutException:
            logger.error("Fish Speech stream timed out")
        except Exception as e:
            logger.error(f"Fish Speech stream error: {e}")

    # =========================================================================
    # VOICE CLONING - Fish Audio Model Creation
    # =========================================================================

    async def clone_voice(
        self,
        audio_bytes: bytes,
        voice_name: str,
        description: Optional[str] = None,
        language: str = "en",
    ) -> str:
        """
        Clone a voice by creating a Fish Audio model from an audio sample.

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
            Model ID for the cloned voice (use as voice_id for TTS)
        """
        if not self.config.has_api_key:
            raise FishSpeechError("FISH_AUDIO_API_KEY not configured")

        try:
            client = await self._get_client()

            # Fish Audio model creation API
            # Uses multipart form data with audio file
            files = {
                "voices": ("voice.wav", audio_bytes, "audio/wav"),
            }
            data = {
                "visibility": "private",
                "type": "tts",
                "title": voice_name,
                "description": description or f"Voice clone: {voice_name}",
                "train_mode": "fast",  # Options: fast, full
            }

            response = await client.post(
                f"{self.config.api_base_url}/model",
                data=data,
                files=files,
                timeout=120.0,  # Model creation takes time
            )

            if response.status_code in (200, 201):
                result = response.json()
                model_id = result.get("_id") or result.get("id")
                logger.info(f"Fish Audio model created: {voice_name} -> {model_id}")
                return model_id
            else:
                error_text = response.text[:500]
                logger.error(f"Fish Audio model creation failed: {response.status_code} - {error_text}")
                raise FishSpeechError(f"Voice cloning failed: {error_text}")

        except httpx.TimeoutException:
            raise FishSpeechError("Voice cloning timed out")
        except FishSpeechError:
            raise
        except Exception as e:
            raise FishSpeechError(f"Voice cloning error: {e}")

    async def delete_voice(self, voice_id: str) -> bool:
        """
        Delete a cloned voice (Fish Audio model).

        Args:
            voice_id: Model ID of the voice to delete

        Returns:
            True if deleted successfully
        """
        if not self.config.has_api_key:
            logger.error("Cannot delete voice - no API key")
            return False

        try:
            client = await self._get_client()
            response = await client.delete(
                f"{self.config.api_base_url}/model/{voice_id}",
            )
            success = response.status_code in (200, 204)
            if success:
                logger.info(f"Deleted Fish Audio model: {voice_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to delete voice: {e}")
            return False

    # =========================================================================
    # VOICE MANAGEMENT
    # =========================================================================

    async def list_voices(self, include_cloned: bool = True) -> List[FishSpeechVoice]:
        """
        List available Fish Audio models (voices).

        Args:
            include_cloned: Include user's private models

        Returns:
            List of FishSpeechVoice objects
        """
        if not self.config.has_api_key:
            logger.warning("Cannot list voices - no API key")
            return []

        try:
            client = await self._get_client()

            # Fish Audio models endpoint
            params = {
                "page_size": 50,
                "self": "true" if include_cloned else "false",
            }
            response = await client.get(
                f"{self.config.api_base_url}/model",
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", data) if isinstance(data, dict) else data
                self._available_voices = [
                    FishSpeechVoice(
                        id=v.get("_id") or v.get("id"),
                        name=v.get("title") or v.get("name", "Unknown"),
                        description=v.get("description"),
                        language=v.get("languages", ["en"])[0] if v.get("languages") else "en",
                        is_cloned=v.get("visibility") == "private",
                        sample_url=v.get("cover_image"),
                    )
                    for v in items if isinstance(v, dict)
                ]
                return self._available_voices
            else:
                logger.warning(f"Failed to list voices: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []

    async def get_voice(self, voice_id: str) -> Optional[FishSpeechVoice]:
        """Get a specific voice/model by ID."""
        if not self.config.has_api_key:
            return None

        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.config.api_base_url}/model/{voice_id}",
            )
            if response.status_code == 200:
                v = response.json()
                return FishSpeechVoice(
                    id=v.get("_id") or v.get("id"),
                    name=v.get("title") or v.get("name", "Unknown"),
                    description=v.get("description"),
                    language=v.get("languages", ["en"])[0] if v.get("languages") else "en",
                    is_cloned=v.get("visibility") == "private",
                    sample_url=v.get("cover_image"),
                )
        except Exception as e:
            logger.error(f"Failed to get voice: {e}")
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


class TTSStreamWrapper:
    """Wrapper to make async generator compatible with async context manager protocol."""

    def __init__(self, generator):
        self._generator = generator
        self._iterator = None

    async def __aenter__(self):
        self._iterator = self._generator.__aiter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cleanup if needed
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self._iterator.__anext__()
        except StopAsyncIteration:
            raise


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

    def stream(self, text: str = None, *, conn_options=None, **kwargs) -> TTSStreamWrapper:
        """Stream synthesize text to audio chunks.

        Returns an async context manager that yields audio chunks.

        Args:
            text: Text to synthesize (can also be passed via kwargs)
            conn_options: LiveKit connection options (ignored, for compatibility)
            **kwargs: Additional arguments for LiveKit compatibility
        """
        # Handle text being passed different ways
        if text is None:
            text = kwargs.get('text', '')

        async def _generate():
            async for chunk in self._client.synthesize_stream(text, voice_id=self.voice_id):
                yield chunk

        return TTSStreamWrapper(_generate())

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
