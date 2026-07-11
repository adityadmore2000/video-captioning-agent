"""Readability checks and metadata collection for downloaded video files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path

import cv2

from .contracts import VideoMetadata


LOGGER = logging.getLogger(__name__)


class VideoInspectionFailureKind(str, Enum):
    """Reasons a downloaded video cannot be analyzed."""

    UNREADABLE = "unreadable"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class VideoInspectionFailure:
    """A non-fatal inspection failure for one task's downloaded media."""

    task_id: str
    kind: VideoInspectionFailureKind
    message: str


@dataclass(frozen=True, slots=True)
class VideoInspectionResult:
    """Usable metadata or a structured readability failure."""

    task_id: str
    metadata: VideoMetadata | None = None
    failure: VideoInspectionFailure | None = None

    @property
    def succeeded(self) -> bool:
        return self.metadata is not None and self.failure is None


def inspect_video(task_id: str, video_path: Path) -> VideoInspectionResult:
    """Validate video readability and collect available OpenCV metadata.

    A decoded probe frame distinguishes truly empty media from videos whose frame-count
    metadata is zero or corrupt. The latter remain eligible for Task 6's sequential
    sampling fallback.
    """

    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            return _failure(task_id, VideoInspectionFailureKind.UNREADABLE, "could not open")

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        readable, first_frame = capture.read()
        if not readable or first_frame is None:
            return _failure(task_id, VideoInspectionFailureKind.EMPTY, "contains no readable frames")

        if width <= 0 or height <= 0:
            height, width = first_frame.shape[:2]
        duration_seconds = frame_count / fps if frame_count > 0 and fps > 0 else 0.0
        metadata = VideoMetadata(
            duration_seconds=duration_seconds,
            fps=fps if fps >= 0 else 0.0,
            frame_count=max(frame_count, 0),
            width=width,
            height=height,
        )
        return VideoInspectionResult(task_id=task_id, metadata=metadata)
    except cv2.error as error:
        return _failure(task_id, VideoInspectionFailureKind.UNREADABLE, str(error))
    finally:
        capture.release()


def _failure(
    task_id: str, kind: VideoInspectionFailureKind, reason: str
) -> VideoInspectionResult:
    message = f"Video inspection failed for task {task_id}: {reason}"
    LOGGER.warning(message)
    return VideoInspectionResult(
        task_id=task_id,
        failure=VideoInspectionFailure(task_id=task_id, kind=kind, message=message),
    )
