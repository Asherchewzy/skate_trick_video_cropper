# Architecture

## Overview
- Purpose: detect when a skater is in motion in long raw videos, cut those regions, and build a highlight reel per upload.
- Runtime shape: a FastAPI web server handles uploads/serves the UI, Redis acts as both Celery broker/result backend and lightweight job store, and Celery workers run CPU/GPU-heavy video work. A static frontend polls job status and surfaces download links.
- Storage layout: paths live under `DATA_ROOT` (default repo root, containers set `/data` via a volume) with `uploads/{job_id}` for incoming originals, `processing/{job_id}` for converted/temporary MP4s, `downloads/{job_id}` for compiled highlights. Temporary and original files are deleted after processing finishes.

## Components
- **API/UI (FastAPI)** — `src/main.py`
  - Serves `static/index.html` + assets.
  - Streaming upload endpoints (`/api/upload`, `/api/upload/batch`) write files to `uploads/` in chunks to avoid memory spikes.
  - Status/download endpoints read job state from Redis and return compiled artifacts.
- **Job store (Redis)** — `src/job_store.py`
  - Persists per-job + per-file status, messages, and result paths under keys `job:{job_id}`.
  - Derives aggregate batch status from item states (queued/processing/completed/failed) so the UI can display progress.
- **Worker queue (Celery + Redis)** — `src/celery_app.py`, `src/tasks.py`
  - Celery uses Redis for broker + result backend; workers listen for `process_video_file` tasks.
  - Each upload schedules one task; concurrency controlled by `CELERY_CONCURRENCY`/`CELERY_POOL`.
- **Video processing pipeline** — `src/video_processor.py`
  - `prepare_video_file`: converts non-MP4 inputs to MP4 via ffmpeg (yuv420p, faststart), optionally downscaling (`POSE_TARGET_HEIGHT`) and/or reducing FPS (`POSE_TARGET_FPS`) to speed pose detection.
  - `detect_human_segments`: runs MediaPipe Pose on frames, calculating average landmark deltas; marks a segment when movement exceeds `POSE_MOVEMENT_THRESHOLD` for at least `min_moving_frames`, closes once stationary for `max_stationary_frames`, then merges nearby segments.
  - `extract_and_compile`: buffers [-2s, +3s] around each segment, trims with MoviePy, concatenates, and writes the highlight MP4.
- **Frontend** — `static/js/app.js`
  - Drag/drop multi-upload UI; posts to `/api/upload/batch`, polls `/api/status/{job_id}` every 2s, shows per-file state, and renders download links from `download_url` in job items.

## Data flow
1. User opens `/` → static UI served from `static/`.
2. Upload request (`/api/upload/batch`) streams files to `uploads/{job_id}/{file_id}_{filename}` in chunks of `UPLOAD_CHUNK_SIZE`.
3. API seeds Redis job record with items (status=queued) and enqueues one Celery task per file.
4. Worker pulls task:
   - Marks item `processing` in Redis.
   - Ensures per-job `processing/` and `downloads/` directories exist.
   - Converts to MP4 if needed (`prepare_video_file`).
   - Runs pose-based motion detection to produce segments. No segments → marks `failed`.
   - Compiles buffered subclips to `downloads/{job_id}/{file_id}.mp4`; updates item to `completed` with `download_url` and `result_path`.
5. API status endpoint returns the cached job state; UI polls and reacts to `completed` or `failed`.
6. Download endpoint streams the compiled MP4 from disk; filenames returned as `highlight_{original}`.
7. Cleanup: worker deletes the uploaded source and the normalized intermediate clip once the task finishes.

## Deployment/runtime notes
- Start stack locally with `scripts/dev_up.sh` (activates `.venv`, launches Redis if using the default URL, starts Celery worker, starts uvicorn on `PORT`).
- Docker: multi-stage `Dockerfile` builds a non-root image with ffmpeg + dependencies; `docker-compose.yml` brings up API, worker, and Redis with shared `/data` storage (volume-backed).
- Required system deps: ffmpeg, Redis; Python libs in `requirements.txt` (FastAPI, Celery, Redis client, MediaPipe, OpenCV, MoviePy).
- Env vars: `REDIS_URL`, `PORT`, `CELERY_CONCURRENCY`, `CELERY_POOL`, `UPLOAD_CHUNK_SIZE`, `POSE_MOVEMENT_THRESHOLD`, `POSE_TARGET_HEIGHT`, `POSE_TARGET_FPS`, `DATA_ROOT` (plus optional overrides for `STATIC_DIR`/`UPLOAD_DIR`/`PROCESSING_DIR`/`DOWNLOAD_DIR`).
- Scaling: add more Celery workers/hosts pointing to the same Redis; ensure shared disk or persisted object storage for `downloads/` if running multiple nodes. Uvicorn can be fronted by a reverse proxy (e.g., nginx) for TLS/static caching.

