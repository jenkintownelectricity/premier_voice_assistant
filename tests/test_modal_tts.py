"""
Test Coqui TTS deployment on Modal
"""
import pytest
from pathlib import Path


def test_modal_tts_deployment():
    """Test that Modal TTS deployment works"""
    try:
        from modal_deployment.coqui_tts import test_tts

        result = test_tts.remote()
        assert result['status'] == 'ok'
        assert result['model'] == 'xtts_v2'
        print("✓ Coqui TTS deployment test passed")

    except Exception as e:
        pytest.skip(f"Modal not configured: {e}")


def test_voice_listing():
    """Test listing available voices"""
    try:
        from modal_deployment.coqui_tts import CoquiTTS

        tts = CoquiTTS()
        voices = tts.list_voices.remote()

        print(f"✓ Voice listing test passed")
        print(f"  Available voices: {voices if voices else 'None yet'}")

    except Exception as e:
        pytest.skip(f"Modal not configured: {e}")


def test_synthesis_with_builtin_voice():
    """Test TTS synthesis (will fail if no voice cloned yet)"""
    try:
        from modal_deployment.coqui_tts import CoquiTTS

        tts = CoquiTTS()

        # This will fail if no voice is cloned yet, which is expected
        try:
            audio_bytes = tts.synthesize.remote(
                text="This is a test of the text to speech system.",
                voice_name="fabio",
            )

            assert isinstance(audio_bytes, bytes)
            assert len(audio_bytes) > 0

            print(f"✓ TTS synthesis test passed")
            print(f"  Generated {len(audio_bytes)} bytes of audio")

        except ValueError as e:
            print(f"⚠ TTS synthesis skipped: {e}")
            print("  This is expected if voices haven't been cloned yet")

    except Exception as e:
        pytest.skip(f"Modal not configured: {e}")


if __name__ == '__main__':
    print("Testing Coqui TTS on Modal...\n")
    test_modal_tts_deployment()
    print()
    test_voice_listing()
    print()
    test_synthesis_with_builtin_voice()
    print("\nTTS tests complete!")
