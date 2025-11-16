"""
Whisper STT deployment on Modal with faster-whisper for optimal speed/cost.
Target latency: <200ms per audio chunk
"""
import modal
import io
from pathlib import Path

# Create Modal app
app = modal.App("premier-whisper-stt")

# Function to download model at build time
def download_whisper_model():
    """Download Whisper model during image build to avoid cold start delays"""
    from faster_whisper import WhisperModel
    # Download base.en model (good balance of speed/accuracy)
    WhisperModel(
        "base.en",
        device="cpu",  # Use CPU during build, GPU during runtime
        compute_type="int8",
    )

# Define the container image with faster-whisper
whisper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "faster-whisper==1.0.3",
        "numpy==1.26.4",
    )
    .run_function(download_whisper_model)
)


@app.cls(
    image=whisper_image,
    gpu="T4",  # T4 is cost-effective for Whisper
    scaledown_window=300,  # Keep warm for 5 min (renamed from container_idle_timeout)
    timeout=600,
)
class WhisperSTT:
    """
    Faster-Whisper STT service optimized for low latency and cost.
    Model is downloaded at build time for faster cold starts.
    """

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


@app.function(image=whisper_image, gpu="T4", scaledown_window=300, timeout=600)
@modal.web_endpoint(method="POST")
def transcribe_web(audio_bytes: bytes, language: str = "en"):
    """
    Web endpoint for transcription.
    Call this from your API with audio bytes.

    Example usage:
        import requests
        with open("audio.wav", "rb") as f:
            response = requests.post(
                "https://[workspace]--premier-whisper-stt-transcribe-web.modal.run",
                files={"audio_bytes": f},
                data={"language": "en"}
            )
        result = response.json()
    """
    import time
    import tempfile
    from pathlib import Path
    from faster_whisper import WhisperModel

    start_time = time.time()

    # Load model
    model = WhisperModel(
        "base.en",
        device="cuda",
        compute_type="float16",
    )

    # Write bytes to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        # Transcribe
        segments, info = model.transcribe(
            temp_path,
            language=language,
            beam_size=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
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

        return {
            "text": " ".join(full_text).strip(),
            "language": info.language,
            "duration": info.duration,
            "segments": segments_list,
            "processing_time": processing_time,
        }

    finally:
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
