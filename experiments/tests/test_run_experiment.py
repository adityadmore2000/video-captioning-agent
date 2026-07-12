"""End-to-end tests for experiments/run_experiment.py.

These tests reuse the real production frame sampler (Task 6) and video inspector from
``src/`` against a tiny synthetic mp4 fixture written by OpenCV — exactly the reuse
contract EXPERIMENT_TRACKING.md requires ("call the real frame-sampling and VLM-client
code from src/"). The Fireworks HTTP layer (Task 7 vision + Task 10 style generation) is
mocked via ``requests.Session`` so no network or API key is required.

Both CVR-generation (Task 7) and style-generation (Task 10) stages are exercised and
logged in the same MLflow run, per the user's decision to track both in one experiment.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

import mlflow

import harness
from harness import (
    EXPERIMENT_NAME,
    ExperimentConfig,
    FrameSamplingConfig,
    ModelConfig,
    setup_mlflow,
)
import run_experiment


def _write_tiny_video(path: Path, frame_count: int = 10) -> Path:
    """Write a 10-frame 8x8 grayscale mp4 so inspect_video/sample_frames run for real."""

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 5.0, (8, 8))
    try:
        for _ in range(frame_count):
            writer.write(np.zeros((8, 8, 3), dtype=np.uint8))
    finally:
        writer.release()
    return path


def _valid_cvr_response_text() -> str:
    return json.dumps(
        {
            "scene": "Tiny fixture",
            "primary_subjects": ["A pixel"],
            "important_objects": ["A frame"],
            "timeline": ["0.0s: A pixel appears."],
            "overall_summary": "A pixel appears in a tiny fixture.",
        }
    )


def _mocked_session() -> Mock:
    """A Mock session that returns a CVR text for vision calls and a fixed caption for text calls.

    The harness's CVR client and style client both POST to FIREWORKS_URL. We distinguish
    by inspecting the request's model id: CVR uses the qwen VLM id, style uses gpt-oss-120b.
    """
    session = Mock()

    def post_side_effect(url, headers=None, json=None, timeout=None, **kwargs):
        response = Mock()
        response.raise_for_status = Mock()
        request_model = json.get("model") if isinstance(json, dict) else None
        content = (
            _valid_cvr_response_text()
            if request_model and "qwen" in request_model
            else "A caption."
        )
        response.json.return_value = {"choices": [{"message": {"content": content}}]}
        return response

    session.post.side_effect = post_side_effect
    return session


def _make_config(video_path: str) -> ExperimentConfig:
    return ExperimentConfig(
        name="exp_test",
        video_path=video_path,
        system_prompt="Test CVR system prompt.",
        user_prompt_template="Test template {frame_count} {duration_seconds:.1f} {metadata_json} {timestamp_lines}",
        frame_sampling=FrameSamplingConfig(num_frames=4, max_resolution=8, fallback_fps=1),
        cvr_model=ModelConfig("accounts/fireworks/models/qwen2p5-vl-32b-instruct", 0.1, 256),
        style_model=ModelConfig("accounts/fireworks/models/gpt-oss-120b", 0.2, 64),
    )


def test_run_one_experiment_logs_cvr_and_style_artifacts_to_one_mlflow_run(
    tmp_path: Path, monkeypatch
) -> None:
    tracking_uri = f"file:{tmp_path / 'mlruns'}"
    setup_mlflow(tracking_uri)
    video_path = _write_tiny_video(tmp_path / "fixture.mp4")
    config = _make_config(str(video_path))

    # Inject a mocked requests.Session into both Fireworks clients so no real network
    # call is made. Both clients accept a `session` kwarg (Task 7 + the additive Task 10
    # kwargs), so we patch the constructors to pre-inject it.
    session = _mocked_session()
    real_cvr_init = run_experiment.FireworksCvrClient.__init__
    real_style_init = run_experiment.FireworksStyleClient.__init__

    def patched_cvr_init(self, *args, **kwargs):
        kwargs.setdefault("session", session)
        real_cvr_init(self, *args, **kwargs)

    def patched_style_init(self, *args, **kwargs):
        kwargs.setdefault("session", session)
        real_style_init(self, *args, **kwargs)

    monkeypatch.setattr(run_experiment.FireworksCvrClient, "__init__", patched_cvr_init)
    monkeypatch.setattr(run_experiment.FireworksStyleClient, "__init__", patched_style_init)
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key")

    summary = run_experiment.run_one_experiment(config, tracking_uri=tracking_uri)

    assert summary["run_id"]
    assert summary["cvr"]["scene"] == "Tiny fixture"
    assert set(summary["captions"]) == {
        "Formal",
        "Sarcastic",
        "Humorous-Tech",
        "Humorous-Non-Tech",
    }
    assert summary["cvr_latency_seconds"] >= 0
    assert summary["style_latency_seconds"] >= 0

    run = mlflow.get_run(summary["run_id"])
    assert run.info.run_name == "exp_test"
    params = run.data.params
    assert params["num_frames"] == "4"
    assert params["cvr_model_name"] == "accounts/fireworks/models/qwen2p5-vl-32b-instruct"
    assert params["style_model_name"] == "accounts/fireworks/models/gpt-oss-120b"
    assert "cvr_latency_seconds" in run.data.metrics
    assert "style_latency_seconds" in run.data.metrics

    client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)
    artifacts = client.list_artifacts(summary["run_id"])
    artifact_names = {item.path for item in artifacts}
    assert "system_prompt.txt" in artifact_names
    assert "user_prompt_template.txt" in artifact_names
    assert "cvr_raw.txt" in artifact_names
    assert "cvr_output.json" in artifact_names
    assert "style_captions.json" in artifact_names

    assert session.post.call_count == 5  # 1 CVR call + 4 style calls


def test_run_one_experiment_aborts_when_cvr_parse_fails(
    tmp_path: Path, monkeypatch
) -> None:
    tracking_uri = f"file:{tmp_path / 'mlruns'}"
    setup_mlflow(tracking_uri)
    video_path = _write_tiny_video(tmp_path / "fixture.mp4")
    config = _make_config(str(video_path))

    session = Mock()

    def post_side_effect(url, headers=None, json=None, timeout=None, **kwargs):
        response = Mock()
        response.raise_for_status = Mock()
        request_model = json.get("model") if isinstance(json, dict) else None
        content = "not valid json {(" if request_model and "qwen" in request_model else "ignored"
        response.json.return_value = {"choices": [{"message": {"content": content}}]}
        return response

    session.post.side_effect = post_side_effect
    real_cvr_init = run_experiment.FireworksCvrClient.__init__

    def patched_cvr_init(self, *args, **kwargs):
        kwargs.setdefault("session", session)
        real_cvr_init(self, *args, **kwargs)

    monkeypatch.setattr(run_experiment.FireworksCvrClient, "__init__", patched_cvr_init)
    monkeypatch.setenv("FIREWORKS_API_KEY", "test-key")

    with pytest.raises(RuntimeError, match="CVR parsing failed"):
        run_experiment.run_one_experiment(config, tracking_uri=tracking_uri)

    assert session.post.call_count == 1  # Only the CVR call; style stage never ran


def test_run_one_experiment_raises_when_video_file_missing(tmp_path: Path, monkeypatch) -> None:
    tracking_uri = f"file:{tmp_path / 'mlruns'}"
    setup_mlflow(tracking_uri)
    config = _make_config(str(tmp_path / "does_not_exist.mp4"))

    with pytest.raises(FileNotFoundError, match="video_path does not exist"):
        run_experiment.run_one_experiment(config, tracking_uri=tracking_uri)