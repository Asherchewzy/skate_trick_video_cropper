"""Celery tasks for per-file video processing."""

from pathlib import Path

from .celery_app import celery_app
from . import settings
from .job_store import job_store
from .video_processor import VideoProcessor

processor = VideoProcessor()


@celery_app.task(name="process_video_file")
def process_video_file(
    job_id: str,
    file_id: str,
    upload_path: str,
    filename: str,
) -> None:
    """Process a single uploaded video file and update job status."""
    prepared_path: Path | None = None
    upload_path = Path(upload_path)
    processing_dir = settings.PROCESSING_DIR / job_id
    downloads_dir = settings.DOWNLOAD_DIR / job_id

    try:
        job_store.update_item(
            job_id, file_id, status="processing", message="Preparing video..."
        )

        processing_dir.mkdir(parents=True, exist_ok=True)
        downloads_dir.mkdir(parents=True, exist_ok=True)

        prepared_path = Path(
            processor.prepare_video_file(
                str(upload_path), str(processing_dir), job_id=file_id
            )
        )

        job_store.update_item(
            job_id, file_id, message="Detecting moving humans..."
        )

        segments = processor.detect_human_segments(
            str(prepared_path), movement_threshold=settings.POSE_MOVEMENT_THRESHOLD
        )
        if not segments:
            job_store.update_item(
                job_id,
                file_id,
                status="failed",
                message="No moving humans detected.",
            )
            return

        job_store.update_item(
            job_id,
            file_id,
            message=f"Found {len(segments)} segments. Compiling...",
        )

        output_path = downloads_dir / f"{file_id}.mp4"
        result_path = processor.extract_and_compile(
            str(prepared_path), segments, str(output_path)
        )

        if result_path:
            job_store.update_item(
                job_id,
                file_id,
                status="completed",
                message="Processing complete!",
                download_url=f"/api/download/{job_id}/{file_id}",
                result_path=str(result_path),
            )
        else:
            job_store.update_item(
                job_id, file_id, status="failed", message="Failed to compile video."
            )

    except Exception as e:  # pragma: no cover - safety net
        job_store.update_item(
            job_id, file_id, status="failed", message=str(e)
        )
    finally:
        if upload_path.exists():
            upload_path.unlink()
        if prepared_path and prepared_path.exists() and prepared_path != upload_path:
            prepared_path.unlink()
