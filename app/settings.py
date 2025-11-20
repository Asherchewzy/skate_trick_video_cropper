"""Shared configuration constants for server and worker processes."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSING_DIR = BASE_DIR / "processing"
DOWNLOAD_DIR = BASE_DIR / "downloads"

# Upload streaming chunk size (bytes)
CHUNK_SIZE = int(os.getenv("UPLOAD_CHUNK_SIZE", 8 * 1024 * 1024))

# Pose motion threshold to consider a person "moving"
POSE_MOVEMENT_THRESHOLD = float(os.getenv("POSE_MOVEMENT_THRESHOLD", "0.02"))

# Redis broker/result backend for Celery and job state
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
