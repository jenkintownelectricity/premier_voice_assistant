"""
Lightning Pipeline - Ultimate Voice AI Stack

Sub-150ms perceived latency voice-to-voice pipeline using:
- Deepgram Nova-3: Streaming STT (~30ms chunks)
- Groq Llama 3.3 70B: Ultra-fast LLM (~40ms TTFT, 800 tok/s)
- Cartesia Sonic-3: Streaming TTS (~30ms TTFB)

Architecture:
┌─────────────────────────────────────────────────────────────┐
│  Audio In → Deepgram → Groq → Cartesia → Audio Out         │
│                ↓           ↓        ↓                       │
│            ~30ms        ~40ms    ~30ms                      │
│                                                             │
│  Secret sauce: Sentence-level streaming                     │
│  TTS starts on first sentence, not full response!          │
│                                                             │
│  Total perceived latency: ~150ms 🚀                        │
└─────────────────────────────────────────────────────────────┘

This is the fastest possible voice AI pipeline in 2025.
"""

import os
import asyncio
import logging
import time
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

# Import our new lightning-fast components
from backend.deepgram_client import DeepgramNova3, DeepgramConfig
from backend.groq_client import HybridLLMClient, GroqConfig
from backend.cartesia_client import CartesiaSonic3, CartesiaConfig
from backend.sentence_detector import SentenceDetector
from backend.turn_taking_model import (
    TurnTakingModel, TurnTakingConfig, TurnEagerness,
    TurnState, TurnPrediction, create_turn_taking_model
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class LightningConfig:
    """Configuration for the Lightning Pipeline."""
    # STT (Deepgram Nova-3)
    deepgram_api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))
    deepgram_model: str = "nova-2"
    deepgram_language: str = "en-US"  # Use "multi" for code-switching

    # LLM (Groq + Claude fallback)
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = "llama-3.3-70b-versatile"
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    max_tokens: int = 150
    temperature: float = 0.7

    # TTS (Cartesia Sonic-3)
    cartesia_api_key: str = field(default_factory=lambda: os.getenv("CARTESIA_API_KEY", ""))
    cartesia_voice_id: str = field(default_factory=lambda: os.getenv("CARTESIA_VOICE_ID", "f786b574-daa5-4673-aa0c-cbe3e8534c02"))  # Katie voice
    cartesia_language: str = "en"
    speech_speed: float = 0.9  # TTS speed (0.5-2.0), 0.9 for natural conversation

    # Voice timing controls (for natural conversation flow)
    response_delay_ms: int = 400  # Wait before responding after user stops

    # Turn-taking model settings
    enable_turn_taking_model: bool = True  # Use advanced turn-taking model
    turn_eagerness: str = "balanced"  # "low", "balanced", or "high"
    enable_backchannels: bool = False  # Send "mm-hmm", "I see" during user speech

    # Pipeline behavior
    enable_barge_in: bool = True  # Allow user to interrupt
    enable_sentence_streaming: bool = True  # Stream to TTS at sentence boundaries
    min_sentence_length: int = 15  # Min chars before sending to TTS

    # Audio settings
    sample_rate: int = 16000
    encoding: str = "linear16"


