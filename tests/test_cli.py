import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from orchestrator.__main__ import cli, format_duration


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "report" in result.output
    assert "preflight" in result.output


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
        patch("orchestrator.__main__.AgentLoader"),
        patch("orchestrator.__main__.run_preflight") as mock_preflight,
    ):
        mock_preflight.return_value.ok = True
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
        patch("orchestrator.__main__.AgentLoader"),
        patch("orchestrator.__main__.run_preflight") as mock_preflight,
    ):
        mock_preflight.return_value.ok = True
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
        patch("orchestrator.__main__.AgentLoader"),
        patch("orchestrator.__main__.run_preflight") as mock_preflight,
    ):
        mock_preflight.return_value.ok = True
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
        patch("orchestrator.__main__.AgentLoader"),
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
        patch("orchestrator.__main__.AgentLoader"),
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
        patch("orchestrator.__main__.AgentLoader"),
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


def test_cli_preflight_command(runner, config_dir):
    with patch("orchestrator.__main__.run_preflight") as mock_preflight:
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.checks = []
        mock_preflight.return_value = mock_result
        result = runner.invoke(cli, ["preflight", "--config", str(config_dir)])
        assert result.exit_code == 0
        assert "Ready to run" in result.output


def test_cli_preflight_fails_when_checks_fail(runner, config_dir):
    with patch("orchestrator.__main__.run_preflight") as mock_preflight:
        from orchestrator.preflight import Check

        mock_result = MagicMock()
        mock_result.ok = False
        mock_result.checks = [Check(name="ANTHROPIC_API_KEY", passed=False, status="FAIL")]
        mock_preflight.return_value = mock_result
        result = runner.invoke(cli, ["preflight", "--config", str(config_dir)])
        assert result.exit_code != 0
        assert "Preflight failed" in result.output


