"""FastAPI app wiring upload, processing, and download endpoints."""

import shutil
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .video_processor import VideoProcessor

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSING_DIR = BASE_DIR / "processing"
DOWNLOAD_DIR = BASE_DIR / "downloads"

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

for directory in (UPLOAD_DIR, PROCESSING_DIR, DOWNLOAD_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# In-memory job store
jobs: Dict[str, Dict[str, Any]] = {}

processor = VideoProcessor()


def process_video(job_id: str, file_path: Path) -> None:
    """Run detection/compilation for a single upload and update job metadata."""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["message"] = "Detecting humans..."

        # Detect segments
        segments = processor.detect_human_segments(str(file_path))

        if not segments:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["message"] = "No humans detected in video."
            return

        jobs[job_id]["message"] = f"Found {len(segments)} segments. Compiling..."

        # Compile video
        output_filename = f"highlight_{job_id}.mp4"
        output_path = DOWNLOAD_DIR / output_filename

        result_path = processor.extract_and_compile(
            str(file_path), segments, str(output_path)
        )

        if result_path:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["message"] = "Processing complete!"
            jobs[job_id]["download_url"] = f"/api/download/{job_id}"
            jobs[job_id]["result_path"] = str(result_path)
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["message"] = "Failed to compile video."

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = str(e)
        print(f"Error processing job {job_id}: {e}")
    finally:
        # Cleanup upload
        if file_path.exists():
            file_path.unlink()


@app.get("/")
async def read_root():
    """Serve the landing page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/upload")
async def upload_video(
    background_tasks: BackgroundTasks, file: UploadFile = File(...)
) -> Dict[str, str]:
    """Accept an upload, enqueue processing, and return the job id."""
    job_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    jobs[job_id] = {
        "status": "queued",
        "message": "Video uploaded. Starting processing...",
        "filename": file.filename,
    }

    background_tasks.add_task(process_video, job_id, file_path)

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str) -> Dict[str, Any]:
    """Return the status for a given job id."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/api/download/{job_id}")
async def download_video(job_id: str) -> FileResponse:
    """Send the compiled highlight reel if the job finished successfully."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video not ready")

    return FileResponse(job["result_path"], filename=f"highlight_{job['filename']}")
