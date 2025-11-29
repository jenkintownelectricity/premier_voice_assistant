"""
Groq LPU Client for Premier Voice Assistant.

Provides ultra-low latency LLM inference using Groq's LPU architecture.

Performance targets:
- Time to First Token (TTFT): ~40ms
- Token throughput: 800+ tokens/second
- 10-20x faster than GPU inference

Supports:
- Llama 3.3 70B (primary - best quality/speed balance)
- Llama 3.1 70B (fallback)
- Mixtral 8x7B (fast fallback)

Architecture:
┌─────────────────────────────────────────────────────────────┐
│  GroqStreamer                                                │
│  ├── Primary: Llama 3.3 70B (~40ms TTFT, 800 tok/s)        │
│  ├── Fallback 1: Llama 3.1 70B                              │
│  ├── Fallback 2: Mixtral 8x7B (fastest)                     │
│  └── Emergency: Claude Haiku (via Anthropic)                │
└─────────────────────────────────────────────────────────────┘
"""

import os
import asyncio
import logging
import time
from typing import Optional, Callable, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# GROQ MODEL REGISTRY
# ============================================================================

class GroqModel(Enum):
    """Available Groq models with their characteristics."""
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"      # Best quality, ~40ms TTFT
    LLAMA_3_1_70B = "llama-3.1-70b-versatile"      # Fallback
    LLAMA_3_1_8B = "llama-3.1-8b-instant"          # Fast, lower quality
    MIXTRAL_8X7B = "mixtral-8x7b-32768"            # Fast, good for simple tasks
    GEMMA_2_9B = "gemma2-9b-it"                    # Alternative


GROQ_MODEL_FALLBACK_CHAIN = [
    GroqModel.LLAMA_3_3_70B,
    GroqModel.LLAMA_3_1_70B,
    GroqModel.MIXTRAL_8X7B,
    GroqModel.LLAMA_3_1_8B,
]


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class GroqConfig:
    """Configuration for Groq client."""
    api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    model: str = GroqModel.LLAMA_3_3_70B.value
    max_tokens: int = 150  # Keep short for voice responses
    temperature: float = 0.7
    top_p: float = 0.9

    # Streaming settings
    stream: bool = True

    # Fallback settings
    enable_fallback: bool = True
    max_retries: int = 3

    # Timeouts (milliseconds)
    timeout_ms: int = 10000  # 10 seconds max

    # Voice-optimized settings
    voice_mode: bool = True  # Optimizes for short, conversational responses


# ============================================================================
# GROQ STREAMING CLIENT
# ============================================================================

