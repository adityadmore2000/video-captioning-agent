import pytest

from video_captioning_agent.contracts import VideoTask
from video_captioning_agent.styles import (
    SUPPORTED_STYLES,
    TaskProcessingOutcome,
    determine_task_eligibility,
)


@pytest.mark.parametrize("style", SUPPORTED_STYLES)
def test_every_supported_style_keeps_a_task_eligible(style: str) -> None:
    task = VideoTask("v1", "https://example.test/video.mp4", (style,))

    selection = determine_task_eligibility(task)

    assert selection.supported_styles == (style,)
    assert selection.ignored_styles == ()
    assert selection.outcome is TaskProcessingOutcome.ELIGIBLE


def test_mixed_style_requests_filter_unsupported_styles_in_request_order() -> None:
    task = VideoTask(
        "v1",
        "https://example.test/video.mp4",
        ("Unsupported", "Formal", "Not-A-Style", "Humorous-Tech"),
    )

    selection = determine_task_eligibility(task)

    assert selection.supported_styles == ("Formal", "Humorous-Tech")
    assert selection.ignored_styles == ("Unsupported", "Not-A-Style")
    assert selection.outcome is TaskProcessingOutcome.ELIGIBLE


def test_task_without_supported_styles_has_an_explicit_ineligible_outcome() -> None:
    task = VideoTask("v1", "https://example.test/video.mp4", ("Poetic", "Brief"))

    selection = determine_task_eligibility(task)

    assert selection.supported_styles == ()
    assert selection.ignored_styles == ("Poetic", "Brief")
    assert selection.outcome is TaskProcessingOutcome.NO_SUPPORTED_STYLES
