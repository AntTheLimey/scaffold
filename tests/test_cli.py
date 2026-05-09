from click.testing import CliRunner
import pytest
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
