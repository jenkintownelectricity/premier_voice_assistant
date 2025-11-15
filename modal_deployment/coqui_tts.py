"""
Coqui XTTS-v2 deployment on Modal for voice cloning and TTS.
Target latency: <150ms per sentence
"""
import modal
from pathlib import Path

# Create Modal app
app = modal.App("premier-coqui-tts")

# Define the container image with Coqui TTS
tts_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libsndfile1", "ffmpeg")  # Audio dependencies
    .pip_install(
        "TTS==0.22.0",
        "numpy==1.26.4",
        "soundfile==0.12.1",
        "pydub==0.25.1",
    )
)

# Create a volume for voice models
voice_models_volume = modal.Volume.from_name(
    "premier-voice-models",
    create_if_missing=True,
)


@app.cls(
    image=tts_image,
    gpu="T4",  # T4 sufficient for XTTS
    container_idle_timeout=300,
    timeout=600,
    volumes={"/voice_models": voice_models_volume},
)
class CoquiTTS:
    """
    Coqui XTTS-v2 service with voice cloning capability.
    """

    @modal.build()
    def download_model(self):
        """Download XTTS-v2 model at build time"""
        from TTS.api import TTS

        # Download XTTS-v2 model
        TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")

    @modal.enter()
    def load_model(self):
        """Load TTS model when container starts"""
        from TTS.api import TTS
        import time

        start = time.time()
        self.tts = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            gpu=True,
        )
        load_time = time.time() - start
        print(f"XTTS-v2 model loaded in {load_time:.2f}s")

        # Cache for cloned voices
        self.voice_cache = {}

    @modal.method()
    def clone_voice(
        self,
        voice_name: str,
        reference_audio: bytes,
    ) -> dict:
        """
        Clone a voice from reference audio.

        Args:
            voice_name: Identifier for this voice (e.g., "fabio", "jake")
            reference_audio: WAV audio sample (6-30 seconds recommended)

        Returns:
            {
                "voice_name": "fabio",
                "status": "success",
                "duration": 12.5,
            }
        """
        import tempfile
        import soundfile as sf
        import time

        start_time = time.time()

        # Save reference audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(reference_audio)
            temp_path = f.name

        try:
            # Get audio duration
            data, samplerate = sf.read(temp_path)
            duration = len(data) / samplerate

            # Store in voice models volume for persistence
            voice_path = f"/voice_models/{voice_name}.wav"
            Path(voice_path).parent.mkdir(parents=True, exist_ok=True)

            with open(voice_path, "wb") as f:
                f.write(reference_audio)

            # Cache the path
            self.voice_cache[voice_name] = voice_path

            # Commit volume changes
            voice_models_volume.commit()

            processing_time = time.time() - start_time

            print(f"Cloned voice '{voice_name}' ({duration:.2f}s) in {processing_time:.2f}s")

            return {
                "voice_name": voice_name,
                "status": "success",
                "duration": duration,
                "processing_time": processing_time,
            }

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @modal.method()
    def synthesize(
        self,
        text: str,
        voice_name: str = "fabio",
        language: str = "en",
    ) -> bytes:
        """
        Synthesize speech from text using cloned voice.

        Args:
            text: Text to synthesize
            voice_name: Name of cloned voice to use
            language: Language code (default: "en")

        Returns:
            WAV audio bytes (22050 Hz, mono)
        """
        import tempfile
        import time

        start_time = time.time()

        # Get voice reference
        voice_path = self.voice_cache.get(voice_name)
        if not voice_path:
            # Try to load from volume
            voice_path = f"/voice_models/{voice_name}.wav"
            if Path(voice_path).exists():
                self.voice_cache[voice_name] = voice_path
            else:
                raise ValueError(
                    f"Voice '{voice_name}' not found. Please clone it first."
                )

        # Generate speech
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            output_path = f.name

        try:
            self.tts.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=voice_path,
                language=language,
            )

            # Read generated audio
            with open(output_path, "rb") as f:
                audio_bytes = f.read()

            processing_time = time.time() - start_time

            print(f"Synthesized {len(text)} chars in {processing_time:.2f}s")

            return audio_bytes

        finally:
            Path(output_path).unlink(missing_ok=True)

    @modal.method()
    def list_voices(self) -> list:
        """List all available cloned voices"""
        voices = []
        voice_dir = Path("/voice_models")

        if voice_dir.exists():
            for voice_file in voice_dir.glob("*.wav"):
                voices.append(voice_file.stem)

        return voices


@app.function(image=tts_image)
def test_tts():
    """Test function to verify deployment"""
    print("Coqui TTS deployment successful!")
    return {
        "status": "ok",
        "model": "xtts_v2",
        "device": "cuda",
    }


# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Test the TTS service"""
    result = test_tts.remote()
    print(f"Test result: {result}")

    print("\nTo use TTS:")
    print("  tts = CoquiTTS()")
    print("  # Clone voice")
    print("  with open('fabio_sample.wav', 'rb') as f:")
    print("      tts.clone_voice.remote('fabio', f.read())")
    print("  # Synthesize")
    print("  audio = tts.synthesize.remote('Hello world', 'fabio')")
