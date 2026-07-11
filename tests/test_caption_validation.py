import logging

from video_captioning_agent.caption_validation import (
    CaptionValidationFailureKind,
    validate_captions,
)


def test_empty_caption_is_rejected_for_its_requested_style() -> None:
    result = validate_captions(("Formal",), {"Formal": "   "})

    assert result.captions == {}
    assert [(failure.style, failure.kind) for failure in result.failures] == [
        ("Formal", CaptionValidationFailureKind.EMPTY)
    ]


def test_missing_and_unrequested_caption_styles_are_recorded() -> None:
    result = validate_captions(
        ("Formal", "Sarcastic"),
        {"Formal": "A formal caption.", "Humorous-Tech": "An extra caption."},
    )

    assert result.captions == {"Formal": "A formal caption."}
    assert [(failure.style, failure.kind) for failure in result.failures] == [
        ("Sarcastic", CaptionValidationFailureKind.MISSING),
        ("Humorous-Tech", CaptionValidationFailureKind.UNREQUESTED_STYLE),
    ]


def test_long_caption_logs_a_warning_without_rejecting_it(caplog) -> None:
    long_caption = "word " * 101

    with caplog.at_level(logging.WARNING):
        result = validate_captions(("Formal",), {"Formal": long_caption})

    assert result.captions == {"Formal": long_caption.strip()}
    assert result.failures == ()
    assert "101 words" in caplog.text
