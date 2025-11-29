"""
Cartesia Sonic-3 Client for Premier Voice Assistant.

Ultra-low latency streaming TTS with voice cloning and 42 language support.

Performance targets:
- Time to First Byte (TTFB): ~30ms
- Supports 42 languages covering 95% of world population
- Real-time voice cloning from 3-10 seconds of audio
- Cross-lingual voice cloning (Cartesia Localize)

Architecture:
┌─────────────────────────────────────────────────────────────┐
│  CartesiaSonic3                                              │
│  ├── WebSocket Streaming TTS (~30ms TTFB)                   │
│  ├── Voice Cloning (3-10 seconds audio)                     │
│  ├── Cross-lingual Localization (40+ languages)             │
│  └── Emotion & Speed Controls                               │
└─────────────────────────────────────────────────────────────┘
"""

import os
import asyncio
import logging
import time
import json
import base64
import uuid
from typing import Optional, Callable, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


# ============================================================================
# SUPPORTED LANGUAGES (42 TOTAL)
# ============================================================================

class CartesiaLanguage(Enum):
    """Supported languages in Cartesia Sonic-3 (42 languages)."""
    # Americas
    ENGLISH = "en"
    SPANISH = "es"
    PORTUGUESE = "pt"

    # Europe
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    DUTCH = "nl"
    POLISH = "pl"
    RUSSIAN = "ru"
    SWEDISH = "sv"
    TURKISH = "tr"
    GREEK = "el"
    CZECH = "cs"
    ROMANIAN = "ro"
    HUNGARIAN = "hu"
    FINNISH = "fi"
    DANISH = "da"
    NORWEGIAN = "no"
    UKRAINIAN = "uk"
    BULGARIAN = "bg"
    CROATIAN = "hr"
    SLOVAK = "sk"

    # Middle East
    ARABIC = "ar"
    HEBREW = "he"

    # South Asia (9 Indian languages!)
    HINDI = "hi"
    BENGALI = "bn"
    TAMIL = "ta"
    TELUGU = "te"
    MARATHI = "mr"
    GUJARATI = "gu"
    KANNADA = "kn"
    MALAYALAM = "ml"
    PUNJABI = "pa"

    # East Asia
    MANDARIN = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    CANTONESE = "yue"

    # Southeast Asia
    VIETNAMESE = "vi"
    THAI = "th"
    INDONESIAN = "id"
    MALAY = "ms"
    FILIPINO = "fil"


# Language to display name mapping
LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "pl": "Polish",
    "ru": "Russian", "sv": "Swedish", "tr": "Turkish", "zh": "Mandarin Chinese",
    "ja": "Japanese", "ko": "Korean", "hi": "Hindi", "bn": "Bengali",
    "ta": "Tamil", "te": "Telugu", "mr": "Marathi", "gu": "Gujarati",
    "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi", "ar": "Arabic",
    "he": "Hebrew", "vi": "Vietnamese", "th": "Thai", "id": "Indonesian",
    "ms": "Malay", "fil": "Filipino", "el": "Greek", "cs": "Czech",
    "ro": "Romanian", "hu": "Hungarian", "fi": "Finnish", "da": "Danish",
    "no": "Norwegian", "uk": "Ukrainian", "bg": "Bulgarian", "hr": "Croatian",
    "sk": "Slovak", "yue": "Cantonese",
}


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class CartesiaConfig:
    """Configuration for Cartesia client."""
    api_key: str = field(default_factory=lambda: os.getenv("CARTESIA_API_KEY", ""))

    # Model
    model_id: str = "sonic-2024-10-01"  # Sonic-3 latest
    model_multilingual: str = "sonic-multilingual"  # For non-English

    # Voice settings
    default_voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091"  # Default voice
    language: str = "en"

    # Output format
    output_format: str = "pcm_s16le"  # 16-bit PCM for low latency
    sample_rate: int = 16000  # 16kHz for voice

    # Streaming settings
    container: str = "raw"  # raw for WebSocket streaming

    # Performance
    speed: float = 1.0  # Speech speed (0.5 - 2.0)

    # Emotion controls
    emotion: Optional[str] = None  # e.g., "happy", "sad", "angry"
    emotion_intensity: float = 1.0  # 0.0 - 2.0

    # WebSocket URL
    ws_url: str = "wss://api.cartesia.ai/tts/websocket"
    api_url: str = "https://api.cartesia.ai"


