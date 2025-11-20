"""Video processing utilities for detecting humans and compiling highlights."""

import subprocess
from pathlib import Path
from typing import List, Sequence, Tuple

import cv2
import mediapipe as mp
from moviepy import VideoFileClip, concatenate_videoclips


class VideoProcessor:
    """Detect human presence in videos and compile buffered highlight reels."""

    def __init__(self):
        """Initialize pose detector."""
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def prepare_video_file(self, input_path: str, processing_dir: str, job_id: str) -> str:
        """Return an MP4 path for downstream work, converting MOV/others when needed."""
        input_path = Path(input_path)
        processing_dir = Path(processing_dir)
        processing_dir.mkdir(parents=True, exist_ok=True)

        if input_path.suffix.lower() == ".mp4":
            return str(input_path)

        output_path = processing_dir / f"{input_path.stem}_{job_id}.mp4"

        self._ffmpeg_convert_to_mp4(str(input_path), str(output_path))

        return str(output_path)

    def _ffmpeg_convert_to_mp4(self, src: str, dst: str) -> None:
        """Use ffmpeg to transcode while ignoring unknown streams."""
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-analyzeduration",
            "100M",
            "-probesize",
            "100M",
            "-i",
            src,
            "-ignore_unknown",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            dst,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"FFmpeg failed to convert file: {msg}")

    def detect_human_segments(
        self,
        video_path: str,
        movement_threshold: float = 0.02,
        min_moving_frames: int = 3,
        max_stationary_frames: int = 10,
    ) -> List[Tuple[float, float]]:
        """Return (start, end) segments where a human is detected *moving* in the video."""
        video_path = str(video_path)
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            cap.release()
            raise ValueError("Unable to read FPS from video.")
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps

        segments = []
        current_segment_start = None
        movement_start_time = None

        frame_idx = 0
        movement_frames = 0
        stationary_frames = 0
        previous_landmarks = None

        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break

            # Convert the BGR image to RGB.
            image.flags.writeable = False
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image)

            current_time = frame_idx / fps

            if results.pose_landmarks:
                current_landmarks = [
                    (lm.x, lm.y, lm.z) for lm in results.pose_landmarks.landmark
                ]
                movement_score = (
                    self._average_landmark_movement(current_landmarks, previous_landmarks)
                    if previous_landmarks
                    else 0.0
                )
                is_moving = movement_score >= movement_threshold
                previous_landmarks = current_landmarks
            else:
                is_moving = False
                previous_landmarks = None

            if is_moving:
                stationary_frames = 0
                movement_frames += 1
                if movement_start_time is None:
                    movement_start_time = current_time

                if current_segment_start is None and movement_frames >= min_moving_frames:
                    current_segment_start = movement_start_time
            else:
                movement_frames = 0
                movement_start_time = None
                if current_segment_start is not None:
                    stationary_frames += 1
                    if stationary_frames >= max_stationary_frames:
                        segments.append((current_segment_start, current_time))
                        current_segment_start = None
                        stationary_frames = 0

            frame_idx += 1

        if current_segment_start is not None:
            segments.append((current_segment_start, duration))

        cap.release()
        return self._merge_close_segments(segments)

    def _merge_close_segments(
        self, segments: Sequence[Tuple[float, float]], gap_threshold: float = 1.0
    ) -> List[Tuple[float, float]]:
        if not segments:
            return []

        merged = []
        current_start, current_end = segments[0]

        for i in range(1, len(segments)):
            next_start, next_end = segments[i]
            if next_start - current_end < gap_threshold:
                current_end = next_end
            else:
                merged.append((current_start, current_end))
                current_start, current_end = next_start, next_end

        merged.append((current_start, current_end))
        return merged

    def _average_landmark_movement(
        self,
        current_landmarks: Sequence[tuple],
        previous_landmarks: Sequence[tuple],
    ) -> float:
        """Average per-landmark displacement between frames."""
        if not current_landmarks or not previous_landmarks:
            return 0.0

        deltas = []
        for curr, prev in zip(current_landmarks, previous_landmarks):
            dx = curr[0] - prev[0]
            dy = curr[1] - prev[1]
            dz = curr[2] - prev[2]
            deltas.append((dx * dx + dy * dy + dz * dz) ** 0.5)

        return sum(deltas) / len(deltas)

    def extract_and_compile(
        self,
        video_path: str,
        segments: Sequence[Tuple[float, float]],
        output_path: str,
        buffer_before: float = 2.0,
        buffer_after: float = 3.0,
    ) -> str | None:
        """Compile buffered subclips for detected segments and write to output_path."""
        video_path = str(video_path)
        output_path = str(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if not segments:
            return None

        clip = VideoFileClip(video_path)
        subclips = []

        for start, end in segments:
            # Add buffer
            start_time = max(0, start - buffer_before)
            end_time = min(clip.duration, end + buffer_after)

            # Avoid extremely short clips
            if end_time - start_time < 1.0:
                continue

            subclip = clip.subclipped(start_time, end_time)
            subclips.append(subclip)

        if not subclips:
            return None

        final_clip = concatenate_videoclips(subclips)
        final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")

        # Close clips to release resources
        clip.close()
        for sub in subclips:
            sub.close()
        final_clip.close()

        return output_path
