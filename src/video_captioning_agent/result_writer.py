"""Atomic serialization of public task-caption results."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Mapping, Sequence

from .contracts import TaskResult, VideoTask
from .styles import STYLE_OUTPUT_KEYS, filter_supported_styles


OUTPUT_RESULTS_PATH = Path("/output/results.json")


def build_task_result(task: VideoTask, captions: Mapping[str, object]) -> TaskResult:
    """Build a schema-compliant result containing only task-requested styles.

    A missing or invalid value for a supported requested style is represented by an
    empty string, preserving the key for downstream scoring without inventing a
    caption. Unsupported requested styles remain excluded by the defensive filter.
    """

    requested_styles, _ = filter_supported_styles(task.styles)
    output_captions: dict[str, str] = {}
    for style in dict.fromkeys(requested_styles):
        caption = captions.get(style, "")
        output_captions[STYLE_OUTPUT_KEYS[style]] = caption if isinstance(caption, str) else ""
    return TaskResult(task_id=task.task_id, captions=output_captions)


def write_results(
    results: Sequence[TaskResult], output_path: Path = OUTPUT_RESULTS_PATH
) -> Path:
    """Validate and atomically write a top-level results JSON array."""

    serialized = _serialize_results(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}-", suffix=".tmp", dir=output_path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output_file:
            output_file.write(serialized)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_path, output_path)
        os.chmod(output_path, 0o644)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise
    return output_path


def _serialize_results(results: Sequence[TaskResult]) -> str:
    serialized = json.dumps(
        [result.to_dict() for result in results], ensure_ascii=False, separators=(",", ":")
    )
    _validate_serialized_document(serialized)
    return serialized


def _validate_serialized_document(serialized: str) -> None:
    try:
        document = json.loads(serialized)
    except json.JSONDecodeError as error:
        raise ValueError("Results serialization produced invalid JSON") from error
    if not isinstance(document, list):
        raise ValueError("Results document must be a JSON array")
    for result in document:
        if not isinstance(result, dict) or set(result) != {"task_id", "captions"}:
            raise ValueError("Each result must contain only task_id and captions")
        if not isinstance(result["task_id"], str) or not isinstance(result["captions"], dict):
            raise ValueError("Each result must have a string task_id and captions object")
        if not all(
            isinstance(style, str) and isinstance(caption, str)
            for style, caption in result["captions"].items()
        ):
            raise ValueError("Caption keys and values must be strings")