class GroqStreamer:
    """
    Streaming LLM client using Groq's ultra-fast LPU inference.

    Features:
    - ~40ms time-to-first-token
    - 800+ tokens/second throughput
    - Automatic model fallback
    - Sentence boundary detection for TTS streaming

    Usage:
        streamer = GroqStreamer()

        async for token in streamer.stream_response(
            user_message="Hello, how are you?",
            system_prompt="You are a helpful assistant."
        ):
            print(token, end="", flush=True)
    """

    def __init__(self, config: Optional[GroqConfig] = None):
        self.config = config or GroqConfig()
        self._client = None
        self._failed_models: List[str] = []

        # Metrics
        self._last_ttft: Optional[int] = None
        self._last_total_time: Optional[int] = None
        self._last_token_count: int = 0

    def _get_client(self):
        """Get or create Groq client."""
        if self._client is None:
            try:
                from groq import Groq
                self._client = Groq(api_key=self.config.api_key)
                logger.info("Groq client initialized")
            except ImportError:
                logger.error("Groq SDK not installed. Run: pip install groq")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
                raise
        return self._client

    def _get_model(self, exclude: Optional[List[str]] = None) -> str:
        """Get the best available model, excluding failed ones."""
        exclude = exclude or []
        exclude.extend(self._failed_models)

        for model in GROQ_MODEL_FALLBACK_CHAIN:
            if model.value not in exclude:
                return model.value

        # All models failed, reset and try primary
        logger.warning("All Groq models failed, resetting fallback chain")
        self._failed_models = []
        return GroqModel.LLAMA_3_3_70B.value

    def _mark_model_failed(self, model: str):
        """Mark a model as failed."""
        if model not in self._failed_models:
            self._failed_models.append(model)
            logger.warning(f"Marked Groq model as failed: {model}")

    async def stream_response(
        self,
        user_message: str,
        system_prompt: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        on_token: Optional[Callable[[str], Any]] = None,
        on_sentence: Optional[Callable[[str], Any]] = None,
    ) -> str:
        """
        Stream a response from Groq.

        Args:
            user_message: The user's input
            system_prompt: System instructions
            conversation_history: Previous messages
            on_token: Callback for each token
            on_sentence: Callback for each complete sentence (for TTS)

        Returns:
            Full response text
        """
        client = self._get_client()

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        # Get model to use
        model = self._get_model()

        full_response = ""
        sentence_buffer = ""
        start_time = time.time()
        first_token_time = None
        token_count = 0

        for attempt in range(self.config.max_retries):
            try:
                logger.debug(f"Groq request with model: {model} (attempt {attempt + 1})")

                # Create streaming completion
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    stream=True,
                )

                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        token_count += 1

                        # Track TTFT
                        if first_token_time is None:
                            first_token_time = time.time()
                            self._last_ttft = int((first_token_time - start_time) * 1000)
                            logger.info(f"Groq TTFT: {self._last_ttft}ms (model: {model})")

                        full_response += token
                        sentence_buffer += token

                        # Token callback
                        if on_token:
                            try:
                                result = on_token(token)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception as e:
                                logger.error(f"Token callback error: {e}")

                        # Sentence boundary detection for TTS streaming
                        if on_sentence and self._is_sentence_boundary(sentence_buffer):
                            sentence = sentence_buffer.strip()
                            if sentence:
                                try:
                                    result = on_sentence(sentence)
                                    if asyncio.iscoroutine(result):
                                        await result
                                except Exception as e:
                                    logger.error(f"Sentence callback error: {e}")
                            sentence_buffer = ""

                # Send any remaining text as final sentence
                if on_sentence and sentence_buffer.strip():
                    try:
                        result = on_sentence(sentence_buffer.strip())
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Final sentence callback error: {e}")

                # Calculate metrics
                total_time = int((time.time() - start_time) * 1000)
                self._last_total_time = total_time
                self._last_token_count = token_count

                tokens_per_second = (token_count / (total_time / 1000)) if total_time > 0 else 0

                logger.info(
                    f"Groq complete: {token_count} tokens in {total_time}ms "
                    f"({tokens_per_second:.0f} tok/s, TTFT: {self._last_ttft}ms)"
                )

                return full_response

            except Exception as e:
                logger.error(f"Groq error with {model}: {e}")
                self._mark_model_failed(model)

                if attempt < self.config.max_retries - 1:
                    model = self._get_model()
                    logger.info(f"Retrying with model: {model}")
                else:
                    raise

        return full_response

    async def stream_response_async(
        self,
        user_message: str,
        system_prompt: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator for streaming tokens.

        Usage:
            async for token in streamer.stream_response_async("Hello"):
                print(token, end="")
        """
        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        model = self._get_model()
        start_time = time.time()
        first_token_time = None

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content

                    if first_token_time is None:
                        first_token_time = time.time()
                        ttft = int((first_token_time - start_time) * 1000)
                        logger.info(f"Groq TTFT: {ttft}ms")

                    yield token

        except Exception as e:
            logger.error(f"Groq streaming error: {e}")
            raise

    def _is_sentence_boundary(self, text: str) -> bool:
        """
        Check if text ends at a sentence boundary.
        Used for streaming to TTS at natural break points.
        """
        text = text.rstrip()

        # Check for sentence-ending punctuation
        if text.endswith(('.', '!', '?')):
            # Make sure it's not an abbreviation
            words = text.split()
            if words:
                last_word = words[-1].rstrip('.!?')
                # Common abbreviations that shouldn't trigger
                abbrevs = {'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'vs', 'etc', 'e.g', 'i.e'}
                if last_word.lower() not in abbrevs:
                    return True

        # Also break on colons and semicolons for natural pauses
        if text.endswith((':', ';')):
            return len(text) > 20  # Only if substantial content

        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get last request metrics."""
        return {
            "ttft_ms": self._last_ttft,
            "total_ms": self._last_total_time,
            "tokens": self._last_token_count,
            "tokens_per_second": (
                self._last_token_count / (self._last_total_time / 1000)
                if self._last_total_time and self._last_total_time > 0
                else None
            ),
        }


# ============================================================================
# HYBRID LLM CLIENT (GROQ + CLAUDE FALLBACK)
# ============================================================================

class HybridLLMClient:
    """
    Hybrid LLM client that uses Groq for speed with Claude as fallback.

    Strategy:
    1. Try Groq (Llama 3.3 70B) first - 40ms TTFT
    2. If Groq fails or is unavailable, fall back to Claude
    3. Track success rates for monitoring

    This ensures:
    - Ultra-low latency when Groq is available
    - High reliability with Claude as backup
    - Graceful degradation under load
    """

    def __init__(
        self,
        groq_config: Optional[GroqConfig] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        self.groq_config = groq_config or GroqConfig()
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")

        self._groq_streamer: Optional[GroqStreamer] = None
        self._anthropic_client = None

        # Track provider usage
        self._groq_success_count = 0
        self._groq_fail_count = 0
        self._claude_fallback_count = 0

        # Determine primary provider
        self._groq_available = bool(self.groq_config.api_key)
        self._claude_available = bool(self.anthropic_api_key)

        logger.info(
            f"HybridLLMClient initialized - "
            f"Groq: {'available' if self._groq_available else 'unavailable'}, "
            f"Claude: {'available' if self._claude_available else 'unavailable'}"
        )

    def _get_groq(self) -> GroqStreamer:
        """Get or create Groq streamer."""
        if self._groq_streamer is None:
            self._groq_streamer = GroqStreamer(self.groq_config)
        return self._groq_streamer

    def _get_anthropic(self):
        """Get or create Anthropic client."""
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        return self._anthropic_client

    async def stream_response(
        self,
        user_message: str,
        system_prompt: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        on_token: Optional[Callable[[str], Any]] = None,
        on_sentence: Optional[Callable[[str], Any]] = None,
        prefer_provider: Optional[str] = None,  # "groq" or "claude"
    ) -> str:
        """
        Stream a response using the best available provider.

        Args:
            user_message: User input
            system_prompt: System instructions
            conversation_history: Previous messages
            on_token: Token callback
            on_sentence: Sentence callback (for TTS)
            prefer_provider: Override default provider selection

        Returns:
            Full response text
        """
        # Determine provider order
        if prefer_provider == "claude":
            providers = ["claude", "groq"]
        elif prefer_provider == "groq":
            providers = ["groq", "claude"]
        else:
            # Default: Groq first for speed
            providers = ["groq", "claude"]

        last_error = None

        for provider in providers:
            try:
                if provider == "groq" and self._groq_available:
                    response = await self._stream_groq(
                        user_message, system_prompt, conversation_history,
                        on_token, on_sentence
                    )
                    self._groq_success_count += 1
                    return response

                elif provider == "claude" and self._claude_available:
                    response = await self._stream_claude(
                        user_message, system_prompt, conversation_history,
                        on_token, on_sentence
                    )
                    self._claude_fallback_count += 1
                    return response

            except Exception as e:
                last_error = e
                logger.warning(f"{provider} failed: {e}")

                if provider == "groq":
                    self._groq_fail_count += 1

        # All providers failed
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def _stream_groq(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]],
        on_token: Optional[Callable],
        on_sentence: Optional[Callable],
    ) -> str:
        """Stream from Groq."""
        groq = self._get_groq()
        return await groq.stream_response(
            user_message=user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            on_token=on_token,
            on_sentence=on_sentence,
        )

    async def _stream_claude(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]],
        on_token: Optional[Callable],
        on_sentence: Optional[Callable],
    ) -> str:
        """Stream from Claude."""
        client = self._get_anthropic()

        from backend.model_manager import get_model
        model = get_model("haiku")  # Use Haiku for speed when falling back

        messages = conversation_history or []
        messages.append({"role": "user", "content": user_message})

        full_response = ""
        sentence_buffer = ""

        with client.messages.stream(
            model=model,
            max_tokens=self.groq_config.max_tokens,
            temperature=self.groq_config.temperature,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                sentence_buffer += text

                if on_token:
                    try:
                        result = on_token(text)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Token callback error: {e}")

                # Sentence boundary detection
                if on_sentence and self._is_sentence_end(sentence_buffer):
                    try:
                        result = on_sentence(sentence_buffer.strip())
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Sentence callback error: {e}")
                    sentence_buffer = ""

        # Send remaining text
        if on_sentence and sentence_buffer.strip():
            try:
                result = on_sentence(sentence_buffer.strip())
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Final sentence callback error: {e}")

        return full_response

    def _is_sentence_end(self, text: str) -> bool:
        """Check if text ends at sentence boundary."""
        text = text.rstrip()
        return text.endswith(('.', '!', '?')) and len(text) > 10

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        total = self._groq_success_count + self._claude_fallback_count
        return {
            "groq_success": self._groq_success_count,
            "groq_fail": self._groq_fail_count,
            "claude_fallback": self._claude_fallback_count,
            "total_requests": total,
            "groq_success_rate": (
                self._groq_success_count / (self._groq_success_count + self._groq_fail_count)
                if (self._groq_success_count + self._groq_fail_count) > 0
                else 1.0
            ),
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_hybrid_client: Optional[HybridLLMClient] = None


def get_hybrid_llm_client() -> HybridLLMClient:
    """Get or create the global hybrid LLM client."""
    global _hybrid_client
    if _hybrid_client is None:
        _hybrid_client = HybridLLMClient()
    return _hybrid_client


async def quick_response(
    message: str,
    system_prompt: str = "You are a helpful voice assistant. Keep responses concise.",
) -> str:
    """
    Quick utility for getting a fast LLM response.

    Usage:
        response = await quick_response("What's the weather like?")
    """
    client = get_hybrid_llm_client()
    return await client.stream_response(
        user_message=message,
        system_prompt=system_prompt,
    )


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    async def test():
        print("\n" + "=" * 60)
        print("GROQ CLIENT TEST")
        print("=" * 60 + "\n")

        # Check configuration
        config = GroqConfig()
        print(f"Groq API Key configured: {bool(config.api_key)}")

        if not config.api_key:
            print("\n[!] GROQ_API_KEY not set. Set it to test Groq.")
            print("    Get a free API key at: https://console.groq.com/")
            print("\n    Testing with Claude fallback instead...\n")

        # Test hybrid client
        print("--- Testing Hybrid LLM Client ---\n")

        client = HybridLLMClient()

        tokens = []
        sentences = []

        def on_token(token):
            tokens.append(token)
            print(token, end="", flush=True)

        def on_sentence(sentence):
            sentences.append(sentence)
            # print(f"\n[SENTENCE: {sentence[:50]}...]")

        try:
            response = await client.stream_response(
                user_message="Explain quantum computing in exactly 3 sentences.",
                system_prompt="You are a helpful assistant. Be concise and accurate.",
                on_token=on_token,
                on_sentence=on_sentence,
            )

            print(f"\n\n--- Results ---")
            print(f"Total tokens: {len(tokens)}")
            print(f"Sentences detected: {len(sentences)}")
            print(f"Stats: {client.get_stats()}")

            if client._groq_streamer:
                print(f"Groq metrics: {client._groq_streamer.get_metrics()}")

        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 60 + "\n")

    asyncio.run(test())
