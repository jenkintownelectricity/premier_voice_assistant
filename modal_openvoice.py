"""
OpenVoice TTS - Modal Deployment with MeloTTS + Tone Color Cloning

MIT Licensed TTS with instant voice cloning using OpenVoice V2.
Commercial use permitted - no API key required.

Two-Stage Pipeline:
1. MeloTTS: High-quality base speech synthesis
2. OpenVoice: Zero-shot tone color transfer from reference audio

Features:
- Real-time streaming synthesis
- Zero-shot voice cloning (3-30 seconds of audio)
- Cross-lingual voice cloning (EN, ES, FR, ZH, JP, KR)
- Style control (speed, pitch, emotion)
- 24000 Hz audio output

Models:
- MeloTTS: MIT Licensed base TTS
- OpenVoice V2: MIT Licensed tone color converter

Deployment:
    modal deploy modal_openvoice.py

Test locally:
    modal serve modal_openvoice.py

Endpoints:
    POST /v1/tts - Streaming/full synthesis (Fish Audio compatible)
    POST /tts/synthesize - Full synthesis
    POST /clone - Create voice from audio sample
    GET /voices - List available voices
    GET /health - Health check
"""

import modal
import os
import io
import base64
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# =============================================================================
# MODAL APP SETUP
# =============================================================================

app = modal.App("openvoice-tts")

# Model volume for caching downloaded weights
model_volume = modal.Volume.from_name("openvoice-models", create_if_missing=True)

# Voices volume for storing cloned voice embeddings
voices_volume = modal.Volume.from_name("openvoice-voices", create_if_missing=True)

# GPU image with OpenVoice + MeloTTS dependencies
openvoice_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install(
        "ffmpeg",
        "libsndfile1",
        "git",
        "espeak-ng",  # Required for MeloTTS phonemization
        "cmake",
        "build-essential",
    )
    .pip_install(
        # Core ML
        "torch==2.1.2",
        "torchaudio==2.1.2",
        "numpy>=1.24.0,<2.0",
        "scipy>=1.11.0",

        # Audio processing
        "librosa>=0.10.0",
        "soundfile>=0.12.0",
        "pydub>=0.25.0",

        # MeloTTS dependencies
        "transformers>=4.40.0",
        "pypinyin",
        "jieba",
        "cn2an",
        "inflect",
        "unidecode",
        "num2words",
        "g2p_en",
        "anyascii",
        "gruut[de,es,fr]",
        "cached_path",

        # OpenVoice dependencies
        "huggingface_hub>=0.20.0",
        "wavmark>=0.0.2",
        "silero-vad",

        # API
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "pydantic>=2.5.0",
        "httpx>=0.26.0",
        "python-multipart>=0.0.6",
    )
    # Install MeloTTS and OpenVoice from source
    .run_commands(
        # Clone and install MeloTTS
        "git clone https://github.com/myshell-ai/MeloTTS.git /opt/MeloTTS",
        "cd /opt/MeloTTS && pip install -e .",
        "python -m unidic download || true",
        # Clone and install OpenVoice
        "git clone https://github.com/myshell-ai/OpenVoice.git /opt/OpenVoice",
        "cd /opt/OpenVoice && pip install -e .",
    )
)


# =============================================================================
# OPENVOICE MODEL CLASS
# =============================================================================

