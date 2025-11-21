"""FastAPI app wiring upload, processing, and download endpoints."""

import uuid  # generate unique IDs for jobs/files
from typing import Any  # flexible payloads for job metadata

from fastapi import FastAPI, File, HTTPException, UploadFile  # FastAPI primitives
from fastapi.responses import FileResponse  # send files back to clients
from fastapi.staticfiles import StaticFiles  # serve built frontend assets

from . import settings  # shared config (paths, Redis URL, thresholds)
from .job_store import job_store  # Redis-backed job state
from .tasks import process_video_file  # Celery task to process uploads

app = FastAPI()  # main ASGI app instance
# Serve built frontend assets
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

# Ensure required directories exist on startup (shared with Celery worker)
for directory in (settings.UPLOAD_DIR, settings.PROCESSING_DIR, settings.DOWNLOAD_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def read_root():
    """Serve the landing page."""
    return FileResponse(settings.STATIC_DIR / "index.html")


async def _handle_uploads(files: list[UploadFile]) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Batch uploads are grouped by job_id so the UI can poll once for all
    job_id = str(uuid.uuid4())
    upload_dir = settings.UPLOAD_DIR / job_id  # each batch gets its own folder
    upload_dir.mkdir(parents=True, exist_ok=True)  # ensure it exists

    items: list[dict[str, Any]] = []  # data we persist for status
    task_payloads: list[dict[str, str]] = []  # args to send into Celery tasks
    for upload in files:
        file_id = str(uuid.uuid4())  # unique per file in the batch
        filename = upload.filename or "upload"  # original name (fallback if missing)
        destination = upload_dir / f"{file_id}_{filename}"  # where we save the upload

        with open(destination, "wb") as buffer:  # stream upload to disk in chunks
            while True:
                chunk = upload.file.read(settings.CHUNK_SIZE)  # read a chunk
                if not chunk:
                    break  # stop at EOF
                buffer.write(chunk)  # persist to disk

        # Record initial status for this file
        items.append(
            {
                "file_id": file_id,
                "filename": filename,
                "status": "queued",
                "message": "Queued",
                "download_url": None,
                "result_path": None,
            }
        )
        # Payload passed into Celery for processing
        task_payloads.append(
            {
                "file_id": file_id,
                "upload_path": str(destination),
                "filename": filename,
            }
        )

    job_store.create_job(job_id, items)

    # Kick work to Celery worker processes; .delay sends an async task
    for task_args in task_payloads:
        process_video_file.delay(
            job_id, task_args["file_id"], task_args["upload_path"], task_args["filename"]
        )

    return {"job_id": job_id, "items": [{"file_id": i["file_id"], "filename": i["filename"]} for i in items]}


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)) -> dict[str, Any]:
    """Accept a single upload, enqueue processing, and return the job id."""
    return await _handle_uploads([file])


@app.post("/api/upload/batch")
async def upload_batch(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Accept multiple uploads, enqueue processing for each, and return the batch job id."""
    return await _handle_uploads(files)


@app.get("/api/status/{job_id}")
async def get_status(job_id: str) -> dict[str, Any]:
    """Return the batch + item status for a given job id."""
    job = job_store.get_job(job_id)  # fetch from Redis
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/download/{job_id}/{file_id}")
async def download_video_file(job_id: str, file_id: str) -> FileResponse:
    """Send a compiled highlight clip for a specific file within a batch."""
    job = job_store.get_job(job_id)  # load job metadata
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    item = next((i for i in job["items"] if i["file_id"] == file_id), None)  # find the file
    if not item:
        raise HTTPException(status_code=404, detail="File not found in job")
    if item.get("status") != "completed" or not item.get("result_path"):
        raise HTTPException(status_code=400, detail="Video not ready")

    return FileResponse(item["result_path"], filename=f"highlight_{item['filename']}")


@app.get("/api/download/{job_id}")
async def download_first_completed(job_id: str) -> FileResponse:
    """Backward-compatible download of the first completed item in a batch."""
    job = job_store.get_job(job_id)  # retrieve job state
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    item = next((i for i in job["items"] if i.get("status") == "completed"), None)  # first success
    if not item or not item.get("result_path"):
        raise HTTPException(status_code=400, detail="No completed videos")

    return FileResponse(item["result_path"], filename=f"highlight_{item['filename']}")
