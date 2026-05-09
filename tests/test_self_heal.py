import pytest

from orchestrator.self_heal import SelfHealer
from orchestrator.telemetry import Telemetry


@pytest.fixture
def healer(db):
    telemetry = Telemetry(db)
    return SelfHealer(telemetry, max_review_cycles=3, max_bug_cycles=3)


@pytest.fixture
def telemetry(db):
    return Telemetry(db)


def test_detect_stuck_loop(healer, db, telemetry):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES ('t1', 'task', 'in_progress', 'T1')"
    )
    db.commit()
    for _ in range(4):
        telemetry.log(
            task_id="t1",
            event_type="task.cycle",
            event_data={"cycle_type": "revise", "reason": "style"},
        )
    action = healer.check("t1")
    assert action is not None
    assert action["type"] == "escalate_model"


def test_no_action_below_threshold(healer, db, telemetry):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES ('t1', 'task', 'in_progress', 'T1')"
    )
    db.commit()
    telemetry.log(
        task_id="t1",
        event_type="task.cycle",
        event_data={"cycle_type": "revise", "reason": "style"},
    )
    action = healer.check("t1")
    assert action is None


def test_detect_cascading_failures(healer, db, telemetry):
    db.execute(
        "INSERT INTO tasks (id, parent_id, level, status, title) VALUES "
        "('epic1', NULL, 'epic', 'in_progress', 'Epic')"
    )
    for i in range(3):
        tid = f"task-{i}"
        db.execute(
            "INSERT INTO tasks (id, parent_id, level, status, title) VALUES "
            f"('{tid}', 'epic1', 'task', 'stuck', 'Task {i}')"
        )
    db.commit()
    action = healer.check_epic("epic1")
    assert action is not None
    assert action["type"] == "pause_epic"


def test_detect_review_ping_pong(healer, db, telemetry):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES ('t1', 'task', 'in_progress', 'T1')"
    )
    db.commit()
    for _ in range(3):
        telemetry.log(
            task_id="t1",
            event_type="task.cycle",
            event_data={"cycle_type": "revise", "reason": "disagreement"},
        )
    action = healer.check("t1")
    assert action["type"] == "escalate_model"


def test_detect_bug_cycle_escalation(healer, db, telemetry):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES ('t1', 'task', 'in_progress', 'T1')"
    )
    db.commit()
    for _ in range(4):
        telemetry.log(
            task_id="t1",
            event_type="task.cycle",
            event_data={"cycle_type": "bug", "reason": "test failure"},
        )
    action = healer.check("t1")
    assert action is not None