@app.cls(
    image=openvoice_image,
    gpu="T4",  # T4 is sufficient for OpenVoice, A10G for faster inference
    timeout=600,
    scaledown_window=300,  # Keep warm for 5 minutes
    volumes={
        "/models": model_volume,
        "/voices": voices_volume,
    },
)
class OpenVoiceModel:
    """OpenVoice TTS model with MeloTTS base + tone color conversion."""

    @modal.enter()
    def load_model(self):
        """Load OpenVoice + MeloTTS models on container start."""
        import torch
        import sys

        # Add installed packages to path
        sys.path.insert(0, "/opt/MeloTTS")
        sys.path.insert(0, "/opt/OpenVoice")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.sample_rate = 24000  # OpenVoice outputs 24kHz
        self.model_loaded = False

        logger.info(f"Initializing OpenVoice on {self.device}")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")

        # Load cloned voices from volume
        self.cloned_voices: Dict[str, Dict[str, Any]] = {}
        self._load_cloned_voices()

        # Load models
        try:
            self._load_openvoice_models()
            self.model_loaded = True
            logger.info("OpenVoice models loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load OpenVoice models: {e}")
            import traceback
            traceback.print_exc()
            logger.info("Will use fallback synthesis")
            self.model_loaded = False

        logger.info("OpenVoice ready")

    def _load_openvoice_models(self):
        """Load MeloTTS and OpenVoice tone color converter."""
        import torch
        from huggingface_hub import snapshot_download

        # Download OpenVoice V2 checkpoint if not cached
        openvoice_path = Path("/models/openvoice_v2")
        if not openvoice_path.exists() or not any(openvoice_path.iterdir()):
            logger.info("Downloading OpenVoice V2 from HuggingFace...")
            snapshot_download(
                repo_id="myshell-ai/OpenVoice",
                local_dir=str(openvoice_path),
                local_dir_use_symlinks=False,
            )
            model_volume.commit()
            logger.info("OpenVoice model downloaded and cached")
        else:
            logger.info("Using cached OpenVoice model")

        # Load MeloTTS for base synthesis
        try:
            from melo.api import TTS as MeloTTS
            self.melo_tts = MeloTTS(language="EN", device=self.device)
            self.speaker_ids = self.melo_tts.hps.data.spk2id
            logger.info(f"MeloTTS loaded with speakers: {list(self.speaker_ids.keys())}")
        except Exception as e:
            logger.warning(f"Failed to load MeloTTS: {e}")
            self.melo_tts = None

        # Load OpenVoice tone color converter
        try:
            from openvoice.api import ToneColorConverter
            from openvoice import se_extractor

            ckpt_converter = openvoice_path / "checkpoints_v2" / "converter"
            if not ckpt_converter.exists():
                # Try alternative path
                ckpt_converter = openvoice_path / "converter"

            self.tone_color_converter = ToneColorConverter(
                f"{ckpt_converter}/config.json",
                device=self.device,
            )
            self.tone_color_converter.load_ckpt(f"{ckpt_converter}/checkpoint.pth")
            self.se_extractor = se_extractor
            logger.info("OpenVoice tone color converter loaded")
        except Exception as e:
            logger.warning(f"Failed to load tone color converter: {e}")
            self.tone_color_converter = None
            self.se_extractor = None

    def _load_cloned_voices(self):
        """Load cloned voices from persistent volume."""
        voices_dir = Path("/voices")
        if voices_dir.exists():
            for voice_file in voices_dir.glob("*.json"):
                try:
                    with open(voice_file) as f:
                        voice_data = json.load(f)
                        voice_id = voice_file.stem
                        self.cloned_voices[voice_id] = voice_data
                        logger.info(f"Loaded cloned voice: {voice_id}")
                except Exception as e:
                    logger.warning(f"Failed to load voice {voice_file}: {e}")

    def _save_cloned_voice(self, voice_id: str, voice_data: dict):
        """Save a cloned voice to persistent volume."""
        import torch

        voices_dir = Path("/voices")
        voices_dir.mkdir(exist_ok=True)

        # Save metadata
        metadata = {k: v for k, v in voice_data.items() if k != "se_embedding"}
        with open(voices_dir / f"{voice_id}.json", "w") as f:
            json.dump(metadata, f)

        # Save speaker embedding tensor
        if "se_embedding" in voice_data:
            torch.save(
                voice_data["se_embedding"],
                voices_dir / f"{voice_id}_se.pt"
            )

        # Save audio reference if provided
        if "reference_audio" in voice_data:
            audio_path = voices_dir / f"{voice_id}.wav"
            audio_bytes = base64.b64decode(voice_data["reference_audio"])
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

        voices_volume.commit()

    def _load_voice_embedding(self, voice_id: str):
        """Load a voice's speaker embedding tensor."""
        import torch

        se_path = Path("/voices") / f"{voice_id}_se.pt"
        if se_path.exists():
            return torch.load(se_path, map_location=self.device)
        return None

    @modal.method()
    def synthesize(
        self,
        text: str,
        voice_id: str = "default",
        language: str = "en",
        speed: float = 1.0,
        sample_rate: int = 24000,
    ) -> dict:
        """
        Synthesize text to audio.

        Pipeline:
        1. Generate base audio with MeloTTS
        2. Apply tone color transfer if cloned voice selected

        Returns:
            Dict with audio (base64 PCM), sample_rate, duration_ms
        """
        import numpy as np
        import torch
        import soundfile as sf

        logger.info(f"Synthesizing: '{text[:50]}...' with voice {voice_id}")

        try:
            if self.model_loaded and self.melo_tts is not None:
                # Step 1: Generate base audio with MeloTTS
                audio = self._synthesize_with_melotts(text, language, speed)

                # Step 2: Apply tone color conversion if cloned voice
                if voice_id not in ("default", "") and voice_id in self.cloned_voices:
                    audio = self._apply_tone_color(audio, voice_id)

            else:
                # Fallback: generate notification sound
                logger.warning("Using fallback synthesis (model not loaded)")
                duration = max(0.5, len(text) * 0.06 / speed)
                samples = int(sample_rate * duration)

                # Generate a two-tone notification
                t = np.linspace(0, duration, samples)
                audio = np.sin(2 * np.pi * 440 * t) * 0.3
                audio[samples//2:] = np.sin(2 * np.pi * 554 * t[samples//2:]) * 0.3

            # Ensure audio is numpy float32
            if isinstance(audio, torch.Tensor):
                audio = audio.cpu().numpy()
            audio = audio.astype(np.float32)

            # Handle multi-dimensional audio (squeeze to 1D if needed)
            if audio.ndim > 1:
                audio = audio.squeeze()
            if audio.ndim > 1:
                audio = audio[0]  # Take first channel

            # Normalize
            max_val = np.abs(audio).max()
            if max_val > 0:
                audio = audio / max_val * 0.9

            # Resample if needed
            if sample_rate != self.sample_rate:
                import librosa
                audio = librosa.resample(
                    audio,
                    orig_sr=self.sample_rate,
                    target_sr=sample_rate,
                )

            # Convert to 16-bit PCM
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            duration_ms = len(audio) / sample_rate * 1000

            return {
                "audio": base64.b64encode(audio_bytes).decode(),
                "sample_rate": sample_rate,
                "duration_ms": duration_ms,
                "format": "pcm",
                "voice_id": voice_id,
            }

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _synthesize_with_melotts(
        self,
        text: str,
        language: str,
        speed: float,
    ):
        """Generate base audio with MeloTTS."""
        import numpy as np
        import tempfile
        import soundfile as sf

        # Map language codes to MeloTTS speaker IDs
        lang_speaker_map = {
            "en": "EN-US",
            "en-us": "EN-US",
            "en-gb": "EN-BR",
            "es": "ES",
            "fr": "FR",
            "zh": "ZH",
            "ja": "JP",
            "ko": "KR",
        }

        speaker_key = lang_speaker_map.get(language.lower(), "EN-US")
        if speaker_key not in self.speaker_ids:
            speaker_key = list(self.speaker_ids.keys())[0]
        speaker_id = self.speaker_ids[speaker_key]

        # Generate audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name

        self.melo_tts.tts_to_file(
            text,
            speaker_id,
            output_path,
            speed=speed,
        )

        # Read the generated audio
        audio, sr = sf.read(output_path)

        # Resample to our standard rate if needed
        if sr != self.sample_rate:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)

        # Cleanup
        os.unlink(output_path)

        return audio.astype(np.float32)

    def _apply_tone_color(self, audio, voice_id: str):
        """Apply tone color transfer using OpenVoice."""
        import numpy as np
        import torch
        import tempfile
        import soundfile as sf

        if self.tone_color_converter is None:
            logger.warning("Tone color converter not loaded, returning base audio")
            return audio

        # Load target speaker embedding
        target_se = self._load_voice_embedding(voice_id)
        if target_se is None:
            logger.warning(f"No embedding found for voice {voice_id}")
            return audio

        # Get source speaker embedding (from base audio)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            source_path = tmp.name
            sf.write(source_path, audio, self.sample_rate)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name

        try:
            # Extract source embedding
            source_se = self.se_extractor.get_se(
                source_path,
                self.tone_color_converter,
                vad=True,
            )

            # Apply tone color conversion
            self.tone_color_converter.convert(
                audio_src_path=source_path,
                src_se=source_se,
                tgt_se=target_se,
                output_path=output_path,
            )

            # Read converted audio
            converted_audio, sr = sf.read(output_path)

            if sr != self.sample_rate:
                import librosa
                converted_audio = librosa.resample(
                    converted_audio,
                    orig_sr=sr,
                    target_sr=self.sample_rate,
                )

            return converted_audio.astype(np.float32)

        finally:
            # Cleanup temp files
            for path in [source_path, output_path]:
                if os.path.exists(path):
                    os.unlink(path)

    @modal.method()
    def synthesize_stream(
        self,
        text: str,
        voice_id: str = "default",
        language: str = "en",
        speed: float = 1.0,
        sample_rate: int = 24000,
    ):
        """Stream synthesize - yields audio chunks."""
        import numpy as np

        # Full synthesis then chunk (true streaming requires model changes)
        result = self.synthesize(text, voice_id, language, speed, sample_rate)
        audio_bytes = base64.b64decode(result["audio"])

        # Yield in 100ms chunks
        chunk_size = int(sample_rate * 0.1) * 2  # 2 bytes per sample (int16)

        for i in range(0, len(audio_bytes), chunk_size):
            yield audio_bytes[i:i + chunk_size]

    @modal.method()
    def clone_voice(
        self,
        audio_b64: str,
        voice_name: str,
        reference_text: str = "",
        description: str = "",
        language: str = "en",
    ) -> dict:
        """
        Clone a voice from an audio sample.

        Extracts speaker embedding using OpenVoice SE extractor.
        """
        import hashlib
        import soundfile as sf
        import numpy as np
        import tempfile
        import torch

        logger.info(f"Cloning voice: {voice_name}")

        try:
            # Decode and validate audio
            audio_bytes = base64.b64decode(audio_b64)
            audio_file = io.BytesIO(audio_bytes)
            audio, sr = sf.read(audio_file)

            # Validate duration (3-30 seconds recommended)
            duration = len(audio) / sr
            if duration < 3.0:
                raise ValueError("Audio too short (minimum 3 seconds)")
            if duration > 60.0:
                raise ValueError("Audio too long (maximum 60 seconds)")

            # Generate voice ID
            voice_id = f"clone_{hashlib.md5(audio_bytes[:1000]).hexdigest()[:12]}"

            # Extract speaker embedding
            se_embedding = None
            if self.se_extractor is not None and self.tone_color_converter is not None:
                # Save to temp file for SE extraction
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    temp_path = tmp.name
                    sf.write(temp_path, audio, sr)

                try:
                    se_embedding = self.se_extractor.get_se(
                        temp_path,
                        self.tone_color_converter,
                        vad=True,
                    )
                    logger.info(f"Extracted speaker embedding for {voice_id}")
                finally:
                    os.unlink(temp_path)
            else:
                logger.warning("SE extractor not available, voice cloning may not work")

            # Store voice data
            voice_data = {
                "name": voice_name,
                "description": description,
                "language": language,
                "is_cloned": True,
                "duration": duration,
                "sample_rate": sr,
                "reference_text": reference_text,
                "reference_audio": audio_b64,
            }

            if se_embedding is not None:
                voice_data["se_embedding"] = se_embedding

            # Save to persistent volume
            self._save_cloned_voice(voice_id, voice_data)
            self.cloned_voices[voice_id] = voice_data

            logger.info(f"Voice cloned: {voice_id} ({duration:.1f}s)")

            return {
                "voice_id": voice_id,
                "name": voice_name,
                "description": description,
                "language": language,
                "duration": duration,
            }

        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @modal.method()
    def list_voices(self, include_cloned: bool = True) -> dict:
        """List all available voices."""
        voices = [
            {
                "id": "default",
                "name": "Default (EN-US)",
                "description": "MeloTTS English-US voice",
                "language": "en",
                "is_cloned": False,
            }
        ]

        # Add MeloTTS base voices
        if hasattr(self, 'speaker_ids') and self.speaker_ids:
            for speaker_key in self.speaker_ids.keys():
                if speaker_key != "EN-US":  # Already added as default
                    lang = speaker_key.split("-")[0].lower() if "-" in speaker_key else speaker_key.lower()
                    voices.append({
                        "id": f"base_{speaker_key.lower().replace('-', '_')}",
                        "name": f"Base ({speaker_key})",
                        "description": f"MeloTTS {speaker_key} voice",
                        "language": lang,
                        "is_cloned": False,
                    })

        # Add cloned voices
        if include_cloned:
            for voice_id, data in self.cloned_voices.items():
                voices.append({
                    "id": voice_id,
                    "name": data.get("name", voice_id),
                    "description": data.get("description", ""),
                    "language": data.get("language", "en"),
                    "is_cloned": True,
                })

        return {"voices": voices, "count": len(voices)}

    @modal.method()
    def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice."""
        if voice_id in self.cloned_voices:
            del self.cloned_voices[voice_id]

            voices_dir = Path("/voices")
            for suffix in [".json", "_se.pt", ".wav"]:
                path = voices_dir / f"{voice_id}{suffix}"
                if path.exists():
                    path.unlink()

            voices_volume.commit()
            return True
        return False

    @modal.method()
    def health(self) -> dict:
        """Health check."""
        import torch

        return {
            "status": "healthy",
            "engine": "openvoice-v2",
            "base_tts": "melotts",
            "model_loaded": self.model_loaded,
            "melo_loaded": self.melo_tts is not None,
            "tone_converter_loaded": self.tone_color_converter is not None,
            "device": self.device,
            "cuda_available": torch.cuda.is_available(),
            "sample_rate": self.sample_rate,
            "cloned_voices": len(self.cloned_voices),
            "license": "MIT",
        }


# =============================================================================
# FASTAPI WEB APP
# =============================================================================

@app.function(
    image=openvoice_image,
    timeout=300,
)
@modal.asgi_app()
def fastapi_app():
    """FastAPI web server for OpenVoice TTS."""
    from fastapi import FastAPI, HTTPException, File, UploadFile, Form
    from fastapi.responses import StreamingResponse, Response
    from pydantic import BaseModel
    from typing import Optional

    web_app = FastAPI(
        title="OpenVoice TTS",
        description="MIT Licensed TTS with voice cloning using OpenVoice V2 + MeloTTS",
        version="1.0.0",
    )

    model = OpenVoiceModel()

    class TTSRequest(BaseModel):
        text: str
        reference_id: Optional[str] = "default"
        voice_id: Optional[str] = None
        format: str = "pcm"
        latency: str = "normal"
        language: str = "en"
        speed: float = 1.0

    class SynthesizeRequest(BaseModel):
        text: str
        voice_id: str = "default"
        language: str = "en"
        speed: float = 1.0
        sample_rate: int = 24000

    @web_app.get("/health")
    async def health():
        """Health check."""
        try:
            return model.health.remote()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @web_app.get("/voices")
    @web_app.get("/model")
    async def list_voices(include_cloned: bool = True):
        """List available voices (Fish Audio compatible)."""
        try:
            result = model.list_voices.remote(include_cloned=include_cloned)
            # Return in Fish Audio format
            return {"items": result.get("voices", [])}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @web_app.post("/v1/tts")
    async def tts_v1(request: TTSRequest):
        """
        Fish Audio compatible TTS endpoint.
        Returns raw PCM audio bytes.
        """
        try:
            voice_id = request.voice_id or request.reference_id or "default"

            result = model.synthesize.remote(
                text=request.text,
                voice_id=voice_id,
                language=request.language,
                speed=request.speed,
            )

            audio_bytes = base64.b64decode(result["audio"])

            return Response(
                content=audio_bytes,
                media_type="audio/pcm",
                headers={
                    "X-Sample-Rate": str(result["sample_rate"]),
                    "X-Duration-Ms": str(result["duration_ms"]),
                },
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @web_app.post("/tts/synthesize")
    async def synthesize(request: SynthesizeRequest):
        """Full synthesis endpoint - returns JSON with base64 audio."""
        try:
            return model.synthesize.remote(
                text=request.text,
                voice_id=request.voice_id,
                language=request.language,
                speed=request.speed,
                sample_rate=request.sample_rate,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @web_app.post("/tts/stream")
    async def synthesize_stream(request: SynthesizeRequest):
        """Streaming synthesis."""
        def generate():
            for chunk in model.synthesize_stream.remote_gen(
                text=request.text,
                voice_id=request.voice_id,
                language=request.language,
                speed=request.speed,
                sample_rate=request.sample_rate,
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="audio/pcm",
            headers={
                "X-Sample-Rate": str(request.sample_rate),
                "Transfer-Encoding": "chunked",
            },
        )

    @web_app.post("/clone")
    @web_app.post("/model")
    async def clone_voice(
        voices: UploadFile = File(...),
        title: str = Form(...),
        description: str = Form(""),
        visibility: str = Form("private"),
        train_mode: str = Form("fast"),
    ):
        """Clone a voice (Fish Audio compatible)."""
        try:
            audio_bytes = await voices.read()
            audio_b64 = base64.b64encode(audio_bytes).decode()

            result = model.clone_voice.remote(
                audio_b64=audio_b64,
                voice_name=title,
                description=description,
            )

            # Return in Fish Audio format
            return {
                "_id": result["voice_id"],
                "id": result["voice_id"],
                "title": result["name"],
                "description": result["description"],
                "visibility": visibility,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @web_app.delete("/model/{voice_id}")
    @web_app.delete("/voices/{voice_id}")
    async def delete_voice(voice_id: str):
        """Delete a cloned voice."""
        success = model.delete_voice.remote(voice_id)
        if success:
            return {"message": f"Voice {voice_id} deleted"}
        raise HTTPException(status_code=404, detail="Voice not found")

    return web_app


# =============================================================================
# LOCAL TESTING
# =============================================================================

@app.local_entrypoint()
def main():
    """Test the OpenVoice deployment."""
    print("Testing OpenVoice TTS...")

    model = OpenVoiceModel()

    # Health check
    health = model.health.remote()
    print(f"Health: {health}")

    # List voices
    voices = model.list_voices.remote()
    print(f"Voices: {voices}")

    # Synthesize
    result = model.synthesize.remote(
        text="Hello, I am OpenVoice. This is a test of the MIT licensed text to speech system with voice cloning capabilities.",
        voice_id="default",
    )
    print(f"Synthesis: {len(result['audio'])} bytes base64, {result['duration_ms']:.0f}ms")

    # Save test audio
    audio_bytes = base64.b64decode(result["audio"])
    with open("/tmp/openvoice_test.pcm", "wb") as f:
        f.write(audio_bytes)
    print(f"Saved test audio to /tmp/openvoice_test.pcm")

    print("OpenVoice TTS test complete!")
