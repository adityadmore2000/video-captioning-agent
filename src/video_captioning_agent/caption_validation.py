"""Validation for generated caption responses before result serialization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Mapping, Sequence

from .styles import filter_supported_styles


LONG_CAPTION_WORD_WARNING_THRESHOLD = 100
LOGGER = logging.getLogger(__name__)


class CaptionValidationFailureKind(str, Enum):
    """Reasons a generated caption cannot be included in task output."""

    EMPTY = "empty"
    MISSING = "missing"
    UNREQUESTED_STYLE = "unrequested_style"


@dataclass(frozen=True, slots=True)
class CaptionValidationFailure:
    """A deterministic validation failure for one style."""

    style: str
    kind: CaptionValidationFailureKind
    message: str


@dataclass(frozen=True, slots=True)
class CaptionValidationResult:
    """Captions accepted for requested styles and non-fatal validation failures."""

    captions: dict[str, str]
    failures: tuple[CaptionValidationFailure, ...]


def validate_captions(
    requested_styles: Sequence[str], generated_captions: Mapping[str, object]
) -> CaptionValidationResult:
    """Keep only non-empty captions associated with requested supported styles."""

    supported_styles, _ = filter_supported_styles(requested_styles)
    expected_styles = tuple(dict.fromkeys(supported_styles))
    expected_style_set = set(expected_styles)
    accepted: dict[str, str] = {}
    failures: list[CaptionValidationFailure] = []

    for style in expected_styles:
        if style not in generated_captions:
            failures.append(_failure(style, CaptionValidationFailureKind.MISSING))
            continue
        caption = generated_captions[style]
        if not isinstance(caption, str) or not caption.strip():
            failures.append(_failure(style, CaptionValidationFailureKind.EMPTY))
            continue
        normalized_caption = caption.strip()
        accepted[style] = normalized_caption
        _warn_if_long(style, normalized_caption)

    for style in generated_captions:
        if style not in expected_style_set:
            failures.append(_failure(style, CaptionValidationFailureKind.UNREQUESTED_STYLE))

    return CaptionValidationResult(captions=accepted, failures=tuple(failures))


def _warn_if_long(style: str, caption: str) -> None:
    word_count = len(caption.split())
    if word_count > LONG_CAPTION_WORD_WARNING_THRESHOLD:
        LOGGER.warning(
            "Caption for style %s is %d words; expected concise output.",
            style,
            word_count,
        )


def _failure(
    style: str, kind: CaptionValidationFailureKind
) -> CaptionValidationFailure:
    return CaptionValidationFailure(
        style=style,
        kind=kind,
        message=f"Caption validation failed for style {style}: {kind.value}",
    )
