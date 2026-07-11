"""Load and structurally validate captioning tasks from JSON input."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import logging
from pathlib import Path

from .contracts import ContractValidationError, VideoTask


INPUT_TASKS_PATH = Path("/input/tasks.json")
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InputLoadResult:
    """Valid tasks plus non-fatal structural errors encountered while loading."""

    tasks: tuple[VideoTask, ...]
    errors: tuple[str, ...]


def load_tasks(path: Path = INPUT_TASKS_PATH) -> InputLoadResult:
    """Load valid tasks from *path* without allowing malformed input to crash a run.

    A malformed document produces an empty task set. Invalid entries are skipped. If
    an ID is duplicated, every task using that ID is skipped because no authoritative
    task can be selected safely.
    """

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        message = f"Unable to read tasks from {path}: {error}"
        LOGGER.warning(message)
        return InputLoadResult(tasks=(), errors=(message,))

    if not isinstance(payload, list):
        message = f"Task input at {path} must be a JSON array"
        LOGGER.warning(message)
        return InputLoadResult(tasks=(), errors=(message,))

    valid_tasks: list[VideoTask] = []
    errors: list[str] = []
    for index, raw_task in enumerate(payload):
        try:
            valid_tasks.append(VideoTask.from_dict(raw_task))
        except ContractValidationError as error:
            message = f"Skipping task at index {index}: {error}"
            LOGGER.warning(message)
            errors.append(message)

    task_id_counts = Counter(task.task_id for task in valid_tasks)
    duplicate_ids = {task_id for task_id, count in task_id_counts.items() if count > 1}
    if duplicate_ids:
        for task_id in sorted(duplicate_ids):
            message = f"Skipping duplicate task_id: {task_id}"
            LOGGER.warning(message)
            errors.append(message)
        valid_tasks = [task for task in valid_tasks if task.task_id not in duplicate_ids]

    return InputLoadResult(tasks=tuple(valid_tasks), errors=tuple(errors))
