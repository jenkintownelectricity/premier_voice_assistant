"""
Deepgram Nova-3 Client for Premier Voice Assistant.

Ultra-low latency streaming STT with multi-language and code-switching support.

Performance targets:
- Chunk latency: ~30ms
- Supports 36+ languages
- Code-switching (auto language detection within utterance)
- Voice Activity Detection (VAD)

Architecture:
┌─────────────────────────────────────────────────────────────┐
│  DeepgramNova3                                               │
│  ├── WebSocket Streaming STT (~30ms chunks)                 │
│  ├── Multi-language (36+ languages)                         │
│  ├── Code-switching (language=multi)                        │
│  ├── Voice Activity Detection (VAD)                         │
│  ├── Smart Endpointing (utterance detection)                │
│  └── Interim Results (for fast processing)                  │
└─────────────────────────────────────────────────────────────┘
"""

import os
import asyncio
import logging
import time
import json
from typing import Optional, Callable, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


# ============================================================================
# SUPPORTED LANGUAGES (36+)
# ============================================================================

class DeepgramLanguage(Enum):
    """Supported languages in Deepgram Nova-3."""
    # Auto-detect (code-switching)
    MULTI = "multi"  # Auto-detect up to 10 languages

    # Americas
    ENGLISH = "en"
    ENGLISH_US = "en-US"
    ENGLISH_UK = "en-GB"
    ENGLISH_AU = "en-AU"
    ENGLISH_IN = "en-IN"
    SPANISH = "es"
    SPANISH_LATAM = "es-419"
    PORTUGUESE = "pt"
    PORTUGUESE_BR = "pt-BR"

    # Europe
    FRENCH = "fr"
    FRENCH_CA = "fr-CA"
    GERMAN = "de"
    ITALIAN = "it"
    DUTCH = "nl"
    POLISH = "pl"
    RUSSIAN = "ru"
    SWEDISH = "sv"
    TURKISH = "tr"
    UKRAINIAN = "uk"
    DANISH = "da"
    NORWEGIAN = "no"
    FINNISH = "fi"
    CZECH = "cs"
    ROMANIAN = "ro"
    HUNGARIAN = "hu"
    GREEK = "el"
    BULGARIAN = "bg"

    # Asia
    MANDARIN = "zh"
    MANDARIN_TW = "zh-TW"
    CANTONESE = "zh-HK"
    JAPANESE = "ja"
    KOREAN = "ko"
    HINDI = "hi"
    TAMIL = "ta"
    INDONESIAN = "id"
    MALAY = "ms"
    VIETNAMESE = "vi"
    THAI = "th"
    TAGALOG = "tl"

    # Middle East
    ARABIC = "ar"
    HEBREW = "he"


# Language display names
LANGUAGE_NAMES = {
    "multi": "Auto-Detect (Multi-language)",
    "en": "English", "en-US": "English (US)", "en-GB": "English (UK)",
    "en-AU": "English (Australia)", "en-IN": "English (India)",
    "es": "Spanish", "es-419": "Spanish (Latin America)",
    "fr": "French", "fr-CA": "French (Canada)",
    "de": "German", "it": "Italian", "pt": "Portuguese", "pt-BR": "Portuguese (Brazil)",
    "nl": "Dutch", "pl": "Polish", "ru": "Russian", "sv": "Swedish",
    "tr": "Turkish", "uk": "Ukrainian", "da": "Danish", "no": "Norwegian",
    "fi": "Finnish", "cs": "Czech", "ro": "Romanian", "hu": "Hungarian",
    "el": "Greek", "bg": "Bulgarian",
    "zh": "Mandarin Chinese", "zh-TW": "Mandarin (Taiwan)", "zh-HK": "Cantonese",
    "ja": "Japanese", "ko": "Korean", "hi": "Hindi", "ta": "Tamil",
    "id": "Indonesian", "ms": "Malay", "vi": "Vietnamese", "th": "Thai",
    "tl": "Tagalog", "ar": "Arabic", "he": "Hebrew",
}


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class DeepgramConfig:
    """Configuration for Deepgram client."""
    api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))

    # Model
    model: str = "nova-2"  # nova-2 or nova-3 (when available)

    # Language
    language: str = "en-US"  # Use "multi" for code-switching

    # Audio format
    encoding: str = "linear16"  # 16-bit PCM
    sample_rate: int = 16000
    channels: int = 1

    # Features
    smart_format: bool = True  # Automatic formatting (numbers, dates, etc.)
    punctuate: bool = True  # Add punctuation
    diarize: bool = False  # Speaker diarization
    filler_words: bool = False  # Include "um", "uh", etc.
    profanity_filter: bool = False

    # VAD and Endpointing
    vad_events: bool = True  # Voice activity detection events
    utterance_end_ms: int = 1000  # Silence duration to end utterance
    interim_results: bool = True  # Send partial transcripts

    # Streaming
    endpointing: int = 300  # ms of silence to trigger endpoint

    # WebSocket URL
    ws_url: str = "wss://api.deepgram.com/v1/listen"