def test_cli_init_command(runner, tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects").mkdir()

    with (
        patch("orchestrator.__main__.detect_project") as mock_detect,
        patch("orchestrator.__main__.run_init") as mock_init,
    ):
        detection = {
            "detected_languages": [],
            "detected_frameworks": [],
            "test_framework": "",
            "has_database": False,
            "has_makefile": False,
            "claude_md_quality": "missing",
            "project_context": "",
        }
        mock_detect.return_value = detection
        mock_init.return_value = {
            "project_name": "myrepo",
            "claude_md_action": "create",
            "claude_md_path": str(repo / "CLAUDE.md"),
            "claude_md_lines": 12,
            "project_yaml_path": str(config_dir / "projects" / "myrepo.yaml"),
        }
        result = runner.invoke(
            cli,
            ["init", str(repo), "--config", str(config_dir)],
        )
        assert result.exit_code == 0
        mock_init.assert_called_once_with(str(repo), str(config_dir), detection=detection)
        assert "myrepo" in result.output


def test_cli_init_shows_detection(runner, tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    with (
        patch("orchestrator.__main__.detect_project") as mock_detect,
        patch("orchestrator.__main__.format_detection") as mock_format,
        patch("orchestrator.__main__.run_init") as mock_init,
    ):
        mock_detect.return_value = {
            "detected_languages": ["python"],
            "detected_frameworks": [],
            "test_framework": "pytest",
            "has_database": False,
            "has_makefile": True,
            "claude_md_quality": "missing",
            "project_context": "",
        }
        mock_format.return_value = "Detected:\n  Languages ... Python"
        mock_init.return_value = {
            "project_name": "myrepo",
            "claude_md_action": "create",
            "claude_md_path": str(repo / "CLAUDE.md"),
            "claude_md_lines": 12,
            "project_yaml_path": str(config_dir / "projects" / "myrepo.yaml"),
        }
        result = runner.invoke(
            cli,
            ["init", str(repo), "--config", str(config_dir)],
        )
        assert result.exit_code == 0
        assert "Detected" in result.output


def test_cli_help_shows_init(runner):
    result = runner.invoke(cli, ["--help"])
    assert "init" in result.output


def test_cli_run_with_project(runner, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Test Spec")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    governance = config_dir / "governance.yaml"
    governance.write_text("rapid: {}\nraci: {}\n")
    agents = config_dir / "agents.yaml"
    agents.write_text(
        "workflow:\n"
        "  product_owner:\n"
        "    model: claude-opus-4-6\n"
        "    execution: api\n"
        "specialists:\n"
        "  python-expert:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 10\n"
        "    completion_promise: TASK COMPLETE\n"
        "escalation:\n"
        "  stuck_loop_model: claude-opus-4-6\n"
    )
    projects_dir = config_dir / "projects"
    projects_dir.mkdir()
    project_file = projects_dir / "webapp.yaml"
    project_file.write_text(
        "repo_path: /tmp/repo\n"
        "branch_prefix: scaffold\n"
        "max_concurrent_agents: 3\n"
        "db_path: ':memory:'\n"
    )

    with (
        patch("orchestrator.__main__.build_graph") as mock_build,
        patch("orchestrator.__main__.TelegramBot"),
        patch("orchestrator.__main__.SqliteSaver"),
        patch("orchestrator.__main__.AgentLoader"),
        patch("orchestrator.__main__.run_preflight") as mock_preflight,
    ):
        mock_preflight.return_value.ok = True
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
                "--project",
                "webapp",
            ],
        )
        assert result.exit_code == 0


def test_format_duration_seconds():
    assert format_duration(45000) == "45s"


def test_format_duration_minutes():
    assert format_duration(154000) == "2m 34s"


def test_format_duration_hours():
    assert format_duration(4320000) == "1h 12m"


def test_format_duration_zero():
    assert format_duration(0) == "0s"


def test_format_duration_none():
    assert format_duration(None) == "-"


def _make_report_db(tmp_path):
    db_path = tmp_path / "scaffold.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "db" / "schema.sql"
    conn.executescript(schema.read_text())
    conn.execute(
        "INSERT INTO tasks (id, level, status, title) "
        "VALUES ('epic-1', 'epic', 'done', 'Auth Epic')"
    )
    conn.execute(
        "INSERT INTO tasks (id, parent_id, level, status, title) "
        "VALUES ('task-1', 'epic-1', 'task', 'done', 'Implement login')"
    )
    conn.execute(
        "INSERT INTO agent_runs (id, task_id, agent_role, model, started_at, finished_at, "
        "iterations, token_in, token_out, outcome) VALUES "
        "('run-1', 'task-1', 'developer', 'claude-sonnet-4-6', "
        "'2026-05-13T10:00:00', '2026-05-13T10:04:12', 1, 5000, 2000, 'success')"
    )
    conn.commit()
    conn.close()
    return db_path


def test_report_agents_shows_wallclock(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    result = runner.invoke(cli, ["report", "--agents", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "4m" in result.output


def test_report_costs_shows_wallclock(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    result = runner.invoke(cli, ["report", "--costs", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "4m" in result.output


def test_report_tools_shows_usage(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e1', 'task-1', 'developer', 'tool.call', '{\"tool_name\": \"Edit\"}')"
    )
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e2', 'task-1', 'developer', 'tool.call', '{\"tool_name\": \"Edit\"}')"
    )
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e3', 'task-1', 'developer', 'tool.call', '{\"tool_name\": \"Read\"}')"
    )
    conn.commit()
    conn.close()
    result = runner.invoke(cli, ["report", "--tools", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "developer" in result.output
    assert "Edit" in result.output
    assert "Read" in result.output


def test_report_tools_empty(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    result = runner.invoke(cli, ["report", "--tools", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "No tool" in result.output


def test_report_costs_shows_cumulative_spend(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e1', 'task-1', 'developer', 'cli.done', "
        '\'{"iteration": 1, "success": true, "cost_usd": 0.12}\')'
    )
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e2', 'task-1', 'developer', 'cli.done', "
        '\'{"iteration": 2, "success": true, "cost_usd": 0.08}\')'
    )
    conn.commit()
    conn.close()
    result = runner.invoke(cli, ["report", "--costs", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "$0.20" in result.output


def test_cli_run_project_not_found(runner, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Test Spec")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    governance = config_dir / "governance.yaml"
    governance.write_text("rapid: {}\nraci: {}\n")
    agents = config_dir / "agents.yaml"
    agents.write_text("workflow: {}\nspecialists: {}\nescalation: {}\n")

    result = runner.invoke(
        cli,
        [
            "run",
            "--spec",
            str(spec),
            "--config",
            str(config_dir),
            "--project",
            "nonexistent",
        ],
    )
    assert result.exit_code != 0
