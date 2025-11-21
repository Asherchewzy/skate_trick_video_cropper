# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies for ffmpeg/OpenCV/MediaPipe
RUN set -eux; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6; \
    rm -rf /var/lib/apt/lists/*

# Non-root user for runtime
RUN groupadd -r app && useradd -r -g app app

FROM base AS builder

RUN python -m venv /venv
ENV PATH="/venv/bin:${PATH}"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

FROM base AS runtime

ENV PATH="/venv/bin:${PATH}" \
    DATA_ROOT=/data

WORKDIR /app

COPY --from=builder /venv /venv
COPY --chown=app:app . .

# Persistent volume for uploads/processing/downloads
RUN mkdir -p /data/uploads /data/processing /data/downloads && chown -R app:app /data

USER app
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
