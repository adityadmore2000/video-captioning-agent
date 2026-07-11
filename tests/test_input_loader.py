import json
from pathlib import Path

import pytest

from video_captioning_agent.input_loader import load_tasks


def _write_tasks(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _valid_task(task_id: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "video_url": f"https://example.test/{task_id}.mp4",
        "styles": ["Formal"],
    }


def test_load_tasks_reads_a_valid_multi_task_file(tmp_path: Path) -> None:
    input_path = tmp_path / "tasks.json"
    _write_tasks(input_path, [_valid_task("v1"), _valid_task("v2")])

    result = load_tasks(input_path)

    assert [task.task_id for task in result.tasks] == ["v1", "v2"]
    assert result.tasks[1].styles == ("Formal",)
    assert result.errors == ()


def test_load_tasks_accepts_an_empty_task_list(tmp_path: Path) -> None:
    input_path = tmp_path / "tasks.json"
    _write_tasks(input_path, [])

    assert load_tasks(input_path).tasks == ()


def test_load_tasks_handles_malformed_json(tmp_path: Path) -> None:
    input_path = tmp_path / "tasks.json"
    input_path.write_text("{not valid json", encoding="utf-8")

    result = load_tasks(input_path)

    assert result.tasks == ()
    assert len(result.errors) == 1
    assert "Unable to read tasks" in result.errors[0]


def test_load_tasks_skips_every_task_with_a_duplicate_id(tmp_path: Path) -> None:
    input_path = tmp_path / "tasks.json"
    _write_tasks(
        input_path,
        [_valid_task("duplicate"), _valid_task("valid"), _valid_task("duplicate")],
    )

    result = load_tasks(input_path)

    assert [task.task_id for task in result.tasks] == ["valid"]
    assert result.errors == ("Skipping duplicate task_id: duplicate",)


@pytest.mark.parametrize("missing_field", ["task_id", "video_url", "styles"])
def test_load_tasks_skips_tasks_with_missing_required_fields(
    tmp_path: Path, missing_field: str
) -> None:
    input_path = tmp_path / "tasks.json"
    task = _valid_task("v1")
    del task[missing_field]
    _write_tasks(input_path, [task])

    result = load_tasks(input_path)

    assert result.tasks == ()
    assert len(result.errors) == 1
    assert missing_field in result.errors[0]


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [("task_id", 1), ("video_url", 1), ("styles", "Formal")],
)
def test_load_tasks_skips_tasks_with_invalid_field_types(
    tmp_path: Path, field: str, invalid_value: object
) -> None:
    input_path = tmp_path / "tasks.json"
    task = _valid_task("v1")
    task[field] = invalid_value
    _write_tasks(input_path, [task])

    result = load_tasks(input_path)

    assert result.tasks == ()
    assert len(result.errors) == 1
    assert field in result.errors[0]
