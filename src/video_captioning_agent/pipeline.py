"""Sequential, failure-isolated orchestration for video captioning tasks.

The vision/CVR stage runs one video at a time, in input order, on the calling
thread (Task 13). After each video's CVR is parsed, style generation for that
video is dispatched as a fire-and-collect background task so it overlaps with
the next video's frame sampling + CVR call, rather than blocking it. Each
pending style-generation result is collected by its submission index and
matched back to its task before serialization (Task 12). Task-level failure
isolation holds across both stages: a task that fails before style generation
yields empty captions at its slot; a style-generation failure for task N is
recorded for task N alone and never affects task N+1's VLM processing.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import logging
import os
from pathlib import Path
import tempfile
from typing import Callable

import requests

from ._env import load_env_file
from .caption_validation import validate_all_captions
from .contracts import (
    CanonicalVideoReport,
    FrameSample,
    TaskResult,
    VideoMetadata,
    VideoTask,
)
from .cvr_client import CvrGenerationError, FireworksCvrClient
from .cvr_parser import parse_cvr_response
from .deployment_manager import (
    DeploymentProvisioningError,
    FireworksDeploymentManager,
    resolve_vision_model_id,
)
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

STYLE_WORKERS = 4
"""Maximum number of style-generation tasks kept in flight at once.

