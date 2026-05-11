import os
from unittest.mock import patch

import pytest

from orchestrator.preflight import run_preflight


@pytest.fixture
def valid_config(config_dir, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    from orchestrator.config import load_config

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
        cfg = load_config(str(config_dir))
    cfg.project.repo_path = str(repo)
    return cfg


def test_preflight_passes_with_all_configured(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "user@email.com"})()
        result = run_preflight(valid_config)
        assert result.ok


def test_preflight_fails_without_api_key(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {}, clear=True),
    ):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "user"})()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_preflight(valid_config)
        assert not result.ok
        assert any("ANTHROPIC_API_KEY" in c.name for c in result.checks if not c.passed)


def test_preflight_fails_without_claude_cli(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value=None),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "user"})()
        result = run_preflight(valid_config)
        assert not result.ok
        assert any("Claude CLI" in c.name for c in result.checks if not c.passed)


def test_preflight_fails_without_git_identity(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
        result = run_preflight(valid_config)
        assert not result.ok


def test_preflight_fails_without_repo(valid_config):
    valid_config.project.repo_path = "/nonexistent/path"
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "user"})()
        result = run_preflight(valid_config)
        assert not result.ok


def test_preflight_telegram_optional(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "user"})()
        result = run_preflight(valid_config)
        telegram_check = next(c for c in result.checks if "Telegram" in c.name)
        assert telegram_check.status == "SKIP (not configured)"
