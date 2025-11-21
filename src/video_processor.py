"""Video processing utilities for detecting humans and compiling highlights."""

from collections.abc import Sequence
import os
import subprocess
import warnings
from pathlib import Path

os.environ["GLOG_minloglevel"] = "2"  # 0=all, 1=warn, 2=error
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # silence TF/TFLite info/warn
warnings.filterwarnings(
    "ignore",
    message="SymbolDatabase.GetPrototype\\(\\) is deprecated",
    category=UserWarning,
)

from absl import logging

logging.set_verbosity(logging.ERROR)
logging.set_stderrthreshold(logging.ERROR)

import cv2
import mediapipe as mp
from moviepy import VideoFileClip, concatenate_videoclips


class VideoProcessor:
    """Detect human presence in videos and compile buffered highlight reels."""

    def __init__(self):
        """Initialize the MediaPipe Pose detector (legacy Solutions API)."""
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def prepare_video_file(
        self,
        input_path: str,
        processing_dir: str,
        job_id: str,
        target_height: int | None = None,
        target_fps: float | None = None,
    ) -> str:
        """Ensure an input video is MP4, converting when needed.

        Args:
            input_path: Path to the uploaded video.
            processing_dir: Directory to place converted assets.
            job_id: Identifier to include in converted filenames.
            target_height: Optional output height for downscaling.
            target_fps: Optional output frame rate for downsampling.

        Returns:
            String path to an MP4 file ready for processing.
        """
        input_path = Path(input_path)
        processing_dir = Path(processing_dir)
        processing_dir.mkdir(parents=True, exist_ok=True)

        if target_height is not None and target_height <= 0:
            target_height = None
        if target_fps is not None and target_fps <= 0:
            target_fps = None

        needs_transcode = (
            input_path.suffix.lower() != ".mp4" or target_height is not None or target_fps is not None
        )
        if not needs_transcode:
            return str(input_path)

        output_path = processing_dir / f"{input_path.stem}_{job_id}.mp4"
        self._ffmpeg_convert_to_mp4(
            str(input_path),
            str(output_path),
            target_height=target_height,
            target_fps=target_fps,
        )
        return str(output_path)

    def _ffmpeg_convert_to_mp4(
        self, src: str, dst: str, target_height: int | None = None, target_fps: float | None = None
    ) -> None:
        """Use ffmpeg to transcode while ignoring unknown streams.

        Args:
            src: Source video path.
            dst: Destination MP4 path.
            target_height: Optional output height to downscale while preserving aspect ratio.
            target_fps: Optional output frame rate to downsample.
        """
        filters = []
        if target_height is not None:
            even_height = target_height if target_height % 2 == 0 else max(target_height - 1, 2)
            filters.append(f"scale=-2:{even_height}")  # preserve aspect, even width
        else:
            filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")  # ensure even dims for encoders
        if target_fps is not None:
            filters.append(f"fps={target_fps}")
        vf_filter = ",".join(filters)

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
            vf_filter,
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
        max_stationary_frames: int = 20,
    ) -> list[tuple[float, float]]:
        """Detect moving-human segments.

        Args:
            video_path: Input video file path.
            movement_threshold: Minimum average landmark displacement to count as motion.
            min_moving_frames: Frames of motion needed before starting a segment.
            max_stationary_frames: Frames of stillness allowed before closing a segment.

        Returns:
            List of (start, end) times in seconds for motion windows.
        """
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
        self, segments: Sequence[tuple[float, float]], gap_threshold: float = 1.0
    ) -> list[tuple[float, float]]:
        """Merge adjacent segments if the gap between them is below the threshold."""
        if not segments:
            return []

        merged = []
        current_start, current_end = segments[0]

        for i in range(1, len(segments)):
            next_start, next_end = segments[i]
            if next_start - current_end < gap_threshold:
                current_end = next_end  # extend current window across the small gap
            else:
                merged.append((current_start, current_end))  # store finished window
                current_start, current_end = next_start, next_end  # start new window

        merged.append((current_start, current_end))  # keep the final window
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
        segments: Sequence[tuple[float, float]],
        output_path: str,
        buffer_before: float = 2.0,
        buffer_after: float = 3.0,
    ) -> str | None:
        """Compile buffered subclips for detected segments and write to output_path.

        Args:
            video_path: Source video to slice.
            segments: List of (start, end) times in seconds.
            output_path: Destination MP4 path.
            buffer_before: Seconds to prepend before each segment start.
            buffer_after: Seconds to append after each segment end.

        Returns:
            Path to the compiled video, or None if no segments are provided.
        """
        video_path = str(video_path)
        output_path = str(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if not segments:
            return None

        with VideoFileClip(video_path) as clip:
            subclips = []

            for start, end in segments:
                start_time = max(0, start - buffer_before)
                end_time = min(clip.duration, end + buffer_after)

                subclip = clip.subclipped(start_time, end_time)
                subclips.append(subclip)

            if not subclips:
                return None

            final_clip = None
            try:
                final_clip = concatenate_videoclips(subclips)
                final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
                return output_path
            finally:
                for sub in subclips:
                    sub.close()
                if final_clip:
                    final_clip.close()


if __name__ == "__main__":
    import argparse
    from . import settings

    # Example: python app/video_processor.py input.mov --out downloads/output.mp4 --buffer-before 2 --buffer-after 3
    # python app/video_processor.py test_videos/test1.mov --out downloads/test1_out.mp4 

    parser = argparse.ArgumentParser(description="Detect motion segments and compile highlights.")
    parser.add_argument("video", help="Path to an input video (mp4/mov/etc).")
    parser.add_argument(
        "--out",
        required=True,
        help="Path to write the compiled highlights MP4.",
    )
    parser.add_argument(
        "--buffer-before",
        type=float,
        default=2.0,
        help="Seconds to include before each detected segment.",
    )
    parser.add_argument(
        "--buffer-after",
        type=float,
        default=3.0,
        help="Seconds to include after each detected segment.",
    )
    parser.add_argument(
        "--movement-threshold",
        type=float,
        default=0.02,
        help="Minimum average landmark movement to count as motion.",
    )
    parser.add_argument(
        "--min-moving-frames",
        type=int,
        default=3,
        help="Frames of motion required before opening a segment.",
    )
    parser.add_argument(
        "--max-still-frames",
        type=int,
        default=20,
        help="Frames of stillness before closing a segment.",
    )
    parser.add_argument(
        "--resize-height",
        type=int,
        default=720,
        help="Output height to downscale before detection (keeps aspect ratio). Use 0 to keep source.",
    )
    parser.add_argument(
        "--target-fps",
        type=float,
        default=30,
        help="Output FPS to downsample before detection. Use 0 to keep source.",
    )
    args = parser.parse_args()

    processor = VideoProcessor()
    mp4_path = processor.prepare_video_file(
        args.video,
        processing_dir=settings.PROCESSING_DIR,
        job_id="cli",
        target_height=args.resize_height,
        target_fps=args.target_fps,
    )
    segments = processor.detect_human_segments(
        mp4_path,
        movement_threshold=args.movement_threshold,
        min_moving_frames=args.min_moving_frames,
        max_stationary_frames=args.max_still_frames,
    )
    if not segments:
        print("No moving-human segments detected.")
    else:
        output = processor.extract_and_compile(
            mp4_path,
            segments,
            args.out,
            buffer_before=args.buffer_before,
            buffer_after=args.buffer_after,
        )
        if output:
            print(f"Wrote highlights to {output}")
