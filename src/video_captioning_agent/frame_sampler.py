"""Chronological video-frame sampling for visual understanding."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import cv2
from PIL import Image

from .contracts import FrameSample, VideoMetadata


JPEG_QUALITY = 85


class FrameSamplingError(RuntimeError):
    """Raised when a readable video cannot yield any usable frame samples."""


def sample_frames(
    video_path: Path,
    metadata: VideoMetadata,
    target_frames: int = 16,
    max_resolution: int = 768,
) -> list[FrameSample]:
    """Sample chronological JPEG data URLs from a video.

    Usable frame-count metadata enables direct, timeline-wide uniform sampling. When
    it is unavailable, the video is read sequentially at 1 fps (or every frame when
    no FPS exists), then capped to evenly spaced ordinal positions. Neither path
    duplicates frames merely to satisfy ``target_frames``.
    """

    _validate_configuration(target_frames, max_resolution)
    if metadata.frame_count > 0:
        frame_indices = _uniform_indices(metadata.frame_count, target_frames)
        return _sample_uniformly(
            video_path, frame_indices, metadata.fps, max_resolution
        )
    return _sample_sequentially(video_path, metadata.fps, target_frames, max_resolution)


def _validate_configuration(target_frames: int, max_resolution: int) -> None:
    if isinstance(target_frames, bool) or not isinstance(target_frames, int) or target_frames < 1:
        raise ValueError("target_frames must be a positive integer")
    if isinstance(max_resolution, bool) or not isinstance(max_resolution, int) or max_resolution < 1:
        raise ValueError("max_resolution must be a positive integer")


def _uniform_indices(frame_count: int, target_frames: int) -> list[int]:
    sample_count = min(frame_count, target_frames)
    if sample_count == 1:
        return [0]
    return [
        round(position * (frame_count - 1) / (sample_count - 1))
        for position in range(sample_count)
    ]


def _sample_uniformly(
    video_path: Path,
    frame_indices: list[int],
    fps: float,
    max_resolution: int,
) -> list[FrameSample]:
    capture = cv2.VideoCapture(str(video_path))
    samples: list[FrameSample] = []
    try:
        if not capture.isOpened():
            raise FrameSamplingError(f"Could not open video for sampling: {video_path}")
        for ordinal, frame_index in enumerate(frame_indices, start=1):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            readable, frame = capture.read()
            if not readable or frame is None:
                continue
            samples.append(
                _make_sample(
                    frame,
                    frame_index,
                    fps,
                    ordinal,
                    len(frame_indices),
                    max_resolution,
                )
            )
    finally:
        capture.release()
    if not samples:
        raise FrameSamplingError(f"No readable sampled frames in {video_path}")
    return samples


def _sample_sequentially(
    video_path: Path,
    fps: float,
    target_frames: int,
    max_resolution: int,
) -> list[FrameSample]:
    candidate_indices = _read_fallback_candidate_indices(video_path, fps)
    selected_indices = _uniform_indices(len(candidate_indices), target_frames)
    selected_frame_indices = [candidate_indices[index] for index in selected_indices]
    selected_set = set(selected_frame_indices)

    capture = cv2.VideoCapture(str(video_path))
    samples_by_index: dict[int, FrameSample] = {}
    try:
        if not capture.isOpened():
            raise FrameSamplingError(f"Could not reopen video for sampling: {video_path}")
        frame_index = 0
        while len(samples_by_index) < len(selected_set):
            readable, frame = capture.read()
            if not readable or frame is None:
                break
            if frame_index in selected_set:
                ordinal = selected_frame_indices.index(frame_index) + 1
                samples_by_index[frame_index] = _make_sample(
                    frame,
                    frame_index,
                    fps,
                    ordinal,
                    len(selected_frame_indices),
                    max_resolution,
                )
            frame_index += 1
    finally:
        capture.release()

    samples = [samples_by_index[index] for index in selected_frame_indices if index in samples_by_index]
    if not samples:
        raise FrameSamplingError(f"No readable fallback frames in {video_path}")
    return samples


def _read_fallback_candidate_indices(video_path: Path, fps: float) -> list[int]:
    capture = cv2.VideoCapture(str(video_path))
    candidate_indices: list[int] = []
    try:
        if not capture.isOpened():
            raise FrameSamplingError(f"Could not open video for fallback sampling: {video_path}")
        frame_index = 0
        last_second = -1
        while True:
            readable, frame = capture.read()
            if not readable or frame is None:
                break
            if fps > 0:
                second = int(frame_index / fps)
                if second != last_second:
                    candidate_indices.append(frame_index)
                    last_second = second
            else:
                candidate_indices.append(frame_index)
            frame_index += 1
    finally:
        capture.release()
    if not candidate_indices:
        raise FrameSamplingError(f"No readable fallback frames in {video_path}")
    return candidate_indices


def _make_sample(
    frame: object,
    frame_index: int,
    fps: float,
    ordinal: int,
    total_samples: int,
    max_resolution: int,
) -> FrameSample:
    image_data_url = _encode_frame(frame, max_resolution)
    if fps > 0:
        return FrameSample(
            frame_index=frame_index,
            timestamp_seconds=frame_index / fps,
            image_data_url=image_data_url,
        )
    return FrameSample(
        frame_index=frame_index,
        timestamp_seconds=None,
        image_data_url=image_data_url,
        timestamp_label=(
            f"frame {ordinal} of {total_samples}, exact timing unavailable"
        ),
    )


def _encode_frame(frame: object, max_resolution: int) -> str:
    height, width = frame.shape[:2]
    scale = min(1.0, max_resolution / max(width, height))
    if scale < 1.0:
        resized_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        frame = cv2.resize(frame, resized_size, interpolation=cv2.INTER_AREA)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb_frame)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
