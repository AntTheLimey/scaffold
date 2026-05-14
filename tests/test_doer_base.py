import subprocess
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.nodes.base import DoerAgent, parse_cli_output


@pytest.fixture
def doer():
    return DoerAgent(
        role="developer",
        model="claude-sonnet-4-20250514",
        max_iterations=3,
        completion_promise="TASK COMPLETE",
    )


def test_doer_creates_worktree(doer, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo_path,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": str(tmp_path),
        },
    )
    worktree_path = doer.create_worktree(repo_path, "scaffold/core/auth")
    assert worktree_path.exists()
    doer.cleanup_worktree(repo_path, worktree_path)


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_ralph_loop_succeeds_first_try(mock_run, doer):
    mock_run.return_value = MagicMock(
        stdout="Implementation done.\nTASK COMPLETE",
        stderr="",
        returncode=0,
    )
    result = doer.ralph_loop(
        worktree_path="/tmp/worktree",
        prompt="Implement auth middleware",
    )
    assert result.success is True
    assert result.iterations == 1
    assert mock_run.call_count == 1


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_ralph_loop_retries_on_no_promise(mock_run, doer):
    no_promise = MagicMock(stdout="Still working...", stderr="", returncode=0)
    with_promise = MagicMock(stdout="Fixed it.\nTASK COMPLETE", stderr="", returncode=0)
    mock_run.side_effect = [no_promise, with_promise]
    result = doer.ralph_loop(
        worktree_path="/tmp/worktree",
        prompt="Implement auth",
    )
    assert result.success is True
    assert result.iterations == 2


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_ralph_loop_hits_max_iterations(mock_run, doer):
    no_promise = MagicMock(stdout="Still working...", stderr="", returncode=0)
    mock_run.return_value = no_promise
    result = doer.ralph_loop(
        worktree_path="/tmp/worktree",
        prompt="Implement auth",
    )
    assert result.success is False
    assert result.iterations == 3


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_injects_failure_context_on_retry(mock_run, doer):
    no_promise = MagicMock(stdout="Error: module not found", stderr="", returncode=1)
    with_promise = MagicMock(stdout="Fixed.\nTASK COMPLETE", stderr="", returncode=0)
    mock_run.side_effect = [no_promise, with_promise]
    doer.ralph_loop(worktree_path="/tmp/wt", prompt="Implement auth")
    second_call = mock_run.call_args_list[1]
    prompt_arg = second_call.args[0][-1]
    assert "PREVIOUS ATTEMPT" in prompt_arg
    assert "Error: module not found" in prompt_arg


_READ_CALL = (
    '{"type":"assistant","message":{"content":'
    '[{"type":"tool_use","name":"Read","id":"t1","input":{"file_path":"/tmp/f.py"}}]}}'
)
_EDIT_CALL = (
    '{"type":"assistant","message":{"content":'
    '[{"type":"tool_use","name":"Edit","id":"t2",'
    '"input":{"file_path":"/tmp/f.py","old_string":"a","new_string":"b"}}]}}'
)
_TEXT_MSG = (
    '{"type":"assistant","message":{"content":[{"type":"text","text":"Done.\\nTASK COMPLETE"}]}}'
)
SAMPLE_JSONL = "\n".join(
    [
        '{"type":"system","subtype":"init","session_id":"abc"}',
        _READ_CALL,
        '{"type":"user","subtype":"tool_result"}',
        _EDIT_CALL,
        '{"type":"user","subtype":"tool_result"}',
        _TEXT_MSG,
        '{"type":"result","result":"Done.\\nTASK COMPLETE","num_turns":3,"total_cost_usd":0.12}',
    ]
)


def test_parse_cli_output_extracts_tool_names():
    output = parse_cli_output(SAMPLE_JSONL)
    assert output.tool_names == ["Read", "Edit"]


def test_parse_cli_output_extracts_result_text():
    output = parse_cli_output(SAMPLE_JSONL)
    assert "TASK COMPLETE" in output.result_text


def test_parse_cli_output_extracts_cost():
    output = parse_cli_output(SAMPLE_JSONL)
    assert output.cost_usd == pytest.approx(0.12)


def test_parse_cli_output_fallback_on_invalid_json():
    raw = "This is plain text output.\nTASK COMPLETE"
    output = parse_cli_output(raw)
    assert output.result_text == raw
    assert output.tool_names == []
    assert output.cost_usd is None


def test_parse_cli_output_fallback_on_missing_result_line():
    partial = (
        '{"type":"system","subtype":"init"}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]}}'
    )
    output = parse_cli_output(partial)
    assert output.result_text == partial
    assert output.tool_names == []
    assert output.cost_usd is None
