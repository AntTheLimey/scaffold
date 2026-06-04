import contextlib
import json
from unittest.mock import MagicMock, patch

from orchestrator.nodes.reviewer import _reviewer_worktree_path, make_reviewer_node
from orchestrator.state import initial_state


def _make_mock_loader(prompt: str = "loaded reviewer prompt") -> MagicMock:
    loader = MagicMock()
    loader.load_workflow_agent.return_value = prompt
    return loader


def _worktree_side_effect(claude_stdout: str, returncode: int = 0):
    """Return a side_effect function that routes subprocess.run calls correctly.

    Call order:
      1. git worktree add  → success (returncode 0)
      2. claude -p -       → the review output (prompt via stdin)
      3. git worktree remove → success (returncode 0)
    """
    git_ok = MagicMock(stdout="", stderr="", returncode=0)
    claude_result = MagicMock(stdout=claude_stdout, stderr="", returncode=returncode)

    def _side_effect(cmd, **kwargs):
        if cmd[0] == "git":
            return git_ok
        return claude_result

    return _side_effect


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_approves(mock_run):
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "in_review"
    result = node_fn(state)
    assert result["verdict"] == "approve"
    assert result["status"] == "testing"


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_requests_revision(mock_run):
    mock_run.side_effect = _worktree_side_effect(
        json.dumps(
            {"verdict": "revise", "feedback": "Missing input validation on invite code endpoint."}
        )
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "in_review"
    result = node_fn(state)
    assert result["verdict"] == "revise"
    assert "input validation" in result["feedback"]
    assert result["review_cycles"] == 1


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_uses_configured_branch_prefix(mock_run):
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="custom-prefix",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    claude_call = mock_run.call_args_list[1]
    prompt_text = claude_call.kwargs["input"]
    assert "custom-prefix/task-001" in prompt_text


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_uses_agent_loader(mock_run):
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    loader = _make_mock_loader("my custom reviewer prompt")
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=loader,
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    loader.load_workflow_agent.assert_called_once_with("reviewer")
    claude_call = mock_run.call_args_list[1]
    prompt_text = claude_call.kwargs["input"]
    assert "my custom reviewer prompt" in prompt_text


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_appends_project_context(mock_run):
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    state["project_context"] = "Use strict type checking throughout."
    node_fn(state)
    claude_call = mock_run.call_args_list[1]
    prompt_text = claude_call.kwargs["input"]
    assert "Use strict type checking throughout." in prompt_text


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_falls_back_to_inline_prompt(mock_run):
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    loader = _make_mock_loader("")  # empty string — loader has no agent file
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=loader,
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    claude_call = mock_run.call_args_list[1]
    prompt_text = claude_call.kwargs["input"]
    assert "code review engine" in prompt_text


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_passes_prompt_via_stdin(mock_run):
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    claude_call = mock_run.call_args_list[1]
    assert claude_call.args[0] == ["claude", "-p", "-", "--model", "claude-sonnet-4-20250514"]
    assert "input" in claude_call.kwargs
    assert "loaded reviewer prompt" in claude_call.kwargs["input"]


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_uses_configured_timeout(mock_run):
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
        timeout=900,
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    claude_call = mock_run.call_args_list[1]
    assert claude_call.kwargs["timeout"] == 900


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_runs_in_worktree(mock_run):
    """claude -p must run with cwd set to the worktree path, not repo_path."""
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)

    expected_worktree = str(_reviewer_worktree_path("/tmp/repo", "scaffold/task-001"))
    claude_call = mock_run.call_args_list[1]
    assert claude_call.kwargs["cwd"] == expected_worktree
    # Must NOT run in the main repo path
    assert claude_call.kwargs["cwd"] != "/tmp/repo"


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_cleans_up_worktree(mock_run):
    """git worktree remove must be called even when claude raises an exception."""
    git_ok = MagicMock(stdout="", stderr="", returncode=0)

    call_count = {"n": 0}

    def _failing_side_effect(cmd, **kwargs):
        call_count["n"] += 1
        if cmd[0] == "git":
            return git_ok
        # claude call raises
        raise RuntimeError("claude crashed")

    mock_run.side_effect = _failing_side_effect

    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")

    with contextlib.suppress(RuntimeError):
        node_fn(state)

    # Calls: worktree add, claude (raises), worktree remove
    assert call_count["n"] == 3
    remove_call = mock_run.call_args_list[2]
    assert remove_call.args[0][0] == "git"
    assert "remove" in remove_call.args[0]


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_writes_artifact(mock_run, tmp_path):
    mock_run.side_effect = _worktree_side_effect(json.dumps({"verdict": "approve", "feedback": ""}))
    node_fn = make_reviewer_node(
        repo_path=str(tmp_path),
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    artifact = tmp_path / ".scaffold" / "artifacts" / "task-001" / "reviewer.md"
    assert artifact.exists()
    assert "approve" in artifact.read_text()
