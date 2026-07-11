"""Video captioning agent package."""

from .contracts import (
    CanonicalVideoReport,
    FrameSample,
    TaskResult,
    VideoMetadata,
    VideoTask,
)
from .input_loader import InputLoadResult, load_tasks
from .styles import (
    SUPPORTED_STYLES,
    StyleSelection,
    TaskProcessingOutcome,
    determine_task_eligibility,
    filter_supported_styles,
)

__all__ = [
    "CanonicalVideoReport",
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
    "filter_supported_styles",
]
