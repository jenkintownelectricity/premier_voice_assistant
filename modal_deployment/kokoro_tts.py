"""
HIVE215 Kokoro TTS - Voice Generation Engine
============================================
Deploys Kokoro TTS (82M params, 54 voices) on Modal for HIVE215 Voice AI Platform.

Features:
- 54 pre-built professional voices (8 languages)
- Apache 2.0 license (FREE commercial use)
- 210x realtime on GPU, 3-11x on CPU
- #1 ranked on HuggingFace TTS Arena

Deploy: modal deploy kokoro_tts.py
Test: curl -X POST https://YOUR_WORKSPACE--hive215-kokoro-tts-synthesize-web.modal.run \
      -F "text=Hello, welcome to HIVE215!" -F "voice=af_heart"
"""

import modal
import io
import numpy as np
from pathlib import Path

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
# VOICE LIBRARY - 54 Professional Voices
# =============================================================================

VOICE_LIBRARY = {
    # ===================
    # AMERICAN ENGLISH
    # ===================
    "af_heart": {
        "name": "Heart",
        "gender": "female",
        "language": "en-US",
        "description": "Warm, natural, friendly - Best for general use",
        "best_for": ["general", "customer_service", "receptionist"],
    },
    "af_bella": {
        "name": "Bella", 
        "gender": "female",
        "language": "en-US",
        "description": "Clear, professional, articulate",
        "best_for": ["business", "professional", "announcements"],
    },
    "af_sarah": {
        "name": "Sarah",
        "gender": "female", 
        "language": "en-US",
        "description": "Friendly, approachable, warm",
        "best_for": ["healthcare", "wellness", "support"],
    },
    "af_nicole": {
        "name": "Nicole",
        "gender": "female",
        "language": "en-US", 
        "description": "Energetic, upbeat, engaging",
        "best_for": ["sales", "marketing", "promotions"],
    },
    "af_sky": {
        "name": "Sky",
        "gender": "female",
        "language": "en-US",
        "description": "Calm, soothing, relaxed",
        "best_for": ["spa", "wellness", "meditation"],
    },
    "am_adam": {
        "name": "Adam",
        "gender": "male",
        "language": "en-US",
        "description": "Professional, trustworthy, confident",
        "best_for": ["contractors", "business", "legal"],
    },
    "am_michael": {
        "name": "Michael",
        "gender": "male",
        "language": "en-US",
        "description": "Deep, authoritative, commanding",
        "best_for": ["legal", "finance", "executive"],
    },
    "am_fenrir": {
        "name": "Fenrir",
        "gender": "male",
        "language": "en-US",
        "description": "Energetic, dynamic, enthusiastic",
        "best_for": ["sales", "events", "entertainment"],
    },
    
    # ===================
    # BRITISH ENGLISH
    # ===================
    "bf_emma": {
        "name": "Emma",
        "gender": "female",
        "language": "en-GB",
        "description": "Elegant, refined, professional",
        "best_for": ["healthcare", "luxury", "professional"],
    },
    "bf_isabella": {
        "name": "Isabella",
        "gender": "female",
        "language": "en-GB",
        "description": "Sophisticated, warm, trustworthy",
        "best_for": ["legal", "finance", "consulting"],
    },
    "bf_alice": {
        "name": "Alice",
        "gender": "female",
        "language": "en-GB",
        "description": "Friendly, clear, approachable",
        "best_for": ["customer_service", "support", "retail"],
    },
    "bf_lily": {
        "name": "Lily",
        "gender": "female",
        "language": "en-GB",
        "description": "Soft, calming, gentle",
        "best_for": ["spa", "wellness", "healthcare"],
    },
    "bm_george": {
        "name": "George",
        "gender": "male",
        "language": "en-GB",
        "description": "Authoritative, distinguished, professional",
        "best_for": ["legal", "finance", "corporate"],
    },
    "bm_lewis": {
        "name": "Lewis",
        "gender": "male",
        "language": "en-GB",
        "description": "Friendly, warm, conversational",
        "best_for": ["customer_service", "support", "retail"],
    },
    "bm_daniel": {
        "name": "Daniel",
        "gender": "male",
        "language": "en-GB",
        "description": "Clear, professional, reliable",
        "best_for": ["business", "announcements", "corporate"],
    },
    
    # ===================
    # SPANISH
    # ===================
    "ef_dora": {
        "name": "Dora",
        "gender": "female",
        "language": "es",
        "description": "Warm, friendly, natural Spanish",
        "best_for": ["general", "customer_service"],
    },
    "em_alex": {
        "name": "Alex",
        "gender": "male",
        "language": "es",
        "description": "Professional, clear Spanish",
        "best_for": ["business", "announcements"],
    },
    
    # ===================
    # FRENCH
    # ===================
    "ff_siwis": {
        "name": "Siwis",
        "gender": "female",
        "language": "fr",
        "description": "Elegant, refined French",
        "best_for": ["luxury", "hospitality"],
    },
    
    # ===================
    # JAPANESE
    # ===================
    "jf_alpha": {
        "name": "Alpha",
        "gender": "female",
        "language": "ja",
        "description": "Natural Japanese female voice",
        "best_for": ["general", "customer_service"],
    },
    "jf_gongitsune": {
        "name": "Gongitsune",
        "gender": "female",
        "language": "ja",
        "description": "Soft, gentle Japanese",
        "best_for": ["storytelling", "narration"],
    },
    "jm_kumo": {
        "name": "Kumo",
        "gender": "male",
        "language": "ja",
        "description": "Professional Japanese male",
        "best_for": ["business", "announcements"],
    },
    
    # ===================
    # CHINESE (Mandarin)
    # ===================
    "zf_xiaobei": {
        "name": "Xiaobei",
        "gender": "female",
        "language": "zh",
        "description": "Clear, natural Mandarin",
        "best_for": ["general", "customer_service"],
    },
    "zf_xiaoni": {
        "name": "Xiaoni",
        "gender": "female",
        "language": "zh",
        "description": "Warm, friendly Mandarin",
        "best_for": ["support", "retail"],
    },
    "zf_xiaoxiao": {
        "name": "Xiaoxiao",
        "gender": "female",
        "language": "zh",
        "description": "Professional Mandarin",
        "best_for": ["business", "corporate"],
    },
    "zm_yunjian": {
        "name": "Yunjian",
        "gender": "male",
        "language": "zh",
        "description": "Authoritative Mandarin male",
        "best_for": ["business", "announcements"],
    },
    
    # ===================
    # HINDI
    # ===================
    "hf_alpha": {
        "name": "Hindi Alpha",
        "gender": "female",
        "language": "hi",
        "description": "Natural Hindi female",
        "best_for": ["general", "customer_service"],
    },
    "hf_beta": {
        "name": "Hindi Beta",
        "gender": "female",
        "language": "hi",
        "description": "Professional Hindi",
        "best_for": ["business", "support"],
    },
    "hm_omega": {
        "name": "Hindi Omega",
        "gender": "male",
        "language": "hi",
        "description": "Professional Hindi male",
        "best_for": ["business", "announcements"],
    },
    
    # ===================
    # ITALIAN
    # ===================
    "if_sara": {
        "name": "Sara",
        "gender": "female",
        "language": "it",
        "description": "Warm Italian female",
        "best_for": ["hospitality", "restaurant"],
    },
    "im_nicola": {
        "name": "Nicola",
        "gender": "male",
        "language": "it",
        "description": "Professional Italian male",
        "best_for": ["business", "restaurant"],
    },
    
    # ===================
    # PORTUGUESE (Brazilian)
    # ===================
    "pf_dora": {
        "name": "Dora BR",
        "gender": "female",
        "language": "pt-BR",
        "description": "Friendly Brazilian Portuguese",
        "best_for": ["general", "customer_service"],
    },
    "pm_alex": {
        "name": "Alex BR",
        "gender": "male",
        "language": "pt-BR",
        "description": "Professional Brazilian Portuguese",
        "best_for": ["business", "announcements"],
    },
}

