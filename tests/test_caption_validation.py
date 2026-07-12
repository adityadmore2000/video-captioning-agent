"""Tests for Task 11: validation of all 4 generated captions.

Per the revised Task 11 (see TASKS.md): validation is unconditional over the 4 supported
styles — it does not know which styles the task requested. Concision is a soft guideline:
captions beyond ~100 words log a warning but are never rejected. A missing supported style
is recorded as a MISSING failure and stays out of ``captions`` so Task 12 can substitute the
required empty-string value for any requested style it does not find here.
"""

import logging

from video_captioning_agent.caption_validation import (
    CaptionValidationFailureKind,
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