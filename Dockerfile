FROM python:3.11-slim

# Build cache buster: 2025-12-31-v1 (add gcc for webrtcvad)
WORKDIR /app

# Install system dependencies
# - build-essential, gcc: Required for compiling webrtcvad (resemblyzer dependency)
# - ffmpeg, libopus0: Audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    ffmpeg \
    libopus0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir 'livekit-agents[deepgram,cartesia,openai,silero]==1.3.8'

# Copy application code
COPY . .

# Download turn detector model (ONNX file for smarter turn-taking)
RUN python backend/livekit_agent.py download-files

# Start script handles SERVICE_TYPE routing
CMD ["bash", "start.sh"]