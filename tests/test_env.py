"""Tests for best-effort .env loading (see ``_env.load_env_file``)."""

from __future__ import annotations

import builtins
import importlib
from pathlib import Path

import pytest

from video_captioning_agent._env import load_env_file


def test_loads_vars_from_default_dotenv_in_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VCA_TEST_FOO", raising=False)
    (tmp_path / ".env").write_text('VCA_TEST_FOO=bar\n', encoding="utf-8")

    load_env_file()

    assert __import__("os").environ["VCA_TEST_FOO"] == "bar"


def test_existing_env_wins_over_dotenv_when_override_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VCA_TEST_BAR", "from-shell")
    (tmp_path / ".env").write_text('VCA_TEST_BAR=from-file\n', encoding="utf-8")

    load_env_file()

    assert __import__("os").environ["VCA_TEST_BAR"] == "from-shell"


def test_dotenv_path_env_points_at_explicit_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VCA_TEST_BAZ", raising=False)
    custom = tmp_path / "secrets.env"
    custom.write_text('VCA_TEST_BAZ=qux\n', encoding="utf-8")
    monkeypatch.setenv("DOTENV_PATH", str(custom))

    load_env_file()

    assert __import__("os").environ["VCA_TEST_BAZ"] == "qux"


def test_missing_dotenv_file_is_silent_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOTENV_PATH", raising=False)
    (tmp_path / ".env").unlink(missing_ok=True)

    # Must not raise.
    load_env_file()


def test_missing_dotenv_import_is_silent_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def _block_dotenv(name: str, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("dotenv not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_dotenv)
    # Re-import the module so the ImportError path is exercised cleanly.
    import video_captioning_agent._env as env_module

    importlib.reload(env_module)

    # Must not raise even though dotenv is unavailable.
    env_module.load_env_file()
