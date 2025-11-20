# Skate Trick Detector

A simple web application that automatically detects when a skater enters and exits the frame in uploaded videos, extracts those segments, and creates a compiled highlight reel.

![Screenshot](assets/ss.png)


## How human detection works

- The app uses [MediaPipe Pose](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker) via `mediapipe` to detect a person. Each frame is fed into the pose estimator, which returns pose landmarks when a human skeleton is visible.
- A human is considered present if pose landmarks are found; segments are started/stopped based on these detections as the video plays.
- Close detections are merged if gaps are <1s, and a 2s buffer is added before/after each detected segment to avoid abrupt cuts when compiling the final reel.

## Prerequisites

- `uv` (Python package installer)
- FFmpeg (installed via system package manager, e.g., `brew install ffmpeg` on macOS)

## Setup

1.  **Install dependencies:**

    ```bash
    uv venv .venv --python 3.11
    source .venv/bin/activate
    uv pip install -r requirements.txt
    ```

2.  **Run the server:**

    ```bash
    source .venv/bin/activate
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```

3.  **(Optional) Enable git hooks:**

    ```bash
    pip install pre-commit
    pre-commit install
    ```

## Usage

1.  Open your browser and navigate to `http://localhost:8000`.
2.  Upload a video file (e.g., `.mp4`, `.mov`).
3.  Wait for the processing to complete.
4.  Download the generated highlight reel.