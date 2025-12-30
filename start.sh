#!/bin/bash
set -e

# Default PORT if not set
if [ -z "$PORT" ]; then
    PORT=8000
fi

if [ "$SERVICE_TYPE" = "worker" ]; then
    echo "Starting LiveKit Worker..."
    exec python backend/livekit_worker.py start
else
    echo "Starting Web Server on port $PORT..."
    exec uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
fi
