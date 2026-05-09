from unittest.mock import patch, MagicMock
import pytest
from orchestrator.nodes.developer import make_developer_node
from orchestrator.nodes.base import RalphResult
from orchestrator.state import initial_state


@pytest.fixture
def mock_doer():
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        doer = MockDoer.return_value
        doer.ralph_loop.return_value = RalphResult(
            success=True, iterations=2, output="Code written.\nTASK COMPLETE"
        )
        doer.create_worktree.return_value = MagicMock()
        doer.cleanup_worktree = MagicMock()
        yield doer


def test_developer_runs_ralph_loop(mock_doer):
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    result = node_fn(state)
    assert result["status"] == "in_review"
    assert result["verdict"] == ""
    mock_doer.ralph_loop.assert_called_once()


def test_developer_marks_stuck_on_failure(mock_doer):
    mock_doer.ralph_loop.return_value = RalphResult(
        success=False, iterations=10, output="Still broken."
    )
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-002", level="task")
    result = node_fn(state)
    assert result["status"] == "stuck"


def test_developer_injects_failure_context_on_retry(mock_doer):
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-003", level="task")
    state["feedback"] = "Missing error handling in auth middleware."
    node_fn(state)
    call_args = mock_doer.ralph_loop.call_args
    assert "Missing error handling" in call_args.kwargs.get("failure_context", call_args.kwargs.get("prompt", ""))
