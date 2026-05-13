import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    schema = Path(__file__).parent.parent / "db" / "schema.sql"
    conn.executescript(schema.read_text())
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _mock_event_bus():
    with patch("orchestrator.event_bus._bus", None):
        yield


@pytest.fixture
def config_dir(tmp_path):
    governance = tmp_path / "governance.yaml"
    governance.write_text(
        "rapid:\n"
        "  product_scope:\n"
        "    recommend: product_owner\n"
        "    agree: architect\n"
        "    perform: developer\n"
        "    decide: human\n"
        "raci:\n"
        "  write_code:\n"
        "    responsible: developer\n"
        "    accountable: reviewer\n"
        "    consulted: [architect]\n"
        "    informed: [product_owner, qa]\n"
    )
    agents = tmp_path / "agents.yaml"
    agents.write_text(
        "workflow:\n"
        "  product_owner:\n"
        "    model: claude-opus-4-6\n"
        "    execution: api\n"
        "  architect:\n"
        "    model: claude-opus-4-6\n"
        "    execution: api\n"
        "  designer:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: api\n"
        "  reviewer:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "  qa:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 8\n"
        "    completion_promise: TESTS PASSING\n"
        "  consensus:\n"
        "    model: claude-opus-4-6\n"
        "    execution: api\n"
        "specialists:\n"
        "  python-expert:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 10\n"
        "    completion_promise: TASK COMPLETE\n"
        "  go-expert:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 10\n"
        "    completion_promise: TASK COMPLETE\n"
        "escalation:\n"
        "  stuck_loop_model: claude-opus-4-6\n"
        "  max_review_cycles: 3\n"
        "  max_bug_cycles: 3\n"
        "  cost_threshold_per_run: 5.00\n"
    )
    project = tmp_path / "project.yaml"
    project.write_text(
        "repo_path: /tmp/test-repo\n"
        "branch_prefix: scaffold\n"
        "max_concurrent_agents: 3\n"
        "db_path: ':memory:'\n"
    )
    return tmp_path


@pytest.fixture
def sample_task():
    return {
        "id": "task-001",
        "parent_id": None,
        "level": "epic",
        "title": "Core Platform",
        "spec_ref": "Section 12.1",
        "acceptance": '["Auth works", "WebSocket connects"]',
    }