## Reliability/observability
- Status durability comes from Redis; API/worker restarts keep job progress as long as Redis is up.
- Minimal error paths: ffmpeg/MediaPipe exceptions mark items `failed`; aggregated batch status reflects partial failures.
- No built-in metrics/log aggregation; rely on worker logs and web server logs. Consider adding structured logging and tracing if needed.

---------------------


## Scaling and GCP deployment plan
- **Containerization**: build two images (API/UI + worker) from the same repo; push to Artifact Registry. Static assets stay in the API image.
- **Compute on GKE**: create a GKE cluster with:
  - Workload identity enabled (avoid node service account keys).
  - One node pool for API pods (CPU only) behind an Ingress + HTTPS Load Balancer; another node pool for Celery workers (optionally GPU-enabled if MediaPipe benefits).
  - Horizontal Pod Autoscaler for API (requests-driven) and for workers (queue depth or custom metrics).
- **Stateful services**: replace local Redis with Cloud Memorystore (Redis) and point `REDIS_URL` at it. Use Cloud Storage buckets for `uploads/`, `processing/`, and `downloads/` instead of node disks; use signed URLs for uploads/downloads to avoid serving big files through the API pods.
- **Network and ingress**: expose FastAPI via an Ingress with managed certs; restrict worker + Redis access with VPC-native GKE + firewall rules; optionally add Cloud Armor for basic WAF/rate limits.
- **CI/CD**: Cloud Build to build/push images on main; deploy via GitHub Actions/Cloud Deploy applying vetted manifests/Helm chart. Include migrations/hooks to seed buckets.
- **Video segmentation strategy**: during processing each video is effectively broken into logical parts by pose-based movement detection—segments start when movement exceeds the threshold and end after sustained stillness, then buffers are added and subclips compiled. For higher throughput, we can also shard the video into fixed-length chunks (e.g., 30–60s with 2–3s overlap) and run pose detection in parallel worker tasks, merging adjacent detections post-hoc to preserve continuity.
- **Reliability**: use liveness/readiness probes on API and workers; set resource requests/limits to avoid node pressure; enable pod disruption budgets for the API to keep endpoints available during upgrades.

## Future improvements
- Move media to Cloud Storage with signed URLs and resumable uploads for large files; store only metadata in Redis.
- GPU-aware worker pool for faster pose inference where supported; autoscale that pool on queue depth.
- Structured logging and tracing (e.g., OpenTelemetry) plus metrics (queue depth, task latency, segment counts) surfaced to Cloud Monitoring.
- Smarter chunk-level parallelism with overlap handling and dedupe to accelerate long videos.
- Add basic auth or API keys for uploads/downloads; enforce max file size and MIME validation server-side.
- Retry/backoff around ffmpeg/IO failures and isolate per-job temp space to simplify cleanup.

---------------------

# Suggest building in layers so you can test each piece early:

- Start with the video-processing pipeline in isolation: read a clip, run pose detection, extract segments, compile a highlight. Get CLI scripts working and tuned thresholds.
- Add a minimal job model/state (in-memory or a simple Redis schema) to track per-file status and messages.
- Wrap the pipeline in a worker (Celery or alternatives) that consumes tasks and updates job state; add error handling and cleanup.
- Expose a minimal API (FastAPI) for upload/status/download; wire it to enqueue worker tasks and serve a static test page.
- Build the frontend to upload multiple files and poll status; keep it simple first, then polish UX.
- Add persistence/infra plumbing: bucket/disk layout, Redis/queue config, environment variables, startup scripts.
- Finish with observability and hardening: logging, metrics on queue depth and task latency, health checks, auth/rate limits, retries/backoff, and deployment manifests (e.g., Docker, Helm).
