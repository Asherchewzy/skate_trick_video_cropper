# Skate Trick Detection Web App - Technical Specification

## Project Overview
A web application that automatically detects when a skater enters and exits the frame in uploaded videos, extracts those segments with 2-second buffers, and creates a compiled highlight reel.

## Core Functionality
- Upload video files from mobile browsers (iPhone focus)
- Detect human presence entering/exiting frame
- Extract 2s before entry + trick duration + 2s after exit
- Handle multiple trick instances per video
- Compile all segments into single downloadable video

## System Architecture

### Frontend (Minimalistic Web Interface)
- Single page application
- HTML5 + CSS + Vanilla JavaScript
- Responsive design for mobile browsers
- Components:
  - Video upload interface with drag/drop
  - Progress indicator during processing
  - Video preview player
  - Download button for final compilation

### Backend (Python)
- FastAPI web server
- Video processing pipeline
- RESTful API endpoints
- File management system

## Technical Stack

### Backend Dependencies
```
- Python 3.9+
- OpenCV (cv2) - Video processing and human detection
- FFmpeg - Video manipulation and encoding
- Flask/FastAPI - Web framework
- Celery + Redis - Background job processing
- YOLO or MediaPipe - Human detection model
- Pillow - Image processing
- Gunicorn - WSGI server
```

### Frontend Dependencies
```
- HTML5 File API
- Fetch API for uploads
- CSS Grid/Flexbox
- Minimal JavaScript (no frameworks)
```

## API Specification

### Endpoints

#### POST /api/upload
- Accept video file upload
- Return job ID for processing tracking
- File size limit: 2GB
- Supported formats: MP4, MOV, AVI

#### GET /api/status/{job_id}
- Return processing status
- Response: `{"status": "processing|completed|failed", "progress": 75, "message": "Detecting humans..."}`

#### GET /api/download/{job_id}
- Download compiled video file
- Return 404 if not ready

#### GET /api/preview/{job_id}
- Return detected segments metadata
- Response: `{"segments": [{"start": 10.5, "end": 15.2, "confidence": 0.95}]}`

## Processing Pipeline

### 1. Video Upload & Validation
```python
def validate_video(file):
    # Check file format, size, duration
    # Basic video integrity check
    pass
```

### 2. Human Detection
```python
def detect_human_segments(video_path):
    # Load YOLO/MediaPipe model
    # Process frame by frame
    # Identify entry/exit points
    # Return list of (entry_time, exit_time) tuples
    pass
```

### 3. Video Segmentation
```python
def extract_segments(video_path, segments):
    # For each segment:
    #   - Calculate start_time = entry_time - 2s
    #   - Calculate end_time = exit_time + 2s
    #   - Extract using FFmpeg
    # Return list of segment file paths
    pass
```

### 4. Video Compilation
```python
def compile_segments(segment_files):
    # Use FFmpeg to concatenate segments
    # Apply consistent encoding settings
    # Return final video path
    pass
```

## File Structure
```
Skate_app/
├── app.py                 # Main Flask application
├── models/
│   ├── human_detector.py  # YOLO/MediaPipe wrapper
│   └── video_processor.py # Video manipulation logic
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── index.html
├── uploads/               # Temporary uploaded files
├── processing/            # Intermediate processing files
├── downloads/             # Final compiled videos
├── requirements.txt
└── config.py
```

## Frontend Interface Design

### Upload Page
```html
<!-- Minimalistic upload interface -->
<div class="upload-container">
    <h1>Skate Trick Detector</h1>
    <div class="upload-zone" id="dropZone">
        <p>Drop video here or click to select</p>
        <input type="file" id="videoInput" accept="video/*">
    </div>
    <div class="progress-container" id="progressContainer" style="display:none;">
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        <p id="statusText">Uploading...</p>
    </div>
    <div class="result-container" id="resultContainer" style="display:none;">
        <video id="previewVideo" controls></video>
        <button id="downloadBtn">Download Highlight Reel</button>
    </div>
</div>
```

### CSS (Mobile-First)
```css
/* Responsive, clean design */
.upload-container {
    max-width: 400px;
    margin: 20px auto;
    padding: 20px;
}

.upload-zone {
    border: 2px dashed #ccc;
    border-radius: 10px;
    padding: 40px 20px;
    text-align: center;
    cursor: pointer;
}

.progress-bar {
    width: 100%;
    height: 10px;
    background: #f0f0f0;
    border-radius: 5px;
    overflow: hidden;
}
```

## Configuration

### Environment Variables
```
UPLOAD_FOLDER=/path/to/uploads
MAX_FILE_SIZE=2GB
REDIS_URL=redis://localhost:6379
MODEL_PATH=/path/to/yolo/weights
FFMPEG_PATH=/usr/local/bin/ffmpeg
```

### Detection Parameters
```python
DETECTION_CONFIG = {
    'confidence_threshold': 0.5,
    'buffer_seconds': 2.0,
    'min_segment_duration': 1.0,
    'max_segments_per_video': 10
}
```

## Deployment Setup

### Mac Server Configuration
1. Install Python dependencies: `pip install -r requirements.txt`
2. Install FFmpeg: `brew install ffmpeg`
3. Download YOLO weights or setup MediaPipe
4. Configure port forwarding on router (port 5000)
5. Run with: `gunicorn -w 4 -b 0.0.0.0:5000 app:app`

### Security Considerations
- File upload size limits
- File type validation
- Temporary file cleanup
- Rate limiting for uploads
- Basic authentication (optional)

## Performance Expectations
- Video upload: 2-15 minutes (depending on size/connection, up to 2GB files)
- Processing time: 2-3x video duration
- Maximum video length: 30 minutes (with 2GB limit)
- Concurrent users: 3-5 (single Mac server, due to larger file processing)

## Error Handling
- Invalid file format → User-friendly error message
- Processing timeout → Graceful failure with retry option
- Server overload → Queue system with wait times
- Network issues → Resume upload capability

## Future Enhancements (Optional)
- Multiple sport detection (surfing, snowboarding)
- Advanced trick classification
- Social sharing features
- Cloud deployment option
- Batch processing for multiple videos

## Testing Strategy
- Unit tests for detection accuracy
- Integration tests for full pipeline
- Mobile browser compatibility testing
- Load testing with multiple concurrent uploads
- Video quality validation tests