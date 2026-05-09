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
        patch("orchestrator.__main__.SqliteSaver"),
    ):
        mock_graph = MagicMock()
        mock_build.return_value = mock_graph
        result = runner.invoke(
            cli,
            ["run", "--spec", str(spec), "--config", str(config_dir)],
        )
        assert result.exit_code == 0
        mock_build.assert_called_once()


def test_cli_run_passes_checkpointer_to_build_graph(runner, tmp_path, config_dir):
    spec = tmp_path / "spec.md"
    spec.write_text("# Test Spec")
    with (
        patch("orchestrator.__main__.build_graph") as mock_build,
        patch("orchestrator.__main__.TelegramBot"),
        patch("orchestrator.__main__.SqliteSaver") as MockSaver,
    ):
        mock_checkpointer = MagicMock()
        MockSaver.from_conn_string.return_value.__enter__ = MagicMock(
            return_value=mock_checkpointer
        )
        MockSaver.from_conn_string.return_value.__exit__ = MagicMock(return_value=False)
        mock_graph = MagicMock()
        mock_build.return_value = mock_graph

        result = runner.invoke(
            cli,
            ["run", "--spec", str(spec), "--config", str(config_dir)],
        )
        assert result.exit_code == 0
        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["checkpointer"] is mock_checkpointer


def test_cli_run_closes_bot(runner, tmp_path, config_dir):
    spec = tmp_path / "spec.md"
    spec.write_text("# Test Spec")
    with (
        patch("orchestrator.__main__.build_graph") as mock_build,
        patch("orchestrator.__main__.TelegramBot") as MockBot,
        patch("orchestrator.__main__.SqliteSaver"),
    ):
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot
        mock_graph = MagicMock()
        mock_build.return_value = mock_graph

        runner.invoke(cli, ["run", "--spec", str(spec), "--config", str(config_dir)])
        mock_bot.close.assert_called_once()


def test_cli_decide_command(runner):
    result = runner.invoke(cli, ["decide", "--help"])
    assert result.exit_code == 0
    assert "task" in result.output
    assert "choice" in result.output


def test_cli_decide_invokes_with_command(runner, tmp_path, config_dir):
    db = tmp_path / "scaffold.db"
    db.touch()
    with (
        patch("orchestrator.__main__.build_graph") as mock_build,
        patch("orchestrator.__main__.TelegramBot"),
        patch("orchestrator.__main__.SqliteSaver"),
    ):
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"status": "done"}
        mock_build.return_value = mock_graph

        result = runner.invoke(
            cli,
            [
                "decide",
                "--task",
                "task-001",
                "--choice",
                "Approve",
                "--db",
                str(db),
                "--config",
                str(config_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Decision applied: Approve" in result.output
        mock_graph.invoke.assert_called_once()
        call_args = mock_graph.invoke.call_args
        cmd = call_args.args[0]
        assert cmd.resume == {"choice": "Approve"}


def test_cli_decide_closes_bot(runner, tmp_path, config_dir):
    db = tmp_path / "scaffold.db"
    db.touch()
    with (
        patch("orchestrator.__main__.build_graph") as mock_build,
        patch("orchestrator.__main__.TelegramBot") as MockBot,
        patch("orchestrator.__main__.SqliteSaver"),
    ):
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"status": "done"}
        mock_build.return_value = mock_graph

        runner.invoke(
            cli,
            [
                "decide",
                "--task",
                "task-001",
                "--choice",
                "Revise",
                "--db",
                str(db),
                "--config",
                str(config_dir),
            ],
        )
        mock_bot.close.assert_called_once()


def test_cli_resume_invokes_graph(runner, tmp_path, config_dir):
    db = tmp_path / "scaffold.db"
    db.touch()
    with (
        patch("orchestrator.__main__.build_graph") as mock_build,
        patch("orchestrator.__main__.TelegramBot"),
        patch("orchestrator.__main__.SqliteSaver"),
    ):
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"status": "done"}
        mock_build.return_value = mock_graph

        result = runner.invoke(
            cli,
            [
                "resume",
                "--task",
                "task-001",
                "--db",
                str(db),
                "--config",
                str(config_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Resuming task task-001" in result.output
        mock_graph.invoke.assert_called_once()
        call_args = mock_graph.invoke.call_args
        assert call_args.args[0] is None
        assert call_args.kwargs["config"]["configurable"]["thread_id"] == "task-001"


def test_cli_resume_no_db(runner, tmp_path, config_dir):
    result = runner.invoke(
        cli,
        [
            "resume",
            "--task",
            "task-001",
            "--db",
            str(tmp_path / "missing.db"),
            "--config",
            str(config_dir),
        ],
    )
    assert result.exit_code != 0 or "No database" in result.output
