from unittest.mock import MagicMock

from orchestrator.dispatcher import _normalize_acceptance, run_task
from orchestrator.state import initial_state


def test_run_task_leaf_no_children(db):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    task_id = tree.create(title="Leaf task", level="task")

    graph = MagicMock()
    graph.invoke.return_value = {"status": "done", "child_tasks": []}

    state = initial_state(task_id=task_id, level="task")
    result = run_task(graph, tree, state, task_id)

    graph.invoke.assert_called_once()
    assert result["status"] == "done"
    row = tree.get(task_id)
    assert row["status"] == "done"


def test_run_task_with_children_recurses(db):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    parent_id = tree.create(title="Epic", level="epic")

    graph = MagicMock()
    call_count = 0

    def mock_invoke(state, config=None):
        nonlocal call_count
        call_count += 1
        if state["level"] == "epic":
            return {
                "status": "decomposing",
                "child_tasks": [
                    {
                        "title": "Feature A",
                        "level": "feature",
                        "spec_ref": "Section 1",
                        "acceptance": ["AC-1"],
                    },
                    {
                        "title": "Feature B",
                        "level": "feature",
                        "spec_ref": "Section 2",
                        "acceptance": ["AC-2"],
                    },
                ],
                "project_context": "test context",
                "specialists": ["python-expert"],
                "advisory": [],
                "detected_languages": ["python"],
                "test_framework": "pytest",
            }
        return {"status": "done", "child_tasks": []}

    graph.invoke.side_effect = mock_invoke

    state = initial_state(task_id=parent_id, level="epic")
    run_task(graph, tree, state, parent_id)

    assert graph.invoke.call_count == 3
    children = tree.list_children(parent_id)
    assert len(children) == 2
    assert {c["title"] for c in children} == {"Feature A", "Feature B"}
    assert all(c["level"] == "feature" for c in children)
    parent = tree.get(parent_id)
    assert parent["status"] == "done"


def test_run_task_children_inherit_context(db):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    parent_id = tree.create(title="Epic", level="epic")

    graph = MagicMock()
    captured_states = []

    def mock_invoke(state, config=None):
        captured_states.append(dict(state))
        if state["level"] == "epic":
            return {
                "status": "decomposing",
                "child_tasks": [
                    {"title": "Child", "level": "task", "acceptance": ["works"]},
                ],
                "project_context": "Go + React",
                "specialists": ["go-expert", "react-expert"],
                "advisory": ["postgres-expert"],
                "detected_languages": ["go", "typescript"],
                "test_framework": "go test",
            }
        return {"status": "done", "child_tasks": []}

    graph.invoke.side_effect = mock_invoke

    state = initial_state(task_id=parent_id, level="epic")
    run_task(graph, tree, state, parent_id)

    child_state = captured_states[1]
    assert child_state["project_context"] == "Go + React"
    assert child_state["specialists"] == ["go-expert", "react-expert"]
    assert child_state["advisory"] == ["postgres-expert"]
    assert child_state["detected_languages"] == ["go", "typescript"]
    assert child_state["test_framework"] == "go test"
    assert child_state["level"] == "task"
    assert "Child" in child_state["agent_output"]
    assert "works" in child_state["agent_output"]


def test_run_task_nested_decomposition(db):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    epic_id = tree.create(title="Epic", level="epic")

    graph = MagicMock()

    def mock_invoke(state, config=None):
        if state["level"] == "epic":
            return {
                "status": "decomposing",
                "child_tasks": [
                    {"title": "Feature", "level": "feature"},
                ],
                "project_context": "",
                "specialists": ["python-expert"],
                "advisory": [],
                "detected_languages": [],
                "test_framework": "",
            }
        if state["level"] == "feature":
            return {
                "status": "decomposing",
                "child_tasks": [
                    {"title": "Task 1", "level": "task"},
                    {"title": "Task 2", "level": "task"},
                ],
                "project_context": "",
                "specialists": ["python-expert"],
                "advisory": [],
                "detected_languages": [],
                "test_framework": "",
            }
        return {"status": "done", "child_tasks": []}

    graph.invoke.side_effect = mock_invoke

    state = initial_state(task_id=epic_id, level="epic")
    run_task(graph, tree, state, epic_id)

    assert graph.invoke.call_count == 4
    features = tree.list_children(epic_id)
    assert len(features) == 1
    tasks = tree.list_children(features[0]["id"])
    assert len(tasks) == 2


def test_run_task_parent_blocked_when_child_not_done(db):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    parent_id = tree.create(title="Epic", level="epic")

    graph = MagicMock()

    def mock_invoke(state, config=None):
        if state["level"] == "epic":
            return {
                "status": "decomposing",
                "child_tasks": [
                    {"title": "OK", "level": "task"},
                    {"title": "Stuck", "level": "task"},
                ],
                "project_context": "",
                "specialists": [],
                "advisory": [],
                "detected_languages": [],
                "test_framework": "",
            }
        if "Stuck" in state.get("agent_output", ""):
            return {"status": "stuck", "child_tasks": []}
        return {"status": "done", "child_tasks": []}

    graph.invoke.side_effect = mock_invoke

    state = initial_state(task_id=parent_id, level="epic")
    run_task(graph, tree, state, parent_id)

    parent = tree.get(parent_id)
    assert parent["status"] == "blocked"


def test_run_task_graph_invoke_exception_marks_stuck(db):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    task_id = tree.create(title="Exploding task", level="task")

    graph = MagicMock()
    graph.invoke.side_effect = RuntimeError("LLM provider timeout")

    state = initial_state(task_id=task_id, level="task")
    result = run_task(graph, tree, state, task_id)

    assert result["status"] == "stuck"
    row = tree.get(task_id)
    assert row["status"] == "stuck"


def test_normalize_acceptance_variants():
    assert _normalize_acceptance(None) == []
    assert _normalize_acceptance(["a", "b"]) == ["a", "b"]
    assert _normalize_acceptance('["x","y"]') == ["x", "y"]
    assert _normalize_acceptance("plain text criterion") == ["plain text criterion"]
    assert _normalize_acceptance(42) == []
