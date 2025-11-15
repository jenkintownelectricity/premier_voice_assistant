#!/usr/bin/env python3
"""
End-to-end integration test for the voice pipeline.
Tests: Audio → Whisper → Claude → Coqui → Audio
"""
import sys
import time
from pathlib import Path
import wave
import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_test_audio(text: str = "Hello", duration: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate simple test audio"""
    import io

    # Generate sine wave
    frequency = 440
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio_data = np.sin(2 * np.pi * frequency * t)
    audio_data = (audio_data * 32767).astype(np.int16)

    # Write WAV
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    return buffer.getvalue()


def test_stt():
    """Test Speech-to-Text"""
    print("=" * 60)
    print("Testing Whisper STT")
    print("=" * 60)

    from modal_deployment.whisper_stt import WhisperSTT

    audio = generate_test_audio(duration=2.0)

    stt = WhisperSTT()
    start = time.time()
    result = stt.transcribe.remote(audio)
    latency = time.time() - start

    print(f"✓ Transcription completed")
    print(f"  Text: {result['text']}")
    print(f"  Duration: {result['duration']:.2f}s")
    print(f"  Latency: {latency:.2f}s")

    return result


def test_tts():
    """Test Text-to-Speech"""
    print("\n" + "=" * 60)
    print("Testing Coqui TTS")
    print("=" * 60)

    from modal_deployment.coqui_tts import CoquiTTS

    tts = CoquiTTS()

    # List available voices
    voices = tts.list_voices.remote()
    print(f"Available voices: {voices}")

    if not voices:
        print("⚠ No voices cloned yet, skipping synthesis test")
        print("  Clone a voice first with:")
        print("  modal run modal_deployment/voice_cloner.py --voice-name fabio --audio-path voices/fabio_sample.wav")
        return None

    # Synthesize with first available voice
    voice = voices[0]
    text = "This is a test of the text to speech system."

    start = time.time()
    audio = tts.synthesize.remote(text, voice)
    latency = time.time() - start

    print(f"✓ Synthesis completed")
    print(f"  Voice: {voice}")
    print(f"  Text: {text}")
    print(f"  Audio size: {len(audio)} bytes")
    print(f"  Latency: {latency:.2f}s")

    # Save to file
    output_path = Path(__file__).parent.parent / "test_output.wav"
    with open(output_path, "wb") as f:
        f.write(audio)
    print(f"  Saved to: {output_path}")

    return audio


def test_claude():
    """Test Claude LLM"""
    print("\n" + "=" * 60)
    print("Testing Claude API")
    print("=" * 60)

    from config import settings
    from anthropic import Anthropic

    if not settings.ANTHROPIC_API_KEY:
        print("⚠ ANTHROPIC_API_KEY not configured, skipping")
        return None

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    prompt = "You are a receptionist. A caller says: 'I need to schedule a service call.' Respond in 1 sentence."

    start = time.time()
    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    latency = time.time() - start

    text = response.content[0].text

    print(f"✓ Claude response received")
    print(f"  Response: {text}")
    print(f"  Latency: {latency:.2f}s")

    return text


def test_full_pipeline():
    """Test complete pipeline"""
    print("\n" + "=" * 60)
    print("Testing Full Pipeline: Audio → STT → LLM → TTS → Audio")
    print("=" * 60)

    from main import VoiceAssistant

    assistant = VoiceAssistant()

    # Generate test input audio
    input_audio = generate_test_audio(duration=2.0)

    print("\nProcessing voice input...")
    start = time.time()

    try:
        result = assistant.process_voice_input(
            audio_bytes=input_audio,
            voice="fabio",  # Will fail gracefully if not cloned
        )

        total_latency = time.time() - start

        print(f"\n✓ Pipeline completed successfully!")
        print(f"\n  User (transcribed): {result['user_text']}")
        print(f"  AI response: {result['ai_text']}")
        print(f"\n  Metrics:")
        print(f"    STT latency:   {result['metrics']['stt_latency']:.3f}s")
        print(f"    LLM latency:   {result['metrics']['llm_latency']:.3f}s")
        print(f"    TTS latency:   {result['metrics']['tts_latency']:.3f}s")
        print(f"    Total latency: {result['metrics']['total_latency']:.3f}s")

        # Check against targets
        target = 0.5  # 500ms target
        status = "✓" if result['metrics']['total_latency'] < target else "⚠"
        print(f"\n  {status} Target latency (<500ms): {result['metrics']['total_latency']:.3f}s")

        # Save output audio
        output_path = Path(__file__).parent.parent / "test_pipeline_output.wav"
        with open(output_path, "wb") as f:
            f.write(result['audio_response'])
        print(f"  Saved audio to: {output_path}")

        return result

    except ValueError as e:
        if "not found" in str(e):
            print(f"\n⚠ Skipping TTS: {e}")
            print("  Clone a voice first to test the full pipeline")
        else:
            raise


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PREMIER VOICE ASSISTANT - Integration Tests")
    print("=" * 60)

    try:
        # Individual component tests
        test_stt()
        test_tts()
        test_claude()

        # Full pipeline test
        test_full_pipeline()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
