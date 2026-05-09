import json
from unittest.mock import MagicMock, patch

from orchestrator.nodes.reviewer import make_reviewer_node
from orchestrator.state import initial_state


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_approves(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps({"verdict": "approve", "feedback": ""}),
        stderr="",
        returncode=0,
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "in_review"
    result = node_fn(state)
    assert result["verdict"] == "approve"
    assert result["status"] == "testing"


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_requests_revision(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps(
            {"verdict": "revise", "feedback": "Missing input validation on invite code endpoint."}
        ),
        stderr="",
        returncode=0,
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "in_review"
    result = node_fn(state)
    assert result["verdict"] == "revise"
    assert "input validation" in result["feedback"]
    assert result["review_cycles"] == 1


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_uses_configured_branch_prefix(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps({"verdict": "approve", "feedback": ""}),
        stderr="",
        returncode=0,
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="custom-prefix",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    call_args = mock_run.call_args
    prompt_text = " ".join(call_args.args[0])
    assert "custom-prefix/task-001" in prompt_text
