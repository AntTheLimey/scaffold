from orchestrator.state import initial_state


def test_initial_state_has_required_fields():
    state = initial_state(task_id="task-001", level="task")
    assert state["task_id"] == "task-001"
    assert state["level"] == "task"
    assert state["status"] == "pending"
    assert state["verdict"] == ""
    assert state["review_cycles"] == 0
    assert state["bug_cycles"] == 0
    assert state["model_override"] is None
    assert state["escalation_reason"] is None


def test_initial_state_for_epic():
    state = initial_state(task_id="epic-001", level="epic")
    assert state["level"] == "epic"
    assert state["child_tasks"] == []


def test_initial_state_has_specialist_roster_fields():
    state = initial_state(task_id="task-002", level="task")
    assert state["specialists"] == []
    assert state["advisory"] == []
    assert state["project_context"] == ""
    assert state["detected_languages"] == []
    assert state["test_framework"] == ""
