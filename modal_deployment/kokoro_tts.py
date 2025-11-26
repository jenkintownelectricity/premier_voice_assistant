"""
HIVE215 Kokoro TTS - Voice Generation Engine
============================================
Deploys Kokoro TTS (82M params, 54 voices) on Modal for HIVE215 Voice AI Platform.

Deploy: modal deploy kokoro_tts.py
"""

import modal
import io
import numpy as np

# =============================================================================
# MODAL APP SETUP
# =============================================================================

app = modal.App("hive215-kokoro-tts")

# Image with all dependencies
kokoro_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("espeak-ng", "ffmpeg", "libsndfile1")
    .pip_install(
        "kokoro>=0.9.2",
        "soundfile>=0.12.1",
        "torch>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
    )
)

# =============================================================================
# VOICE LIBRARY
# =============================================================================

VOICE_LIBRARY = {
    # AMERICAN ENGLISH
    "af_heart": {"name": "Heart", "gender": "female", "language": "en-US"},
    "af_bella": {"name": "Bella", "gender": "female", "language": "en-US"},
    "af_sarah": {"name": "Sarah", "gender": "female", "language": "en-US"},
    "af_nicole": {"name": "Nicole", "gender": "female", "language": "en-US"},
    "af_sky": {"name": "Sky", "gender": "female", "language": "en-US"},
    "am_adam": {"name": "Adam", "gender": "male", "language": "en-US"},
    "am_michael": {"name": "Michael", "gender": "male", "language": "en-US"},
    "am_fenrir": {"name": "Fenrir", "gender": "male", "language": "en-US"},
    
    # BRITISH ENGLISH
    "bf_emma": {"name": "Emma", "gender": "female", "language": "en-GB"},
    "bf_isabella": {"name": "Isabella", "gender": "female", "language": "en-GB"},
    "bf_alice": {"name": "Alice", "gender": "female", "language": "en-GB"},
    "bf_lily": {"name": "Lily", "gender": "female", "language": "en-GB"},
    "bm_george": {"name": "George", "gender": "male", "language": "en-GB"},
    "bm_lewis": {"name": "Lewis", "gender": "male", "language": "en-GB"},
    "bm_daniel": {"name": "Daniel", "gender": "male", "language": "en-GB"},
    
    # OTHER LANGUAGES
    "ef_dora": {"name": "Dora", "gender": "female", "language": "es"},
    "em_alex": {"name": "Alex", "gender": "male", "language": "es"},
    "ff_siwis": {"name": "Siwis", "gender": "female", "language": "fr"},
    "jf_alpha": {"name": "Alpha", "gender": "female", "language": "ja"},
    "jm_kumo": {"name": "Kumo", "gender": "male", "language": "ja"},
    "zf_xiaobei": {"name": "Xiaobei", "gender": "female", "language": "zh"},
    "zm_yunjian": {"name": "Yunjian", "gender": "male", "language": "zh"},
}

# HIVE215 Voice Mapping
HIVE215_VOICE_MAP = {
    "fabio": "am_adam",
    "hannah": "bf_emma",
    "riley": "af_nicole",
    "lauren": "bf_isabella",
    "sofia": "af_sky",
    "carlos": "am_fenrir",
    "default": "af_heart",
}

# Language codes
LANG_CODES = {
    "en-US": "a", "en-GB": "b", "es": "e", "fr": "f",
    "ja": "j", "zh": "z", "hi": "h", "it": "i", "pt-BR": "p",
}


# =============================================================================
# CORE SYNTHESIS FUNCTION
# =============================================================================

def do_synthesis(text: str, voice: str = "af_heart", speed: float = 1.0) -> bytes:
    """Core synthesis logic"""
    from kokoro import KPipeline
    import soundfile as sf
    
    # Map HIVE215 voice names
    if voice.lower() in HIVE215_VOICE_MAP:
        voice = HIVE215_VOICE_MAP[voice.lower()]
    
    if voice not in VOICE_LIBRARY:
        voice = "af_heart"
    
    # Get language code
    voice_info = VOICE_LIBRARY[voice]
    lang_code = LANG_CODES.get(voice_info["language"], "a")
    
    speed = max(0.5, min(2.0, speed))
    
    print(f"🎤 Generating: voice={voice}, lang={lang_code}, text={text[:50]}...")
    
    # Generate audio
    pipeline = KPipeline(lang_code=lang_code)
    
    audio_chunks = []
    for i, (gs, ps, audio) in enumerate(pipeline(text, voice=voice, speed=speed)):
        audio_chunks.append(audio)
    
    full_audio = np.concatenate(audio_chunks) if audio_chunks else np.array([])
    
    # Convert to WAV
    buffer = io.BytesIO()
    sf.write(buffer, full_audio, 24000, format="WAV")
    buffer.seek(0)
    
    print(f"✅ Generated {len(full_audio)/24000:.2f}s of audio")
    
    return buffer.read()


# =============================================================================
# WEB ENDPOINTS
# =============================================================================

@app.function(image=kokoro_image, gpu="T4", timeout=120)
@modal.web_endpoint(method="POST")
def synthesize_web(item: dict):
    """
    POST JSON endpoint.
    
    curl -X POST URL -H "Content-Type: application/json" \
         -d '{"text":"Hello","voice":"af_heart"}'
    """
    text = item.get("text", "Hello")
    voice = item.get("voice", "af_heart")
    speed = float(item.get("speed", 1.0))
    
    audio_bytes = do_synthesis(text, voice, speed)
    
    return modal.web_endpoint.Response(
        content=audio_bytes,
        media_type="audio/wav",
    )


@app.function(image=kokoro_image)
@modal.web_endpoint(method="GET")
def list_voices():
    """List available voices"""
    return {
        "total": len(VOICE_LIBRARY),
        "voices": VOICE_LIBRARY,
        "hive215_mapping": HIVE215_VOICE_MAP,
    }


@app.function(image=kokoro_image)
@modal.web_endpoint(method="GET")
def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "hive215-kokoro-tts",
        "model": "Kokoro-82M",
        "voices": len(VOICE_LIBRARY),
    }


# =============================================================================
# DIRECT FUNCTION CALL (For backend integration)
# =============================================================================

@app.function(image=kokoro_image, gpu="T4", timeout=120)
def synthesize(text: str, voice: str = "af_heart", speed: float = 1.0) -> bytes:
    """
    Direct function call for backend integration.
    
    Usage from Python:
        f = modal.Function.lookup("hive215-kokoro-tts", "synthesize")
        audio = f.remote("Hello", "af_heart")
    """
    return do_synthesis(text, voice, speed)


# =============================================================================
# CLI TEST
# =============================================================================

@app.local_entrypoint()
def main():
    print("🎙️ HIVE215 Kokoro TTS")
    print(f"📊 {len(VOICE_LIBRARY)} voices available")
    print("\nVoice mapping:")
    for hive_name, kokoro_id in HIVE215_VOICE_MAP.items():
        print(f"  {hive_name} → {kokoro_id}")
    print("\n✅ Ready to deploy with: modal deploy kokoro_tts.py")
