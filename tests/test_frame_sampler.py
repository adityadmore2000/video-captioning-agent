import base64
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from video_captioning_agent.contracts import VideoMetadata
from video_captioning_agent.frame_sampler import sample_frames


def _create_video(path: Path, frame_count: int, fps: float, size: tuple[int, int]) -> None:
    width, height = size
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size
    )
    assert writer.isOpened()
    for index in range(frame_count):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = (0, 0, max(255 - index * 25, 0))
        writer.write(frame)
    writer.release()


def _decode_data_url(data_url: str) -> Image.Image:
    prefix, encoded = data_url.split(",", maxsplit=1)
    assert prefix == "data:image/jpeg;base64"
    return Image.open(BytesIO(base64.b64decode(encoded)))


def test_uniform_sampling_is_chronological_and_covers_the_full_timeline(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "timeline.avi"
    _create_video(video_path, frame_count=10, fps=5.0, size=(32, 24))
    metadata = VideoMetadata(2.0, 5.0, 10, 32, 24)

    samples = sample_frames(video_path, metadata, target_frames=4)

    assert [sample.frame_index for sample in samples] == [0, 3, 6, 9]
    assert [sample.timestamp_seconds for sample in samples] == [0.0, 0.6, 1.2, 1.8]
    assert [sample.display_timestamp for sample in samples] == ["0.0s", "0.6s", "1.2s", "1.8s"]


def test_sampler_resizes_encodes_jpeg_data_urls_and_converts_bgr_to_rgb(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "large.avi"
    _create_video(video_path, frame_count=1, fps=1.0, size=(1600, 800))
    metadata = VideoMetadata(1.0, 1.0, 1, 1600, 800)

    sample = sample_frames(video_path, metadata, target_frames=16, max_resolution=768)[0]
    image = _decode_data_url(sample.image_data_url)

    assert image.size == (768, 384)
    red, green, blue = image.convert("RGB").getpixel((384, 192))
    assert red > 200
    assert green < 30
    assert blue < 30


def test_sampler_uses_sequential_one_fps_fallback_for_unusable_frame_count(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "fallback.avi"
    _create_video(video_path, frame_count=6, fps=2.0, size=(32, 24))
    metadata = VideoMetadata(0.0, 2.0, 0, 32, 24)

    samples = sample_frames(video_path, metadata, target_frames=16)

    assert [sample.frame_index for sample in samples] == [0, 2, 4]
    assert [sample.timestamp_seconds for sample in samples] == [0.0, 1.0, 2.0]


def test_sampler_uses_ordinal_labels_when_no_timing_metadata_exists(tmp_path: Path) -> None:
    video_path = tmp_path / "ordinal.avi"
    _create_video(video_path, frame_count=5, fps=5.0, size=(32, 24))
    metadata = VideoMetadata(0.0, 0.0, 0, 32, 24)

    samples = sample_frames(video_path, metadata, target_frames=3)

    assert [sample.frame_index for sample in samples] == [0, 2, 4]
    assert [sample.timestamp_seconds for sample in samples] == [None, None, None]
    assert [sample.display_timestamp for sample in samples] == [
        "frame 1 of 3, exact timing unavailable",
        "frame 2 of 3, exact timing unavailable",
        "frame 3 of 3, exact timing unavailable",
    ]
