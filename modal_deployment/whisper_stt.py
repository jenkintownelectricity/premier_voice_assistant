"""
Whisper STT deployment on Modal with faster-whisper.
Fixed: Auto-detect audio format instead of assuming WAV.
"""
import modal
import io
from pathlib import Path

app = modal.App("premier-whisper-stt")

def download_whisper_model():
    from faster_whisper import WhisperModel
    WhisperModel("base.en", device="cpu", compute_type="int8")

whisper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")  # Required for audio format conversion
    .pip_install(
        "faster-whisper==1.0.3",
        "numpy==1.26.4",
        "fastapi[standard]",
    )
    .run_function(download_whisper_model)
)


@app.function(image=whisper_image, gpu="T4", scaledown_window=300, timeout=600)
@modal.asgi_app()
def transcribe_web():
    from fastapi import FastAPI, File, Form, UploadFile
    import time
    import tempfile
    import subprocess
    from pathlib import Path
    from faster_whisper import WhisperModel

    web_app = FastAPI()
    
    # Load model once at startup
    model = None
    
    def get_model():
        nonlocal model
        if model is None:
            model = WhisperModel("base.en", device="cuda", compute_type="float16")
        return model

    @web_app.post("/")
    async def transcribe(
        audio_bytes: UploadFile = File(...),
        language: str = Form("en")
    ):
        """Transcribe audio - auto-detects format."""
        start_time = time.time()
        
        # Read the uploaded file
        audio_data = await audio_bytes.read()
        
        if len(audio_data) < 100:
            return {"text": "", "error": "Audio too short", "duration": 0}
        
        # Write to temp file with no extension (let ffmpeg detect)
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_data)
            input_path = f.name
        
        # Convert to WAV using ffmpeg (handles any input format)
        output_path = input_path.replace(".webm", ".wav")
        try:
            result = subprocess.run([
                "ffmpeg", "-y", "-i", input_path,
                "-ar", "16000",  # 16kHz sample rate (optimal for Whisper)
                "-ac", "1",      # Mono
                "-f", "wav",
                output_path
            ], capture_output=True, timeout=30)
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr.decode()}")
                return {"text": "", "error": "Audio conversion failed", "duration": 0}
                
        except Exception as e:
            print(f"FFmpeg exception: {e}")
            Path(input_path).unlink(missing_ok=True)
            return {"text": "", "error": str(e), "duration": 0}
        finally:
            Path(input_path).unlink(missing_ok=True)

        try:
            # Transcribe the converted WAV
            m = get_model()
            segments, info = m.transcribe(
                output_path,
                language=language,
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

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
            
            print(f"Transcribed {info.duration:.2f}s audio in {processing_time:.2f}s: {' '.join(full_text)[:50]}...")

            return {
                "text": " ".join(full_text).strip(),
                "language": info.language,
                "duration": info.duration,
                "segments": segments_list,
                "processing_time": processing_time,
            }

        finally:
            Path(output_path).unlink(missing_ok=True)

    @web_app.get("/health")
    def health():
        return {"status": "healthy", "model": "base.en"}

    return web_app


@app.local_entrypoint()
def main():
    print("Whisper STT ready to deploy!")
