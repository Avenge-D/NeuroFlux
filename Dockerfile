FROM python:3.12-slim

WORKDIR /app

# ── System dependencies ────────────────────────────────────────────────────────
# ffmpeg        : video rendering / stitching
# libgl1        : OpenCV dependency pulled in by instagrapi
# build-essential / libffi-dev / libssl-dev : compile C-extension packages
#   (pycryptodome, cryptography used by instagrapi)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Non-root user for security ─────────────────────────────────────────────────
RUN addgroup --system appgroup && adduser --system --group appuser

# ── Application code ───────────────────────────────────────────────────────────
COPY . /app
RUN chown -R appuser:appgroup /app

USER appuser

# Disable Python output buffering so structured logs appear in real time
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "orchestrator"]
