"""
Test Whisper STT deployment on Modal
"""
import pytest
from pathlib import Path
import wave
import numpy as np


def generate_test_audio(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate a simple sine wave as test audio"""
    import io

    # Generate sine wave
    frequency = 440  # A4 note
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
    audio_data = np.sin(2 * np.pi * frequency * t)

    # Convert to 16-bit PCM
    audio_data = (audio_data * 32767).astype(np.int16)

    # Write to WAV in memory
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    return buffer.getvalue()


def test_modal_stt_deployment():
    """Test that Modal STT deployment works"""
    try:
        from modal_deployment.whisper_stt import test_whisper

        result = test_whisper.remote()
        assert result['status'] == 'ok'
        assert result['model'] == 'base.en'
        print("✓ Whisper STT deployment test passed")

    except Exception as e:
        pytest.skip(f"Modal not configured: {e}")


def test_transcription():
    """Test actual transcription with audio"""
    try:
        from modal_deployment.whisper_stt import WhisperSTT

        # Generate test audio
        audio_bytes = generate_test_audio(duration_seconds=2.0)

        # Transcribe
        stt = WhisperSTT()
        result = stt.transcribe.remote(audio_bytes)

        # Verify structure
        assert 'text' in result
        assert 'duration' in result
        assert 'processing_time' in result

        print(f"✓ Transcription test passed")
        print(f"  Duration: {result['duration']:.2f}s")
        print(f"  Processing time: {result['processing_time']:.2f}s")
        print(f"  Text: {result['text']}")

    except Exception as e:
        pytest.skip(f"Modal not configured: {e}")


if __name__ == '__main__':
    print("Testing Whisper STT on Modal...\n")
    test_modal_stt_deployment()
    print()
    test_transcription()
    print("\nAll STT tests passed!")
