web: /app/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: /app/venv/bin/python backend/livekit_worker.py start
