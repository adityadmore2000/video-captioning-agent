from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest

from video_captioning_agent.video_inspection import (
    VideoInspectionFailureKind,
    inspect_video,
)


@pytest.fixture
def tiny_video(tmp_path: Path) -> Path:
    """Create a small, two-frame AVI fixture without requiring external media."""

    path = tmp_path / "tiny.avi"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (16, 12)
    )
    assert writer.isOpened()
    writer.write(np.zeros((12, 16, 3), dtype=np.uint8))
    writer.write(np.full((12, 16, 3), 255, dtype=np.uint8))
    writer.release()
    return path


def test_inspect_video_collects_metadata_from_a_tiny_readable_fixture(
    tiny_video: Path,
) -> None:
    result = inspect_video("v1", tiny_video)

    assert result.succeeded
    assert result.metadata is not None
    assert result.metadata.frame_count == 2
    assert result.metadata.fps == pytest.approx(5.0)
    assert result.metadata.duration_seconds == pytest.approx(0.4)
    assert (result.metadata.width, result.metadata.height) == (16, 12)


@patch("video_captioning_agent.video_inspection.cv2.VideoCapture")
def test_inspect_video_rejects_corrupted_media(mock_capture_factory: Mock, tmp_path: Path) -> None:
    capture = Mock()
    capture.isOpened.return_value = False
    mock_capture_factory.return_value = capture

    result = inspect_video("corrupt", tmp_path / "corrupt.mp4")

    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.kind is VideoInspectionFailureKind.UNREADABLE
    capture.release.assert_called_once_with()


@patch("video_captioning_agent.video_inspection.cv2.VideoCapture")
def test_inspect_video_rejects_empty_media(mock_capture_factory: Mock, tmp_path: Path) -> None:
    capture = Mock()
    capture.isOpened.return_value = True
    capture.get.return_value = 0
    capture.read.return_value = (False, None)
    mock_capture_factory.return_value = capture

    result = inspect_video("empty", tmp_path / "empty.mp4")

    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.kind is VideoInspectionFailureKind.EMPTY
    capture.release.assert_called_once_with()
