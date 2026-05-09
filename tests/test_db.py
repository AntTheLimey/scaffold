from orchestrator.db import init_db


def test_init_db_creates_tables():
    conn = init_db(":memory:")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    assert "tasks" in tables
    assert "task_edges" in tables
    assert "decisions" in tables
    assert "agent_runs" in tables
    assert "events" in tables
    conn.close()


def test_init_db_creates_views():
    conn = init_db(":memory:")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
    views = [row[0] for row in cursor.fetchall()]
    assert "epic_costs" in views
    assert "cycle_hotspots" in views
    assert "agent_efficiency" in views
    conn.close()


def test_foreign_keys_enabled():
    conn = init_db(":memory:")
    result = conn.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1
    conn.close()
