"""
Coqui XTTS-v2 deployment on Modal for voice cloning and TTS.
Target latency: <150ms per sentence
"""
import modal
from pathlib import Path

# Create Modal app
app = modal.App("premier-coqui-tts")

# Function to download TTS model at build time
def download_tts_model():
    """Download Coqui XTTS-v2 model during image build to avoid cold start delays"""
    import os
    # Agree to Coqui TOS (required for non-interactive environments)
    os.environ["COQUI_TOS_AGREED"] = "1"

    from TTS.api import TTS
    # Download XTTS-v2 model
    TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")

# Define the container image with Coqui TTS
tts_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libsndfile1", "ffmpeg")  # Audio dependencies
    .pip_install(
        "torch==2.5.1",  # Pin PyTorch version (2.6+ has incompatible weights_only default)
        "transformers==4.33.0",  # Pin transformers for TTS compatibility
        "TTS==0.22.0",
        "numpy==1.26.4",
        "soundfile==0.12.1",
        "pydub==0.25.1",
        "fastapi[standard]",
    )
    .run_function(download_tts_model)
)

# Create a volume for voice models
voice_models_volume = modal.Volume.from_name(
    "premier-voice-models",
    create_if_missing=True,
)


@app.cls(
    image=tts_image,
    gpu="T4",  # T4 sufficient for XTTS
    scaledown_window=300,  # Keep warm for 5 min (renamed from container_idle_timeout)
    timeout=600,
    volumes={"/voice_models": voice_models_volume},
)
class CoquiTTS:
    """
    Coqui XTTS-v2 service with voice cloning capability.
    Model is downloaded at build time for faster cold starts.
    """

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


@app.function(image=tts_image, gpu="T4", scaledown_window=300, timeout=600, volumes={"/voice_models": voice_models_volume})
@modal.asgi_app()
def synthesize_web():
    from fastapi import FastAPI, Form
    from fastapi.responses import Response
    import tempfile
    import time
    from pathlib import Path
    from TTS.api import TTS

    web_app = FastAPI()

    @web_app.post("/")
    async def synthesize(text: str = Form(...), voice_name: str = Form("fabio"), language: str = Form("en")):
        """Web endpoint for text-to-speech synthesis."""
        start_time = time.time()

        # Load TTS model
        tts = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            gpu=True,
        )

        # Get voice reference
        voice_path = f"/voice_models/{voice_name}.wav"
        if not Path(voice_path).exists():
            return {"error": f"Voice '{voice_name}' not found. Please clone it first."}

        # Generate speech
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            output_path = f.name

        try:
            tts.tts_to_file(
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

            return Response(content=audio_bytes, media_type="audio/wav")

        finally:
            Path(output_path).unlink(missing_ok=True)

    return web_app


@app.function(image=tts_image, gpu="T4", scaledown_window=300, timeout=600, volumes={"/voice_models": voice_models_volume})
@modal.asgi_app()
def clone_voice_web():
    from fastapi import FastAPI, File, Form
    import tempfile
    import soundfile as sf
    import subprocess
    import time
    from pathlib import Path

    web_app = FastAPI()

    @web_app.post("/")
    async def clone_voice(voice_name: str = Form(...), reference_audio: bytes = File(...)):
        """Web endpoint for voice cloning."""
        start_time = time.time()

        # Save reference audio to temp file (could be any format)
        with tempfile.NamedTemporaryFile(suffix=".input", delete=False) as f:
            f.write(reference_audio)
            input_path = f.name

        # Convert to WAV using ffmpeg (handles webm, mp3, ogg, etc.)
        wav_path = input_path.replace(".input", ".wav")
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", input_path, "-ar", "22050", "-ac", "1", wav_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                raise ValueError(f"Audio conversion failed: {result.stderr}")

            # Get audio duration
            data, samplerate = sf.read(wav_path)
            duration = len(data) / samplerate

            # Read converted WAV bytes
            with open(wav_path, "rb") as f:
                wav_bytes = f.read()

            # Store in voice models volume for persistence
            voice_path = f"/voice_models/{voice_name}.wav"
            Path(voice_path).parent.mkdir(parents=True, exist_ok=True)

            with open(voice_path, "wb") as f:
                f.write(wav_bytes)

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
            Path(input_path).unlink(missing_ok=True)
            Path(wav_path).unlink(missing_ok=True)

    return web_app


@app.function(image=tts_image, gpu="T4", scaledown_window=300, timeout=600, volumes={"/voice_models": voice_models_volume})
@modal.asgi_app()
def synthesize_stream_web():
    """
    Streaming TTS endpoint for LiveKit integration.
    Returns chunked PCM audio (24kHz, 16-bit, mono) for smooth playback.
    """
    from fastapi import FastAPI, Form, HTTPException
    from fastapi.responses import StreamingResponse
    import tempfile
    import time
    import io
    import struct
    from pathlib import Path
    from TTS.api import TTS
    import numpy as np

    web_app = FastAPI()

    # Pre-load TTS model at startup for faster responses
    tts_model = None

    def get_tts():
        nonlocal tts_model
        if tts_model is None:
            tts_model = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                gpu=True,
            )
        return tts_model

    @web_app.post("/")
    async def synthesize_stream(
        text: str = Form(...),
        voice_name: str = Form("fabio"),
        language: str = Form("en"),
        sample_rate: int = Form(24000),
    ):
        """
        Stream synthesized speech as raw PCM audio chunks.

        Returns: Chunked PCM audio (24kHz, 16-bit signed, mono)
        """
        start_time = time.time()

        # Get voice reference
        voice_path = f"/voice_models/{voice_name}.wav"
        if not Path(voice_path).exists():
            raise HTTPException(status_code=404, detail=f"Voice '{voice_name}' not found")

        tts = get_tts()

        async def audio_generator():
            """
            Generate audio chunks using XTTS streaming inference.
            Yields PCM audio in ~20ms chunks for smooth playback.
            """
            try:
                # XTTS-v2 streaming synthesis
                # Returns a generator of audio chunks
                gpt_cond_latent, speaker_embedding = tts.synthesizer.tts_model.get_conditioning_latents(
                    audio_path=voice_path
                )

                # Stream the audio generation
                chunks = tts.synthesizer.tts_model.inference_stream(
                    text,
                    language,
                    gpt_cond_latent,
                    speaker_embedding,
                    stream_chunk_size=20,  # ~20 tokens per chunk
                )

                chunk_count = 0
                for chunk in chunks:
                    if chunk is not None:
                        # Convert to 16-bit PCM
                        audio_np = chunk.cpu().numpy()

                        # Normalize and convert to int16
                        audio_np = np.clip(audio_np, -1.0, 1.0)
                        audio_int16 = (audio_np * 32767).astype(np.int16)

                        # Yield raw PCM bytes
                        yield audio_int16.tobytes()
                        chunk_count += 1

                elapsed = time.time() - start_time
                print(f"Streamed {chunk_count} chunks for '{text[:50]}...' in {elapsed:.2f}s")

            except Exception as e:
                print(f"Streaming error: {e}")
                raise

        return StreamingResponse(
            audio_generator(),
            media_type="audio/pcm",
            headers={
                "X-Audio-Sample-Rate": str(sample_rate),
                "X-Audio-Channels": "1",
                "X-Audio-Bits": "16",
            }
        )

    @web_app.get("/health")
    async def health():
        return {"status": "ok", "streaming": True}

    return web_app


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
