"""Tests for Task 11: validation of all 4 generated captions.

Per the revised Task 11 (see TASKS.md): validation is unconditional over the 4 supported
styles — it does not know which styles the task requested. Concision is a soft guideline:
captions beyond ~100 words log a warning but are never rejected. A missing supported style
is recorded as a MISSING failure and stays out of ``captions`` so Task 12 can substitute the
required empty-string value for any requested style it does not find here.
"""

import logging

import pytest

from video_captioning_agent.caption_validation import (
    CaptionValidationFailureKind,
    CVR_LEAKAGE_PATTERN,
    LONG_CAPTION_WORD_WARNING_THRESHOLD,
    validate_all_captions,
)
from video_captioning_agent.styles import SUPPORTED_STYLES


def test_all_four_supported_styles_present_and_nonempty_are_accepted() -> None:
    captions = {style: f"{style} caption." for style in SUPPORTED_STYLES}

    result = validate_all_captions(captions)

    assert result.captions == captions
    assert result.failures == ()


def test_missing_supported_styles_are_recorded_without_rejecting_the_set() -> None:
    captions = {"Formal": "A formal caption."}

    result = validate_all_captions(captions)

    assert result.captions == {"Formal": "A formal caption."}
    missing_styles = sorted(set(SUPPORTED_STYLES) - {"Formal"})
    assert sorted(failure.style for failure in result.failures) == missing_styles
    assert all(failure.kind is CaptionValidationFailureKind.MISSING for failure in result.failures)


def test_empty_caption_for_a_supported_style_is_recorded_as_empty() -> None:
    result = validate_all_captions({"Sarcastic": "   "})

    assert result.captions == {}
    empty_failure = next(f for f in result.failures if f.style == "Sarcastic")
    assert empty_failure.kind is CaptionValidationFailureKind.EMPTY


def test_unrequested_style_keys_outside_supported_set_are_flagged() -> None:
    captions = {style: f"{style} caption." for style in SUPPORTED_STYLES}
    captions["Poetic"] = "An unsupported style caption."

    result = validate_all_captions(captions)

    assert result.captions == {style: f"{style} caption." for style in SUPPORTED_STYLES}
    assert [failure.kind for failure in result.failures] == [
        CaptionValidationFailureKind.UNREQUESTED_STYLE
    ]
    assert result.failures[0].style == "Poetic"


def test_runaway_length_logs_warning_without_rejecting_the_caption(caplog) -> None:
    long_caption = "word " * (LONG_CAPTION_WORD_WARNING_THRESHOLD + 1)
    captions = {style: f"{style} caption." for style in SUPPORTED_STYLES}
    captions["Formal"] = long_caption

    with caplog.at_level(logging.WARNING):
        result = validate_all_captions(captions)

    expected = {style: f"{style} caption." for style in SUPPORTED_STYLES}
    expected["Formal"] = long_caption.strip()
    assert result.captions == expected
    assert result.failures == ()
    assert f"{LONG_CAPTION_WORD_WARNING_THRESHOLD + 1} words" in caplog.text


@pytest.mark.parametrize(
    "caption",
    [
        "At timestamp 0.0 s, a person sits at a desk.",
        "By timestamp 30.6 s, the same individual stands up.",
        "A person looks at a laptop, then by 13.1s shifts focus to a bag.",
        "After 30.6 seconds the person stands up holding a blue bag.",
        "A person unzips the bag at 4.4's into the video.",
    ],
)
def test_cvr_leakage_pattern_detects_timestamp_references(caption: str) -> None:
    assert CVR_LEAKAGE_PATTERN.search(caption), f"expected leakage match in: {caption!r}"


@pytest.mark.parametrize(
    "caption",
    [
        "A person in a blue shirt sits at a desk then shifts focus to a blue shopping bag.",
        "Afterwards the individual examines the bag and eventually stands up holding it.",
        "The second frame shows a desk with a laptop and a bed in the background.",
        "Someone wearing a cap transitions from screen time to a hands-on bag adventure.",
    ],
)
def test_cvr_leakage_pattern_does_not_flag_natural_prose(caption: str) -> None:
    assert CVR_LEAKAGE_PATTERN.search(caption) is None, (
        f"unexpected leakage match in natural prose: {caption!r}"
    )


def test_cvr_leakage_in_caption_logs_warning_without_rejecting(caplog) -> None:
    captions = {style: f"{style} caption." for style in SUPPORTED_STYLES}
    captions["Formal"] = "At timestamp 0.0 s, a person sits at a desk."

    with caplog.at_level(logging.WARNING):
        result = validate_all_captions(captions)

    assert set(result.captions) == set(SUPPORTED_STYLES)
    assert result.failures == ()
    assert "leaks CVR-internal formatting" in caplog.text
    assert "Formal" in caplog.text


def test_natural_caption_logs_no_leakage_warning(caplog) -> None:
    captions = {style: f"{style} caption." for style in SUPPORTED_STYLES}
    captions["Formal"] = "A person sits at a desk then shifts focus to a blue shopping bag."

    with caplog.at_level(logging.WARNING):
        validate_all_captions(captions)

    assert "leaks CVR-internal formatting" not in caplog.text