"""Shared configuration constants for server and worker processes."""

import os  # read environment variables
from pathlib import Path  # build filesystem paths

# Paths commonly reused by the API and Celery worker
BASE_DIR = Path(__file__).resolve().parent.parent  # project root
STATIC_DIR = BASE_DIR / "static"  # built frontend assets
UPLOAD_DIR = BASE_DIR / "uploads"  # where raw uploads are stored
PROCESSING_DIR = BASE_DIR / "processing"  # temp workspace for conversions
DOWNLOAD_DIR = BASE_DIR / "downloads"  # final highlight outputs

# Upload streaming chunk size (bytes)
CHUNK_SIZE = int(os.getenv("UPLOAD_CHUNK_SIZE", 8 * 1024 * 1024))

# Pose motion threshold to consider a person "moving"
POSE_MOVEMENT_THRESHOLD = float(os.getenv("POSE_MOVEMENT_THRESHOLD", "0.01"))

# Optional pre-processing to speed up detection (transcode to lower res/FPS).
# Set to 0/None to leave source resolution/FPS unchanged.
POSE_TARGET_HEIGHT = int(os.getenv("POSE_TARGET_HEIGHT", "0")) or None
POSE_TARGET_FPS = float(os.getenv("POSE_TARGET_FPS", "0")) or None

# Redis broker/result backend for Celery and job state
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
