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
from .frame_sampler import FrameSamplingError, sample_frames
from .styles import (
    SUPPORTED_STYLES,
    StyleSelection,
    TaskProcessingOutcome,
    determine_task_eligibility,
    filter_supported_styles,
)
from .video_inspection import (
    VideoInspectionFailure,
    VideoInspectionFailureKind,
    VideoInspectionResult,
    inspect_video,
)

__all__ = [
    "CanonicalVideoReport",
    "DEFAULT_DOWNLOAD_TIMEOUT_SECONDS",
    "DownloadFailure",
    "DownloadFailureKind",
    "DownloadResult",
    "FrameSamplingError",
    "FrameSample",
    "InputLoadResult",
    "SUPPORTED_STYLES",
    "StyleSelection",
    "TaskResult",
    "TaskProcessingOutcome",
    "VideoMetadata",
    "VideoInspectionFailure",
    "VideoInspectionFailureKind",
    "VideoInspectionResult",
    "VideoTask",
    "load_tasks",
    "determine_task_eligibility",
    "download_video",
    "sample_frames",
    "filter_supported_styles",
    "inspect_video",
]
