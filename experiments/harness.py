# Shared helpers for the experiment-tracking harness.
#
# Pure configuration + MLflow setup. This file deliberately imports nothing heavy
# from ``src/`` so config loading can be unit-tested in isolation.
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml


EXPERIMENT_NAME = "video_captioning_cvr_experiments_v2"
DEFAULT_TRACKING_URI = "sqlite:///experiments/mlflow.db"
DEFAULT_ARTIFACT_ROOT = "./experiments/mlruns"


@dataclass(frozen=True, slots=True)
class FrameSamplingConfig:
    """Frame-sampling parameters forwarded to ``sample_frames``."""

    num_frames: int = 16
    max_resolution: int = 768
    fallback_fps: int = 1


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Model name and generation parameters for one VLM/text-model call."""

    name: str
    temperature: float
    max_tokens: int


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """One loaded experiment configuration, ready to drive a single MLflow run.

    The harness supports loading ``system_prompt`` / ``user_prompt_template`` either
    inline (from the YAML) or from external ``.md`` / ``.txt`` files via a
    ``system_prompt_path`` / ``user_prompt_template_path`` field (see
    EXPERIMENT_TRACKING.md). File references are resolved relative to the config file.
    """

    name: str
    video_path: str
    system_prompt: str
    user_prompt_template: str
    frame_sampling: FrameSamplingConfig
    cvr_model: ModelConfig
    style_model: ModelConfig


def _resolve_text_field(
    config_dir: Path, raw: dict[str, Any], inline_key: str, path_key: str, field_name: str
) -> str:
    """Return prompt text either inline from ``raw[inline_key]`` or read from a file path."""

    inline_value = raw.get(inline_key)
    path_value = raw.get(path_key)
    if inline_value is not None and path_value is not None:
        raise ValueError(
            f"{field_name}: provide exactly one of '{inline_key}' or '{path_key}', not both"
        )
    if inline_value is not None:
        if not isinstance(inline_value, str) or not inline_value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return inline_value
    if path_value is not None:
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError(f"{path_key} must be a non-empty path string")
        resolved_path = (config_dir / path_value).resolve()
        if not resolved_path.is_file():
            raise FileNotFoundError(f"{field_name} file not found: {resolved_path}")
        return resolved_path.read_text(encoding="utf-8")
    raise ValueError(f"{field_name} is required (as '{inline_key}' or '{path_key}')")


def _model_section(raw: dict[str, Any], section_name: str, fallback: ModelConfig) -> ModelConfig:
    """Build a ModelConfig, allowing a section to default to ``fallback`` if omitted."""

    section = raw.get(section_name)
    if section is None:
        return fallback
    if not isinstance(section, dict):
        raise ValueError(f"{section_name} must be a mapping")
    return ModelConfig(
        name=section.get("name", fallback.name),
        temperature=section.get("temperature", fallback.temperature),
        max_tokens=section.get("max_tokens", fallback.max_tokens),
    )


def load_config(config_path: Path) -> ExperimentConfig:
    """Load and validate one experiment config from a YAML file.

    The schema matches EXPERIMENT_TRACKING.md's example. ``cvr_model`` defaults to the
    production vision-model constants (Qwen2.5-VL 32B Instruct); ``style_model`` defaults
    to the production style-model constants (gpt-oss-120b). Each can be overridden in the
    YAML via the ``cvr_model`` / ``style_model`` sections.
    """

    from video_captioning_agent.cvr_client import (
        CVR_SYSTEM_PROMPT,
        CVR_USER_PROMPT_TEMPLATE,
        VISION_MAX_TOKENS,
        VISION_MODEL_ID,
        VISION_TEMPERATURE,
    )
    from video_captioning_agent.style_generator import (
        STYLE_MAX_TOKENS,
        STYLE_MODEL_ID,
        STYLE_TEMPERATURE,
    )

    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Experiment config must be a YAML mapping")

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Experiment config must have a non-empty 'name'")
    video_path = raw.get("video_path")
    if not isinstance(video_path, str) or not video_path.strip():
        raise ValueError("Experiment config must have a non-empty 'video_path'")

    config_dir = config_path.resolve().parent
    system_prompt = _resolve_text_field(
        config_dir, raw, "system_prompt", "system_prompt_path", "system_prompt"
    )
    user_prompt_template = _resolve_text_field(
        config_dir, raw, "user_prompt_template", "user_prompt_template_path", "user_prompt_template"
    )

    sampling_raw = raw.get("frame_sampling", {})
    if not isinstance(sampling_raw, dict):
        raise ValueError("frame_sampling must be a mapping")
    frame_sampling = FrameSamplingConfig(
        num_frames=sampling_raw.get("num_frames", 16),
        max_resolution=sampling_raw.get("max_resolution", 768),
        fallback_fps=sampling_raw.get("fallback_fps", 1),
    )

    cvr_model = _model_section(
        raw,
        "cvr_model",
        ModelConfig(name=VISION_MODEL_ID, temperature=VISION_TEMPERATURE, max_tokens=VISION_MAX_TOKENS),
    )
    style_model = _model_section(
        raw,
        "style_model",
        ModelConfig(name=STYLE_MODEL_ID, temperature=STYLE_TEMPERATURE, max_tokens=STYLE_MAX_TOKENS),
    )

    return ExperimentConfig(
        name=name,
        video_path=video_path,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        frame_sampling=frame_sampling,
        cvr_model=cvr_model,
        style_model=style_model,
    )


def setup_mlflow(
    tracking_uri: str = DEFAULT_TRACKING_URI, artifact_root: str = DEFAULT_ARTIFACT_ROOT
) -> str:
    """Configure SQLite-backed MLflow tracking and ensure the experiment exists.

    Returns the resolved tracking URI so callers (and tests) can assert on it.

    MLflow 3.x places the plain filesystem backend (``file:``) in maintenance mode and
    raises on startup unless a database backend is used. This harness follows MLflow's
    recommended path: tracking metadata lives in a local SQLite database
    (``sqlite:///experiments/mlflow.db``), while artifacts (the logged prompts and CVR
    JSON) still live as files under ``./experiments/mlruns``. This keeps the setup a
    lightweight single-command local operation — ``mlflow ui`` with a SQLite backend is
    sufficient for this project's sequential, single-user use case, and no
    ``mlflow server`` background process is required. ``MLFLOW_ALLOW_FILE_STORE`` is
    intentionally NOT set — following the database-backend recommendation keeps the
    harness working on future MLflow versions.
    """

    import mlflow

    if not tracking_uri.startswith("sqlite:"):
        raise ValueError(
            "This harness uses a SQLite MLflow backend; tracking_uri must start with 'sqlite:'"
        )
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)
    mlflow.set_registry_uri(tracking_uri)
    return tracking_uri


def apply_overrides(config: ExperimentConfig, overrides: dict[str, Any]) -> ExperimentConfig:
    """Return a new ExperimentConfig with CLI overrides applied.

    Supported override keys: ``video_path``, ``num_frames``, ``max_resolution``,
    ``fallback_fps``. Each is optional; absent keys inherit from ``config``.
    """

    if not overrides:
        return config
    video_path = overrides.get("video_path", config.video_path)
    frame_sampling = FrameSamplingConfig(
        num_frames=overrides.get("num_frames", config.frame_sampling.num_frames),
        max_resolution=overrides.get("max_resolution", config.frame_sampling.max_resolution),
        fallback_fps=overrides.get("fallback_fps", config.frame_sampling.fallback_fps),
    )
    return ExperimentConfig(
        name=config.name,
        video_path=video_path,
        system_prompt=config.system_prompt,
        user_prompt_template=config.user_prompt_template,
        frame_sampling=frame_sampling,
        cvr_model=config.cvr_model,
        style_model=config.style_model,
    )