"""Celery tasks for per-file video processing."""

from pathlib import Path  # path handling for file locations
from shutil import rmtree  # cleanup helper

from .celery_app import celery_app  # the shared Celery app instance
from . import settings  # configuration constants
from .job_store import job_store  # Redis-backed status helper
from .video_processor import VideoProcessor  # heavy lifting for video work

# Reuse one processor per worker process to avoid reloading models
processor = VideoProcessor()


@celery_app.task(name="process_video_file")  # register this function as a Celery task
def process_video_file(
    job_id: str,
    file_id: str,
    upload_path: str,
    filename: str,
) -> None:
    """Process a single uploaded video file and update job status."""
    prepared_path: Path | None = None  # placeholder for converted file
    upload_path = Path(upload_path)  # original upload location
    processing_dir = settings.PROCESSING_DIR / job_id  # temp work dir per job
    downloads_dir = settings.DOWNLOAD_DIR / job_id  # final output dir per job

    try:
        # Update Redis-backed status store so the API can report progress
        job_store.update_item(
            job_id, file_id, status="processing", message="Preparing video..."
        )

        processing_dir.mkdir(parents=True, exist_ok=True)  # make sure temp dir exists
        downloads_dir.mkdir(parents=True, exist_ok=True)  # make sure output dir exists

        # Convert to mp4 if needed so later steps handle a consistent format
        prepared_path = Path(
            processor.prepare_video_file(
                str(upload_path),
                str(processing_dir),
                job_id=file_id,
                target_height=settings.POSE_TARGET_HEIGHT,
                target_fps=settings.POSE_TARGET_FPS,
            )
        )

        # Update message so the UI knows we're starting detection
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

        # Let the UI know how many highlights we found before compiling
        job_store.update_item(
            job_id,
            file_id,
            message=f"Found {len(segments)} segments. Compiling...",
        )

        output_path = downloads_dir / f"{file_id}.mp4"  # where the highlight file will go
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

    except Exception as e:  # pragma: no cover - safety net to keep worker alive
        job_store.update_item(
            job_id, file_id, status="failed", message=str(e)
        )
    finally:
        # Clean up both the raw upload and any intermediate conversions
        if upload_path.exists():
            upload_path.unlink()
        if prepared_path and prepared_path.exists() and prepared_path != upload_path:
            prepared_path.unlink()
        _maybe_cleanup_job_dirs(job_id)


def _maybe_cleanup_job_dirs(job_id: str) -> None:
    """Remove per-job upload/processing folders once all items are finished."""
    job = job_store.get_job(job_id)
    if not job:
        return

    items = job.get("items", [])
    if not items:
        return

    terminal = {"completed", "failed"}
    if all(i.get("status") in terminal for i in items):
        for path in (
            settings.UPLOAD_DIR / job_id,
            settings.PROCESSING_DIR / job_id,
        ):
            if path.exists():
                rmtree(path, ignore_errors=True)