class PipelineState(Enum):
    """Pipeline state machine."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class LatencyMetrics:
    """Track latency for each component."""
    stt_ms: int = 0
    llm_ttft_ms: int = 0
    llm_total_ms: int = 0
    tts_ttfb_ms: int = 0
    tts_total_ms: int = 0
    total_perceived_ms: int = 0
    total_e2e_ms: int = 0


# ============================================================================
# LIGHTNING PIPELINE
# ============================================================================

class LightningPipeline:
    """
    The Ultimate Voice AI Pipeline.

    Orchestrates Deepgram → Groq → Cartesia with sentence-level streaming
    for sub-150ms perceived latency.

    Usage:
        pipeline = LightningPipeline()
        await pipeline.initialize(system_prompt="You are a helpful assistant.")

        # Set callbacks
        pipeline.on_transcript = lambda role, text: print(f"{role}: {text}")
        pipeline.on_audio_out = lambda audio: play_audio(audio)

        # Send audio
        await pipeline.send_audio(audio_bytes)

        # Cleanup
        await pipeline.close()
    """

    def __init__(self, config: Optional[LightningConfig] = None):
        self.config = config or LightningConfig()

        # Components
        self.stt: Optional[DeepgramNova3] = None
        self.llm: Optional[HybridLLMClient] = None
        self.tts: Optional[CartesiaSonic3] = None
        self.sentence_detector: Optional[SentenceDetector] = None
        self.turn_model: Optional[TurnTakingModel] = None

        # State
        self.state = PipelineState.IDLE
        self._system_prompt = ""
        self._conversation_history: List[Dict[str, str]] = []

        # Callbacks
        self.on_transcript: Optional[Callable[[str, str], Any]] = None  # (role, text)
        self.on_audio_out: Optional[Callable[[bytes], Any]] = None
        self.on_state_change: Optional[Callable[[PipelineState], Any]] = None
        self.on_latency: Optional[Callable[[LatencyMetrics], Any]] = None
        self.on_error: Optional[Callable[[str], Any]] = None
        self.on_backchannel: Optional[Callable[[str], Any]] = None  # For "mm-hmm" etc.

        # Timing for metrics
        self._utterance_start: Optional[float] = None
        self._processing_start: Optional[float] = None
        self._first_audio_time: Optional[float] = None

        # Current metrics
        self._current_metrics = LatencyMetrics()

    async def initialize(
        self,
        system_prompt: str = "You are a helpful voice assistant. Keep responses concise and conversational.",
        voice_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bool:
        """
        Initialize all pipeline components.

        Args:
            system_prompt: System instructions for the LLM
            voice_id: Cartesia voice ID (optional)
            language: Language code for STT/TTS (optional)

        Returns:
            True if all components initialized successfully
        """
        self._system_prompt = system_prompt

        if language:
            self.config.deepgram_language = language
            self.config.cartesia_language = language

        if voice_id:
            self.config.cartesia_voice_id = voice_id

        success = True

        # Initialize STT (Deepgram)
        if self.config.deepgram_api_key:
            stt_config = DeepgramConfig(
                api_key=self.config.deepgram_api_key,
                model=self.config.deepgram_model,
                language=self.config.deepgram_language,
                sample_rate=self.config.sample_rate,
            )
            self.stt = DeepgramNova3(stt_config)
            self.stt.on_transcript = self._on_stt_transcript
            self.stt.on_utterance_end = self._on_utterance_end
            self.stt.on_speech_start = self._on_speech_start
            self.stt.on_speech_end = self._on_speech_end

            if not await self.stt.connect():
                logger.error("Failed to connect to Deepgram")
                success = False
                self.stt = None
        else:
            logger.warning("Deepgram not configured - STT disabled")

        # Initialize LLM (Groq + Claude)
        groq_config = GroqConfig(
            api_key=self.config.groq_api_key,
            model=self.config.groq_model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        self.llm = HybridLLMClient(
            groq_config=groq_config,
            anthropic_api_key=self.config.anthropic_api_key,
        )

        # Initialize TTS (Cartesia)
        if self.config.cartesia_api_key:
            tts_config = CartesiaConfig(
                api_key=self.config.cartesia_api_key,
                default_voice_id=self.config.cartesia_voice_id,
                language=self.config.cartesia_language,
                sample_rate=self.config.sample_rate,
                speed=self.config.speech_speed,  # Pass speech speed to TTS
            )
            self.tts = CartesiaSonic3(tts_config)
            self.tts.on_audio = self._on_tts_audio
            self.tts.on_done = self._on_tts_done

            if not await self.tts.connect():
                logger.error("Failed to connect to Cartesia")
                success = False
                self.tts = None
            else:
                logger.info(f"Cartesia TTS connected (speed={self.config.speech_speed})")
        else:
            logger.warning("Cartesia not configured - TTS disabled")

        # Initialize sentence detector
        self.sentence_detector = SentenceDetector()

        # Initialize turn-taking model
        if self.config.enable_turn_taking_model:
            self.turn_model = create_turn_taking_model(
                eagerness=self.config.turn_eagerness,
                response_delay_ms=self.config.response_delay_ms,
                enable_backchannels=self.config.enable_backchannels,
            )
            # Wire up backchannel callback
            self.turn_model.on_backchannel = self._on_backchannel
            logger.info(f"Turn-taking model initialized (eagerness={self.config.turn_eagerness})")

        self._set_state(PipelineState.IDLE)

        logger.info(
            f"Lightning Pipeline initialized: "
            f"STT={'OK' if self.stt else 'DISABLED'}, "
            f"LLM={'OK' if self.llm else 'DISABLED'}, "
            f"TTS={'OK' if self.tts else 'DISABLED'}, "
            f"TurnModel={'OK' if self.turn_model else 'DISABLED'}"
        )

        return success

    def _set_state(self, state: PipelineState):
        """Update pipeline state."""
        if self.state != state:
            old_state = self.state
            self.state = state
            logger.debug(f"Pipeline: {old_state.value} -> {state.value}")

            if self.on_state_change:
                asyncio.create_task(self._safe_callback(self.on_state_change, state))

    async def _safe_callback(self, callback, *args):
        """Safely execute a callback."""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Callback error: {e}")

    # =========================================================================
    # STT CALLBACKS
    # =========================================================================

    async def _on_stt_transcript(self, text: str, is_final: bool):
        """Handle interim transcript from Deepgram.

        Note: We don't send transcript here - _on_utterance_end handles final transcripts
        to avoid duplicates.
        """
        # Feed transcript to turn-taking model for analysis
        if self.turn_model and text:
            self.turn_model.on_transcript(text, is_final)

        # Only log interim transcripts for debugging
        if not is_final:
            logger.debug(f"Interim transcript: {text}")

    async def _on_speech_start(self):
        """User started speaking."""
        self._utterance_start = time.time()

        # Notify turn-taking model
        if self.turn_model:
            self.turn_model.on_speech_start()

        # Barge-in: stop TTS if user interrupts
        if self.state == PipelineState.SPEAKING and self.config.enable_barge_in:
            logger.info("Barge-in detected!")
            self._set_state(PipelineState.INTERRUPTED)
            if self.tts:
                await self.tts.cancel()

        self._set_state(PipelineState.LISTENING)

    async def _on_speech_end(self):
        """User stopped speaking."""
        # Notify turn-taking model
        if self.turn_model:
            self.turn_model.on_speech_end()

    async def _on_backchannel(self, text: str):
        """Handle backchannel request from turn-taking model."""
        logger.debug(f"Backchannel: {text}")
        if self.on_backchannel:
            await self._safe_callback(self.on_backchannel, text)
        # Optionally speak the backchannel through TTS
        # (disabled by default to avoid interrupting user)

    async def _on_utterance_end(self, text: str):
        """User finished utterance - use turn-taking model to decide when to respond."""
        if not text.strip():
            return

        # Calculate STT latency
        stt_latency = 0
        if self._utterance_start:
            stt_latency = int((time.time() - self._utterance_start) * 1000)
            self._current_metrics.stt_ms = stt_latency

        logger.info(f"User: {text} (STT: {stt_latency}ms)")

        # Notify transcript
        if self.on_transcript:
            await self._safe_callback(self.on_transcript, "user", text)

        # Add to history
        self._conversation_history.append({"role": "user", "content": text})

        # Use turn-taking model for intelligent turn detection
        if self.turn_model and self.config.enable_turn_taking_model:
            # Feed final transcript to model
            self.turn_model.on_transcript(text, is_final=True)

            # Get turn prediction
            prediction = await self.turn_model.predict_turn()

            # Log turn-taking decision (INFO level for visibility)
            logger.info(
                f"🎯 Turn-Taking: confidence={prediction.confidence:.2f}, "
                f"delay={prediction.recommended_delay_ms}ms, "
                f"emotion={prediction.recommended_tone.value}, "
                f"reason='{prediction.reason}'"
            )

            # Log talk-time stats periodically
            stats = self.turn_model.get_talk_time_stats()
            if stats.user_turn_count > 0:
                logger.info(
                    f"📊 Talk-Time: ratio={stats.assistant_ratio:.1%}, "
                    f"optimal={stats.is_ratio_optimal}, "
                    f"turns={stats.user_turn_count}/{stats.assistant_turn_count}"
                )

            if prediction.should_take_turn:
                # Apply recommended delay
                if prediction.recommended_delay_ms > 0:
                    await asyncio.sleep(prediction.recommended_delay_ms / 1000.0)

                    # Check if user started speaking during delay
                    if self.state == PipelineState.INTERRUPTED:
                        logger.debug("Response cancelled during delay - user started speaking")
                        self.turn_model.reset_for_next_turn()
                        return

                # Notify turn model we're taking the turn
                self.turn_model.start_assistant_turn()
            else:
                # Model says wait - but we already got utterance_end from Deepgram
                # Use a minimum delay
                await asyncio.sleep(self.config.response_delay_ms / 1000.0)
                if self.state == PipelineState.INTERRUPTED:
                    self.turn_model.reset_for_next_turn()
                    return
        else:
            # Fallback: simple delay-based approach
            if self.config.response_delay_ms > 0:
                await asyncio.sleep(self.config.response_delay_ms / 1000.0)
                if self.state == PipelineState.INTERRUPTED:
                    logger.debug("Response cancelled during delay - user started speaking")
                    return

        # Start processing
        self._processing_start = time.time()
        self._first_audio_time = None
        self._set_state(PipelineState.PROCESSING)

        # Generate response with sentence-level streaming
        await self._generate_response(text)

    # =========================================================================
    # RESPONSE GENERATION
    # =========================================================================

    async def _generate_response(self, user_text: str):
        """Generate and stream response using sentence-level pipeline."""
        if not self.llm:
            logger.error("LLM not initialized")
            return

        llm_start = time.time()
        llm_first_token = None
        full_response = ""

        # Reset sentence detector
        if self.sentence_detector:
            self.sentence_detector.reset()

        async def on_token(token: str):
            """Handle each LLM token."""
            nonlocal llm_first_token, full_response

            # Track TTFT
            if llm_first_token is None:
                llm_first_token = time.time()
                ttft = int((llm_first_token - llm_start) * 1000)
                self._current_metrics.llm_ttft_ms = ttft
                logger.info(f"LLM TTFT: {ttft}ms")

            full_response += token

        async def on_sentence(sentence: str):
            """Handle complete sentence - send to TTS immediately!"""
            if not sentence.strip():
                return

            logger.debug(f"Sentence detected: {sentence[:50]}...")

            # Send to TTS immediately
            if self.tts and self.state != PipelineState.INTERRUPTED:
                self._set_state(PipelineState.SPEAKING)
                await self.tts.synthesize(
                    text=sentence,
                    voice_id=self.config.cartesia_voice_id,
                    language=self.config.cartesia_language,
                    speed=self.config.speech_speed,
                )

        try:
            # Stream LLM response with sentence detection
            await self.llm.stream_response(
                user_message=user_text,
                system_prompt=self._system_prompt,
                conversation_history=self._conversation_history[:-1],
                on_token=on_token,
                on_sentence=on_sentence if self.config.enable_sentence_streaming else None,
            )

            # Calculate LLM total time
            llm_total = int((time.time() - llm_start) * 1000)
            self._current_metrics.llm_total_ms = llm_total

            # If not using sentence streaming, send full response to TTS
            if not self.config.enable_sentence_streaming and self.tts:
                self._set_state(PipelineState.SPEAKING)
                await self.tts.synthesize(
                    text=full_response,
                    voice_id=self.config.cartesia_voice_id,
                    language=self.config.cartesia_language,
                    speed=self.config.speech_speed,
                )

            # Add assistant response to history
            self._conversation_history.append({
                "role": "assistant",
                "content": full_response
            })

            # Notify transcript
            if self.on_transcript:
                await self._safe_callback(self.on_transcript, "assistant", full_response)

            # Calculate perceived latency (time from utterance end to first audio)
            if self._first_audio_time and self._processing_start:
                perceived = int((self._first_audio_time - self._processing_start) * 1000)
                self._current_metrics.total_perceived_ms = perceived
                logger.info(f"Perceived latency: {perceived}ms")

            # Report metrics
            if self.on_latency:
                await self._safe_callback(self.on_latency, self._current_metrics)

            logger.info(
                f"Response: {full_response[:80]}... "
                f"(LLM: {llm_total}ms, TTFT: {self._current_metrics.llm_ttft_ms}ms)"
            )

        except Exception as e:
            logger.error(f"Response generation error: {e}")
            if self.on_error:
                await self._safe_callback(self.on_error, str(e))
            self._set_state(PipelineState.IDLE)

    # =========================================================================
    # TTS CALLBACKS
    # =========================================================================

    async def _on_tts_audio(self, audio_bytes: bytes):
        """Handle audio chunk from Cartesia."""
        # Track time to first audio and report latency
        if self._first_audio_time is None:
            self._first_audio_time = time.time()

            if self._processing_start:
                perceived = int((self._first_audio_time - self._processing_start) * 1000)
                self._current_metrics.tts_ttfb_ms = perceived
                self._current_metrics.total_perceived_ms = perceived
                logger.info(f"⚡ Perceived latency: {perceived}ms (STT: {self._current_metrics.stt_ms}ms, LLM: {self._current_metrics.llm_ttft_ms}ms)")

                # Report latency immediately when first audio arrives
                if self.on_latency:
                    await self._safe_callback(self.on_latency, self._current_metrics)

        # Don't send if interrupted
        if self.state == PipelineState.INTERRUPTED:
            return

        # Send audio to callback
        if self.on_audio_out:
            await self._safe_callback(self.on_audio_out, audio_bytes)

    async def _on_tts_done(self):
        """TTS finished speaking."""
        if self.state != PipelineState.INTERRUPTED:
            self._set_state(PipelineState.IDLE)

        # Notify turn model that assistant finished speaking
        if self.turn_model:
            self.turn_model.end_assistant_turn()

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    async def send_audio(self, audio_bytes: bytes):
        """Send audio to the pipeline for processing."""
        if self.stt:
            await self.stt.send_audio(audio_bytes)

        # Feed audio features to turn-taking model for prosody analysis
        if self.turn_model and len(audio_bytes) >= 2:
            # Calculate RMS energy from 16-bit PCM audio
            try:
                import struct
                samples = struct.unpack(f'<{len(audio_bytes)//2}h', audio_bytes)
                if samples:
                    rms = (sum(s**2 for s in samples) / len(samples)) ** 0.5
                    # Normalize to 0-1 range (16-bit max is 32767)
                    energy = min(1.0, rms / 10000.0)
                    self.turn_model.on_audio_features(energy=energy)
            except Exception:
                pass  # Don't fail on audio processing errors

    async def speak(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = None,
    ):
        """
        Directly speak text (bypass STT/LLM).

        Useful for greetings, confirmations, etc.
        """
        if not self.tts:
            logger.warning("TTS not initialized")
            return

        self._set_state(PipelineState.SPEAKING)
        await self.tts.synthesize(
            text=text,
            voice_id=voice_id or self.config.cartesia_voice_id,
            language=language or self.config.cartesia_language,
            speed=self.config.speech_speed,
        )

    async def process_text(self, text: str) -> str:
        """
        Process text input (bypass STT).

        Returns the LLM response.
        """
        if not self.llm:
            return ""

        self._conversation_history.append({"role": "user", "content": text})

        response = await self.llm.stream_response(
            user_message=text,
            system_prompt=self._system_prompt,
            conversation_history=self._conversation_history[:-1],
        )

        self._conversation_history.append({"role": "assistant", "content": response})
        return response

    def clear_history(self):
        """Clear conversation history."""
        self._conversation_history = []

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            "stt_ms": self._current_metrics.stt_ms,
            "llm_ttft_ms": self._current_metrics.llm_ttft_ms,
            "llm_total_ms": self._current_metrics.llm_total_ms,
            "tts_ttfb_ms": self._current_metrics.tts_ttfb_ms,
            "perceived_ms": self._current_metrics.total_perceived_ms,
            "state": self.state.value,
            "history_length": len(self._conversation_history),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get LLM provider stats."""
        if self.llm:
            return self.llm.get_stats()
        return {}

    # =========================================================================
    # REAL-TIME CONFIGURATION UPDATES
    # =========================================================================

    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update pipeline configuration in real-time during a call.

        Supported updates:
        - speech_speed: float (0.5 - 2.0)
        - response_delay_ms: int (0 - 2000)
        - turn_eagerness: str ("low", "balanced", "high")
        - enable_backchannels: bool
        - enable_emotional_matching: bool
        - enable_talk_time_tracking: bool

        Returns the current config after updates.
        """
        applied = {}

        # Speech speed
        if "speech_speed" in updates:
            speed = float(updates["speech_speed"])
            speed = max(0.5, min(2.0, speed))  # Clamp to valid range
            self.config.speech_speed = speed
            if self.tts:
                self.tts.config.speed = speed
            applied["speech_speed"] = speed
            logger.info(f"🔧 Speed updated to {speed}x")

        # Response delay
        if "response_delay_ms" in updates:
            delay = int(updates["response_delay_ms"])
            delay = max(0, min(2000, delay))  # Clamp to valid range
            self.config.response_delay_ms = delay
            applied["response_delay_ms"] = delay
            logger.info(f"🔧 Response delay updated to {delay}ms")

        # Turn eagerness
        if "turn_eagerness" in updates:
            eagerness = updates["turn_eagerness"]
            if eagerness in ("low", "balanced", "high"):
                self.config.turn_eagerness = eagerness
                if self.turn_model:
                    self.turn_model.set_eagerness(eagerness)
                applied["turn_eagerness"] = eagerness
                logger.info(f"🔧 Turn eagerness updated to {eagerness}")

        # Backchannels
        if "enable_backchannels" in updates:
            enabled = bool(updates["enable_backchannels"])
            self.config.enable_backchannels = enabled
            if self.turn_model:
                self.turn_model.config.enable_backchannels = enabled
            applied["enable_backchannels"] = enabled
            logger.info(f"🔧 Backchannels {'enabled' if enabled else 'disabled'}")

        # Emotional matching
        if "enable_emotional_matching" in updates:
            enabled = bool(updates["enable_emotional_matching"])
            if self.turn_model:
                self.turn_model.config.enable_emotional_matching = enabled
            applied["enable_emotional_matching"] = enabled
            logger.info(f"🔧 Emotional matching {'enabled' if enabled else 'disabled'}")

        # Talk-time tracking
        if "enable_talk_time_tracking" in updates:
            enabled = bool(updates["enable_talk_time_tracking"])
            if self.turn_model:
                self.turn_model.config.enable_talk_time_tracking = enabled
            applied["enable_talk_time_tracking"] = enabled
            logger.info(f"🔧 Talk-time tracking {'enabled' if enabled else 'disabled'}")

        # Voice ID (for switching voices mid-call)
        if "voice_id" in updates:
            voice_id = updates["voice_id"]
            if voice_id and len(voice_id) > 10:
                self.config.cartesia_voice_id = voice_id
                if self.tts:
                    self.tts.config.default_voice_id = voice_id
                applied["voice_id"] = voice_id
                logger.info(f"🔧 Voice changed to {voice_id[:8]}...")

        return {
            "applied": applied,
            "current_config": self.get_current_config(),
        }

    def get_current_config(self) -> Dict[str, Any]:
        """Get current pipeline configuration."""
        config = {
            "speech_speed": self.config.speech_speed,
            "response_delay_ms": self.config.response_delay_ms,
            "turn_eagerness": self.config.turn_eagerness,
            "enable_backchannels": self.config.enable_backchannels,
            "enable_turn_taking_model": self.config.enable_turn_taking_model,
            "voice_id": self.config.cartesia_voice_id,
        }

        # Add turn model config if available
        if self.turn_model:
            config.update({
                "enable_emotional_matching": self.turn_model.config.enable_emotional_matching,
                "enable_talk_time_tracking": self.turn_model.config.enable_talk_time_tracking,
                "prediction_threshold": self.turn_model.config.prediction_threshold,
            })

            # Add current stats
            stats = self.turn_model.get_talk_time_stats()
            config["talk_time_stats"] = {
                "assistant_ratio": round(stats.assistant_ratio, 2),
                "is_optimal": stats.is_ratio_optimal,
                "user_turns": stats.user_turn_count,
                "assistant_turns": stats.assistant_turn_count,
            }

        return config

    async def close(self):
        """Close all connections."""
        if self.stt:
            await self.stt.close()
        if self.tts:
            await self.tts.close()

        self._set_state(PipelineState.IDLE)
        logger.info("Lightning Pipeline closed")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_pipeline: Optional[LightningPipeline] = None


async def get_lightning_pipeline(
    system_prompt: str = "You are a helpful voice assistant.",
    voice_id: Optional[str] = None,
    language: Optional[str] = None,
) -> LightningPipeline:
    """Get or create the global Lightning Pipeline."""
    global _pipeline

    if _pipeline is None:
        _pipeline = LightningPipeline()
        await _pipeline.initialize(
            system_prompt=system_prompt,
            voice_id=voice_id,
            language=language,
        )

    return _pipeline


async def quick_voice_response(
    text: str,
    voice_id: Optional[str] = None,
) -> bytes:
    """
    Quick utility for text-to-speech.

    Returns concatenated audio bytes.
    """
    pipeline = await get_lightning_pipeline()

    audio_chunks = []

    original_callback = pipeline.on_audio_out
    pipeline.on_audio_out = lambda chunk: audio_chunks.append(chunk)

    await pipeline.speak(text, voice_id=voice_id)

    # Wait for completion
    await asyncio.sleep(0.5)

    pipeline.on_audio_out = original_callback
    return b"".join(audio_chunks)


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    async def test():
        print("\n" + "=" * 70)
        print("⚡ LIGHTNING PIPELINE TEST")
        print("=" * 70 + "\n")

        config = LightningConfig()
        print(f"Deepgram: {'✓' if config.deepgram_api_key else '✗'}")
        print(f"Groq: {'✓' if config.groq_api_key else '✗'}")
        print(f"Anthropic: {'✓' if config.anthropic_api_key else '✗'}")
        print(f"Cartesia: {'✓' if config.cartesia_api_key else '✗'}")

        if not any([config.groq_api_key, config.anthropic_api_key]):
            print("\n[!] No LLM API key configured. Set GROQ_API_KEY or ANTHROPIC_API_KEY")
            return

        print("\n--- Initializing Pipeline ---")
        pipeline = LightningPipeline(config)

        def on_transcript(role: str, text: str):
            print(f"  [{role}] {text}")

        def on_state(state: PipelineState):
            print(f"  [state] {state.value}")

        def on_latency(metrics: LatencyMetrics):
            print(f"  [metrics] STT={metrics.stt_ms}ms, LLM={metrics.llm_ttft_ms}ms, "
                  f"TTS={metrics.tts_ttfb_ms}ms, Perceived={metrics.total_perceived_ms}ms")

        pipeline.on_transcript = on_transcript
        pipeline.on_state_change = on_state
        pipeline.on_latency = on_latency

        if await pipeline.initialize():
            print("[OK] Pipeline initialized\n")

            # Test text processing (bypass STT)
            print("--- Testing Text Processing ---")
            test_prompts = [
                "Hello! How are you today?",
                "Explain quantum computing in one sentence.",
                "What's the weather like? (Just say you don't know)",
            ]

            for prompt in test_prompts:
                print(f"\nInput: {prompt}")
                start = time.time()
                response = await pipeline.process_text(prompt)
                elapsed = int((time.time() - start) * 1000)
                print(f"Output ({elapsed}ms): {response[:100]}...")

            # Show stats
            print(f"\n--- Stats ---")
            print(f"LLM: {pipeline.get_stats()}")
            print(f"Metrics: {pipeline.get_metrics()}")

            await pipeline.close()
            print("\n[OK] Test complete!")

        else:
            print("[FAIL] Pipeline initialization failed")

        print("\n" + "=" * 70 + "\n")

    asyncio.run(test())
