"""FastAPI app wiring upload, processing, and download endpoints."""

import uuid
from typing import Any, Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import settings
from .job_store import job_store
from .tasks import process_video_file

app = FastAPI()
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

for directory in (settings.UPLOAD_DIR, settings.PROCESSING_DIR, settings.DOWNLOAD_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def read_root():
    """Serve the landing page."""
    return FileResponse(settings.STATIC_DIR / "index.html")


async def _handle_uploads(files: List[UploadFile]) -> Dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    job_id = str(uuid.uuid4())
    upload_dir = settings.UPLOAD_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    items: List[Dict[str, Any]] = []
    task_payloads: List[Dict[str, str]] = []
    for upload in files:
        file_id = str(uuid.uuid4())
        filename = upload.filename or "upload"
        destination = upload_dir / f"{file_id}_{filename}"

        with open(destination, "wb") as buffer:
            while True:
                chunk = upload.file.read(settings.CHUNK_SIZE)
                if not chunk:
                    break
                buffer.write(chunk)

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
        task_payloads.append(
            {
                "file_id": file_id,
                "upload_path": str(destination),
                "filename": filename,
            }
        )

    job_store.create_job(job_id, items)

    for task_args in task_payloads:
        process_video_file.delay(
            job_id, task_args["file_id"], task_args["upload_path"], task_args["filename"]
        )

    return {"job_id": job_id, "items": [{"file_id": i["file_id"], "filename": i["filename"]} for i in items]}


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Accept a single upload, enqueue processing, and return the job id."""
    return await _handle_uploads([file])


@app.post("/api/upload/batch")
async def upload_batch(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    """Accept multiple uploads, enqueue processing for each, and return the batch job id."""
    return await _handle_uploads(files)


@app.get("/api/status/{job_id}")
async def get_status(job_id: str) -> Dict[str, Any]:
    """Return the batch + item status for a given job id."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/download/{job_id}/{file_id}")
async def download_video_file(job_id: str, file_id: str) -> FileResponse:
    """Send a compiled highlight clip for a specific file within a batch."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    item = next((i for i in job["items"] if i["file_id"] == file_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="File not found in job")
    if item.get("status") != "completed" or not item.get("result_path"):
        raise HTTPException(status_code=400, detail="Video not ready")

    return FileResponse(item["result_path"], filename=f"highlight_{item['filename']}")


@app.get("/api/download/{job_id}")
async def download_first_completed(job_id: str) -> FileResponse:
    """Backward-compatible download of the first completed item in a batch."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    item = next((i for i in job["items"] if i.get("status") == "completed"), None)
    if not item or not item.get("result_path"):
        raise HTTPException(status_code=400, detail="No completed videos")

    return FileResponse(item["result_path"], filename=f"highlight_{item['filename']}")
