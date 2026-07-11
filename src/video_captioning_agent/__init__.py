"""Video captioning agent package."""

from .contracts import (
    CanonicalVideoReport,
    FrameSample,
    TaskResult,
    VideoMetadata,
    VideoTask,
)
from .cvr_client import (
    CVR_SYSTEM_PROMPT,
    DEFAULT_VISION_TIMEOUT_SECONDS,
    FIREWORKS_URL,
    VISION_MAX_TOKENS,
    VISION_MODEL_ID,
    VISION_TEMPERATURE,
    CvrGenerationError,
    FireworksCvrClient,
    build_cvr_request,
)
from .cvr_parser import (
    CvrParseFailure,
    CvrParseFailureKind,
    CvrParseResult,
    parse_cvr_response,
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
from .style_generator import (
    DEFAULT_STYLE_TIMEOUT_SECONDS,
    STYLE_MAX_TOKENS,
    STYLE_SYSTEM_PROMPT,
    STYLE_TEMPERATURE,
    FireworksStyleClient,
    StyleCaptionClient,
    StyleGenerationError,
    build_style_request,
    generate_requested_captions,
)
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
    "CVR_SYSTEM_PROMPT",
    "CvrGenerationError",
    "CvrParseFailure",
    "CvrParseFailureKind",
    "CvrParseResult",
    "DEFAULT_VISION_TIMEOUT_SECONDS",
    "DEFAULT_DOWNLOAD_TIMEOUT_SECONDS",
    "DEFAULT_STYLE_TIMEOUT_SECONDS",
    "DownloadFailure",
    "DownloadFailureKind",
    "DownloadResult",
    "FIREWORKS_URL",
    "FireworksCvrClient",
    "FrameSamplingError",
    "FireworksStyleClient",
    "FrameSample",
    "InputLoadResult",
    "SUPPORTED_STYLES",
    "StyleSelection",
    "StyleCaptionClient",
    "StyleGenerationError",
    "STYLE_MAX_TOKENS",
    "STYLE_SYSTEM_PROMPT",
    "STYLE_TEMPERATURE",
    "TaskResult",
    "TaskProcessingOutcome",
    "VideoMetadata",
    "VideoInspectionFailure",
    "VideoInspectionFailureKind",
    "VideoInspectionResult",
    "VideoTask",
    "VISION_MAX_TOKENS",
    "VISION_MODEL_ID",
    "VISION_TEMPERATURE",
    "build_cvr_request",
    "build_style_request",
    "parse_cvr_response",
    "load_tasks",
    "determine_task_eligibility",
    "download_video",
    "sample_frames",
    "filter_supported_styles",
    "generate_requested_captions",
    "inspect_video",
]
