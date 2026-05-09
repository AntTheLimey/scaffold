import json
import pytest
from orchestrator.telemetry import Telemetry


@pytest.fixture
def telemetry(db):
    return Telemetry(db)


def test_log_event(telemetry, db):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
        ("task-001", "task", "in_progress", "Test"),
    )
    db.commit()
    telemetry.log(
        task_id="task-001",
        agent_role="developer",
        event_type="agent.start",
        event_data={"model": "claude-sonnet-4-20250514", "prompt_hash": "abc123"},
    )
    events = telemetry.get_events("task-001")
    assert len(events) == 1
    assert events[0]["event_type"] == "agent.start"
    data = json.loads(events[0]["event_data"])
    assert data["model"] == "claude-sonnet-4-20250514"


def test_log_event_with_run_id(telemetry, db):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
        ("task-001", "task", "in_progress", "Test"),
    )
    db.execute(
        "INSERT INTO agent_runs (id, task_id, agent_role, model) VALUES (?, ?, ?, ?)",
        ("run-001", "task-001", "developer", "claude-sonnet-4-20250514"),
    )
    db.commit()
    telemetry.log(
        task_id="task-001",
        agent_role="developer",
        event_type="agent.iteration",
        event_data={"iteration": 1},
        run_id="run-001",
    )
    events = telemetry.get_events("task-001")
    assert events[0]["run_id"] == "run-001"


def test_count_cycles(telemetry, db):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
        ("task-001", "task", "in_progress", "Test"),
    )
    db.commit()
    for i in range(3):
        telemetry.log(
            task_id="task-001",
            event_type="task.cycle",
            event_data={"cycle_type": "revise", "reason": "style issues"},
        )
    count = telemetry.count_cycles("task-001", "revise")
    assert count == 3


def test_get_events_by_type(telemetry, db):
    for tid in ("t1", "t2"):
        db.execute(
            "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
            (tid, "task", "in_progress", "Test"),
        )
    db.commit()
    telemetry.log(task_id="t1", event_type="agent.start", event_data={})
    telemetry.log(task_id="t1", event_type="agent.output", event_data={})
    telemetry.log(task_id="t2", event_type="agent.start", event_data={})
    starts = telemetry.get_events_by_type("agent.start")
    assert len(starts) == 2


def test_start_run(telemetry, db):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
        ("task-001", "task", "in_progress", "Test"),
    )
    db.commit()
    run_id = telemetry.start_run("task-001", "developer", "claude-sonnet-4-20250514")
    run = db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    assert run["agent_role"] == "developer"
    assert run["outcome"] is None


def test_finish_run(telemetry, db):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
        ("task-001", "task", "in_progress", "Test"),
    )
    db.commit()
    run_id = telemetry.start_run("task-001", "developer", "claude-sonnet-4-20250514")
    telemetry.finish_run(
        run_id, outcome="success", iterations=3, token_in=1000, token_out=500
    )
    run = db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    assert run["outcome"] == "success"
    assert run["iterations"] == 3