# =============================================================================
# HIVE215 VOICE MAPPING (Your 6 planned voices → Kokoro equivalents)
# =============================================================================

HIVE215_VOICE_MAP = {
    # Your planned voice → Best Kokoro match
    "fabio": "am_adam",       # Professional Fabio → Adam (professional, trustworthy)
    "hannah": "bf_emma",      # Healthcare Hannah → Emma (elegant, professional British)
    "riley": "af_nicole",     # Restaurant Riley → Nicole (energetic, upbeat)
    "lauren": "bf_isabella",  # Legal Lauren → Isabella (sophisticated, trustworthy)
    "sofia": "af_sky",        # Spa Sofia → Sky (calm, soothing)
    "carlos": "am_fenrir",    # Catering Carlos → Fenrir (energetic, enthusiastic)
    
    # Default fallback
    "default": "af_heart",
}

# Language code mapping
LANG_CODES = {
    "en-US": "a",  # American English
    "en-GB": "b",  # British English
    "es": "e",     # Spanish
    "fr": "f",     # French
    "ja": "j",     # Japanese
    "zh": "z",     # Chinese
    "hi": "h",     # Hindi
    "it": "i",     # Italian
    "pt-BR": "p",  # Portuguese
}


# =============================================================================
# KOKORO TTS CLASS
# =============================================================================

