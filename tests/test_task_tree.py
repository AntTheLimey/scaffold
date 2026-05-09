import json

import pytest

from orchestrator.task_tree import TaskTree


@pytest.fixture
def tree(db):
    return TaskTree(db)


def test_create_task(tree):
    task_id = tree.create(
        title="Core Platform",
        level="epic",
        spec_ref="Section 12.1",
        acceptance=["Auth works", "WebSocket connects"],
    )
    task = tree.get(task_id)
    assert task["title"] == "Core Platform"
    assert task["level"] == "epic"
    assert task["status"] == "pending"
    assert json.loads(task["acceptance"]) == ["Auth works", "WebSocket connects"]


def test_create_child_task(tree):
    parent_id = tree.create(title="Core Platform", level="epic")
    child_id = tree.create(title="Auth System", level="feature", parent_id=parent_id)
    child = tree.get(child_id)
    assert child["parent_id"] == parent_id


def test_update_status(tree):
    task_id = tree.create(title="Test Task", level="task")
    tree.update_status(task_id, "ready")
    assert tree.get(task_id)["status"] == "ready"


def test_invalid_status_transition(tree):
    task_id = tree.create(title="Test Task", level="task")
    with pytest.raises(ValueError, match="Invalid status"):
        tree.update_status(task_id, "invalid_status")


def test_list_children(tree):
    parent_id = tree.create(title="Epic", level="epic")
    tree.create(title="Feature 1", level="feature", parent_id=parent_id)
    tree.create(title="Feature 2", level="feature", parent_id=parent_id)
    children = tree.list_children(parent_id)
    assert len(children) == 2


def test_add_dependency(tree):
    blocker = tree.create(title="Blocker", level="task")
    blocked = tree.create(title="Blocked", level="task")
    tree.add_dependency(blocker_id=blocker, blocked_id=blocked)
    deps = tree.get_blockers(blocked)
    assert len(deps) == 1
    assert deps[0]["id"] == blocker


def test_unblocked_tasks(tree):
    t1 = tree.create(title="Task 1", level="task")
    t2 = tree.create(title="Task 2", level="task")
    t3 = tree.create(title="Task 3", level="task")
    tree.update_status(t1, "ready")
    tree.update_status(t2, "ready")
    tree.update_status(t3, "ready")
    tree.add_dependency(blocker_id=t1, blocked_id=t2)
    unblocked = tree.get_ready_tasks()
    ids = [t["id"] for t in unblocked]
    assert t1 in ids
    assert t3 in ids
    assert t2 not in ids


def test_unblocked_after_blocker_done(tree):
    t1 = tree.create(title="Blocker", level="task")
    t2 = tree.create(title="Blocked", level="task")
    tree.update_status(t1, "ready")
    tree.update_status(t2, "ready")
    tree.add_dependency(blocker_id=t1, blocked_id=t2)
    tree.update_status(t1, "done")
    unblocked = tree.get_ready_tasks()
    ids = [t["id"] for t in unblocked]
    assert t2 in ids


def test_list_by_status(tree):
    tree.create(title="T1", level="task")
    t2 = tree.create(title="T2", level="task")
    tree.update_status(t2, "ready")
    ready = tree.list_by_status("ready")
    assert len(ready) == 1
    assert ready[0]["id"] == t2
