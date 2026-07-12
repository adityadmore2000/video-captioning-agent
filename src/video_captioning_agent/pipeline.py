"""Sequential, failure-isolated orchestration for video captioning tasks."""

from __future__ import annotations

import logging
from pathlib import Path
import tempfile
from typing import Callable, Sequence

import requests

from .caption_validation import validate_all_captions
from .contracts import FrameSample, TaskResult, VideoMetadata, VideoTask
from .cvr_client import CvrGenerationError, FireworksCvrClient
from .cvr_parser import parse_cvr_response
from .downloader import DownloadResult, download_video
from .frame_sampler import FrameSamplingError, sample_frames
from .input_loader import INPUT_TASKS_PATH, load_tasks
from .result_writer import OUTPUT_RESULTS_PATH, build_task_result, write_results
from .style_generator import (
    FireworksStyleClient,
    StyleCaptionClient,
    generate_all_captions,
)
from .styles import determine_task_eligibility
from .video_inspection import VideoInspectionResult, inspect_video


LOGGER = logging.getLogger(__name__)
VisionClient = FireworksCvrClient
DownloadFunction = Callable[[VideoTask, Path], DownloadResult]
InspectionFunction = Callable[[str, Path], VideoInspectionResult]
SamplingFunction = Callable[[Path, VideoMetadata], list[FrameSample]]


def run_pipeline(
    input_path: Path = INPUT_TASKS_PATH,
    output_path: Path = OUTPUT_RESULTS_PATH,
    vision_client: VisionClient | None = None,
    style_client: StyleCaptionClient | None = None,
    downloader: DownloadFunction = download_video,
    inspector: InspectionFunction = inspect_video,
    sampler: SamplingFunction = sample_frames,
) -> int:
    """Process all structurally valid tasks and always return exit code zero.

    Any task-level problem yields empty strings for that task's requested output
    styles, preserving successfully completed tasks and the mandated output schema.
    """

    loaded_tasks = load_tasks(input_path)
    results: list[TaskResult] = []
    if not loaded_tasks.tasks:
        write_results(results, output_path)
        return 0

    if vision_client is None or style_client is None:
        try:
            vision_client = vision_client or FireworksCvrClient()
            style_client = style_client or FireworksStyleClient()
        except ValueError as error:
            LOGGER.error("Pipeline model client is unavailable: %s", error)
            results = [build_task_result(task, {}) for task in loaded_tasks.tasks]
            write_results(results, output_path)
            return 0

    with tempfile.TemporaryDirectory(prefix="video-captioning-") as temporary_directory:
        run_directory = Path(temporary_directory)
        for task in loaded_tasks.tasks:
            results.append(
                _process_task(
                    task,
                    run_directory,
                    vision_client,
                    style_client,
                    downloader,
                    inspector,
                    sampler,
                )
            )

    write_results(results, output_path)
    return 0


def _process_task(
    task: VideoTask,
    run_directory: Path,
    vision_client: VisionClient,
    style_client: StyleCaptionClient,
    downloader: DownloadFunction,
    inspector: InspectionFunction,
    sampler: SamplingFunction,
) -> TaskResult:
    eligibility = determine_task_eligibility(task)
    if not eligibility.supported_styles:
        return build_task_result(task, {})

    try:
        download_result = downloader(task, run_directory)
        if not download_result.succeeded or download_result.path is None:
            return build_task_result(task, {})

        inspection_result = inspector(task.task_id, download_result.path)
        if not inspection_result.succeeded or inspection_result.metadata is None:
            return build_task_result(task, {})

        frames = sampler(download_result.path, inspection_result.metadata)
        raw_cvr = vision_client.generate_cvr(frames, inspection_result.metadata)
        parsed_cvr = parse_cvr_response(task.task_id, raw_cvr)
        if not parsed_cvr.succeeded or parsed_cvr.report is None:
            return build_task_result(task, {})

        # Task 10: generate all 4 supported styles unconditionally from the CVR. Task 11
        # validates that full 4-style set. Task 12 (build_task_result) then filters the
        # validated captions down to just this task's requested styles for output.
        generation = generate_all_captions(style_client, parsed_cvr.report)
        validation = validate_all_captions(generation.captions)
        return build_task_result(task, validation.captions)
    except (CvrGenerationError, FrameSamplingError, requests.RequestException, OSError) as error:
        LOGGER.warning("Task %s failed: %s", task.task_id, error)
        return build_task_result(task, {})


def main() -> int:
    """Run the pipeline at the required `/input` and `/output` locations."""

    return run_pipeline()


if __name__ == "__main__":
    raise SystemExit(main())
