# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies
# ffmpeg: Required for video processing and audio handling
# libsndfile1: Required by soundfile/torchaudio
# git: Required if any dependencies are installed from git
# build-essential: Required for compiling some python packages
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run gunicorn
# Timeout 600s accommodates Demucs model load (~2 min cold start) plus the
# longer-running TTS/sync work. Cloud Run --timeout caps the inbound HTTP
# request separately at 3600s; this is the per-worker request budget.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 600 app:app