# ============================================================================
# DEEPGRAM NOVA-3 STREAMING STT
# ============================================================================

class DeepgramNova3:
    """
    Streaming Speech-to-Text using Deepgram Nova-3.

    Features:
    - ~30ms chunk latency
    - 36+ languages
    - Code-switching (auto language detection)
    - Voice Activity Detection
    - Smart endpointing
    - Interim results for fast processing

    Usage:
        deepgram = DeepgramNova3()
        await deepgram.connect()

        # Set callbacks
        deepgram.on_transcript = lambda text, is_final: print(text)
        deepgram.on_utterance_end = lambda text: process(text)

        # Send audio
        await deepgram.send_audio(audio_bytes)
    """

    def __init__(self, config: Optional[DeepgramConfig] = None):
        self.config = config or DeepgramConfig()
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self._transcript_buffer = ""

        # Callbacks
        self.on_transcript: Optional[Callable[[str, bool], Any]] = None
        self.on_utterance_end: Optional[Callable[[str], Any]] = None
        self.on_speech_start: Optional[Callable[[], Any]] = None
        self.on_speech_end: Optional[Callable[[], Any]] = None
        self.on_metadata: Optional[Callable[[Dict], Any]] = None
        self.on_error: Optional[Callable[[str], Any]] = None
        self.on_language_detected: Optional[Callable[[str], Any]] = None

        # Metrics
        self._last_latency: Optional[int] = None
        self._total_audio_ms: int = 0
        self._utterance_count: int = 0

    async def connect(self) -> bool:
        """Establish WebSocket connection to Deepgram."""
        if not self.config.api_key:
            logger.error("Deepgram API key not configured")
            return False

        try:
            # Build query parameters
            params = {
                "model": self.config.model,
                "language": self.config.language,
                "encoding": self.config.encoding,
                "sample_rate": str(self.config.sample_rate),
                "channels": str(self.config.channels),
                "smart_format": str(self.config.smart_format).lower(),
                "punctuate": str(self.config.punctuate).lower(),
                "diarize": str(self.config.diarize).lower(),
                "filler_words": str(self.config.filler_words).lower(),
                "profanity_filter": str(self.config.profanity_filter).lower(),
                "vad_events": str(self.config.vad_events).lower(),
                "utterance_end_ms": str(self.config.utterance_end_ms),
                "interim_results": str(self.config.interim_results).lower(),
                "endpointing": str(self.config.endpointing),
            }

            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{self.config.ws_url}?{query_string}"

            headers = {
                "Authorization": f"Token {self.config.api_key}",
            }

            logger.info(f"Connecting to Deepgram ({self.config.model}, lang={self.config.language})...")

            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(
                url,
                headers=headers,
                heartbeat=30.0,
            )
            self._connected = True

            logger.info(
                f"Connected to Deepgram Nova ({self.config.model}, "
                f"lang={self.config.language})"
            )

            # Start receive loop
            asyncio.create_task(self._receive_loop())

            return True

        except aiohttp.ClientResponseError as e:
            logger.error(f"Deepgram auth error: {e.status} - {e.message}")
            return False
        except aiohttp.WSServerHandshakeError as e:
            logger.error(f"Deepgram WebSocket handshake failed: {e.status} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram: {type(e).__name__}: {e}")
            return False

    async def _receive_loop(self):
        """Receive and process messages from Deepgram."""
        if not self.ws:
            logger.error("Deepgram receive loop: WebSocket is None")
            return

        logger.info("Deepgram receive loop started")

        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_message(data)

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"Deepgram WebSocket error: {msg.data}")
                    if self.on_error:
                        await self._safe_callback(self.on_error, str(msg.data))
                    break

                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("Deepgram WebSocket closed by server")
                    break

                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    close_code = msg.data
                    close_msg = msg.extra
                    logger.warning(f"Deepgram close frame: code={close_code}, msg={close_msg}")
                    break

        except asyncio.CancelledError:
            logger.info("Deepgram receive loop cancelled")
        except Exception as e:
            logger.error(f"Error in Deepgram receive loop: {type(e).__name__}: {e}")
        finally:
            self._connected = False
            logger.info("Deepgram receive loop ended, _connected=False")

    async def _handle_message(self, data: dict):
        """Handle a message from Deepgram."""
        msg_type = data.get("type", "")

        if msg_type == "Results":
            await self._handle_results(data)

        elif msg_type == "SpeechStarted":
            logger.debug("Speech started")
            if self.on_speech_start:
                await self._safe_callback(self.on_speech_start)

        elif msg_type == "UtteranceEnd":
            logger.debug("Utterance end detected")
            if self._transcript_buffer.strip():
                self._utterance_count += 1
                if self.on_utterance_end:
                    await self._safe_callback(
                        self.on_utterance_end,
                        self._transcript_buffer.strip()
                    )
                self._transcript_buffer = ""

            if self.on_speech_end:
                await self._safe_callback(self.on_speech_end)

        elif msg_type == "Metadata":
            logger.debug(f"Deepgram metadata: {data}")
            if self.on_metadata:
                await self._safe_callback(self.on_metadata, data)

        elif msg_type == "Error":
            error_msg = data.get("message", "Unknown error")
            logger.error(f"Deepgram error: {error_msg}")
            if self.on_error:
                await self._safe_callback(self.on_error, error_msg)

    async def _handle_results(self, data: dict):
        """Handle transcription results."""
        channel = data.get("channel", {})
        alternatives = channel.get("alternatives", [])

        if not alternatives:
            return

        # Get best alternative
        alt = alternatives[0]
        transcript = alt.get("transcript", "")
        confidence = alt.get("confidence", 0)

        # Check if final
        is_final = data.get("is_final", False)
        speech_final = data.get("speech_final", False)

        # Detect language (for multi-language mode)
        detected_language = data.get("channel", {}).get("detected_language")
        if detected_language and self.on_language_detected:
            await self._safe_callback(self.on_language_detected, detected_language)

        # Track latency
        start_time = data.get("start", 0)
        duration = data.get("duration", 0)
        if duration > 0:
            # Calculate processing latency
            self._total_audio_ms += int(duration * 1000)

        if transcript:
            # Update buffer for final results
            if is_final:
                self._transcript_buffer += transcript + " "

            # Notify transcript callback
            if self.on_transcript:
                await self._safe_callback(self.on_transcript, transcript, is_final)

            # Check for speech_final (complete utterance)
            if speech_final and self._transcript_buffer.strip():
                self._utterance_count += 1
                if self.on_utterance_end:
                    await self._safe_callback(
                        self.on_utterance_end,
                        self._transcript_buffer.strip()
                    )
                self._transcript_buffer = ""

    async def _safe_callback(self, callback, *args):
        """Safely execute a callback."""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Callback error: {e}")

    async def send_audio(self, audio_bytes: bytes):
        """Send audio data to Deepgram for transcription."""
        if self.ws and self._connected:
            await self.ws.send_bytes(audio_bytes)
        else:
            logger.warning("Deepgram not connected, dropping audio")

    async def send_audio_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        chunk_interval_ms: int = 100
    ):
        """
        Send an audio stream to Deepgram.

        Args:
            audio_stream: Async generator yielding audio chunks
            chunk_interval_ms: Delay between chunks (for real-time simulation)
        """
        async for chunk in audio_stream:
            if not self._connected:
                break
            await self.send_audio(chunk)
            if chunk_interval_ms > 0:
                await asyncio.sleep(chunk_interval_ms / 1000)

    async def keep_alive(self):
        """Send keep-alive to maintain connection."""
        if self.ws and self._connected:
            await self.ws.send_json({"type": "KeepAlive"})
            logger.debug("Sent keep-alive")

    async def close(self):
        """Close the Deepgram connection."""
        self._connected = False

        if self.ws:
            # Send close message
            try:
                await self.ws.send_json({"type": "CloseStream"})
                await self.ws.close()
            except Exception as e:
                logger.debug(f"Error closing Deepgram: {e}")

        if self.session:
            await self.session.close()

        logger.info("Deepgram connection closed")

    def get_metrics(self) -> Dict[str, Any]:
        """Get session metrics."""
        return {
            "total_audio_ms": self._total_audio_ms,
            "utterance_count": self._utterance_count,
            "last_latency_ms": self._last_latency,
        }

    def reset_metrics(self):
        """Reset metrics for new session."""
        self._total_audio_ms = 0
        self._utterance_count = 0
        self._last_latency = None


