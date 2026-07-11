"""Video captioning agent package."""

from .contracts import (
    CanonicalVideoReport,
    FrameSample,
    TaskResult,
    VideoMetadata,
    VideoTask,
)
from .input_loader import InputLoadResult, load_tasks

__all__ = [
    "CanonicalVideoReport",
    "FrameSample",
    "InputLoadResult",
    "TaskResult",
    "VideoMetadata",
    "VideoTask",
    "load_tasks",
]
