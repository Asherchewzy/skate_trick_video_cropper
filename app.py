import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from video_processor import VideoProcessor

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuration
UPLOAD_DIR = "uploads"
PROCESSING_DIR = "processing"
DOWNLOAD_DIR = "downloads"

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSING_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# In-memory job store
jobs = {}

processor = VideoProcessor()

def process_video(job_id: str, file_path: str):
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["message"] = "Detecting humans..."
        
        # Detect segments
        segments = processor.detect_human_segments(file_path)
        
        if not segments:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["message"] = "No humans detected in video."
            return

        jobs[job_id]["message"] = f"Found {len(segments)} segments. Compiling..."
        
        # Compile video
        output_filename = f"highlight_{job_id}.mp4"
        output_path = os.path.join(DOWNLOAD_DIR, output_filename)
        
        result_path = processor.extract_and_compile(file_path, segments, output_path)
        
        if result_path:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["message"] = "Processing complete!"
            jobs[job_id]["download_url"] = f"/api/download/{job_id}"
            jobs[job_id]["result_path"] = result_path
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["message"] = "Failed to compile video."
            
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = str(e)
        print(f"Error processing job {job_id}: {e}")
    finally:
        # Cleanup upload
        if os.path.exists(file_path):
            os.remove(file_path)

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.post("/api/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    jobs[job_id] = {
        "status": "queued",
        "message": "Video uploaded. Starting processing...",
        "filename": file.filename
    }
    
    background_tasks.add_task(process_video, job_id, file_path)
    
    return {"job_id": job_id}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video not ready")
        
    return FileResponse(job["result_path"], filename=f"highlight_{job['filename']}")
