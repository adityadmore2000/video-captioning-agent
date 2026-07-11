"""Supported caption-style selection and task eligibility."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .contracts import VideoTask


SUPPORTED_STYLES = (
    "Formal",
    "Sarcastic",
    "Humorous-Tech",
    "Humorous-Non-Tech",
)
_SUPPORTED_STYLE_SET = frozenset(SUPPORTED_STYLES)


class TaskProcessingOutcome(str, Enum):
    """Whether a structurally valid task can enter video processing."""

    ELIGIBLE = "eligible"
    NO_SUPPORTED_STYLES = "no_supported_styles"


@dataclass(frozen=True, slots=True)
class StyleSelection:
    """Requested styles divided into supported and defensively ignored values."""

    task_id: str
    supported_styles: tuple[str, ...]
    ignored_styles: tuple[str, ...]
    outcome: TaskProcessingOutcome


def filter_supported_styles(styles: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return requested styles split into supported and unsupported groups.

    Input order is retained so later caption generation is deterministic. Unsupported
    styles are retained in the result for logging but are never processed.
    """

    supported: list[str] = []
    ignored: list[str] = []
    for style in styles:
        if style in _SUPPORTED_STYLE_SET:
            supported.append(style)
        else:
            ignored.append(style)
    return tuple(supported), tuple(ignored)


def determine_task_eligibility(task: VideoTask) -> StyleSelection:
    """Determine whether *task* requests at least one supported caption style."""

    supported_styles, ignored_styles = filter_supported_styles(task.styles)
    outcome = (
        TaskProcessingOutcome.ELIGIBLE
        if supported_styles
        else TaskProcessingOutcome.NO_SUPPORTED_STYLES
    )
    return StyleSelection(
        task_id=task.task_id,
        supported_styles=supported_styles,
        ignored_styles=ignored_styles,
        outcome=outcome,
    )