# ============================================================================
# CARTESIA SONIC-3 STREAMING TTS
# ============================================================================

class CartesiaSonic3:
    """
    Streaming Text-to-Speech using Cartesia Sonic-3.

    Features:
    - ~30ms time-to-first-byte
    - 42 language support
    - Real-time voice cloning
    - Cross-lingual voice localization
    - Emotion and speed controls
    - Word-level timestamps

    Usage:
        cartesia = CartesiaSonic3()
        await cartesia.connect()

        # Simple synthesis
        async for audio_chunk in cartesia.synthesize_stream("Hello world"):
            play_audio(audio_chunk)

        # With voice cloning
        voice_id = await cartesia.clone_voice(audio_bytes, "My Voice")
        async for chunk in cartesia.synthesize_stream("Hello", voice_id=voice_id):
            play_audio(chunk)
    """

    def __init__(self, config: Optional[CartesiaConfig] = None):
        self.config = config or CartesiaConfig()
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._connected = False

        # Callbacks
        self.on_audio: Optional[Callable[[bytes], Any]] = None
        self.on_word_timestamp: Optional[Callable[[str, float, float], Any]] = None
        self.on_done: Optional[Callable[[], Any]] = None
        self.on_error: Optional[Callable[[str], Any]] = None

        # Metrics
        self._last_ttfb: Optional[int] = None
        self._last_total_time: Optional[int] = None

        # Pending requests
        self._pending_contexts: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> bool:
        """Establish WebSocket connection to Cartesia."""
        if not self.config.api_key:
            logger.error("Cartesia API key not configured")
            return False

        try:
            url = (
                f"{self.config.ws_url}"
                f"?api_key={self.config.api_key}"
                f"&cartesia_version=2024-06-10"
            )

            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(
                url,
                heartbeat=30.0,
                timeout=aiohttp.ClientWSTimeout(ws_receive=60.0),
            )
            self._connected = True

            logger.info("Connected to Cartesia Sonic-3 WebSocket")

            # Start receive loop
            asyncio.create_task(self._receive_loop())

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Cartesia: {e}")
            return False

    async def _receive_loop(self):
        """Receive and process messages from Cartesia."""
        if not self.ws:
            return

        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_message(data)

                elif msg.type == aiohttp.WSMsgType.BINARY:
                    # Direct binary audio (less common)
                    if self.on_audio:
                        await self._safe_callback(self.on_audio, msg.data)

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"Cartesia WebSocket error: {msg.data}")
                    if self.on_error:
                        await self._safe_callback(self.on_error, str(msg.data))
                    break

                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("Cartesia WebSocket closed")
                    break

        except Exception as e:
            logger.error(f"Error in Cartesia receive loop: {e}")
        finally:
            self._connected = False

    async def _handle_message(self, data: dict):
        """Handle a message from Cartesia."""
        msg_type = data.get("type", "")
        context_id = data.get("context_id", "")

        # Track timing
        if context_id in self._pending_contexts:
            ctx = self._pending_contexts[context_id]
            if ctx.get("first_chunk_time") is None:
                ctx["first_chunk_time"] = time.time()
                ttfb = int((ctx["first_chunk_time"] - ctx["start_time"]) * 1000)
                self._last_ttfb = ttfb
                logger.info(f"Cartesia TTFB: {ttfb}ms")

        if msg_type == "chunk":
            # Audio chunk
            audio_b64 = data.get("data", "")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                if self.on_audio:
                    await self._safe_callback(self.on_audio, audio_bytes)

                # Also notify via context callback if set
                if context_id in self._pending_contexts:
                    ctx = self._pending_contexts[context_id]
                    if ctx.get("on_audio"):
                        await self._safe_callback(ctx["on_audio"], audio_bytes)

        elif msg_type == "timestamps":
            # Word-level timestamps
            words = data.get("word_timestamps", {})
            if self.on_word_timestamp and words:
                for word_data in words.get("words", []):
                    await self._safe_callback(
                        self.on_word_timestamp,
                        word_data.get("word", ""),
                        word_data.get("start", 0),
                        word_data.get("end", 0),
                    )

        elif msg_type == "done":
            # Synthesis complete
            if context_id in self._pending_contexts:
                ctx = self._pending_contexts[context_id]
                total_time = int((time.time() - ctx["start_time"]) * 1000)
                self._last_total_time = total_time
                logger.debug(f"Cartesia synthesis complete: {total_time}ms")

                if ctx.get("on_done"):
                    await self._safe_callback(ctx["on_done"])

                del self._pending_contexts[context_id]

            if self.on_done:
                await self._safe_callback(self.on_done)

        elif msg_type == "error":
            error_msg = data.get("message", "Unknown error")
            logger.error(f"Cartesia error: {error_msg}")
            if self.on_error:
                await self._safe_callback(self.on_error, error_msg)

    async def _safe_callback(self, callback, *args):
        """Safely execute a callback."""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Callback error: {e}")

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
        on_audio: Optional[Callable[[bytes], Any]] = None,
        on_done: Optional[Callable[[], Any]] = None,
    ) -> str:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_id: Voice ID (default voice if not specified)
            language: Language code (e.g., "en", "es", "hi")
            speed: Speech speed (0.5 - 2.0)
            emotion: Emotion style
            on_audio: Callback for audio chunks
            on_done: Callback when complete

        Returns:
            Context ID for tracking
        """
        if not self.ws or not self._connected:
            logger.error("Cartesia not connected")
            return ""

        context_id = str(uuid.uuid4())
        lang = language or self.config.language

        # Select model based on language
        model_id = (
            self.config.model_id if lang == "en"
            else self.config.model_multilingual
        )

        # Build request
        request = {
            "model_id": model_id,
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": voice_id or self.config.default_voice_id,
            },
            "language": lang,
            "output_format": {
                "container": self.config.container,
                "encoding": self.config.output_format,
                "sample_rate": self.config.sample_rate,
            },
            "context_id": context_id,
        }

        # Add optional parameters
        if speed is not None:
            request["speed"] = speed
        elif self.config.speed != 1.0:
            request["speed"] = self.config.speed

        if emotion:
            request["emotion"] = {
                "name": emotion,
                "intensity": self.config.emotion_intensity,
            }

        # Track context
        self._pending_contexts[context_id] = {
            "start_time": time.time(),
            "first_chunk_time": None,
            "on_audio": on_audio,
            "on_done": on_done,
        }

        await self.ws.send_json(request)
        logger.debug(f"Sent TTS request: {text[:50]}... (lang={lang})")

        return context_id

    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text and yield audio chunks as async generator.

        Usage:
            async for chunk in cartesia.synthesize_stream("Hello"):
                play_audio(chunk)
        """
        audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        done_event = asyncio.Event()

        async def on_audio(audio_bytes: bytes):
            await audio_queue.put(audio_bytes)

        async def on_done():
            await audio_queue.put(None)  # Sentinel
            done_event.set()

        await self.synthesize(
            text=text,
            voice_id=voice_id,
            language=language,
            on_audio=on_audio,
            on_done=on_done,
            **kwargs
        )

        # Yield audio chunks
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            yield chunk

    async def cancel(self, context_id: Optional[str] = None):
        """Cancel synthesis for a context."""
        if self.ws and self._connected:
            if context_id:
                await self.ws.send_json({
                    "type": "cancel",
                    "context_id": context_id,
                })
            # Remove from pending
            if context_id in self._pending_contexts:
                del self._pending_contexts[context_id]
            logger.debug(f"Cancelled Cartesia synthesis: {context_id}")

    async def close(self):
        """Close the Cartesia connection."""
        self._connected = False
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        self._pending_contexts.clear()
        logger.info("Cartesia connection closed")

    def get_metrics(self) -> Dict[str, Any]:
        """Get last request metrics."""
        return {
            "ttfb_ms": self._last_ttfb,
            "total_ms": self._last_total_time,
        }

    # =========================================================================
    # VOICE CLONING API
    # =========================================================================

    async def clone_voice(
        self,
        audio_data: bytes,
        name: str,
        description: str = "",
        language: str = "en",
    ) -> Optional[str]:
        """
        Clone a voice from audio data.

        Args:
            audio_data: Audio bytes (WAV, MP3, etc.) - 3-30 seconds recommended
            name: Name for the cloned voice
            description: Optional description
            language: Primary language of the voice

        Returns:
            Voice ID if successful, None otherwise
        """
        if not self.config.api_key:
            logger.error("Cartesia API key not configured")
            return None

        try:
            url = f"{self.config.api_url}/voices/clone/clip"

            headers = {
                "X-API-Key": self.config.api_key,
                "Cartesia-Version": "2024-06-10",
            }

            # Prepare multipart form data
            data = aiohttp.FormData()
            data.add_field(
                "clip",
                audio_data,
                filename="voice_sample.wav",
                content_type="audio/wav"
            )
            data.add_field("name", name)
            if description:
                data.add_field("description", description)
            data.add_field("language", language)

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        voice_id = result.get("id")
                        logger.info(f"Voice cloned successfully: {voice_id}")
                        return voice_id
                    else:
                        error = await resp.text()
                        logger.error(f"Voice cloning failed: {resp.status} - {error}")
                        return None

        except Exception as e:
            logger.error(f"Voice cloning error: {e}")
            return None

    async def localize_voice(
        self,
        voice_id: str,
        target_language: str,
        name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a localized version of a voice for another language.

        This uses Cartesia's cross-lingual voice cloning to make the
        same voice sound natural in a different language.

        Args:
            voice_id: Source voice ID
            target_language: Target language code (e.g., "es", "fr", "hi")
            name: Optional name for the localized voice

        Returns:
            New voice ID for the localized voice
        """
        if not self.config.api_key:
            logger.error("Cartesia API key not configured")
            return None

        try:
            url = f"{self.config.api_url}/voices/{voice_id}/localize"

            headers = {
                "X-API-Key": self.config.api_key,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json",
            }

            payload = {
                "language": target_language,
            }
            if name:
                payload["name"] = name

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        new_voice_id = result.get("id")
                        logger.info(
                            f"Voice localized: {voice_id} -> {new_voice_id} "
                            f"({target_language})"
                        )
                        return new_voice_id
                    else:
                        error = await resp.text()
                        logger.error(
                            f"Voice localization failed: {resp.status} - {error}"
                        )
                        return None

        except Exception as e:
            logger.error(f"Voice localization error: {e}")
            return None

    async def list_voices(
        self,
        language: Optional[str] = None,
        is_public: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        List available voices.

        Args:
            language: Filter by language code
            is_public: Include public voices

        Returns:
            List of voice objects
        """
        if not self.config.api_key:
            return []

        try:
            url = f"{self.config.api_url}/voices"

            headers = {
                "X-API-Key": self.config.api_key,
                "Cartesia-Version": "2024-06-10",
            }

            params = {}
            if language:
                params["language"] = language

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("voices", [])
                    else:
                        logger.error(f"Failed to list voices: {resp.status}")
                        return []

        except Exception as e:
            logger.error(f"Error listing voices: {e}")
            return []

    async def get_voice(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific voice."""
        if not self.config.api_key:
            return None

        try:
            url = f"{self.config.api_url}/voices/{voice_id}"

            headers = {
                "X-API-Key": self.config.api_key,
                "Cartesia-Version": "2024-06-10",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Failed to get voice: {resp.status}")
                        return None

        except Exception as e:
            logger.error(f"Error getting voice: {e}")
            return None

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice."""
        if not self.config.api_key:
            return False

        try:
            url = f"{self.config.api_url}/voices/{voice_id}"

            headers = {
                "X-API-Key": self.config.api_key,
                "Cartesia-Version": "2024-06-10",
            }

            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as resp:
                    if resp.status in (200, 204):
                        logger.info(f"Voice deleted: {voice_id}")
                        return True
                    else:
                        logger.error(f"Failed to delete voice: {resp.status}")
                        return False

        except Exception as e:
            logger.error(f"Error deleting voice: {e}")
            return False


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_cartesia_client: Optional[CartesiaSonic3] = None


async def get_cartesia_client() -> CartesiaSonic3:
    """Get or create the global Cartesia client."""
    global _cartesia_client
    if _cartesia_client is None or not _cartesia_client._connected:
        _cartesia_client = CartesiaSonic3()
        await _cartesia_client.connect()
    return _cartesia_client


def get_supported_languages() -> List[Dict[str, str]]:
    """Get list of supported languages with codes and names."""
    return [
        {"code": lang.value, "name": LANGUAGE_NAMES.get(lang.value, lang.value)}
        for lang in CartesiaLanguage
    ]


async def quick_tts(
    text: str,
    language: str = "en",
    voice_id: Optional[str] = None,
) -> bytes:
    """
    Quick utility for text-to-speech.

    Returns all audio bytes concatenated.
    """
    client = await get_cartesia_client()

    audio_chunks = []
    async for chunk in client.synthesize_stream(text, voice_id=voice_id, language=language):
        audio_chunks.append(chunk)

    return b"".join(audio_chunks)


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("\n" + "=" * 60)
        print("CARTESIA SONIC-3 TEST")
        print("=" * 60 + "\n")

        config = CartesiaConfig()
        print(f"Cartesia API Key configured: {bool(config.api_key)}")

        if not config.api_key:
            print("\n[!] CARTESIA_API_KEY not set.")
            print("    Get an API key at: https://play.cartesia.ai/")
            return

        print(f"\nSupported languages: {len(CartesiaLanguage)} total")
        print("Sample: English, Spanish, Hindi, Mandarin, Japanese, Arabic...")

        # Test connection
        print("\n--- Testing WebSocket Connection ---")
        client = CartesiaSonic3(config)

        if await client.connect():
            print("[OK] Connected to Cartesia")

            # Test synthesis
            print("\n--- Testing TTS ---")
            text = "Hello! This is a test of Cartesia Sonic-3 streaming text to speech."

            audio_chunks = []
            start_time = time.time()

            async for chunk in client.synthesize_stream(text):
                audio_chunks.append(chunk)
                if len(audio_chunks) == 1:
                    ttfb = int((time.time() - start_time) * 1000)
                    print(f"[OK] TTFB: {ttfb}ms")

            total_time = int((time.time() - start_time) * 1000)
            total_audio = sum(len(c) for c in audio_chunks)

            print(f"[OK] Total: {total_time}ms, {len(audio_chunks)} chunks, {total_audio} bytes")
            print(f"[OK] Metrics: {client.get_metrics()}")

            # Test multilingual
            print("\n--- Testing Multilingual ---")
            for lang, text in [
                ("es", "Hola, esto es una prueba en español."),
                ("fr", "Bonjour, ceci est un test en français."),
                ("hi", "नमस्ते, यह हिंदी में एक परीक्षण है।"),
            ]:
                start = time.time()
                chunks = []
                async for chunk in client.synthesize_stream(text, language=lang):
                    chunks.append(chunk)
                elapsed = int((time.time() - start) * 1000)
                print(f"[OK] {lang}: {elapsed}ms, {len(chunks)} chunks")

            await client.close()
            print("\n[OK] All tests passed!")

        else:
            print("[FAIL] Could not connect to Cartesia")

        print("\n" + "=" * 60 + "\n")

    asyncio.run(test())
