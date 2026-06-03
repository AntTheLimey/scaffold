from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.budget import BudgetExceededError
from orchestrator.nodes.base import AgentResult, DoerAgent, RalphResult
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
        "go-expert": {
            "model": "claude-sonnet-4-6",
            "execution": "cli",
            "max_iterations": 10,
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
    with (
        patch("orchestrator.nodes.developer.DoerAgent") as MockDoer,
        patch("orchestrator.nodes.developer.subprocess"),
    ):
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
        timeout=600,
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
        timeout=600,
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
        timeout=600,
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
        timeout=600,
    )


def test_developer_fallback_uses_detected_languages(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer uses first matching detected_language when specialists list is empty."""
    agent_loader.detect_specialist.return_value = ""
    agents_config.specialists["go-expert"] = {
        "model": "claude-sonnet-4-6",
        "execution": "cli",
        "max_iterations": 10,
        "completion_promise": "TASK COMPLETE",
    }

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-lang-fallback", level="task")
    state["specialists"] = []
    state["detected_languages"] = ["go", "typescript"]
    state["agent_output"] = "Do something with no file extensions mentioned"

    result = node_fn(state)

    assert result["status"] == "in_review"
    mock_doer.assert_called_once_with(
        role="go-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
        timeout=600,
    )


def test_developer_fallback_python_when_no_languages(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer falls back to python-expert when detected_languages is empty."""
    agent_loader.detect_specialist.return_value = ""

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-no-lang-fallback", level="task")
    state["specialists"] = []
    state["detected_languages"] = []
    state["agent_output"] = "Do something with no file extensions mentioned"

    result = node_fn(state)

    assert result["status"] == "in_review"
    mock_doer.assert_called_once_with(
        role="python-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
        timeout=600,
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
        timeout=600,
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


def test_developer_rejects_documentation_writer_when_roster_empty(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer should not auto-select documentation-writer when specialist roster is empty."""
    agents_config.specialists["documentation-writer"] = {
        "model": "claude-sonnet-4-6",
        "execution": "cli",
        "max_iterations": 5,
        "completion_promise": "TASK COMPLETE",
    }
    agent_loader.detect_specialist.return_value = "documentation-writer"

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-013", level="task")
    state["specialists"] = []
    state["agent_output"] = "Create README.md and docs/architecture.md"

    node_fn(state)

    mock_doer.assert_called_once_with(
        role="python-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
        timeout=600,
    )


def test_developer_passes_timeout_from_config(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer passes timeout from specialist config to DoerAgent."""
    agents_config.specialists["python-expert"]["timeout"] = 900

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-014", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Update main.py"

    node_fn(state)

    mock_doer.assert_called_once_with(
        role="python-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
        timeout=900,
    )


def test_developer_checks_budget_after_advisory_api_call(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    mock_bus = MagicMock()
    mock_bus.check_budget.side_effect = BudgetExceededError(spent=6.0, limit=5.0)
    mock_client = MagicMock()
    agents_config.specialists["postgres-expert"] = {
        "model": "claude-opus-4-6",
        "execution": "api",
    }
    mock_advisor.return_value.call.return_value = AgentResult(
        text="Use indexes", token_in=200, token_out=100
    )
    with patch("orchestrator.nodes.developer.get_bus", return_value=mock_bus):
        node_fn = make_developer_node(
            repo_path="/tmp/repo",
            branch_prefix="scaffold",
            agent_loader=agent_loader,
            agents_config=agents_config,
            client=mock_client,
            scaffold_budget_usd=5.0,
        )
        state = initial_state(task_id="task-015", level="task")
        state["specialists"] = ["python-expert"]
        state["advisory"] = ["postgres-expert"]
        state["agent_output"] = "Update db.py"
        with pytest.raises(BudgetExceededError):
            node_fn(state)
    mock_bus.check_budget.assert_called_with(5.0)


def test_developer_commits_after_success(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer runs git add -A and git commit in the worktree after a successful ralph_loop."""
    with patch("orchestrator.nodes.developer.subprocess") as mock_subprocess:
        node_fn = make_developer_node(
            repo_path="/tmp/repo",
            branch_prefix="scaffold",
            agent_loader=agent_loader,
            agents_config=agents_config,
        )
        state = initial_state(task_id="task-commit-success", level="task")
        state["specialists"] = ["python-expert"]
        state["agent_output"] = "Update main.py"

        result = node_fn(state)

        assert result["status"] == "in_review"
        worktree = Path("/tmp/worktree")
        calls = mock_subprocess.run.call_args_list
        assert len(calls) == 2
        git_add_call = calls[0]
        assert git_add_call.args[0] == ["git", "add", "-A"]
        assert git_add_call.kwargs["cwd"] == str(worktree)
        assert git_add_call.kwargs["check"] is True
        git_commit_call = calls[1]
        assert git_commit_call.args[0] == [
            "git",
            "commit",
            "-m",
            "feat: task-commit-success implementation",
        ]
        assert git_commit_call.kwargs["cwd"] == str(worktree)


def test_developer_does_not_commit_on_failure(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer does not run git add/commit when ralph_loop returns success=False."""
    mock_doer.return_value.ralph_loop.return_value = RalphResult(
        success=False, iterations=10, output="Still broken."
    )
    with patch("orchestrator.nodes.developer.subprocess") as mock_subprocess:
        node_fn = make_developer_node(
            repo_path="/tmp/repo",
            branch_prefix="scaffold",
            agent_loader=agent_loader,
            agents_config=agents_config,
        )
        state = initial_state(task_id="task-commit-failure", level="task")
        state["specialists"] = ["python-expert"]
        state["agent_output"] = "Update main.py"

        result = node_fn(state)

        assert result["status"] == "stuck"
        mock_subprocess.run.assert_not_called()


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


def test_developer_uses_architect_specialist(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer uses architect_specialist from state, overriding file-based detection."""
    agent_loader.detect_specialist.return_value = "python-expert"

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-arch-spec", level="task")
    state["specialists"] = []
    state["agent_output"] = "Design SQL schema and migrations"
    state["architect_specialist"] = "go-expert"

    node_fn(state)

    mock_doer.assert_called_once_with(
        role="go-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
        timeout=600,
    )


def test_developer_uses_architect_file_paths(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer uses architect_file_paths when architect_specialist is unset."""

    def detect_side_effect(paths):
        if any(p.endswith(".go") for p in paths):
            return "go-expert"
        return "python-expert"

    agent_loader.detect_specialist.side_effect = detect_side_effect

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-arch-paths", level="task")
    state["specialists"] = []
    state["agent_output"] = "Implement auth service"
    state["architect_file_paths"] = [
        "internal/auth/handler.go",
        "internal/auth/handler_test.go",
    ]

    node_fn(state)

    mock_doer.assert_called_once_with(
        role="go-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
        timeout=600,
    )


def test_developer_architect_specialist_overrides_file_detection(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """architect_specialist wins even when file paths suggest a different specialist."""
    agent_loader.detect_specialist.return_value = "go-expert"

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-arch-override", level="task")
    state["specialists"] = []
    state["agent_output"] = "Update internal/auth/handler.go and internal/auth/service.go"
    state["architect_file_paths"] = [
        "internal/auth/handler.go",
        "internal/auth/service.go",
    ]
    state["architect_specialist"] = "react-expert"

    node_fn(state)

    mock_doer.assert_called_once_with(
        role="react-expert",
        model="claude-sonnet-4-6",
        max_iterations=8,
        completion_promise="TASK COMPLETE",
        max_budget_usd=None,
        timeout=600,
    )


def test_developer_prepends_focus_instructions(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer prompt starts with focus instructions to suppress meta-tools."""
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-focus", level="task")
    state["agent_output"] = "Build auth middleware"

    node_fn(state)

    doer_instance = mock_doer.return_value
    call_args = doer_instance.ralph_loop.call_args
    prompt = call_args.kwargs["prompt"]
    assert prompt.startswith("IMPORTANT: You are a code implementation agent.")
    assert "TaskCreate" in prompt
    assert "Do NOT use planning" in prompt


def test_developer_reads_artifact_files(tmp_path):
    """Developer reads architect.md and task_spec.md artifacts when agent_output is empty."""
    repo = tmp_path / "repo"
    repo.mkdir()
    artifact_dir = repo / ".scaffold" / "artifacts" / "task-001"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "architect.md").write_text(
        '{"technical_design": "REST API", "specialist": "python-expert", '
        '"file_paths": ["src/api.py"], "children": []}'
    )
    (artifact_dir / "task_spec.md").write_text("# Build API\n\nAcceptance criteria:\n- Works")

    mock_loader = MagicMock()
    mock_loader.load_specialist.return_value = "implement this"
    mock_loader.detect_specialist.return_value = "python-expert"
    agents_config = MagicMock()
    agents_config.specialists = {
        "python-expert": {
            "model": "claude-sonnet-4-6",
            "max_iterations": 1,
            "completion_promise": "TASK COMPLETE",
            "timeout": 60,
        }
    }

    node_fn = make_developer_node(
        repo_path=str(repo),
        branch_prefix="scaffold",
        agent_loader=mock_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-001", level="task")
    # agent_output is empty — developer should read from artifacts instead
    state["agent_output"] = ""

    with (
        patch.object(DoerAgent, "create_worktree", return_value=repo),
        patch.object(DoerAgent, "cleanup_worktree"),
        patch.object(
            DoerAgent,
            "ralph_loop",
            return_value=MagicMock(success=True, iterations=1, output="TASK COMPLETE"),
        ),
        patch("orchestrator.nodes.developer.subprocess"),
    ):
        node_fn(state)

    call_args = mock_loader.load_specialist.call_args
    task_context_arg = call_args[0][2] if len(call_args[0]) > 2 else ""
    assert "REST API" in task_context_arg
    assert "Build API" in task_context_arg


def test_developer_writes_artifact(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    mock_loader = MagicMock()
    mock_loader.load_specialist.return_value = "implement this"
    mock_loader.detect_specialist.return_value = ""
    agents_config = MagicMock()
    agents_config.specialists = {
        "python-expert": {
            "model": "claude-sonnet-4-6",
            "max_iterations": 1,
            "completion_promise": "TASK COMPLETE",
            "timeout": 60,
        }
    }

    node_fn = make_developer_node(
        repo_path=str(repo),
        branch_prefix="scaffold",
        agent_loader=mock_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-001", level="task")

    with (
        patch.object(DoerAgent, "create_worktree", return_value=repo),
        patch.object(DoerAgent, "cleanup_worktree"),
        patch.object(
            DoerAgent,
            "ralph_loop",
            return_value=MagicMock(success=True, iterations=1, output="TASK COMPLETE"),
        ),
        patch("orchestrator.nodes.developer.subprocess"),
    ):
        node_fn(state)

    artifact = repo / ".scaffold" / "artifacts" / "task-001" / "developer.md"
    assert artifact.exists()
    assert "TASK COMPLETE" in artifact.read_text()
