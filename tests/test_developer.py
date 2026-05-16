from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.nodes.base import AgentResult, RalphResult
from orchestrator.nodes.developer import _extract_file_paths, make_developer_node
from orchestrator.state import initial_state


@pytest.fixture
def agents_config():
    config = MagicMock()
    config.specialists = {
        "python-expert": {
            "model": "claude-sonnet-4-6",
            "execution": "cli",
            "max_iterations": 10,
            "completion_promise": "TASK COMPLETE",
        },
        "react-expert": {
            "model": "claude-sonnet-4-6",
            "execution": "cli",
            "max_iterations": 8,
            "completion_promise": "TASK COMPLETE",
        },
        "postgres-expert": {
            "model": "claude-opus-4-6",
            "execution": "api",
            "max_iterations": 5,
            "completion_promise": "TASK COMPLETE",
        },
    }
    return config


@pytest.fixture
def agent_loader():
    loader = MagicMock()
    loader.detect_specialist.return_value = "python-expert"
    loader.load_specialist.return_value = "Assembled specialist prompt"
    return loader


@pytest.fixture
def mock_doer():
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        doer = MockDoer.return_value
        doer.ralph_loop.return_value = RalphResult(
            success=True, iterations=2, output="Code written.\nTASK COMPLETE"
        )
        doer.create_worktree.return_value = Path("/tmp/worktree")
        doer.cleanup_worktree = MagicMock()
        yield MockDoer


@pytest.fixture
def mock_advisor():
    with patch("orchestrator.nodes.developer.AdvisorAgent") as MockAdvisor:
        advisor = MockAdvisor.return_value
        advisor.call.return_value = AgentResult(
            text="Advisory recommendation: use connection pooling",
            token_in=100,
            token_out=50,
        )
        yield MockAdvisor


