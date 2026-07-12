"""Validation for the all-4 generated captions before result serialization.

Per the revised Task 11 (see TASKS.md): validates every generated caption for the 4
supported styles unconditionally — it does not know or care which styles the task
actually requested (that filtering is owned by Task 12). Captions must be non-empty and
correctly associated with their style; generation failures are recorded per-style without
ending unrelated work. Concision is a soft guideline only: a caption beyond ~100 words
logs a warning (to flag clearly broken/runaway model output) but is never rejected — the
spec's "approximately one to two sentences" is not a strict threshold worth enforcing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Mapping

from .styles import SUPPORTED_STYLES, filter_supported_styles


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
    """Accepted captions (style -> stripped text) and isolated per-style failures."""

    captions: dict[str, str]
    failures: tuple[CaptionValidationFailure, ...]


def validate_all_captions(
    generated_captions: Mapping[str, object],
) -> CaptionValidationResult:
    """Validate all 4 supported-style captions produced by Task 10.

    Iterates over ``SUPPORTED_STYLES`` unconditionally. A supported style absent from the
    input map is recorded as MISSING; a present but blank value is recorded as EMPTY;
    non-empty values are accepted (stripped) and only warned about if they exceed the
    loose ~100-word sanity threshold. Any key in ``generated_captions`` outside the
    supported set is defensively flagged as UNREQUESTED_STYLE — not expected, since
    Task 10 only iterates the supported set.
    """

    accepted: dict[str, str] = {}
    failures: list[CaptionValidationFailure] = []

    supported_styles, _ = filter_supported_styles(SUPPORTED_STYLES)
    for style in supported_styles:
        if style not in generated_captions:
            failures.append(_failure(style, CaptionValidationFailureKind.MISSING))
            continue
        caption = generated_captions[style]
        if not isinstance(caption, str) or not caption.strip():
            failures.append(_failure(style, CaptionValidationFailureKind.EMPTY))
            continue
        normalized = caption.strip()
        accepted[style] = normalized
        _warn_if_long(style, normalized)

    supported_style_set = set(supported_styles)
    for style in generated_captions:
        if style not in supported_style_set:
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