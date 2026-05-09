from unittest.mock import patch, MagicMock
import subprocess
import pytest
from orchestrator.nodes.base import DoerAgent


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
        env={"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com",
             "HOME": str(tmp_path)},
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
    with_promise = MagicMock(
        stdout="Fixed it.\nTASK COMPLETE", stderr="", returncode=0
    )
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
    with_promise = MagicMock(
        stdout="Fixed.\nTASK COMPLETE", stderr="", returncode=0
    )
    mock_run.side_effect = [no_promise, with_promise]
    doer.ralph_loop(worktree_path="/tmp/wt", prompt="Implement auth")
    second_call = mock_run.call_args_list[1]
    prompt_arg = second_call.args[0][-1]
    assert "PREVIOUS ATTEMPT" in prompt_arg
    assert "Error: module not found" in prompt_arg
