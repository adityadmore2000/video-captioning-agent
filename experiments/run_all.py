"""Batch experiment runner.

Loops sequentially over every ``*.yaml`` / ``*.yml`` config file in ``experiments/configs/``
and runs each as its own MLflow run via ``run_experiment.run_one_experiment``. Each config
is independent; one failing config logs the error and continues to the next.

Usage:
    python experiments/run_all.py
    python experiments/run_all.py --configs-dir experiments/configs --tracking-uri sqlite:///experiments/mlflow.db

This is dev-only tooling. It does not touch the /input->/output contract, the production
pipeline, or the Docker image (Task 14). See EXPERIMENT_TRACKING.md.
"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from pathlib import Path


def _bootstrap_sys_path() -> None:
    """Insert the repo's ``src/`` and ``experiments/`` dirs onto ``sys.path``.

    ``run_experiment`` (imported below) also bootstraps, but this script imports the
    harness directly so it bootstraps too. Resolved relative to this script's location so
    it runs from any CWD without a manual ``PYTHONPATH``.
    """

    experiments_dir = Path(__file__).resolve().parent
    repo_root = experiments_dir.parent
    src_dir = repo_root / "src"
    for path in (str(src_dir), str(experiments_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)


_bootstrap_sys_path()

from run_experiment import run_one_experiment

from harness import DEFAULT_TRACKING_URI, load_config, setup_mlflow


LOGGER = logging.getLogger("experiments.run_all")


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run every experiment config under experiments/configs as its own MLflow run."
    )
    parser.add_argument(
        "--configs-dir",
        type=Path,
        default=Path("experiments/configs"),
        help="Directory containing experiment YAML configs (default: experiments/configs).",
    )
    parser.add_argument(
        "--tracking-uri",
        type=str,
        default=DEFAULT_TRACKING_URI,
        help="MLflow tracking URI (sqlite: scheme; default: sqlite:///experiments/mlflow.db).",
    )
    return parser


def discover_configs(configs_dir: Path) -> list[Path]:
    """Return sorted ``*.yaml`` / ``*.yml`` config paths under ``configs_dir``."""

    if not configs_dir.is_dir():
        return []
    return sorted(
        [
            path
            for path in configs_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
        ]
    )


def run_all(configs_dir: Path, tracking_uri: str = DEFAULT_TRACKING_URI) -> dict[str, object]:
    """Run every discovered config sequentially; collect per-config pass/fail results.

    MLflow tracking is set up exactly once; each config runs inside its own
    ``mlflow.start_run`` block (handled by ``run_one_experiment``). A failure in one
    config does not stop the loop — it's recorded in the returned summary.
    """

    setup_mlflow(tracking_uri)
    configs = discover_configs(configs_dir)
    results: list[dict[str, object]] = []
    succeeded = 0
    failed = 0

    for config_path in configs:
        entry: dict[str, object] = {"config": str(config_path)}
        try:
            config = load_config(config_path)
            summary = run_one_experiment(config, tracking_uri=tracking_uri)
            entry["run_id"] = summary["run_id"]
            entry["status"] = "ok"
            succeeded += 1
        except Exception as error:
            entry["status"] = "error"
            entry["error"] = str(error)
            entry["traceback"] = traceback.format_exc()
            failed += 1
            LOGGER.error("Config %s failed: %s", config_path, error)
        results.append(entry)

    return {
        "configs_dir": str(configs_dir),
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = _build_arg_parser().parse_args(argv)

    summary = run_all(args.configs_dir, args.tracking_uri)
    import json

    print(json.dumps(summary, indent=2, default=str))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())