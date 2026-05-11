from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orchestrator.graph import build_graph
from orchestrator.state import initial_state


@pytest.fixture
def mock_deps():
    agents_config = MagicMock()
    agents_config.specialists = {
        "python-expert": {
            "model": "claude-sonnet-4-6",
            "execution": "cli",
            "max_iterations": 10,
            "completion_promise": "TASK COMPLETE",
        },
    }
    agents_config.workflow = {
        "reviewer": {"model": "claude-sonnet-4-6"},
        "qa": {"model": "claude-sonnet-4-6"},
    }
    mock_loader = MagicMock()
    mock_loader.agents_dir = Path("/tmp/agents")
    return {
        "client": MagicMock(),
        "bot": MagicMock(),
        "repo_path": "/tmp/repo",
        "branch_prefix": "scaffold",
        "spec_path": "/tmp/spec.md",
        "agent_loader": mock_loader,
        "agents_config": agents_config,
    }


def test_build_graph_compiles(mock_deps):
    graph = build_graph(**mock_deps)
    assert graph is not None


def test_graph_has_onboarding_node(mock_deps):
    graph = build_graph(**mock_deps)
    node_names = set(graph.nodes.keys())
    assert "onboarding" in node_names


def test_graph_has_all_nodes(mock_deps):
    graph = build_graph(**mock_deps)
    node_names = set(graph.nodes.keys())
    expected = {
        "onboarding",
        "product_owner",
        "architect",
        "designer",
        "developer",
        "reviewer",
        "qa",
        "consensus",
        "human_gate",
    }
    assert expected.issubset(node_names)


def test_intake_routes_epic_to_po(mock_deps):
    from orchestrator.graph import intake_router

    state = initial_state(task_id="epic-001", level="epic")
    assert intake_router(state) == "product_owner"


def test_intake_routes_feature_to_architect(mock_deps):
    from orchestrator.graph import intake_router

    state = initial_state(task_id="feat-001", level="feature")
    assert intake_router(state) == "architect"


def test_intake_routes_task_to_developer(mock_deps):
    from orchestrator.graph import intake_router

    state = initial_state(task_id="task-001", level="task")
    assert intake_router(state) == "developer"


def test_reviewer_routes_approve_to_qa():
    from orchestrator.graph import reviewer_router

    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "approve"
    assert reviewer_router(state) == "qa"


def test_reviewer_routes_revise_to_developer():
    from orchestrator.graph import reviewer_router

    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "revise"
    state["review_cycles"] = 1
    assert reviewer_router(state) == "developer"


def test_reviewer_routes_to_human_gate_after_3_cycles():
    from orchestrator.graph import reviewer_router

    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "revise"
    state["review_cycles"] = 3
    assert reviewer_router(state) == "human_gate"


def test_qa_routes_pass_to_end():
    from orchestrator.graph import qa_router

    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "pass"
    assert qa_router(state) == "__end__"


def test_qa_routes_fail_to_developer():
    from orchestrator.graph import qa_router

    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "fail"
    state["bug_cycles"] = 1
    assert qa_router(state) == "developer"


def test_human_gate_routes_revise_to_developer():
    from orchestrator.graph import human_gate_router

    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "Revise"
    assert human_gate_router(state) == "developer"


def test_human_gate_routes_approve_to_end():
    from orchestrator.graph import human_gate_router

    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "Approve"
    assert human_gate_router(state) == "__end__"


def test_human_gate_routes_cancel_to_end():
    from orchestrator.graph import human_gate_router

    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "Cancel"
    assert human_gate_router(state) == "__end__"
