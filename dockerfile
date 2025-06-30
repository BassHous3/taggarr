# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (pymediainfo requires mediainfo)
RUN apt-get update && \
    apt-get install -y --no-install-recommends mediainfo && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py /app/  

# Default environment variables (override in CasaOS)
ENV SONARR_API_KEY=""
ENV SONARR_URL="http://192.168.0.1:8989"
ENV ROOT_TV_PATH="/tv"
ENV RUN_INTERVAL_SECONDS="7200"
ENV START_RUNNING="true"
ENV QUICK_MODE="false"
ENV DRY_RUN="false"
ENV WRITE_MODE="0"
ENV TAG_DUB="dub"
ENV TAG_SEMI="semi-dub"
ENV TAG_WRONG_DUB="wrong-dub"
ENV LOG_LEVEL="INFO"
ENV TARGET_LANGUAGES="english"

# Entrypoint
CMD ["python", "main.py"]

