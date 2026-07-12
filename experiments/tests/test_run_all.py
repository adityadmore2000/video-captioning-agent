"""Tests for experiments/run_all.py: config discovery and per-config failure isolation.

No real network or model calls. The actual execution of each config is stubbed by
monkeypatching ``run_experiment.run_one_experiment`` so we can test the batch loop's
sequencing, success/failure accounting, and discovery behavior in isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import run_all
from run_all import discover_configs, run_all as run_all_function


def test_discover_configs_returns_sorted_yaml_files(tmp_path: Path) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "b.yaml").write_text("name: b", encoding="utf-8")
    (configs_dir / "a.yml").write_text("name: a", encoding="utf-8")
    (configs_dir / "ignore.txt").write_text("not a config", encoding="utf-8")
    (configs_dir / "sub_dir").mkdir()

    discovered = discover_configs(configs_dir)

    assert [path.name for path in discovered] == ["a.yml", "b.yaml"]


def test_discover_configs_returns_empty_for_missing_directory(tmp_path: Path) -> None:
    assert discover_configs(tmp_path / "does_not_exist") == []


def test_run_all_isolates_per_config_failures_and_continues(
    tmp_path: Path, monkeypatch
) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "ok.yaml").write_text("name: ok", encoding="utf-8")
    (configs_dir / "bad.yaml").write_text("name: bad", encoding="utf-8")
    (configs_dir / "ok2.yaml").write_text("name: ok2", encoding="utf-8")

    class FakeConfig:
        def __init__(self, name: str) -> None:
            self.name = name

    def fake_load_config(config_path: Path) -> FakeConfig:
        name = config_path.stem
        return FakeConfig(name)

    def fake_run_one(config: Any, **kwargs: Any) -> dict[str, Any]:
        if config.name == "bad":
            raise RuntimeError("simulated failure")
        return {"run_id": f"run-{config.name}"}

    monkeypatch.setattr(run_all, "load_config", fake_load_config)
    monkeypatch.setattr(run_all, "run_one_experiment", fake_run_one)
    monkeypatch.setattr(run_all, "setup_mlflow", lambda *a, **kw: "sqlite:///mlruns")

    summary = run_all_function(configs_dir, tracking_uri="sqlite:///mlruns")

    assert summary["total"] == 3
    assert summary["succeeded"] == 2
    assert summary["failed"] == 1
    statuses = {entry["config"]: entry["status"] for entry in summary["results"]}
    assert statuses[str(configs_dir / "ok.yaml")] == "ok"
    assert statuses[str(configs_dir / "bad.yaml")] == "error"
    assert statuses[str(configs_dir / "ok2.yaml")] == "ok"
    bad_entry = next(e for e in summary["results"] if e["status"] == "error")
    assert "simulated failure" in bad_entry["error"]


def test_run_all_handles_empty_configs_dir(tmp_path: Path, monkeypatch) -> None:
    configs_dir = tmp_path / "empty"
    configs_dir.mkdir()
    monkeypatch.setattr(run_all, "setup_mlflow", lambda *a, **kw: "sqlite:///mlruns")

    summary = run_all_function(configs_dir, tracking_uri="sqlite:///mlruns")

    assert summary["total"] == 0
    assert summary["succeeded"] == 0
    assert summary["failed"] == 0
    assert summary["results"] == []