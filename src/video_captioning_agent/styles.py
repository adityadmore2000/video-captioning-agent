"""Supported caption-style input validation and task eligibility.

This module is pure input validation: it confirms a task's requested styles are within
the fixed supported set and produces a task-level eligibility outcome. It does NOT gate
which styles Task 10 generates (Task 10 always generates all 4 supported styles
unconditionally; see TASKS.md Decisions). The validated requested-styles list produced
here is consumed by Task 12 as the output-time filter that selects which of Task 10's
captions actually appear in results.json.
"""

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
STYLE_OUTPUT_KEYS = {
    "Formal": "formal",
    "Sarcastic": "sarcastic",
    "Humorous-Tech": "humorous_tech",
    "Humorous-Non-Tech": "humorous_non_tech",
}


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
    """Validate requested styles by splitting them into supported and unsupported groups.

    Input order is retained so Task 12's output serialization is deterministic. Unsupported
    styles are retained in the result for logging/visibility but are never processed; per
    TASKS.md Decisions this defensive path is not expected to trigger for valid input.
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
    """Determine whether *task* requests at least one supported caption style.

    The returned ``supported_styles`` tuple is the validated requested-styles list that
    Task 12 uses to filter Task 10's always-complete 4-style output down to the styles
    this task actually requested. This is input validation only; it does not control
    what Task 10 generates.
    """

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
