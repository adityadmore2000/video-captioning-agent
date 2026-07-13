import json
import threading
import time
from pathlib import Path

from video_captioning_agent.contracts import FrameSample, VideoMetadata, VideoTask
from video_captioning_agent.downloader import (
    DownloadFailure,
    DownloadFailureKind,
    DownloadResult,
)
from video_captioning_agent.pipeline import run_pipeline
from video_captioning_agent.video_inspection import VideoInspectionResult


def _cvr_json(task_id: str) -> str:
    """A CVR whose serialized form embeds a task marker style gen can detect."""

    return json.dumps(
        {
            "scene": f"Kitchen marker:{task_id}",
            "primary_subjects": ["A person"],
            "important_objects": ["A bowl"],
            "timeline": ["0.0s: A person holds a bowl."],
            "overall_summary": f"A person holds a bowl in a kitchen. marker:{task_id}",
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _write_two_tasks(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "task_id": "v1",
                    "video_url": "https://example.test/v1.mp4",
                    "styles": ["Formal"],
                },
                {
                    "task_id": "v2",
                    "video_url": "https://example.test/v2.mp4",
                    "styles": ["Sarcastic"],
                },
            ]
        ),
        encoding="utf-8",
    )


def _make_fakes(tmp_path: Path):
    """Build the reusable downloader/inspector/sampler used by all tests here.

    All tasks share the same fake-video setup: downloads are stubbed as local
    in-memory empty files, inspection returns a trivial but valid metadata
    object, and sampling returns a single throwaway frame. Each test plugs its
    own vision/style clients onto this skeleton.
    """

    metadata = VideoMetadata(1.0, 1.0, 1, 16, 12)

    def downloader(task: VideoTask, run_directory: Path) -> DownloadResult:
        return DownloadResult(task_id=task.task_id, path=run_directory / f"{task.task_id}.mp4")

    def inspector(task_id: str, video_path: Path) -> VideoInspectionResult:
        return VideoInspectionResult(task_id=task_id, metadata=metadata)

    def sampler(video_path: Path, video_metadata: VideoMetadata) -> list[FrameSample]:
        return [FrameSample(0, 0.0, "data:image/jpeg;base64,ZmFrZQ==")]

    return downloader, inspector, sampler


class _DeterministicVisionClient:
    """Returns a CVR whose JSON embeds the originating task id.

    Pairs with ``_MarkerAwareStyleClient`` so per-task results can be told apart
    even when both tasks request the same caption style.
    """

    def __init__(self) -> None:
        self.calls = 0

    def generate_cvr(self, frames: list[FrameSample], metadata: VideoMetadata) -> str:
        self.calls += 1
        task_id = f"v{self.calls}"
        return _cvr_json(task_id)


class _MarkerAwareStyleClient:
    """Returns a caption stamped with its CVR's task marker for assertion."""

    def generate_caption(self, cvr_json: str, style: str) -> str:
        marker = "v1" if "marker:v1" in cvr_json else "v2"
        return f"{style} caption from {marker}."


def test_pipeline_isolates_a_failed_task_and_writes_all_results(tmp_path: Path) -> None:
    """Pre-existing Task 13 behavior: a download failure takes only that task down.

    The failed task never reaches the vision or style stages, so the others'
    CVR work proceeds; the failed task's requested style is emitted with an
    empty caption string so its key is still present for scoring.
    """

    input_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output" / "results.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "task_id": "v1",
                    "video_url": "https://example.test/v1.mp4",
                    "styles": ["Formal"],
                },
                {
                    "task_id": "v2",
                    "video_url": "https://example.test/v2.mp4",
                    "styles": ["Sarcastic"],
                },
                {
                    "task_id": "failed",
                    "video_url": "https://example.test/failed.mp4",
                    "styles": ["Humorous-Tech"],
                },
            ]
        ),
        encoding="utf-8",
    )
    metadata = VideoMetadata(1.0, 1.0, 1, 16, 12)
    vision_client = _DeterministicVisionClient()
    # Two tasks reach the CVR stage; the failed one fails download first.
    expected_vision_calls = 2

    def downloader(task: VideoTask, run_directory: Path) -> DownloadResult:
        if task.task_id == "failed":
            return DownloadResult(
                task_id=task.task_id,
                failure=DownloadFailure(
                    task_id=task.task_id,
                    kind=DownloadFailureKind.REQUEST,
                    message="download failed",
                ),
            )
        return DownloadResult(task_id=task.task_id, path=run_directory / f"{task.task_id}.mp4")

    def inspector(task_id: str, video_path: Path) -> VideoInspectionResult:
        return VideoInspectionResult(task_id=task_id, metadata=metadata)

    def sampler(video_path: Path, video_metadata: VideoMetadata) -> list[FrameSample]:
        return [FrameSample(0, 0.0, "data:image/jpeg;base64,ZmFrZQ==")]

    exit_code = run_pipeline(
        input_path=input_path,
        output_path=output_path,
        vision_client=vision_client,
        style_client=_MarkerAwareStyleClient(),
        downloader=downloader,
        inspector=inspector,
        sampler=sampler,
    )

    assert exit_code == 0
    assert vision_client.calls == expected_vision_calls
    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {"task_id": "v1", "captions": {"formal": "Formal caption from v1."}},
        {"task_id": "v2", "captions": {"sarcastic": "Sarcastic caption from v2."}},
        {"task_id": "failed", "captions": {"humorous_tech": ""}},
    ]