# ============================================================================
# DEEPGRAM BATCH API (FOR PRE-RECORDED)
# ============================================================================

class DeepgramBatch:
    """
    Batch transcription for pre-recorded audio.

    Use for:
    - Transcribing call recordings
    - Processing uploaded audio files
    - Non-real-time transcription
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY", "")
        self.api_url = "https://api.deepgram.com/v1/listen"

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "en",
        model: str = "nova-2",
        **options
    ) -> Dict[str, Any]:
        """
        Transcribe audio file.

        Args:
            audio_data: Audio bytes
            language: Language code
            model: Deepgram model
            **options: Additional options (diarize, punctuate, etc.)

        Returns:
            Transcription result
        """
        if not self.api_key:
            raise ValueError("Deepgram API key not configured")

        params = {
            "model": model,
            "language": language,
            "smart_format": options.get("smart_format", True),
            "punctuate": options.get("punctuate", True),
            "diarize": options.get("diarize", False),
            "utterances": options.get("utterances", True),
            "paragraphs": options.get("paragraphs", False),
        }

        query_string = "&".join(
            f"{k}={str(v).lower() if isinstance(v, bool) else v}"
            for k, v in params.items()
        )
        url = f"{self.api_url}?{query_string}"

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",  # Adjust based on input
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=audio_data) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error = await resp.text()
                    raise Exception(f"Deepgram error: {resp.status} - {error}")

    async def transcribe_url(
        self,
        audio_url: str,
        language: str = "en",
        model: str = "nova-2",
        **options
    ) -> Dict[str, Any]:
        """
        Transcribe audio from URL.

        Args:
            audio_url: URL to audio file
            language: Language code
            model: Deepgram model
            **options: Additional options

        Returns:
            Transcription result
        """
        if not self.api_key:
            raise ValueError("Deepgram API key not configured")

        params = {
            "model": model,
            "language": language,
            "smart_format": options.get("smart_format", True),
            "punctuate": options.get("punctuate", True),
        }

        query_string = "&".join(
            f"{k}={str(v).lower() if isinstance(v, bool) else v}"
            for k, v in params.items()
        )
        url = f"{self.api_url}?{query_string}"

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {"url": audio_url}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error = await resp.text()
                    raise Exception(f"Deepgram error: {resp.status} - {error}")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_deepgram_client: Optional[DeepgramNova3] = None


async def get_deepgram_client(language: str = "en-US") -> DeepgramNova3:
    """Get or create the global Deepgram client."""
    global _deepgram_client

    # Check if we need a new client (different language)
    if _deepgram_client is not None:
        if _deepgram_client.config.language != language:
            await _deepgram_client.close()
            _deepgram_client = None

    if _deepgram_client is None or not _deepgram_client._connected:
        config = DeepgramConfig(language=language)
        _deepgram_client = DeepgramNova3(config)
        await _deepgram_client.connect()

    return _deepgram_client


def get_supported_languages() -> List[Dict[str, str]]:
    """Get list of supported languages with codes and names."""
    return [
        {"code": lang.value, "name": LANGUAGE_NAMES.get(lang.value, lang.value)}
        for lang in DeepgramLanguage
    ]


async def transcribe_audio(
    audio_data: bytes,
    language: str = "en",
) -> str:
    """
    Quick utility to transcribe audio data.

    Returns transcript text.
    """
    batch = DeepgramBatch()
    result = await batch.transcribe(audio_data, language=language)

    # Extract transcript
    channels = result.get("results", {}).get("channels", [])
    if channels:
        alternatives = channels[0].get("alternatives", [])
        if alternatives:
            return alternatives[0].get("transcript", "")

    return ""


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("\n" + "=" * 60)
        print("DEEPGRAM NOVA-3 TEST")
        print("=" * 60 + "\n")

        config = DeepgramConfig()
        print(f"Deepgram API Key configured: {bool(config.api_key)}")

        if not config.api_key:
            print("\n[!] DEEPGRAM_API_KEY not set.")
            print("    Get an API key at: https://console.deepgram.com/")
            print("    $200 free credit for new accounts!")
            return

        print(f"\nSupported languages: {len(DeepgramLanguage)} total")
        print("Includes: 'multi' for auto-detection and code-switching")

        # Test connection
        print("\n--- Testing WebSocket Connection ---")
        client = DeepgramNova3(config)

        transcripts = []

        def on_transcript(text, is_final):
            transcripts.append((text, is_final))
            status = "FINAL" if is_final else "interim"
            print(f"  [{status}] {text}")

        def on_utterance_end(text):
            print(f"  [UTTERANCE] {text}")

        client.on_transcript = on_transcript
        client.on_utterance_end = on_utterance_end

        if await client.connect():
            print("[OK] Connected to Deepgram")

            # Test with sample audio (would need actual audio bytes)
            print("\n[INFO] Connection established. Ready for audio input.")
            print("[INFO] Use client.send_audio(bytes) to send audio data.")

            # Keep connection briefly then close
            await asyncio.sleep(2)
            await client.close()

            print(f"\n[OK] Metrics: {client.get_metrics()}")
            print("[OK] Test complete!")

        else:
            print("[FAIL] Could not connect to Deepgram")

        # Test multi-language config
        print("\n--- Testing Multi-Language Config ---")
        multi_config = DeepgramConfig(language="multi")
        print(f"[OK] Multi-language mode: language={multi_config.language}")

        print("\n" + "=" * 60 + "\n")

    asyncio.run(test())
