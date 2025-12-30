FROM python:3.11-slim

# Build cache buster: 2025-12-18-v2
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir 'livekit-agents[deepgram,cartesia,openai,silero]==1.3.8'

# Download turn detector model (ONNX file for smarter turn-taking)
RUN python -c "from livekit.plugins.turn_detector import EOUModel; EOUModel().initialize()" || echo "Turn detector model download skipped"

# Copy application code
COPY . .

# Start script handles SERVICE_TYPE routing
CMD ["bash", "scripts/start.sh"]
