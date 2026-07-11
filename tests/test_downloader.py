from pathlib import Path
from unittest.mock import Mock, patch

import requests

from video_captioning_agent.contracts import VideoTask
from video_captioning_agent.downloader import DownloadFailureKind, download_video


def _task(task_id: str = "v1") -> VideoTask:
    return VideoTask(task_id, "https://example.test/video.mp4", ("Formal",))


def _response(chunks: list[bytes]) -> Mock:
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    response.iter_content.return_value = chunks
    return response


@patch("video_captioning_agent.downloader.requests.get")
def test_download_video_streams_to_the_run_directory(mock_get: Mock, tmp_path: Path) -> None:
    mock_get.return_value = _response([b"first", b"", b"second"])

    result = download_video(_task(), tmp_path, timeout_seconds=12.5)

    assert result.succeeded
    assert result.path is not None
    assert result.path.parent == tmp_path
    assert result.path.read_bytes() == b"firstsecond"
    mock_get.assert_called_once_with(
        "https://example.test/video.mp4", stream=True, timeout=12.5
    )
    mock_get.return_value.raise_for_status.assert_called_once_with()


@patch("video_captioning_agent.downloader.requests.get")
def test_download_video_returns_request_failure_for_an_invalid_url(
    mock_get: Mock, tmp_path: Path
) -> None:
    mock_get.side_effect = requests.exceptions.InvalidURL("invalid URL")

    result = download_video(_task(), tmp_path)

    assert not result.succeeded
    assert result.path is None
    assert result.failure is not None
    assert result.failure.kind is DownloadFailureKind.REQUEST


@patch("video_captioning_agent.downloader.requests.get")
def test_download_video_returns_timeout_failure(mock_get: Mock, tmp_path: Path) -> None:
    mock_get.side_effect = requests.exceptions.Timeout("timed out")

    result = download_video(_task(), tmp_path)

    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.kind is DownloadFailureKind.TIMEOUT


@patch("video_captioning_agent.downloader.requests.get")
def test_one_download_failure_does_not_prevent_another_task(
    mock_get: Mock, tmp_path: Path
) -> None:
    mock_get.side_effect = [
        requests.exceptions.ConnectionError("connection failed"),
        _response([b"video bytes"]),
    ]

    failed_result = download_video(_task("failed"), tmp_path)
    successful_result = download_video(_task("successful"), tmp_path)

    assert failed_result.failure is not None
    assert failed_result.failure.kind is DownloadFailureKind.REQUEST
    assert successful_result.succeeded
    assert successful_result.path is not None
    assert successful_result.path.read_bytes() == b"video bytes"
