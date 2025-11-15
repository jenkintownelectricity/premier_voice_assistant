"""
Premier Voice Assistant - Main Flask Application
Orchestrates the voice AI pipeline: STT → LLM → TTS
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Import configuration
try:
    from config import settings
except ImportError:
    logger.warning("Config not fully set up, using defaults")
    settings = None


class VoiceAssistant:
    """
    Main voice assistant orchestrator.
    Coordinates STT, LLM, and TTS services.
    """

    def __init__(self):
        self.modal_initialized = False
        self.stt = None
        self.tts = None
        self.anthropic_client = None

    def initialize_modal(self):
        """Initialize Modal clients (lazy loading)"""
        if self.modal_initialized:
            return

        try:
            import modal

            # Import Modal apps
            from modal_deployment.whisper_stt import WhisperSTT
            from modal_deployment.coqui_tts import CoquiTTS

            self.stt = WhisperSTT()
            self.tts = CoquiTTS()
            self.modal_initialized = True

            logger.info("Modal services initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Modal: {e}")
            raise

    def initialize_claude(self):
        """Initialize Claude API client"""
        if self.anthropic_client:
            return

        try:
            from anthropic import Anthropic

            api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")

            self.anthropic_client = Anthropic(api_key=api_key)
            logger.info("Claude API initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Claude: {e}")
            raise

    def transcribe_audio(self, audio_bytes: bytes) -> dict:
        """
        Transcribe audio to text using Whisper.

        Args:
            audio_bytes: Raw audio data

        Returns:
            {"text": "...", "duration": 1.23, ...}
        """
        self.initialize_modal()
        return self.stt.transcribe.remote(audio_bytes)

    def generate_response(self, user_message: str, conversation_history: list = None) -> str:
        """
        Generate AI response using Claude.

        Args:
            user_message: User's transcribed message
            conversation_history: Previous messages (optional)

        Returns:
            AI response text
        """
        self.initialize_claude()

        # Build system prompt for electrical receptionist
        system_prompt = """You are a professional receptionist for Jenkintown Electricity,
a local electrical contracting company in Jenkintown, PA.

Your role:
- Answer questions about electrical services
- Schedule appointments and service calls
- Provide pricing information when available
- Detect emergencies and escalate appropriately
- Be friendly, professional, and concise (this is a phone conversation)

