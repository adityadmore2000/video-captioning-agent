import json
from pathlib import Path
import stat

from video_captioning_agent.contracts import VideoTask
from video_captioning_agent.result_writer import build_task_result, write_results


def _task(task_id: str, styles: tuple[str, ...]) -> VideoTask:
    return VideoTask(task_id, "https://example.test/video.mp4", styles)


def test_write_results_creates_valid_json_and_output_directory(tmp_path: Path) -> None:
    result = build_task_result(
        _task("v1", ("Formal", "Humorous-Tech")),
        {"Formal": "A formal caption.", "Humorous-Tech": "A technical caption."},
    )
    output_path = tmp_path / "nested" / "results.json"

    written_path = write_results([result], output_path)

    assert written_path == output_path
    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {
            "task_id": "v1",
            "captions": {
                "formal": "A formal caption.",
                "humorous_tech": "A technical caption.",
            },
        }
    ]
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o644


def test_result_covers_only_requested_styles_and_keeps_missing_requested_caption(tmp_path: Path) -> None:
    result = build_task_result(
        _task("v1", ("Sarcastic", "Humorous-Non-Tech")),
        {"Sarcastic": "Sure, that happened.", "Formal": "Not requested."},
    )

    write_results([result], tmp_path / "results.json")

    assert result.captions == {
        "sarcastic": "Sure, that happened.",
        "humorous_non_tech": "",
    }


def test_write_results_supports_an_empty_task_list(tmp_path: Path) -> None:
    output_path = tmp_path / "results.json"

    write_results([], output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == []


def test_write_results_preserves_successful_and_failed_task_entries(tmp_path: Path) -> None:
    successful = build_task_result(
        _task("success", ("Formal",)), {"Formal": "A formal caption."}
    )
    failed = build_task_result(_task("failed", ("Sarcastic",)), {})
    output_path = tmp_path / "results.json"

    write_results([successful, failed], output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {"task_id": "success", "captions": {"formal": "A formal caption."}},
        {"task_id": "failed", "captions": {"sarcastic": ""}},
    ]
