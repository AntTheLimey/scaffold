from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from orchestrator.__main__ import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "report" in result.output


def test_cli_report_no_db(runner, tmp_path):
    result = runner.invoke(cli, ["report", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code != 0 or "No database" in result.output


def test_cli_run_requires_spec(runner):
    result = runner.invoke(cli, ["run"])
    assert result.exit_code != 0


def test_cli_run_builds_graph(runner, tmp_path, config_dir):
    spec = tmp_path / "spec.md"
    spec.write_text("# Test Spec\nBuild a thing.")
    with (
        patch("orchestrator.__main__.build_graph") as mock_build,
        patch("orchestrator.__main__.TelegramBot"),
    ):
        mock_graph = MagicMock()
        mock_build.return_value = mock_graph
        result = runner.invoke(
            cli,
            [
                "run",
                "--spec",
                str(spec),
                "--config",
                str(config_dir),
            ],
        )
        assert result.exit_code == 0
        mock_build.assert_called_once()


def test_cli_decide_command(runner):
    result = runner.invoke(cli, ["decide", "--help"])
    assert result.exit_code == 0
    assert "task" in result.output
    assert "choice" in result.output
