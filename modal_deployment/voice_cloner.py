"""
Voice cloning utilities and management.
Handles uploading voice samples and managing voice models.
"""
import modal
from pathlib import Path
import io

from modal_deployment.coqui_tts import app, CoquiTTS


@app.function()
def upload_voice_sample(voice_name: str, audio_path: str) -> dict:
    """
    Upload and clone a voice sample to Modal.

    Args:
        voice_name: Identifier for the voice (e.g., "fabio", "jake")
        audio_path: Local path to the voice sample WAV file

    Returns:
        Result dictionary with status and details
    """
    # Read local audio file
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    # Clone the voice
    tts = CoquiTTS()
    result = tts.clone_voice.remote(voice_name, audio_bytes)

    return result


@app.function()
def list_available_voices() -> list:
    """List all voices that have been cloned"""
    tts = CoquiTTS()
    return tts.list_voices.remote()


@app.local_entrypoint()
def clone_voice(voice_name: str, audio_path: str):
    """
    CLI entrypoint to clone a voice.

    Usage:
        modal run modal_deployment/voice_cloner.py --voice-name fabio --audio-path voices/fabio_sample.wav
    """
    print(f"Cloning voice '{voice_name}' from {audio_path}...")

    result = upload_voice_sample.remote(voice_name, audio_path)

    print(f"✓ Voice cloned successfully!")
    print(f"  Name: {result['voice_name']}")
    print(f"  Duration: {result['duration']:.2f}s")
    print(f"  Processing time: {result['processing_time']:.2f}s")


@app.local_entrypoint()
def list_voices():
    """
    List all available voices.

    Usage:
        modal run modal_deployment/voice_cloner.py::list_voices
    """
    voices = list_available_voices.remote()

    if voices:
        print("Available voices:")
        for voice in voices:
            print(f"  - {voice}")
    else:
        print("No voices cloned yet.")
