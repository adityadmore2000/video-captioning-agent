import json
from pathlib import Path

from video_captioning_agent.contracts import FrameSample, VideoMetadata, VideoTask
from video_captioning_agent.downloader import (
    DownloadFailure,
    DownloadFailureKind,
    DownloadResult,
)
from video_captioning_agent.pipeline import run_pipeline
from video_captioning_agent.video_inspection import VideoInspectionResult


class FakeVisionClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_cvr(self, frames: list[FrameSample], metadata: VideoMetadata) -> str:
        self.calls += 1
        return json.dumps(
            {
                "scene": "Kitchen",
                "primary_subjects": ["A person"],
                "important_objects": ["A bowl"],
                "timeline": ["0.0s: A person holds a bowl."],
                "overall_summary": "A person holds a bowl in a kitchen.",
            }
        )


class FakeStyleClient:
    def generate_caption(self, cvr_json: str, style: str) -> str:
        return f"{style} caption."


def _write_tasks(path: Path) -> None:
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
                {
                    "task_id": "failed",
                    "video_url": "https://example.test/failed.mp4",
                    "styles": ["Humorous-Tech"],
                },
            ]
        ),
        encoding="utf-8",
    )


def test_pipeline_isolates_a_failed_task_and_writes_all_results(tmp_path: Path) -> None:
    input_path = tmp_path / "tasks.json"
    output_path = tmp_path / "output" / "results.json"
    _write_tasks(input_path)
    metadata = VideoMetadata(1.0, 1.0, 1, 16, 12)
    vision_client = FakeVisionClient()

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
        style_client=FakeStyleClient(),
        downloader=downloader,
        inspector=inspector,
        sampler=sampler,
    )

    assert exit_code == 0
    assert vision_client.calls == 2
    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        {"task_id": "v1", "captions": {"formal": "Formal caption."}},
        {"task_id": "v2", "captions": {"sarcastic": "Sarcastic caption."}},
        {"task_id": "failed", "captions": {"humorous_tech": ""}},
    ]