This bounded pool enables style generation for video N to overlap with vision
processing for video N+1, without restructuring the vision stage itself into
bounded concurrency across all tasks (which still runs one video at a time,
in order, on the calling thread).
"""


def run_pipeline(
    input_path: Path = INPUT_TASKS_PATH,
    output_path: Path = OUTPUT_RESULTS_PATH,
    vision_client: VisionClient | None = None,
    style_client: StyleCaptionClient | None = None,
    downloader: DownloadFunction = download_video,
    inspector: InspectionFunction = inspect_video,
    sampler: SamplingFunction = sample_frames,
    *,
    style_workers: int = STYLE_WORKERS,
) -> int:
    """Process all structurally valid tasks and always return exit code zero.

    Provisioning (if configured) runs first as container initialization —
    before any task loading. A provisioning failure is fatal and propagates
    to the caller, since infrastructure failures are not task-level degradation.

    Task-level problems yield empty strings for that task's requested output
    styles, preserving successfully completed tasks and the mandated output schema.

    The vision (CVR) stage is processed one video at a time, in input order, on
    the calling thread. Style generation for a parsed CVR is dispatched as a
    fire-and-collect background ``Future`` so it overlaps with the next video's
    VLM work instead of blocking it; results are collected and matched back to
    their tasks by submission index before serialization (Task 12).
    """

    explicit_model = os.environ.get("FIREWORKS_VISION_MODEL")
    deployment_manager: FireworksDeploymentManager | None = None
    deployment_name = os.environ.get("FIREWORKS_VISION_DEPLOYMENT_NAME") or None

    if (
        not explicit_model
        and vision_client is None
        and deployment_name
        and os.environ.get("FIREWORKS_VISION_BASE_MODEL")
    ):
        LOGGER.info(
            "Auto-provisioning vision deployment %s from base model %s",
            deployment_name,
            os.environ.get("FIREWORKS_VISION_BASE_MODEL"),
        )
        deployment_manager = FireworksDeploymentManager()

    if vision_client is None or style_client is None:
        if vision_client is None:
            vision_model_id = resolve_vision_model_id(
                manager=deployment_manager,
            )
            vision_client = FireworksCvrClient(model_id=vision_model_id)
            if deployment_manager is not None:
                LOGGER.info(
                    "Vision deployment ready: %s. "
                    "Add FIREWORKS_VISION_MODEL=%s to .env to skip provisioning on future runs.",
                    vision_model_id,
                    vision_model_id,
                )
        style_client = style_client or FireworksStyleClient()

    loaded_tasks = load_tasks(input_path)
    if loaded_tasks.load_errors:
        for error in loaded_tasks.load_errors:
            LOGGER.error("Input loading failed: %s", error)
        write_results([], output_path)
        return 1
    if not loaded_tasks.tasks:
        if loaded_tasks.task_errors:
            LOGGER.warning(
                "All %d task(s) were invalid; nothing to process.",
                len(loaded_tasks.task_errors),
            )
            for error in loaded_tasks.task_errors:
                LOGGER.warning("  %s", error)
        write_results([], output_path)
        return 0

    tasks = loaded_tasks.tasks
    results: list[TaskResult | None] = [None] * len(tasks)
    pending_style: list[tuple[int, VideoTask, Future[TaskResult]]] = []

    with tempfile.TemporaryDirectory(prefix="video-captioning-") as temporary_directory:
        run_directory = Path(temporary_directory)
        try:
            with ThreadPoolExecutor(
                max_workers=max(1, style_workers),
                thread_name_prefix="style-generation",
            ) as executor:
                for index, task in enumerate(tasks):
                    eligibility = determine_task_eligibility(task)
                    if not eligibility.supported_styles:
                        results[index] = build_task_result(task, {})
                        continue

                    cvr_report = _run_vision_stage(
                        task,
                        run_directory,
                        vision_client,
                        downloader,
                        inspector,
                        sampler,
                    )
                    if cvr_report is None:
                        results[index] = build_task_result(task, {})
                        continue

                    future = executor.submit(
                        _run_style_stage, task, cvr_report, style_client
                    )
                    pending_style.append((index, task, future))

                for index, task, future in pending_style:
                    try:
                        results[index] = future.result()
                    except Exception as error:  # noqa: BLE001 - isolate per task
                        LOGGER.warning(
                            "Style generation failed for task %s: %s",
                            task.task_id,
                            error,
                        )
                        results[index] = build_task_result(task, {})
        finally:
            if (
                deployment_manager is not None
                and deployment_name
                and os.environ.get("FIREWORKS_VISION_TEARDOWN")
            ):
                deployment_manager.teardown(deployment_name)

    final_results: list[TaskResult] = [
        result if result is not None else build_task_result(task, {})
        for result, task in zip(results, tasks)
    ]
    write_results(final_results, output_path)
    return 0


def _run_vision_stage(
    task: VideoTask,
    run_directory: Path,
    vision_client: VisionClient,
    downloader: DownloadFunction,
    inspector: InspectionFunction,
    sampler: SamplingFunction,
) -> CanonicalVideoReport | None:
    """Run download -> inspection -> sampling -> CVR -> parse on the calling thread.

    Returns the parsed CVR on success, or ``None`` to signal any task-level
    failure (download, inspection, sampling, CVR generation, or CVR parsing),
    leaving the caller to record an empty task result and continue.
    """

    try:
        download_result = downloader(task, run_directory)
        if not download_result.succeeded or download_result.path is None:
            return None

        inspection_result = inspector(task.task_id, download_result.path)
        if not inspection_result.succeeded or inspection_result.metadata is None:
            return None

        frames = sampler(download_result.path, inspection_result.metadata)
        raw_cvr = vision_client.generate_cvr(frames, inspection_result.metadata)
        parsed_cvr = parse_cvr_response(task.task_id, raw_cvr)
        if not parsed_cvr.succeeded or parsed_cvr.report is None:
            return None
        return parsed_cvr.report
    except (CvrGenerationError, FrameSamplingError, requests.RequestException, OSError) as error:
        LOGGER.warning("Task %s vision stage failed: %s", task.task_id, error)
        return None


def _run_style_stage(
    task: VideoTask,
    report: CanonicalVideoReport,
    style_client: StyleCaptionClient,
) -> TaskResult:
    """Generate all 4 supported-style captions, validate, and filter to requested.

    Runs on a background worker; only the serialized CVR is admitted (no frames,
    URLs, or metadata). Any surfaced failure is task-scoped and is converted by
    the caller into an empty result for this task alone, leaving others intact.
    """

    # Task 10: generate all 4 supported styles unconditionally from the CVR. Task 11
    # validates that full 4-style set. Task 12 (build_task_result) then filters the
    # validated captions down to just this task's requested styles for output.
    generation = generate_all_captions(style_client, report)
    validation = validate_all_captions(generation.captions)
    return build_task_result(task, validation.captions)


def main() -> int:
    """Run the pipeline with provisioning handled as container initialization."""

    load_env_file()
    try:
        return run_pipeline()
    except (ValueError, DeploymentProvisioningError) as error:
        LOGGER.error("Provisioning failed: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())