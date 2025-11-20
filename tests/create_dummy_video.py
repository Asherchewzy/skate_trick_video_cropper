"""Utility to create dummy video clips for API tests."""

from moviepy import ColorClip


def create_dummy_video(filename="test_video.mp4", duration=5):
    """Create a simple solid-color video for test uploads."""
    # Create a simple video with a color background
    clip = ColorClip(size=(640, 480), color=(255, 0, 0), duration=duration)
    clip.write_videofile(filename, fps=24)
    print(f"Created {filename}")


if __name__ == "__main__":
    """Generate a dummy clip when run directly."""
    create_dummy_video()