Keep responses SHORT - 1-2 sentences maximum. This is voice, not chat."""

        # Build messages
        messages = conversation_history or []
        messages.append({
            "role": "user",
            "content": user_message,
        })

        try:
            # Call Claude API
            response = self.anthropic_client.messages.create(
                model=getattr(settings, 'CLAUDE_MODEL', 'claude-3-5-sonnet-20241022'),
                max_tokens=getattr(settings, 'MAX_TOKENS', 150),
                temperature=getattr(settings, 'TEMPERATURE', 0.7),
                system=system_prompt,
                messages=messages,
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return "I apologize, I'm having trouble processing that right now. Let me transfer you to someone who can help."

    def synthesize_speech(self, text: str, voice: str = "fabio") -> bytes:
        """
        Synthesize text to speech using Coqui TTS.

        Args:
            text: Text to speak
            voice: Voice name (default: "fabio")

        Returns:
            WAV audio bytes
        """
        self.initialize_modal()
        return self.tts.synthesize.remote(text, voice)

    def process_voice_input(
        self,
        audio_bytes: bytes,
        voice: str = "fabio",
        conversation_history: list = None,
    ) -> dict:
        """
        End-to-end voice processing pipeline.

        Args:
            audio_bytes: Input audio from user
            voice: Voice to use for response
            conversation_history: Previous conversation turns

        Returns:
            {
                "user_text": "...",
                "ai_text": "...",
                "audio_response": bytes,
                "metrics": {...}
            }
        """
        start_time = time.time()
        metrics = {}

        # Step 1: STT
        stt_start = time.time()
        transcription = self.transcribe_audio(audio_bytes)
        metrics['stt_latency'] = time.time() - stt_start
        user_text = transcription['text']

        logger.info(f"User said: {user_text}")

        # Step 2: LLM
        llm_start = time.time()
        ai_response = self.generate_response(user_text, conversation_history)
        metrics['llm_latency'] = time.time() - llm_start

        logger.info(f"AI responding: {ai_response}")

        # Step 3: TTS
        tts_start = time.time()
        audio_response = self.synthesize_speech(ai_response, voice)
        metrics['tts_latency'] = time.time() - tts_start

        # Total metrics
        metrics['total_latency'] = time.time() - start_time

        logger.info(
            f"Pipeline complete - STT: {metrics['stt_latency']:.2f}s, "
            f"LLM: {metrics['llm_latency']:.2f}s, "
            f"TTS: {metrics['tts_latency']:.2f}s, "
            f"Total: {metrics['total_latency']:.2f}s"
        )

        return {
            "user_text": user_text,
            "ai_text": ai_response,
            "audio_response": audio_response,
            "metrics": metrics,
        }


# Global assistant instance
assistant = VoiceAssistant()


# API Routes

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "Premier Voice Assistant",
        "version": "0.1.0",
    })


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """
    Transcribe audio to text.

    POST /transcribe
    Body: audio file (multipart/form-data or raw bytes)
    """
    try:
        # Get audio from request
        if 'audio' in request.files:
            audio_bytes = request.files['audio'].read()
        else:
            audio_bytes = request.data

        result = assistant.transcribe_audio(audio_bytes)

        return jsonify({
            "success": True,
            "text": result['text'],
            "duration": result.get('duration'),
            "processing_time": result.get('processing_time'),
        })

    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@app.route('/speak', methods=['POST'])
def speak():
    """
    Convert text to speech.

    POST /speak
    Body: {"text": "Hello world", "voice": "fabio"}
    Returns: WAV audio file
    """
    try:
        data = request.get_json()
        text = data.get('text')
        voice = data.get('voice', 'fabio')

        if not text:
            return jsonify({"error": "Text required"}), 400

        audio_bytes = assistant.synthesize_speech(text, voice)

        return send_file(
            io.BytesIO(audio_bytes),
            mimetype='audio/wav',
            as_attachment=True,
            download_name='response.wav',
        )

    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """
    Full voice conversation turn.

    POST /chat
    Body: audio file + optional conversation history
    Returns: JSON with text + audio response
    """
    try:
        # Get audio
        if 'audio' in request.files:
            audio_bytes = request.files['audio'].read()
        else:
            audio_bytes = request.data

        # Get optional parameters
        voice = request.form.get('voice', 'fabio')
        # TODO: Handle conversation history from form data

        result = assistant.process_voice_input(
            audio_bytes=audio_bytes,
            voice=voice,
        )

        return jsonify({
            "success": True,
            "user_text": result['user_text'],
            "ai_text": result['ai_text'],
            "metrics": result['metrics'],
            # Note: Audio response is binary, encode as base64 for JSON
            "audio_base64": None,  # TODO: Add if needed
        })

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@app.route('/clone-voice', methods=['POST'])
def clone_voice():
    """
    Clone a new voice from reference audio.

    POST /clone-voice
    Body: {"voice_name": "fabio", "audio": file}
    """
    try:
        voice_name = request.form.get('voice_name')
        if not voice_name:
            return jsonify({"error": "voice_name required"}), 400

        if 'audio' not in request.files:
            return jsonify({"error": "audio file required"}), 400

        audio_bytes = request.files['audio'].read()

        assistant.initialize_modal()
        result = assistant.tts.clone_voice.remote(voice_name, audio_bytes)

        return jsonify({
            "success": True,
            "voice_name": result['voice_name'],
            "duration": result['duration'],
        })

    except Exception as e:
        logger.error(f"Voice cloning error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Run development server
    debug_mode = getattr(settings, 'DEBUG', True) if settings else True

    print("=" * 60)
    print("Premier Voice Assistant - Starting...")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /health          - Health check")
    print("  POST /transcribe      - Audio → Text")
    print("  POST /speak           - Text → Audio")
    print("  POST /chat            - Full voice conversation")
    print("  POST /clone-voice     - Clone a new voice")
    print("\n" + "=" * 60)

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=debug_mode,
    )
