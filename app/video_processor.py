"""Video processing utilities for detecting humans and compiling highlights."""

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

    def detect_human_segments(self, video_path: str) -> List[Tuple[float, float]]:
        """Return (start, end) segments where a human pose appears in the video."""
        video_path = str(video_path)
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps

        segments = []
        current_segment_start = None

        frame_idx = 0
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                break

            # Convert the BGR image to RGB.
            image.flags.writeable = False
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image)

            current_time = frame_idx / fps

            is_human_present = results.pose_landmarks is not None

            if is_human_present:
                if current_segment_start is None:
                    current_segment_start = current_time
            else:
                if current_segment_start is not None:
                    segments.append((current_segment_start, current_time))
                    current_segment_start = None

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

    def extract_and_compile(
        self,
        video_path: str,
        segments: Sequence[Tuple[float, float]],
        output_path: str,
        buffer: float = 2.0,
    ) -> str | None:
        """Compile buffered subclips for detected segments and write to output_path."""
        video_path = str(video_path)
        output_path = str(output_path)
        if not segments:
            return None

        clip = VideoFileClip(video_path)
        subclips = []

        for start, end in segments:
            # Add buffer
            start_time = max(0, start - buffer)
            end_time = min(clip.duration, end + buffer)

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
