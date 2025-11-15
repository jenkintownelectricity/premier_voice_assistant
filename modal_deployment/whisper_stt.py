"""
Whisper STT deployment on Modal with faster-whisper for optimal speed/cost.
Target latency: <200ms per audio chunk
"""
import modal
import io
from pathlib import Path

# Create Modal app
app = modal.App("premier-whisper-stt")

# Define the container image with faster-whisper
whisper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "faster-whisper==1.0.3",
        "numpy==1.26.4",
    )
)


@app.cls(
    image=whisper_image,
    gpu="T4",  # T4 is cost-effective for Whisper
    container_idle_timeout=300,  # Keep warm for 5 min
    timeout=600,
)
class WhisperSTT:
    """
    Faster-Whisper STT service optimized for low latency and cost.
    """

    @modal.build()
    def download_model(self):
        """Download model at build time to avoid cold start delays"""
        from faster_whisper import WhisperModel

        # Download base.en model (good balance of speed/accuracy)
        WhisperModel(
            "base.en",
            device="cuda",
            compute_type="float16",
        )

    @modal.enter()
    def load_model(self):
        """Load model when container starts"""
        from faster_whisper import WhisperModel
        import time

        start = time.time()
        self.model = WhisperModel(
            "base.en",
            device="cuda",
            compute_type="float16",
        )
        load_time = time.time() - start
        print(f"Model loaded in {load_time:.2f}s")

    @modal.method()
    def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data (WAV, MP3, etc.)
            language: Language code (default: "en")

        Returns:
            {
                "text": "transcribed text",
                "language": "en",
                "duration": 1.23,
                "segments": [...],
            }
        """
        import time
        import tempfile

        start_time = time.time()

        # Write bytes to temp file (faster-whisper needs file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            # Transcribe with optimized settings
            segments, info = self.model.transcribe(
                temp_path,
                language=language,
                beam_size=1,  # Faster, slight accuracy trade-off
                vad_filter=True,  # Skip silence
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
            )

            # Collect segments
            segments_list = []
            full_text = []

            for segment in segments:
                segments_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                })
                full_text.append(segment.text)

            processing_time = time.time() - start_time

            result = {
                "text": " ".join(full_text).strip(),
                "language": info.language,
                "duration": info.duration,
                "segments": segments_list,
                "processing_time": processing_time,
            }

            print(f"Transcribed {info.duration:.2f}s audio in {processing_time:.2f}s")
            return result

        finally:
            # Cleanup temp file
            Path(temp_path).unlink(missing_ok=True)


@app.function(image=whisper_image)
def test_whisper():
    """Test function to verify deployment"""
    print("Whisper STT deployment successful!")
    return {"status": "ok", "model": "base.en", "device": "cuda"}


# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Test the Whisper STT service"""
    # This would be called with: modal run modal_deployment/whisper_stt.py
    result = test_whisper.remote()
    print(f"Test result: {result}")

    # Example with actual audio
    print("\nTo use with audio:")
    print("  stt = WhisperSTT()")
    print("  with open('audio.wav', 'rb') as f:")
    print("      result = stt.transcribe.remote(f.read())")
    print("      print(result['text'])")