@app.cls(image=kokoro_image, gpu="T4", timeout=120)
class KokoroTTS:
    """Kokoro TTS Engine for HIVE215"""
    
    @modal.enter()
    def setup(self):
        """Initialize Kokoro pipeline on container start"""
        from kokoro import KPipeline
        import torch
        
        print("🎙️ Initializing Kokoro TTS...")
        
        # Pre-load pipelines for each language
        self.pipelines = {}
        
        # Always load American English (most common)
        self.pipelines["a"] = KPipeline(lang_code="a")
        print("✅ American English pipeline loaded")
        
        # Set device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"✅ Using device: {self.device}")
        print(f"✅ Kokoro TTS ready with {len(VOICE_LIBRARY)} voices!")
    
    def get_pipeline(self, lang_code: str):
        """Get or create pipeline for language"""
        from kokoro import KPipeline
        
        if lang_code not in self.pipelines:
            print(f"Loading pipeline for language: {lang_code}")
            self.pipelines[lang_code] = KPipeline(lang_code=lang_code)
        return self.pipelines[lang_code]
    
    @modal.method()
    def synthesize(self, text: str, voice: str = "af_heart", speed: float = 1.0) -> bytes:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to speak
            voice: Voice ID (e.g., "af_heart", "am_adam", "fabio")
            speed: Speech speed multiplier (0.5-2.0)
            
        Returns:
            WAV audio bytes
        """
        import soundfile as sf
        
        # Map HIVE215 voice names to Kokoro voices
        if voice.lower() in HIVE215_VOICE_MAP:
            voice = HIVE215_VOICE_MAP[voice.lower()]
        
        # Validate voice
        if voice not in VOICE_LIBRARY:
            print(f"⚠️ Unknown voice '{voice}', using default")
            voice = "af_heart"
        
        # Get language code for this voice
        voice_info = VOICE_LIBRARY[voice]
        lang_code = LANG_CODES.get(voice_info["language"], "a")
        
        # Get pipeline
        pipeline = self.get_pipeline(lang_code)
        
        # Generate audio
        print(f"🎤 Generating speech: voice={voice}, lang={lang_code}, text={text[:50]}...")
        
        audio_chunks = []
        for i, (gs, ps, audio) in enumerate(pipeline(text, voice=voice, speed=speed)):
            audio_chunks.append(audio)
        
        # Combine chunks
        full_audio = np.concatenate(audio_chunks) if audio_chunks else np.array([])
        
        # Convert to WAV bytes
        buffer = io.BytesIO()
        sf.write(buffer, full_audio, 24000, format="WAV")
        buffer.seek(0)
        
        print(f"✅ Generated {len(full_audio)/24000:.2f}s of audio")
        return buffer.read()
    
    @modal.method()
    def list_voices(self, language: str = None, gender: str = None) -> dict:
        """List available voices with optional filters"""
        voices = {}
        
        for voice_id, info in VOICE_LIBRARY.items():
            # Apply filters
            if language and info["language"] != language:
                continue
            if gender and info["gender"] != gender:
                continue
            
            voices[voice_id] = info
        
        return voices


# =============================================================================
# WEB ENDPOINTS
# =============================================================================

@app.function(image=kokoro_image, gpu="T4", timeout=120)
@modal.web_endpoint(method="POST")
def synthesize_web(
    text: str = modal.web_form_data("text"),
    voice: str = modal.web_form_data("voice", default="af_heart"),
    speed: str = modal.web_form_data("speed", default="1.0"),
):
    """
    Web endpoint for speech synthesis.
    
    Usage:
        curl -X POST https://YOUR_URL/synthesize_web \
            -F "text=Hello, this is HIVE215!" \
            -F "voice=af_heart" \
            -F "speed=1.0"
    
    Returns: audio/wav
    """
    from fastapi.responses import Response
    
    try:
        speed_float = float(speed)
        speed_float = max(0.5, min(2.0, speed_float))  # Clamp 0.5-2.0
    except:
        speed_float = 1.0
    
    # Get TTS instance
    tts = KokoroTTS()
    
    # Generate audio
    audio_bytes = tts.synthesize.remote(text, voice, speed_float)
    
    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="speech.wav"',
            "X-Voice-Used": voice,
            "X-Audio-Duration": str(len(audio_bytes) / 48000),  # Approximate
        }
    )


@app.function(image=kokoro_image)
@modal.web_endpoint(method="GET")
def list_voices_web(
    language: str = None,
    gender: str = None,
):
    """
    List available voices.
    
    Usage:
        GET /list_voices_web
        GET /list_voices_web?language=en-US
        GET /list_voices_web?gender=female
        GET /list_voices_web?language=en-GB&gender=male
    """
    voices = {}
    
    for voice_id, info in VOICE_LIBRARY.items():
        if language and info["language"] != language:
            continue
        if gender and info["gender"] != gender:
            continue
        voices[voice_id] = info
    
    return {
        "total": len(voices),
        "filters": {"language": language, "gender": gender},
        "voices": voices,
        "hive215_mapping": HIVE215_VOICE_MAP,
    }


@app.function(image=kokoro_image)
@modal.web_endpoint(method="GET")
def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "hive215-kokoro-tts",
        "model": "Kokoro-82M",
        "license": "Apache 2.0",
        "voices_available": len(VOICE_LIBRARY),
        "languages": list(set(v["language"] for v in VOICE_LIBRARY.values())),
    }


# =============================================================================
# STREAMING ENDPOINT (for real-time voice calls)
# =============================================================================

@app.function(image=kokoro_image, gpu="T4", timeout=300)
@modal.web_endpoint(method="POST")
async def synthesize_stream(
    text: str = modal.web_form_data("text"),
    voice: str = modal.web_form_data("voice", default="af_heart"),
):
    """
    Streaming synthesis for real-time voice calls.
    Returns audio chunks as they're generated for lower latency.
    """
    from fastapi.responses import StreamingResponse
    from kokoro import KPipeline
    import soundfile as sf
    
    # Map voice
    if voice.lower() in HIVE215_VOICE_MAP:
        voice = HIVE215_VOICE_MAP[voice.lower()]
    
    if voice not in VOICE_LIBRARY:
        voice = "af_heart"
    
    voice_info = VOICE_LIBRARY[voice]
    lang_code = LANG_CODES.get(voice_info["language"], "a")
    
    async def generate_chunks():
        pipeline = KPipeline(lang_code=lang_code)
        
        for i, (gs, ps, audio) in enumerate(pipeline(text, voice=voice)):
            # Convert chunk to WAV bytes
            buffer = io.BytesIO()
            sf.write(buffer, audio, 24000, format="WAV")
            buffer.seek(0)
            yield buffer.read()
    
    return StreamingResponse(
        generate_chunks(),
        media_type="audio/wav",
        headers={"X-Voice-Used": voice}
    )


# =============================================================================
# CLI TESTING
# =============================================================================

@app.local_entrypoint()
def main():
    """Test the TTS locally"""
    print("🎙️ HIVE215 Kokoro TTS Test")
    print("=" * 50)
    
    # Test synthesis
    tts = KokoroTTS()
    
    test_texts = [
        ("Hello, welcome to HIVE215! How can I help you today?", "af_heart"),
        ("Thank you for calling Jenkintown Electricity.", "am_adam"),
        ("Your appointment has been confirmed for tomorrow.", "bf_emma"),
    ]
    
    for text, voice in test_texts:
        print(f"\n🎤 Testing voice: {voice}")
        print(f"   Text: {text}")
        
        audio = tts.synthesize.remote(text, voice)
        print(f"   ✅ Generated {len(audio)} bytes")
        
        # Save to file
        filename = f"test_{voice}.wav"
        with open(filename, "wb") as f:
            f.write(audio)
        print(f"   📁 Saved to {filename}")
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print(f"📊 Total voices available: {len(VOICE_LIBRARY)}")


# =============================================================================
# DEPLOYMENT INSTRUCTIONS
# =============================================================================
"""
DEPLOYMENT:
-----------
1. Install Modal CLI:
   pip install modal

2. Setup Modal (first time):
   modal token new

3. Deploy:
   modal deploy kokoro_tts.py

4. Test endpoints:
   
   # Health check
   curl https://YOUR_WORKSPACE--hive215-kokoro-tts-health.modal.run
   
   # List voices
   curl https://YOUR_WORKSPACE--hive215-kokoro-tts-list-voices-web.modal.run
   
   # Synthesize speech
   curl -X POST https://YOUR_WORKSPACE--hive215-kokoro-tts-synthesize-web.modal.run \
       -F "text=Hello from HIVE215!" \
       -F "voice=af_heart" \
       -o test.wav

5. Update backend/main.py to use new endpoints:
   
   self.modal_tts_url = "https://YOUR_WORKSPACE--hive215-kokoro-tts-synthesize-web.modal.run"

VOICE MAPPING FOR HIVE215:
--------------------------
Your planned voice → Kokoro voice ID:
- fabio  → am_adam (Professional male)
- hannah → bf_emma (British healthcare)
- riley  → af_nicole (Energetic female)
- lauren → bf_isabella (British legal)
- sofia  → af_sky (Calm spa voice)
- carlos → am_fenrir (Energetic male)

Just pass "fabio", "hannah", etc. and it auto-maps!
"""