def test_developer_dispatches_correct_specialist(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer uses state['specialists'][0] when available."""
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-001", level="task")
    state["specialists"] = ["react-expert"]
    state["agent_output"] = "Create component in src/App.tsx"

    result = node_fn(state)

    assert result["status"] == "in_review"
    # DoerAgent should have been created with react-expert's config
    mock_doer.assert_called_once_with(
        role="react-expert",
        model="claude-sonnet-4-6",
        max_iterations=8,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
    )


def test_developer_matches_specialist_by_file_type(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer picks the roster specialist matching the task's file types, not just [0]."""
    agent_loader.detect_specialist.return_value = "react-expert"

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-003", level="task")
    state["specialists"] = ["python-expert", "react-expert"]
    state["agent_output"] = "Update src/components/Header.tsx"

    node_fn(state)

    mock_doer.assert_called_once_with(
        role="react-expert",
        model="claude-sonnet-4-6",
        max_iterations=8,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
    )


def test_developer_detects_specialist_from_agent_output(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer detects specialist from agent_output when specialists list is empty."""
    agent_loader.detect_specialist.return_value = "python-expert"

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-002", level="task")
    state["specialists"] = []
    state["agent_output"] = "Modify orchestrator/nodes/developer.py and tests/test_developer.py"

    result = node_fn(state)

    assert result["status"] == "in_review"
    # detect_specialist should have been called with extracted file paths
    agent_loader.detect_specialist.assert_called_once()
    called_paths = agent_loader.detect_specialist.call_args[0][0]
    assert "orchestrator/nodes/developer.py" in called_paths
    assert "tests/test_developer.py" in called_paths
    # DoerAgent should use python-expert config
    mock_doer.assert_called_once_with(
        role="python-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
    )


def test_developer_dispatches_advisory_specialists(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Advisory specialists dispatched when advisory list is non-empty and client provided."""
    client = MagicMock()
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
        client=client,
    )
    state = initial_state(task_id="task-003", level="task")
    state["specialists"] = ["python-expert"]
    state["advisory"] = ["postgres-expert"]
    state["agent_output"] = "Add database queries in db/queries.sql"

    result = node_fn(state)

    assert result["status"] == "in_review"
    # AdvisorAgent should have been created for postgres-expert (execution=api)
    mock_advisor.assert_called_once_with(
        role="postgres-expert",
        model="claude-opus-4-6",
        client=client,
    )
    mock_advisor.return_value.call.assert_called_once()


def test_developer_skips_advisory_without_client(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Advisory dispatch is skipped when client is None."""
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
        client=None,
    )
    state = initial_state(task_id="task-004", level="task")
    state["specialists"] = ["python-expert"]
    state["advisory"] = ["postgres-expert"]
    state["agent_output"] = "Add database queries"

    result = node_fn(state)

    assert result["status"] == "in_review"
    mock_advisor.assert_not_called()


def test_developer_failure_returns_stuck(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer failure returns status 'stuck'."""
    mock_doer.return_value.ralph_loop.return_value = RalphResult(
        success=False, iterations=10, output="Still broken."
    )
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-005", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Fix bugs in main.py"

    result = node_fn(state)

    assert result["status"] == "stuck"
    assert result["agent_output"] == "Still broken."


def test_developer_includes_review_feedback(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer includes review feedback in the prompt."""
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-006", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Update auth.py"
    state["feedback"] = "Missing error handling in auth middleware."

    node_fn(state)

    call_args = mock_doer.return_value.ralph_loop.call_args
    prompt = call_args.kwargs.get("prompt", "")
    failure_context = call_args.kwargs.get("failure_context", "")
    # Feedback should appear in either prompt or failure_context
    combined = prompt + failure_context
    assert "Missing error handling" in combined


def test_developer_cleans_up_worktree_on_exception(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer cleans up worktree even on exception (try/finally)."""
    mock_doer.return_value.ralph_loop.side_effect = RuntimeError("Unexpected error")
    mock_doer.return_value.create_worktree.return_value = Path("/tmp/worktree")

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-007", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Implement feature"

    with pytest.raises(RuntimeError, match="Unexpected error"):
        node_fn(state)

    mock_doer.return_value.cleanup_worktree.assert_called_once_with(
        "/tmp/repo", Path("/tmp/worktree")
    )


def test_developer_fallback_to_python_expert(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer falls back to python-expert when no specialist detected."""
    agent_loader.detect_specialist.return_value = ""

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-008", level="task")
    state["specialists"] = []
    state["agent_output"] = "Do something with no file extensions mentioned"

    result = node_fn(state)

    assert result["status"] == "in_review"
    mock_doer.assert_called_once_with(
        role="python-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
    )


def test_developer_passes_max_budget_to_doer(mock_doer, mock_advisor, agent_loader, agents_config):
    agents_config.specialists["python-expert"]["max_budget_usd"] = 2.00
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-010", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Update main.py"

    node_fn(state)

    mock_doer.assert_called_once_with(
        role="python-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=2.00,
    )


def test_developer_passes_scaffold_budget_to_ralph_loop(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
        scaffold_budget_usd=10.00,
    )
    state = initial_state(task_id="task-011", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Update main.py"

    node_fn(state)

    ralph_call = mock_doer.return_value.ralph_loop.call_args
    assert ralph_call.kwargs.get("scaffold_budget_usd") == 10.00


def test_developer_no_scaffold_budget_by_default(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-012", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Update main.py"

    node_fn(state)

    ralph_call = mock_doer.return_value.ralph_loop.call_args
    assert ralph_call.kwargs.get("scaffold_budget_usd") is None


def test_extract_file_paths():
    """_extract_file_paths extracts file paths from text."""
    text = """
    Modify orchestrator/nodes/developer.py and tests/test_developer.py.
    Also update config/agents.yaml and src/components/App.tsx.
    """
    paths = _extract_file_paths(text)
    assert "orchestrator/nodes/developer.py" in paths
    assert "tests/test_developer.py" in paths
    assert "config/agents.yaml" in paths
    assert "src/components/App.tsx" in paths
