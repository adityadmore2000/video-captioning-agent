"""Bounded, failure-isolated video downloads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import tempfile
from urllib.parse import urlparse

import requests

from .contracts import VideoTask


DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 30.0
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
LOGGER = logging.getLogger(__name__)


class DownloadFailureKind(str, Enum):
    """The category of a non-fatal download failure."""

    TIMEOUT = "timeout"
    REQUEST = "request"
    WRITE = "write"


@dataclass(frozen=True, slots=True)
class DownloadFailure:
    """Failure details retained for one task while other tasks continue."""

    task_id: str
    kind: DownloadFailureKind
    message: str


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Either a downloaded video path or a structured task-level failure."""

    task_id: str
    path: Path | None = None
    failure: DownloadFailure | None = None

    @property
    def succeeded(self) -> bool:
        return self.path is not None and self.failure is None


def _download_suffix(video_url: str) -> str:
    suffix = Path(urlparse(video_url).path).suffix
    return suffix if suffix else ".mp4"


def download_video(
    task: VideoTask,
    destination_dir: Path,
    timeout_seconds: float = DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
) -> DownloadResult:
    """Download one task's video into an existing per-run directory.

    HTTP and local-write failures are represented in the returned result rather than
    propagated, so a failed task cannot terminate the rest of a batch.
    """

    destination_path: Path | None = None
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        with requests.get(task.video_url, stream=True, timeout=timeout_seconds) as response:
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=_download_suffix(task.video_url), dir=destination_dir, delete=False
            ) as output_file:
                destination_path = Path(output_file.name)
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        output_file.write(chunk)
    except requests.Timeout as error:
        _remove_partial_file(destination_path)
        return _failure(task.task_id, DownloadFailureKind.TIMEOUT, error)
    except requests.RequestException as error:
        _remove_partial_file(destination_path)
        return _failure(task.task_id, DownloadFailureKind.REQUEST, error)
    except OSError as error:
        _remove_partial_file(destination_path)
        return _failure(task.task_id, DownloadFailureKind.WRITE, error)

    return DownloadResult(task_id=task.task_id, path=destination_path)


def _remove_partial_file(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)


def _failure(
    task_id: str, kind: DownloadFailureKind, error: Exception
) -> DownloadResult:
    message = f"Download failed for task {task_id}: {error}"
    LOGGER.warning(message)
    return DownloadResult(
        task_id=task_id,
        failure=DownloadFailure(task_id=task_id, kind=kind, message=message),
    )
