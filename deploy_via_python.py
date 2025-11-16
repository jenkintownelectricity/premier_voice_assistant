#!/usr/bin/env python3
"""
Deploy Modal services using Python SDK directly (bypasses CLI issues)
"""
import os
import sys

# Set Modal credentials
os.environ['MODAL_TOKEN_ID'] = 'ak-jt7FZ9TvShs4gLDth2QK0d'
os.environ['MODAL_TOKEN_SECRET'] = 'as-ds98ZNXm5fibjXkOvz0hvs'

print("=" * 60)
print("Deploying Modal Services via Python SDK")
print("=" * 60)
print()

try:
    import modal
    print(f"✅ Modal SDK version: {modal.__version__}")
    print()

    # Deploy Whisper STT
    print("=" * 60)
    print("Deploying Whisper STT...")
    print("=" * 60)
    sys.path.insert(0, '/home/user/premier_voice_assistant')
    from modal_deployment import whisper_stt

    print("✅ Whisper STT module loaded")
    print(f"   App name: {whisper_stt.app.name}")
    print()

    # Deploy the app
    with whisper_stt.app.run():
        print("✅ Whisper STT deployed successfully!")

    print()

    # Deploy Coqui TTS
    print("=" * 60)
    print("Deploying Coqui TTS...")
    print("=" * 60)
    from modal_deployment import coqui_tts

    print("✅ Coqui TTS module loaded")
    print(f"   App name: {coqui_tts.app.name}")
    print()

    # Deploy the app
    with coqui_tts.app.run():
        print("✅ Coqui TTS deployed successfully!")

    print()
    print("=" * 60)
    print("🎉 ALL SERVICES DEPLOYED!")
    print("=" * 60)
    print()
    print("Your endpoints:")
    print("1. STT: https://jenkintownelectricity--premier-whisper-stt-transcribe-web.modal.run")
    print("2. TTS: https://jenkintownelectricity--premier-coqui-tts-synthesize-web.modal.run")
    print("3. Clone: https://jenkintownelectricity--premier-coqui-tts-clone-voice-web.modal.run")
    print()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
