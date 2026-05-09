from unittest.mock import MagicMock

import pytest

from orchestrator.graph import build_graph
from orchestrator.state import initial_state


@pytest.fixture
def mock_deps():
    return {
        "client": MagicMock(),
        "bot": MagicMock(),
        "repo_path": "/tmp/repo",
        "branch_prefix": "scaffold",
        "spec_path": "/tmp/spec.md",
        "model": "claude-sonnet-4-20250514",
    }


def test_build_graph_compiles(mock_deps):
    graph = build_graph(**mock_deps)
    assert graph is not None


def test_graph_has_all_nodes(mock_deps):
    graph = build_graph(**mock_deps)
    node_names = set(graph.nodes.keys())
    expected = {
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
