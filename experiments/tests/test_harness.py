"""Tests for experiments/harness.py: config loading, overrides, and MLflow setup.

No network or model calls. These tests cover the pure configuration layer in isolation.
"""

from pathlib import Path

import pytest

import harness
from harness import (
    DEFAULT_TRACKING_URI,
    EXPERIMENT_NAME,
    ExperimentConfig,
    FrameSamplingConfig,
    ModelConfig,
    apply_overrides,
    load_config,
    setup_mlflow,
)


def _write_config(tmp_path: Path, name: str, body: str) -> Path:
    config_path = tmp_path / f"{name}.yaml"
    config_path.write_text(body, encoding="utf-8")
    return config_path


def test_load_config_inline_prompts_uses_defaults_for_omitted_model_sections(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        "inline",
        """
name: exp_inline
video_path: /tmp/sample.mp4
system_prompt: |
  Inline CVR system prompt.
user_prompt_template: |
  Inline template {frame_count} {duration_seconds:.1f} {metadata_json} {timestamp_lines}
frame_sampling:
  num_frames: 8
  max_resolution: 512
  fallback_fps: 2
""",
    )

    config = load_config(config_path)

    assert config.name == "exp_inline"
    assert config.video_path == "/tmp/sample.mp4"
    assert config.system_prompt.strip() == "Inline CVR system prompt."
    assert "{frame_count}" in config.user_prompt_template
    assert config.frame_sampling == FrameSamplingConfig(8, 512, 2)
    # Omitted model sections default to production constants.
    assert config.cvr_model.name == "accounts/fireworks/models/qwen2p5-vl-32b-instruct"
    assert config.style_model.name == "accounts/fireworks/models/gpt-oss-120b"
    assert config.cvr_model.temperature == 0.1
    assert config.style_model.temperature == 0.2


def test_load_config_file_backed_prompts_resolves_paths_relative_to_config(tmp_path: Path) -> None:
    (tmp_path / "sys_prompt.md").write_text("# External system prompt", encoding="utf-8")
    (tmp_path / "user_prompt.md").write_text(
        "External template {frame_count} {duration_seconds:.1f}", encoding="utf-8"
    )
    config_path = _write_config(
        tmp_path,
        "filebacked",
        """
name: exp_filebacked
video_path: /tmp/sample.mp4
system_prompt_path: sys_prompt.md
user_prompt_template_path: user_prompt.md
""",
    )

    config = load_config(config_path)

    assert config.system_prompt == "# External system prompt"
    assert config.user_prompt_template.startswith("External template")
    assert "{frame_count}" in config.user_prompt_template


def test_load_config_rejects_specifying_both_inline_and_path_for_a_prompt(tmp_path: Path) -> None:
    (tmp_path / "p.md").write_text("external", encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        "both",
        """
name: exp_both
video_path: /tmp/sample.mp4
system_prompt: inline value
system_prompt_path: p.md
user_prompt_template: tpl {frame_count} {duration_seconds:.1f} {metadata_json} {timestamp_lines}
""",
    )

    with pytest.raises(ValueError, match="exactly one of 'system_prompt' or 'system_prompt_path'"):
        load_config(config_path)


def test_load_config_rejects_missing_prompt(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        "noprompt",
        """
name: exp_noprompt
video_path: /tmp/sample.mp4
""",
    )

    with pytest.raises(ValueError, match="system_prompt is required"):
        load_config(config_path)


def test_load_config_overrides_cvr_and_style_model_sections(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        "models",
        """
name: exp_models
video_path: /tmp/sample.mp4
system_prompt: s
user_prompt_template: t {frame_count} {duration_seconds:.1f} {metadata_json} {timestamp_lines}
cvr_model:
  name: accounts/fireworks/models/alt-vlm
  temperature: 0.3
  max_tokens: 2048
style_model:
  name: accounts/fireworks/models/alt-text
  temperature: 0.5
  max_tokens: 128
""",
    )

    config = load_config(config_path)

    assert config.cvr_model == ModelConfig("accounts/fireworks/models/alt-vlm", 0.3, 2048)
    assert config.style_model == ModelConfig("accounts/fireworks/models/alt-text", 0.5, 128)


def test_apply_overrides_updates_video_path_and_frame_sampling() -> None:
    base = ExperimentConfig(
        name="exp",
        video_path="/original.mp4",
        system_prompt="s",
        user_prompt_template="t",
        frame_sampling=FrameSamplingConfig(16, 768, 1),
        cvr_model=ModelConfig("m", 0.1, 100),
        style_model=ModelConfig("m", 0.2, 100),
    )

    overridden = apply_overrides(
        base,
        {"video_path": "/overridden.mp4", "num_frames": 8, "max_resolution": 512, "fallback_fps": 2},
    )

    assert overridden.video_path == "/overridden.mp4"
    assert overridden.frame_sampling == FrameSamplingConfig(8, 512, 2)
    # Untouched fields preserved.
    assert overridden.name == base.name
    assert overridden.system_prompt == base.system_prompt
    assert overridden.cvr_model == base.cvr_model


def test_apply_overrides_with_empty_dict_returns_equivalent_config() -> None:
    base = ExperimentConfig(
        name="exp",
        video_path="/v.mp4",
        system_prompt="s",
        user_prompt_template="t",
        frame_sampling=FrameSamplingConfig(16, 768, 1),
        cvr_model=ModelConfig("m", 0.1, 100),
        style_model=ModelConfig("m", 0.2, 100),
    )

    overridden = apply_overrides(base, {})

    assert overridden == base


def test_setup_mlflow_uses_sqlite_tracking_and_creates_experiment(tmp_path: Path) -> None:
    tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    import mlflow

    returned = setup_mlflow(tracking_uri)

    assert returned == tracking_uri
    assert mlflow.get_tracking_uri() == tracking_uri
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    assert experiment is not None


def test_setup_mlflow_rejects_non_sqlite_tracking_uri() -> None:
    with pytest.raises(ValueError, match="SQLite MLflow backend"):
        setup_mlflow("file:./experiments/mlruns")