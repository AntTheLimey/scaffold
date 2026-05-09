from unittest.mock import patch, MagicMock
import pytest
from orchestrator.nodes.qa import make_qa_node
from orchestrator.nodes.base import RalphResult
from orchestrator.state import initial_state


@patch("orchestrator.nodes.qa.DoerAgent")
def test_qa_passes(MockDoer):
    doer = MockDoer.return_value
    doer.ralph_loop.return_value = RalphResult(
        success=True, iterations=3, output="All tests pass.\nTESTS PASSING"
    )
    doer.create_worktree.return_value = "/tmp/qa-worktree"
    doer.cleanup_worktree = MagicMock()
    node_fn = make_qa_node(repo_path="/tmp/repo", branch_prefix="scaffold", model="claude-sonnet-4-20250514")
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "testing"
    result = node_fn(state)
    assert result["verdict"] == "pass"
    assert result["status"] == "done"
    doer.cleanup_worktree.assert_called_once()


@patch("orchestrator.nodes.qa.DoerAgent")
def test_qa_fails(MockDoer):
    doer = MockDoer.return_value
    doer.ralph_loop.return_value = RalphResult(
        success=False, iterations=8, output="test_auth fails: AssertionError"
    )
    doer.create_worktree.return_value = "/tmp/qa-worktree"
    doer.cleanup_worktree = MagicMock()
    node_fn = make_qa_node(repo_path="/tmp/repo", branch_prefix="scaffold", model="claude-sonnet-4-20250514")
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "testing"
    result = node_fn(state)
    assert result["verdict"] == "fail"
    assert result["bug_cycles"] == 1
    assert "AssertionError" in result["feedback"]
    doer.cleanup_worktree.assert_called_once()
