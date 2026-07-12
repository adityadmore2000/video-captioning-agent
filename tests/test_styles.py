"""Tests for Task 3: supported-style input validation and task eligibility.

Task 3 is pure input validation. It does NOT gate what Task 10 generates (Task 10 always
generates all 4 supported styles unconditionally; see TASKS.md Decisions). The validated
supported-styles list ``determine_task_eligibility`` returns is what Task 12 consumes as
its output-time filter.
"""

import pytest

from video_captioning_agent.contracts import VideoTask
from video_captioning_agent.styles import (
    SUPPORTED_STYLES,
    TaskProcessingOutcome,
    determine_task_eligibility,
    filter_supported_styles,
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


def test_validated_supported_styles_list_matches_task_12_filter_input() -> None:
    """The list Task 3 exports is exactly what Task 12 filters Task 10's 4-style output on.

    Task 10 always produces all 4 supported styles; Task 12 keeps only the styles in the
    validated list returned here. Confirm the two helpers agree on the supported subset.
    """

    task = VideoTask(
        "v1",
        "https://example.test/video.mp4",
        ("Sarcastic", "Unsupported", "Humorous-Non-Tech"),
    )

    eligibility = determine_task_eligibility(task)
    validated, ignored = filter_supported_styles(task.styles)

    assert eligibility.supported_styles == validated
    assert eligibility.ignored_styles == ignored
    assert set(validated).issubset(set(SUPPORTED_STYLES))
