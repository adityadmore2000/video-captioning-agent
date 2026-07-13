"""Single-run experiment CLI.

Runs one experiment config end-to-end inside a single MLflow run: frame sampling
(reuses Task 6), CVR generation (reuses Task 7 VLM client with config-driven overrides),
and style generation (reuses Task 10's all-4-styles generator). Logs config, prompts,
latencies, and the resulting CVR + 4 captions as artifacts. CVR-generation and
style-generation are both tracked under the same MLflow experiment per the user's decision.

Usage:
    python experiments/run_experiment.py --config experiments/configs/exp_001.yaml
    python experiments/run_experiment.py --config exp_001.yaml --video-path /other.mp4 --num-frames 8

This is dev-only tooling. It does not touch the /input->/output contract, the production
pipeline, or the Docker image (Task 14). See EXPERIMENT_TRACKING.md.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any


def _bootstrap_sys_path() -> None:
    """Insert the repo's ``src/`` and ``experiments/`` dirs onto ``sys.path``.

    Imports the production pipeline package from ``src/`` and the harness from
    ``experiments/`` without requiring the caller to set ``PYTHONPATH``. Paths are
    resolved relative to this script's own location so it runs from any CWD.
    """

    experiments_dir = Path(__file__).resolve().parent
    repo_root = experiments_dir.parent
    src_dir = repo_root / "src"
    for path in (str(src_dir), str(experiments_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)


_bootstrap_sys_path()

from dotenv import load_dotenv

load_dotenv()

from video_captioning_agent.contracts import CanonicalVideoReport
from video_captioning_agent.cvr_client import CvrGenerationError, FireworksCvrClient
from video_captioning_agent.cvr_parser import parse_cvr_response
from video_captioning_agent.frame_sampler import sample_frames
from video_captioning_agent.style_generator import (
    CaptionGenerationFailure,
    CaptionGenerationResult,
    FireworksStyleClient,
    generate_all_captions,
    StyleGenerationError,
)
from video_captioning_agent.video_inspection import inspect_video

from harness import (
    DEFAULT_TRACKING_URI,
    ExperimentConfig,
    apply_overrides,
    load_config,
    setup_mlflow,
)


LOGGER = logging.getLogger("experiments.run_experiment")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one video-captioning experiment and log it to MLflow."
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to the YAML config file.")
    parser.add_argument(
        "--tracking-uri",
        type=str,
        default=DEFAULT_TRACKING_URI,
        help="MLflow tracking URI (sqlite: scheme; default: sqlite:///experiments/mlflow.db).",
    )
    parser.add_argument("--video-path", type=str, default=None, help="Override config's video_path.")
    parser.add_argument("--num-frames", type=int, default=None, help="Override config's num_frames.")
    parser.add_argument(
        "--max-resolution", type=int, default=None, help="Override config's max_resolution."
    )
    parser.add_argument("--fallback-fps", type=int, default=None, help="Override config's fallback_fps.")
    return parser


def _overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if args.video_path is not None:
        overrides["video_path"] = args.video_path
    if args.num_frames is not None:
        overrides["num_frames"] = args.num_frames
    if args.max_resolution is not None:
        overrides["max_resolution"] = args.max_resolution
    if args.fallback_fps is not None:
        overrides["fallback_fps"] = args.fallback_fps
    return overrides


def _log_common_params(config: ExperimentConfig) -> None:
    """Log config params via mlflow.log_params (short strings per MLflow's param limits)."""

    import mlflow

    mlflow.log_params(
        {
            "name": config.name,
            "video_path": config.video_path,
            "num_frames": config.frame_sampling.num_frames,
            "max_resolution": config.frame_sampling.max_resolution,
            "fallback_fps": config.frame_sampling.fallback_fps,
            "cvr_model_name": config.cvr_model.name,
            "cvr_temperature": config.cvr_model.temperature,
            "cvr_max_tokens": config.cvr_model.max_tokens,
            "style_model_name": config.style_model.name,
            "style_temperature": config.style_model.temperature,
            "style_max_tokens": config.style_model.max_tokens,
        }
    )


def _log_prompt_artifacts(config: ExperimentConfig) -> None:
    """Log full prompt text as artifacts (params have a length limit)."""

    import mlflow

    mlflow.log_text(config.system_prompt, "system_prompt.txt")
    mlflow.log_text(config.user_prompt_template, "user_prompt_template.txt")


def _run_cvr_stage(config: ExperimentConfig, video_path: Path) -> tuple[str, float]:
    """Inspect, sample frames, call the VLM; return (raw_cvr_text, latency_seconds)."""

    inspection = inspect_video("experiment", video_path)
    if not inspection.succeeded or inspection.metadata is None:
        raise RuntimeError(
            f"Video inspection failed: {inspection.failure.message if inspection.failure else 'unknown'}"
        )

    frames = sample_frames(
        video_path,
        inspection.metadata,
        target_frames=config.frame_sampling.num_frames,
        max_resolution=config.frame_sampling.max_resolution,
    )

    vision_client = FireworksCvrClient(
        system_prompt=config.system_prompt,
        user_prompt_template=config.user_prompt_template,
        model_id=config.cvr_model.name,
        temperature=config.cvr_model.temperature,
        max_tokens=config.cvr_model.max_tokens,
    )
    start = time.perf_counter()
    raw_cvr = vision_client.generate_cvr(frames, inspection.metadata)
    latency = time.perf_counter() - start
    return raw_cvr, latency


def _run_style_stage(
    config: ExperimentConfig, report: CanonicalVideoReport
) -> tuple[CaptionGenerationResult, float]:
    """Generate all 4 supported-style captions from the CVR; return (result, latency).

    Style system prompt (STYLE_SYSTEM_PROMPT in src/) is NOT user-configurable per
    EXPERIMENT_TRACKING.md's config schema — only CVR prompts and model/temperature/
    max_tokens for both stages are swappable. So this client omits the system_prompt kwarg
    and inherits the production default.

    Returns the full :class:`CaptionGenerationResult` (all 4 captions plus per-style
    failures with raw response bodies) so the caller can log diagnostics for any style
    that failed — e.g. refusal-adjacent hedging or prose commentary from a smaller model.
    """

    style_client = FireworksStyleClient(
        model_id=config.style_model.name,
        temperature=config.style_model.temperature,
        max_tokens=config.style_model.max_tokens,
    )
    start = time.perf_counter()
    result = generate_all_captions(style_client, report)
    latency = time.perf_counter() - start
    return result, latency


def _failures_payload(failures: tuple[CaptionGenerationFailure, ...]) -> list[dict[str, object]]:
    """Serialize per-style failures (including raw response bodies) for MLflow logging."""

    return [
        {
            "style": failure.style,
            "message": failure.message,
            "raw_response": failure.raw_response,
        }
        for failure in failures
    ]


def run_one_experiment(
    config: ExperimentConfig, tracking_uri: str = DEFAULT_TRACKING_URI
) -> dict[str, Any]:
    """Execute one config inside a single MLflow run.

    Returns a small summary dict for stdout printing. CVR failures abort the run (no
    captions to track); style-generation failures still log whatever captions succeeded.
    """

    import mlflow

    setup_mlflow(tracking_uri)
    with mlflow.start_run(run_name=config.name) as run:
        _log_common_params(config)
        _log_prompt_artifacts(config)

        video_path = Path(config.video_path)
        if not video_path.is_file():
            raise FileNotFoundError(f"video_path does not exist: {video_path}")

        cvr_text, cvr_latency = _run_cvr_stage(config, video_path)
        mlflow.log_metric("cvr_latency_seconds", cvr_latency)
        mlflow.log_text(cvr_text, "cvr_raw.txt")

        parsed = parse_cvr_response("experiment", cvr_text)
        if not parsed.succeeded or parsed.report is None:
            mlflow.log_text(
                json.dumps({"parse_failure": parsed.failure.message if parsed.failure else None}),
                "cvr_parse_failure.json",
            )
            raise RuntimeError(
                f"CVR parsing failed: {parsed.failure.message if parsed.failure else 'unknown'}"
            )

        report = parsed.report
        mlflow.log_dict(report.to_dict(), "cvr_output.json")

        captions_result, style_latency = _run_style_stage(config, report)
        mlflow.log_metric("style_latency_seconds", style_latency)
        captions = captions_result.captions
        mlflow.log_dict(captions, "style_captions.json")
        if captions_result.failures:
            mlflow.log_dict(
                _failures_payload(captions_result.failures), "style_failures.json"
            )

        return {
            "run_id": run.info.run_id,
            "cvr_latency_seconds": cvr_latency,
            "style_latency_seconds": style_latency,
            "cvr": report.to_dict(),
            "captions": captions,
            "style_failures": _failures_payload(captions_result.failures),
        }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = _build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    config = apply_overrides(config, _overrides_from_args(args))

    try:
        summary = run_one_experiment(config)
    except (CvrGenerationError, StyleGenerationError, FileNotFoundError, RuntimeError, OSError) as error:
        LOGGER.error("Experiment '%s' failed: %s", config.name, error)
        return 1

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())