def test_pipeline_does_not_block_next_cvr_on_inflight_style_generation(
    tmp_path: Path,
) -> None:
    """Task 13: a video's in-flight style generation does not block the next CVR.

    Style generation for v1 is parked on a ``threading.Event`` that is only set
    by v2's vision call. If the pipeline awaited style generation before moving
    on, this would deadlock (the test would time out). The log order asserted at
    the end confirms v2's CVR completed before v1's style generation completed.
    """

    input_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output" / "results.json"
    _write_two_tasks(input_path)
    downloader, inspector, sampler = _make_fakes(tmp_path)

    style_v1_release = threading.Event()
    style_v1_started = threading.Event()
    log: list[str] = []
    log_lock = threading.Lock()

    def mark(label: str) -> None:
        with log_lock:
            log.append(label)

    class BlockingVisionClient:
        def __init__(self) -> None:
            self.calls = 0

        def generate_cvr(self, frames: list[FrameSample], metadata: VideoMetadata) -> str:
            self.calls += 1
            task_id = f"v{self.calls}"
            if self.calls == 2:
                # v2's CVR has finished: now release the parked style-gen for v1.
                style_v1_release.set()
                mark(f"vision-finish:{task_id}")
                return _cvr_json(task_id)
            mark(f"vision-finish:{task_id}")
            return _cvr_json(task_id)

    class BlockingStyleClient:
        def __init__(self) -> None:
            self.calls = 0

        def generate_caption(self, cvr_json: str, style: str) -> str:
            self.calls += 1
            if "marker:v1" in cvr_json:
                style_v1_started.set()
                # Hold v1's style generation until v2's CVR releases us; the test
                # would hang here if the main thread waited for this future.
                assert style_v1_release.wait(timeout=10.0), (
                    "v2 CVR never released v1 style generation"
                )
                mark(f"style-finish:v1:{style}")
                return f"{style} caption from v1."
            mark(f"style-finish:v2:{style}")
            return f"{style} caption from v2."

    vision_client = BlockingVisionClient()
    exit_code = run_pipeline(
        input_path=input_path,
        output_path=output_path,
        vision_client=vision_client,
        style_client=BlockingStyleClient(),
        downloader=downloader,
        inspector=inspector,
        sampler=sampler,
        style_workers=2,
    )

    assert exit_code == 0
    assert vision_client.calls == 2, "v2's CVR must have been invoked"
    assert style_v1_started.is_set(), "style generation for v1 must have started"
    # The release path proves v2's CVR was called (called .set()) before v1's style
    # generation completed. Cross-check with log ordering.
    v2_vision = log.index("vision-finish:v2")
    first_v1_style = next(i for i, e in enumerate(log) if e.startswith("style-finish:v1:"))
    assert v2_vision < first_v1_style, (
        f"v2 CVR completed only at log index {v2_vision} while v1 style finished earlier "
        f"at {first_v1_style}; full log: {log!r}"
    )

    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {"task_id": "v1", "captions": {"formal": "Formal caption from v1."}},
        {"task_id": "v2", "captions": {"sarcastic": "Sarcastic caption from v2."}},
    ]


def test_pipeline_collects_style_results_in_input_order_even_when_completed_out_of_order(
    tmp_path: Path,
) -> None:
    """Task 13: results are matched to ``task_id`` regardless of completion order.

    v1's style generation is artificially slowed per call while v2's runs
    immediately, so v2 completes first; the output JSON is still ordered by
    input order with each task's captions mapped back to its own ``task_id``.
    """

    input_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output" / "results.json"
    _write_two_tasks(input_path)
    downloader, inspector, sampler = _make_fakes(tmp_path)

    completion_log: list[str] = []
    completion_lock = threading.Lock()
    calls_per_marker: dict[str, int] = {"v1": 0, "v2": 0}

    class OutOfOrderStyleClient:
        def generate_caption(self, cvr_json: str, style: str) -> str:
            marker = "v1" if "marker:v1" in cvr_json else "v2"
            if marker == "v1":
                # Slow every v1 style call so v2's whole style stage finishes first.
                time.sleep(0.2)
            with completion_lock:
                calls_per_marker[marker] += 1
                if calls_per_marker[marker] == 4:
                    completion_log.append(f"task-complete:{marker}")
            return f"{style} caption from {marker}."

    exit_code = run_pipeline(
        input_path=input_path,
        output_path=output_path,
        vision_client=_DeterministicVisionClient(),
        style_client=OutOfOrderStyleClient(),
        downloader=downloader,
        inspector=inspector,
        sampler=sampler,
        style_workers=2,
    )

    assert exit_code == 0
    assert completion_log == ["task-complete:v2", "task-complete:v1"], (
        f"expected v2 to complete before v1; got {completion_log!r}"
    )
    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {"task_id": "v1", "captions": {"formal": "Formal caption from v1."}},
        {"task_id": "v2", "captions": {"sarcastic": "Sarcastic caption from v2."}},
    ]


def test_pipeline_isolates_style_generation_failure_from_next_video(
    tmp_path: Path,
) -> None:
    """Task 13: a style-generation failure for video N does not affect video N+1.

    v1's style stage raises; v1 must surface as an empty `formal` caption while v2
    still produces its sarcastic caption and is fully serialized.
    """

    input_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output" / "results.json"
    _write_two_tasks(input_path)
    downloader, inspector, sampler = _make_fakes(tmp_path)

    class FailingForV1StyleClient:
        def generate_caption(self, cvr_json: str, style: str) -> str:
            if "marker:v1" in cvr_json:
                raise RuntimeError("style model boom for v1")
            return f"{style} caption from v2."

    exit_code = run_pipeline(
        input_path=input_path,
        output_path=output_path,
        vision_client=_DeterministicVisionClient(),
        style_client=FailingForV1StyleClient(),
        downloader=downloader,
        inspector=inspector,
        sampler=sampler,
        style_workers=2,
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {"task_id": "v1", "captions": {"formal": ""}},
        {"task_id": "v2", "captions": {"sarcastic": "Sarcastic caption from v2."}},
    ]