"""Video captioning agent package."""

from .contracts import (
    CanonicalVideoReport,
    FrameSample,
    TaskResult,
    VideoMetadata,
    VideoTask,
)
from .input_loader import InputLoadResult, load_tasks
from .downloader import (
    DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
    DownloadFailure,
    DownloadFailureKind,
    DownloadResult,
    download_video,
)
from .styles import (
    SUPPORTED_STYLES,
    StyleSelection,
    TaskProcessingOutcome,
    determine_task_eligibility,
    filter_supported_styles,
)

__all__ = [
    "CanonicalVideoReport",
    "DEFAULT_DOWNLOAD_TIMEOUT_SECONDS",
    "DownloadFailure",
    "DownloadFailureKind",
    "DownloadResult",
    "FrameSample",
    "InputLoadResult",
    "SUPPORTED_STYLES",
    "StyleSelection",
    "TaskResult",
    "TaskProcessingOutcome",
    "VideoMetadata",
    "VideoTask",
    "load_tasks",
    "determine_task_eligibility",
    "download_video",
    "filter_supported_styles",
]
