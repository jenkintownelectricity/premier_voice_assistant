"""
Whisper STT - Fixed for Modal GPU/CPU fallback
"""
import modal
from pathlib import Path

app = modal.App("premier-whisper-stt")

def download_whisper_model():
    from faster_whisper import WhisperModel
    WhisperModel("base.en", device="cpu", compute_type="int8")

whisper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "faster-whisper==1.0.3",
        "numpy==1.26.4",
        "fastapi[standard]",
        "requests",
    )
    .run_function(download_whisper_model)
)


@app.function(image=whisper_image, cpu=2, memory=4096, scaledown_window=300, timeout=600)
@modal.asgi_app()
def transcribe_web():
    from fastapi import FastAPI, File, Form, UploadFile
    import time
    import tempfile
    import subprocess
    from pathlib import Path
    from faster_whisper import WhisperModel

    web_app = FastAPI()
    model = None
    
    def get_model():
        nonlocal model
        if model is None:
            # Use CPU to avoid CUDA issues
            print("Loading Whisper model on CPU...")
            model = WhisperModel("base.en", device="cpu", compute_type="int8")
            print("Model loaded!")
        return model

    @web_app.post("/")
    async def transcribe(
        audio_bytes: UploadFile = File(...),
        language: str = Form("en")
    ):
        start_time = time.time()
        audio_data = await audio_bytes.read()
        
        if len(audio_data) < 100:
            return {"text": "", "error": "Audio too short", "duration": 0}
        
        print(f"Received audio: {len(audio_data)} bytes")
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(audio_data)
            input_path = f.name
        
        output_path = input_path.replace(".webm", ".wav")
        
        try:
            # Convert webm to wav using ffmpeg
            result = subprocess.run([
                "ffmpeg", "-y", "-i", input_path,
                "-ar", "16000", "-ac", "1", "-f", "wav", output_path
            ], capture_output=True, timeout=30)
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr.decode()}")
                return {"text": "", "error": "Audio conversion failed", "duration": 0}
            
            # Check output file
            if not Path(output_path).exists() or Path(output_path).stat().st_size < 100:
                return {"text": "", "error": "Converted file too small", "duration": 0}
            
            # Transcribe
            m = get_model()
            segments, info = m.transcribe(
                output_path,
                language=language,
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            full_text = []
            for segment in segments:
                full_text.append(segment.text)

            text = " ".join(full_text).strip()
            processing_time = time.time() - start_time
            
            print(f"Transcribed {info.duration:.2f}s -> '{text}' in {processing_time:.2f}s")

            return {
                "text": text,
                "language": info.language,
                "duration": info.duration,
                "processing_time": processing_time,
            }

        except Exception as e:
            print(f"Transcription error: {e}")
            return {"text": "", "error": str(e), "duration": 0}
            
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)

    @web_app.get("/health")
    def health():
        return {"status": "healthy", "model": "base.en", "device": "cpu"}

    return web_app


@app.local_entrypoint()
def main():
    print("Whisper STT ready!")
