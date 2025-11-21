"""Shared configuration constants for server and worker processes."""

from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (one above src/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Validated configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # File system configuration
    BASE_DIR: Path = Field(PROJECT_ROOT, alias="BASE_DIR")  # backwards-compatible alias
    DATA_ROOT: Path = Field(PROJECT_ROOT, alias="DATA_ROOT")  # where uploads/processing/downloads live
    STATIC_DIR: Path | None = Field(None, alias="STATIC_DIR")
    UPLOAD_DIR: Path | None = Field(None, alias="UPLOAD_DIR")
    PROCESSING_DIR: Path | None = Field(None, alias="PROCESSING_DIR")
    DOWNLOAD_DIR: Path | None = Field(None, alias="DOWNLOAD_DIR")

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

    @model_validator(mode="after")
    def derive_paths(self):
        """Fill in path defaults and normalize input to Path instances."""
        data_root = Path(self.DATA_ROOT).resolve()
        self.DATA_ROOT = data_root
        self.BASE_DIR = Path(self.BASE_DIR).resolve()

        self.STATIC_DIR = Path(self.STATIC_DIR) if self.STATIC_DIR else PROJECT_ROOT / "static"
        self.UPLOAD_DIR = Path(self.UPLOAD_DIR) if self.UPLOAD_DIR else data_root / "uploads"
        self.PROCESSING_DIR = Path(self.PROCESSING_DIR) if self.PROCESSING_DIR else data_root / "processing"
        self.DOWNLOAD_DIR = Path(self.DOWNLOAD_DIR) if self.DOWNLOAD_DIR else data_root / "downloads"
        return self


settings = Settings()
