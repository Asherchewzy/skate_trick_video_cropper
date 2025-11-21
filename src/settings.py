"""Shared configuration constants for server and worker processes."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # project root (one above src/)
STATIC_DIR = BASE_DIR / "static"  # built frontend assets
UPLOAD_DIR = BASE_DIR / "uploads"  # where raw uploads are stored
PROCESSING_DIR = BASE_DIR / "processing"  # temp workspace for conversions
DOWNLOAD_DIR = BASE_DIR / "downloads"  # final highlight outputs


class Settings(BaseSettings):
    """Validated configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # File system paths exposed for convenience
    BASE_DIR: Path = BASE_DIR
    STATIC_DIR: Path = STATIC_DIR
    UPLOAD_DIR: Path = UPLOAD_DIR
    PROCESSING_DIR: Path = PROCESSING_DIR
    DOWNLOAD_DIR: Path = DOWNLOAD_DIR

    # Upload streaming chunk size (bytes)
    CHUNK_SIZE: int = Field(8 * 1024 * 1024, alias="UPLOAD_CHUNK_SIZE")

    # Pose configuration
    POSE_MOVEMENT_THRESHOLD: float = Field(0.01, alias="POSE_MOVEMENT_THRESHOLD")
    POSE_TARGET_HEIGHT: int | None = Field(720, alias="POSE_TARGET_HEIGHT")
    POSE_TARGET_FPS: float | None = Field(30.0, alias="POSE_TARGET_FPS")

    # Redis broker/result backend for Celery and job state
    REDIS_URL: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    @field_validator("POSE_TARGET_HEIGHT", "POSE_TARGET_FPS", mode="before")
    @classmethod
    def _zero_to_none(cls, value):
        """Treat 0 (or '0') as a request to disable the override."""
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return value
        return None if numeric == 0 else value


settings = Settings()
