import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from orchestrator.event_bus import EventBus, get_bus, init_event_bus


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "db" / "schema.sql"
    conn.executescript(schema.read_text())
    return conn


def _get_events(conn):
    return conn.execute("SELECT * FROM events ORDER BY timestamp").fetchall()


def test_emit_writes_to_db():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.emit("test.event", agent_role="tester", task_id="t-1", foo="bar")
    events = _get_events(conn)
    assert len(events) == 1
    assert events[0]["event_type"] == "test.event"
    assert events[0]["agent_role"] == "tester"
    assert events[0]["task_id"] == "t-1"
    data = json.loads(events[0]["event_data"])
    assert data["foo"] == "bar"


def test_emit_echoes_to_console():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click") as mock_click:
        bus.emit("node.enter", agent_role="architect", task_id="t-2", level="feature")
    mock_click.echo.assert_called_once()
    output = mock_click.echo.call_args.args[0]
    assert "architect" in output
    assert "node.enter" in output
    assert "t-2" in output


def test_node_enter_event():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.node_enter("onboarding", "t-3", "epic")
    events = _get_events(conn)
    assert events[0]["event_type"] == "node.enter"
    assert events[0]["agent_role"] == "onboarding"
    data = json.loads(events[0]["event_data"])
    assert data["level"] == "epic"


def test_node_exit_event():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.node_exit("architect", "t-4", "has_ui=False")
    events = _get_events(conn)
    assert events[0]["event_type"] == "node.exit"
    data = json.loads(events[0]["event_data"])
    assert data["summary"] == "has_ui=False"


def test_api_call_events():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.api_call_start("product_owner", "claude-opus-4-6", 5000, "t-5")
        bus.api_call_done("product_owner", "claude-opus-4-6", 600, 400, "t-5")
    events = _get_events(conn)
    assert len(events) == 2
    assert events[0]["event_type"] == "api.call"
    assert events[1]["event_type"] == "api.response"
    resp_data = json.loads(events[1]["event_data"])
    assert resp_data["token_in"] == 600
    assert resp_data["token_out"] == 400


def test_cli_events():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.cli_start("python-expert", "claude-sonnet-4-6", 1, "t-6")
        bus.cli_done("python-expert", 1, True, "t-6")
    events = _get_events(conn)
    assert len(events) == 2
    assert events[0]["event_type"] == "cli.start"
    assert events[1]["event_type"] == "cli.done"
    done_data = json.loads(events[1]["event_data"])
    assert done_data["success"] is True


def test_route_event():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.route("onboarding", "product_owner", "level=epic", "t-7")
    events = _get_events(conn)
    assert events[0]["event_type"] == "graph.route"
    data = json.loads(events[0]["event_data"])
    assert data["to"] == "product_owner"
    assert data["reason"] == "level=epic"


def test_error_event():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.error("developer", "subprocess timed out", "t-8")
    events = _get_events(conn)
    assert events[0]["event_type"] == "agent.error"
    data = json.loads(events[0]["event_data"])
    assert "timed out" in data["error"]


def test_escalation_event():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.escalation("stuck after 3 cycles", "t-9")
    events = _get_events(conn)
    assert events[0]["event_type"] == "agent.escalate"


def test_get_bus_returns_none_before_init():
    import orchestrator.event_bus as eb

    old = eb._bus
    try:
        eb._bus = None
        assert get_bus() is None
    finally:
        eb._bus = old


def test_init_event_bus_sets_singleton():
    import orchestrator.event_bus as eb

    old = eb._bus
    try:
        conn = _make_db()
        bus = init_event_bus(conn)
        assert get_bus() is bus
    finally:
        eb._bus = old


def test_tool_call_event():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.tool_call("developer", "Edit", "t-10", run_id="run-1")
    events = _get_events(conn)
    assert len(events) == 1
    assert events[0]["event_type"] == "tool.call"
    assert events[0]["agent_role"] == "developer"
    data = json.loads(events[0]["event_data"])
    assert data["tool_name"] == "Edit"


def test_tool_call_event_without_run_id():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.tool_call("developer", "Bash", "t-11")
    events = _get_events(conn)
    assert len(events) == 1
    assert events[0]["run_id"] is None
    data = json.loads(events[0]["event_data"])
    assert data["tool_name"] == "Bash"
