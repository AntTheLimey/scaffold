# Agentic Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable, project-agnostic orchestration system that coordinates multiple AI agents through a LangGraph workflow with cyclical review loops, governance protocols, and human-in-the-loop escalation via Telegram.

**Architecture:** LangGraph state machine with 7 agent roles as nodes. Advisor agents (Product Owner, Architect, Designer) use the Claude API for pure reasoning. Doer agents (Developer, QA) spawn `claude -p` in git worktrees with Ralph loop iteration. Reviewer is a hybrid that reads code via `claude -p` but only outputs structured verdicts. The Orchestrator is deterministic Python — no LLM reasoning, just routing rules from YAML governance config. SQLite stores the task tree, event log, and LangGraph checkpoints.

**Tech Stack:** Python 3.12+, LangGraph 1.x, Anthropic SDK, SQLite, PyYAML, httpx (Telegram Bot API), Click (CLI)

**Source spec:** `/Users/antonypegg/PROJECTS/inkwell/docs/design/2026-05-08-scaffold-spec.md`

**Project location:** `/Users/antonypegg/PROJECTS/scaffold/` (standalone project — the scaffold is a tool, not part of inkwell)

**Target project:** `/Users/antonypegg/PROJECTS/inkwell/` (the repo the scaffold builds — referenced via `config/project.yaml`)

---

## File Structure

```
scaffold/                            # Standalone project at ~/PROJECTS/scaffold/
├── orchestrator/                    # Main Python package
│   ├── __init__.py
│   ├── __main__.py                  # CLI entry point (run, resume, report)
│   ├── graph.py                     # LangGraph StateGraph wiring
│   ├── state.py                     # TaskState TypedDict
│   ├── router.py                    # RAPID/RACI routing from governance config
│   ├── task_tree.py                 # Task CRUD, status transitions, dependency queries
│   ├── telemetry.py                 # Event logging + metric queries
│   ├── self_heal.py                 # Failure pattern detection + automatic responses
│   ├── db.py                        # SQLite connection management + schema init
│   ├── config.py                    # YAML config loading + validation
│   ├── telegram.py                  # Telegram Bot API client (escalations + digests)
│   └── nodes/                       # One module per agent role
│       ├── __init__.py
│       ├── base.py                  # AdvisorAgent + DoerAgent base classes
│       ├── product_owner.py         # Spec decomposition → epics/features/tasks
│       ├── architect.py             # Technical design, API contracts, data models
│       ├── designer.py              # UI/UX specs (conditional — only for UI tasks)
│       ├── developer.py             # Code implementation via claude -p in worktrees
│       ├── reviewer.py              # Code review → approve/revise verdicts
│       ├── qa.py                    # Test writing + execution via claude -p
│       ├── consensus.py             # Structured debate resolution (RAPID vetoes)
│       └── human_gate.py            # Telegram escalation — pauses graph, awaits reply
├── config/
│   ├── governance.yaml              # RAPID/RACI matrices
│   ├── agents.yaml                  # Model assignments, Ralph loop config per role
│   └── project.yaml                 # Target repo path, branch naming, concurrency limits
├── prompts/                         # Agent priming files (5-layer priming per blog)
│   ├── product_owner.md
│   ├── architect.md
│   ├── designer.md
│   ├── developer.md
│   ├── reviewer.md
│   └── qa.md
├── db/
│   └── schema.sql                   # DDL for tasks, task_edges, decisions, agent_runs, events
├── tests/
│   ├── conftest.py                  # Shared fixtures: in-memory DB, sample configs
│   ├── test_db.py
│   ├── test_task_tree.py
│   ├── test_config.py
│   ├── test_state.py
│   ├── test_telemetry.py
│   ├── test_router.py
│   ├── test_self_heal.py
│   ├── test_advisor_base.py
│   ├── test_doer_base.py
│   ├── test_product_owner.py
│   ├── test_architect.py
│   ├── test_designer.py
│   ├── test_developer.py
│   ├── test_reviewer.py
│   ├── test_qa.py
│   ├── test_consensus.py
│   ├── test_telegram.py
│   ├── test_human_gate.py
│   ├── test_graph.py
│   └── test_cli.py
├── pyproject.toml
└── docs/
    └── superpowers/
        └── plans/
            └── 2026-05-08-agentic-scaffold.md
```

**Note:** The scaffold does NOT contain master specs. Specs live in the target project (inkwell). The scaffold reads them via the `--spec` CLI flag or `project.yaml` config.

**Parallelism opportunities:** After Task 1 (bootstrap), Tasks 2/4/5 can run in parallel. After those, Tasks 6/7/9/10 can run in parallel. After agent bases are built, all agent nodes (Tasks 11-17) can run in parallel. Tasks 18-21 are sequential.

---

## Phase 1: Foundation

### Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `orchestrator/__init__.py`
- Create: `orchestrator/nodes/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "agentic-scaffold"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langgraph>=1.0.0",
    "langgraph-checkpoint-sqlite>=2.0.0",
    "anthropic>=0.45.0",
    "pyyaml>=6.0",
    "httpx>=0.27.0",
    "click>=8.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[project.scripts]
scaffold = "orchestrator.__main__:main"
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p orchestrator/nodes tests config prompts db docs/superpowers/plans
touch orchestrator/__init__.py orchestrator/nodes/__init__.py
```

- [ ] **Step 3: Create test conftest with shared fixtures**

Write `tests/conftest.py`:

```python
import sqlite3
from pathlib import Path

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
        "roles:\n"
        "  product_owner:\n"
        "    model: claude-opus-4-20250514\n"
        "    execution: api\n"
        "  architect:\n"
        "    model: claude-opus-4-20250514\n"
        "    execution: api\n"
        "  designer:\n"
        "    model: claude-sonnet-4-20250514\n"
        "    execution: api\n"
        "  developer:\n"
        "    model: claude-sonnet-4-20250514\n"
        "    execution: cli\n"
        "    max_iterations: 10\n"
        "    completion_promise: TASK COMPLETE\n"
        "  reviewer:\n"
        "    model: claude-sonnet-4-20250514\n"
        "    execution: cli\n"
        "  qa:\n"
        "    model: claude-sonnet-4-20250514\n"
        "    execution: cli\n"
        "    max_iterations: 8\n"
        "    completion_promise: TESTS PASSING\n"
    )
    project = tmp_path / "project.yaml"
    project.write_text(
        "repo_path: /tmp/test-repo\n"
        "branch_prefix: scaffold\n"
        "max_concurrent_agents: 3\n"
        "telegram_bot_token: ''\n"
        "telegram_chat_id: ''\n"
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
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 5: Verify pytest runs**

```bash
pytest --co -q
```

Expected: `no tests ran` (no test files yet, but no import errors)

- [ ] **Step 6: Commit**

```bash
git init
git add pyproject.toml orchestrator/ tests/conftest.py
git commit -m "feat: bootstrap scaffold project with dependencies and test fixtures"
```

---

### Task 2: Database Layer

**Files:**
- Create: `db/schema.sql`
- Create: `orchestrator/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_db.py`:

```python
from orchestrator.db import init_db, get_connection


def test_init_db_creates_tables():
    conn = init_db(":memory:")
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "tasks" in tables
    assert "task_edges" in tables
    assert "decisions" in tables
    assert "agent_runs" in tables
    assert "events" in tables
    conn.close()


def test_init_db_creates_views():
    conn = init_db(":memory:")
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    )
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'orchestrator.db'`

- [ ] **Step 3: Create the schema SQL**

Write `db/schema.sql` — copy the full schema from the spec (Section 8.2). This includes:
- `tasks` table with status constraints
- `task_edges` for dependency tracking
- `decisions` for RAPID-tracked strategic decisions
- `agent_runs` for execution records
- `events` append-only log
- Indexes on events(task_id), events(event_type), tasks(status), tasks(parent_id)
- Views: `epic_costs`, `cycle_hotspots`, `agent_efficiency`

```sql
CREATE TABLE tasks (
    id          TEXT PRIMARY KEY,
    parent_id   TEXT REFERENCES tasks(id),
    level       TEXT CHECK(level IN ('epic','feature','task','subtask')),
    status      TEXT CHECK(status IN ('pending','decomposing','ready',
                    'in_progress','in_review','testing','done',
                    'blocked','stuck')),
    title       TEXT NOT NULL,
    spec_ref    TEXT,
    assigned_to TEXT,
    model       TEXT,
    branch      TEXT,
    acceptance  JSON,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE task_edges (
    blocker_id  TEXT REFERENCES tasks(id),
    blocked_id  TEXT REFERENCES tasks(id),
    PRIMARY KEY (blocker_id, blocked_id)
);

CREATE TABLE decisions (
    id          TEXT PRIMARY KEY,
    task_id     TEXT REFERENCES tasks(id),
    type        TEXT,
    rapid_r     TEXT,
    rapid_a     TEXT,
    rapid_d     TEXT,
    status      TEXT CHECK(status IN ('proposed','agreed','vetoed',
                    'escalated','resolved')),
    context     JSON,
    resolved_at TIMESTAMP
);

CREATE TABLE agent_runs (
    id          TEXT PRIMARY KEY,
    task_id     TEXT REFERENCES tasks(id),
    agent_role  TEXT NOT NULL,
    model       TEXT NOT NULL,
    started_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    iterations  INTEGER,
    token_in    INTEGER,
    token_out   INTEGER,
    outcome     TEXT CHECK(outcome IN ('success','revise','bug',
                    'stuck','escalated','error')),
    output      JSON
);

CREATE TABLE events (
    id          TEXT PRIMARY KEY,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    task_id     TEXT REFERENCES tasks(id),
    agent_role  TEXT,
    run_id      TEXT REFERENCES agent_runs(id),
    event_type  TEXT NOT NULL,
    event_data  JSON NOT NULL
);

CREATE INDEX idx_events_task ON events(task_id, timestamp);
CREATE INDEX idx_events_type ON events(event_type, timestamp);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_parent ON tasks(parent_id);

CREATE VIEW epic_costs AS
SELECT
    t2.title as epic_title,
    t.parent_id as epic_id,
    SUM(ar.token_in) as total_tokens_in,
    SUM(ar.token_out) as total_tokens_out,
    COUNT(DISTINCT ar.id) as total_runs,
    COUNT(DISTINCT t.id) as total_tasks
FROM tasks t
JOIN agent_runs ar ON t.id = ar.task_id
LEFT JOIN tasks t2 ON t.parent_id = t2.id
GROUP BY t.parent_id;

CREATE VIEW cycle_hotspots AS
SELECT
    task_id,
    COUNT(*) as cycle_count,
    GROUP_CONCAT(DISTINCT json_extract(event_data, '$.reason')) as reasons
FROM events
WHERE event_type = 'task.cycle'
GROUP BY task_id
ORDER BY cycle_count DESC;

CREATE VIEW agent_efficiency AS
SELECT
    agent_role,
    model,
    COUNT(*) as total_runs,
    AVG(token_in + token_out) as avg_tokens,
    AVG(CAST((julianday(finished_at) - julianday(started_at)) * 86400000 AS INTEGER)) as avg_wall_clock_ms,
    SUM(CASE outcome WHEN 'success' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate_pct,
    AVG(iterations) as avg_ralph_iterations
FROM agent_runs
WHERE finished_at IS NOT NULL
GROUP BY agent_role, model;
```

- [ ] **Step 4: Write the database module**

Write `orchestrator/db.py`:

```python
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def init_db(db_path: str = "scaffold.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def get_connection(db_path: str = "scaffold.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add db/schema.sql orchestrator/db.py tests/test_db.py
git commit -m "feat: add SQLite schema and database connection layer"
```

---

### Task 3: Task Tree

**Files:**
- Create: `orchestrator/task_tree.py`
- Create: `tests/test_task_tree.py`

- [ ] **Step 1: Write failing tests for task CRUD**

Write `tests/test_task_tree.py`:

```python
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
    child_id = tree.create(
        title="Auth System", level="feature", parent_id=parent_id
    )
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_tree.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write TaskTree implementation**

Write `orchestrator/task_tree.py`:

```python
import json
import sqlite3
import uuid
from datetime import datetime, timezone

VALID_STATUSES = {
    "pending", "decomposing", "ready", "in_progress",
    "in_review", "testing", "done", "blocked", "stuck",
}


class TaskTree:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        title: str,
        level: str,
        parent_id: str | None = None,
        spec_ref: str | None = None,
        acceptance: list[str] | None = None,
    ) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.conn.execute(
            "INSERT INTO tasks (id, parent_id, level, status, title, spec_ref, acceptance) "
            "VALUES (?, ?, ?, 'pending', ?, ?, ?)",
            (task_id, parent_id, level, title, spec_ref,
             json.dumps(acceptance) if acceptance else None),
        )
        self.conn.commit()
        return task_id

    def get(self, task_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()

    def update_status(self, task_id: str, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, task_id),
        )
        self.conn.commit()

    def update_assignment(self, task_id: str, agent_role: str, model: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE tasks SET assigned_to = ?, model = ?, updated_at = ? WHERE id = ?",
            (agent_role, model, now, task_id),
        )
        self.conn.commit()

    def update_branch(self, task_id: str, branch: str) -> None:
        self.conn.execute(
            "UPDATE tasks SET branch = ? WHERE id = ?", (branch, task_id)
        )
        self.conn.commit()

    def list_children(self, parent_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE parent_id = ?", (parent_id,)
        ).fetchall()

    def list_by_status(self, status: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE status = ?", (status,)
        ).fetchall()

    def add_dependency(self, blocker_id: str, blocked_id: str) -> None:
        self.conn.execute(
            "INSERT INTO task_edges (blocker_id, blocked_id) VALUES (?, ?)",
            (blocker_id, blocked_id),
        )
        self.conn.commit()

    def get_blockers(self, task_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT t.* FROM tasks t "
            "JOIN task_edges e ON t.id = e.blocker_id "
            "WHERE e.blocked_id = ?",
            (task_id,),
        ).fetchall()

    def get_ready_tasks(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT t.* FROM tasks t "
            "WHERE t.status = 'ready' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM task_edges e "
            "  JOIN tasks b ON e.blocker_id = b.id "
            "  WHERE e.blocked_id = t.id AND b.status != 'done'"
            ")"
        ).fetchall()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_task_tree.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/task_tree.py tests/test_task_tree.py
git commit -m "feat: add task tree with CRUD, status transitions, and dependency tracking"
```

---

### Task 4: Config Loading

**Files:**
- Create: `config/governance.yaml`
- Create: `config/agents.yaml`
- Create: `config/project.yaml`
- Create: `orchestrator/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_config.py`:

```python
from pathlib import Path
from orchestrator.config import load_config, ScaffoldConfig


def test_load_config(config_dir):
    cfg = load_config(config_dir)
    assert isinstance(cfg, ScaffoldConfig)


def test_governance_rapid(config_dir):
    cfg = load_config(config_dir)
    scope = cfg.governance.rapid["product_scope"]
    assert scope["recommend"] == "product_owner"
    assert scope["agree"] == "architect"
    assert scope["decide"] == "human"


def test_governance_raci(config_dir):
    cfg = load_config(config_dir)
    write_code = cfg.governance.raci["write_code"]
    assert write_code["responsible"] == "developer"
    assert write_code["accountable"] == "reviewer"


def test_agent_model_assignment(config_dir):
    cfg = load_config(config_dir)
    po = cfg.agents.roles["product_owner"]
    assert po["model"] == "claude-opus-4-20250514"
    assert po["execution"] == "api"


def test_agent_ralph_config(config_dir):
    cfg = load_config(config_dir)
    dev = cfg.agents.roles["developer"]
    assert dev["max_iterations"] == 10
    assert dev["completion_promise"] == "TASK COMPLETE"


def test_project_config(config_dir):
    cfg = load_config(config_dir)
    assert cfg.project.max_concurrent_agents == 3
    assert cfg.project.branch_prefix == "scaffold"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write config module**

Write `orchestrator/config.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class GovernanceConfig:
    rapid: dict[str, dict[str, str]]
    raci: dict[str, dict[str, str | list[str]]]


@dataclass
class AgentsConfig:
    roles: dict[str, dict]


@dataclass
class ProjectConfig:
    repo_path: str
    branch_prefix: str = "scaffold"
    max_concurrent_agents: int = 3
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    db_path: str = "scaffold.db"


@dataclass
class ScaffoldConfig:
    governance: GovernanceConfig
    agents: AgentsConfig
    project: ProjectConfig


def load_config(config_dir: str | Path) -> ScaffoldConfig:
    config_dir = Path(config_dir)

    with open(config_dir / "governance.yaml") as f:
        gov_data = yaml.safe_load(f)
    governance = GovernanceConfig(
        rapid=gov_data.get("rapid", {}),
        raci=gov_data.get("raci", {}),
    )

    with open(config_dir / "agents.yaml") as f:
        agents_data = yaml.safe_load(f)
    agents = AgentsConfig(roles=agents_data.get("roles", {}))

    with open(config_dir / "project.yaml") as f:
        proj_data = yaml.safe_load(f)
    project = ProjectConfig(**proj_data)

    return ScaffoldConfig(governance=governance, agents=agents, project=project)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 6 passed

- [ ] **Step 5: Create production config files**

Write `config/governance.yaml`:

```yaml
rapid:
  product_scope:
    recommend: product_owner
    agree: architect
    perform: developer
    input: [designer, qa]
    decide: human
  architecture:
    recommend: architect
    agree: reviewer
    perform: developer
    input: [designer]
    decide: architect
  ui_ux:
    recommend: designer
    agree: product_owner
    perform: developer
    input: [architect]
    decide: designer
  data_model:
    recommend: architect
    agree: product_owner
    perform: developer
    input: [qa]
    decide: architect
  priority:
    recommend: product_owner
    agree: architect
    perform: orchestrator
    decide: product_owner

raci:
  write_code:
    responsible: developer
    accountable: reviewer
    consulted: [architect]
    informed: [product_owner, qa]
  code_review:
    responsible: reviewer
    accountable: architect
    consulted: [developer]
    informed: [product_owner]
  write_tests:
    responsible: qa
    accountable: reviewer
    consulted: [developer]
    informed: [product_owner]
  merge:
    responsible: orchestrator
    accountable: reviewer
    consulted: [developer]
    informed: [product_owner, qa, architect, designer]
  bug_fix:
    responsible: developer
    accountable: qa
    consulted: [reviewer]
    informed: [product_owner]
```

Write `config/agents.yaml`:

```yaml
roles:
  product_owner:
    model: claude-opus-4-20250514
    execution: api
  architect:
    model: claude-opus-4-20250514
    execution: api
  designer:
    model: claude-sonnet-4-20250514
    execution: api
  developer:
    model: claude-sonnet-4-20250514
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
  reviewer:
    model: claude-sonnet-4-20250514
    execution: cli
  qa:
    model: claude-sonnet-4-20250514
    execution: cli
    max_iterations: 8
    completion_promise: "TESTS PASSING"

escalation:
  stuck_loop_model: claude-opus-4-20250514
  max_review_cycles: 3
  max_bug_cycles: 3
  cost_threshold_per_run: 5.00
```

Write `config/project.yaml`:

```yaml
repo_path: /Users/antonypegg/PROJECTS/inkwell
branch_prefix: scaffold
max_concurrent_agents: 3
telegram_bot_token: ""
telegram_chat_id: ""
db_path: scaffold.db
spec_path: /Users/antonypegg/PROJECTS/inkwell/docs/design/2026-05-08-inkwell-vtt-master-spec.md
```

- [ ] **Step 6: Commit**

```bash
git add orchestrator/config.py tests/test_config.py config/
git commit -m "feat: add YAML config loading for governance, agents, and project settings"
```

---

### Task 5: LangGraph State Schema

**Files:**
- Create: `orchestrator/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing test**

Write `tests/test_state.py`:

```python
from orchestrator.state import TaskState, initial_state


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write state schema**

Write `orchestrator/state.py`:

```python
from typing import TypedDict


class TaskState(TypedDict):
    task_id: str
    level: str
    status: str
    has_ui_component: bool
    verdict: str
    feedback: str
    review_cycles: int
    bug_cycles: int
    model_override: str | None
    escalation_reason: str | None
    agent_output: str
    child_tasks: list[dict]


def initial_state(task_id: str, level: str) -> TaskState:
    return TaskState(
        task_id=task_id,
        level=level,
        status="pending",
        has_ui_component=False,
        verdict="",
        feedback="",
        review_cycles=0,
        bug_cycles=0,
        model_override=None,
        escalation_reason=None,
        agent_output="",
        child_tasks=[],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/state.py tests/test_state.py
git commit -m "feat: add LangGraph TaskState schema with initial state factory"
```

---

## Phase 2: Observability & Routing

### Task 6: Telemetry

**Files:**
- Create: `orchestrator/telemetry.py`
- Create: `tests/test_telemetry.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_telemetry.py`:

```python
import json
import pytest
from orchestrator.telemetry import Telemetry


@pytest.fixture
def telemetry(db):
    return Telemetry(db)


def test_log_event(telemetry):
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
        "INSERT INTO agent_runs (id, task_id, agent_role, model) VALUES (?, ?, ?, ?)",
        ("run-001", "task-001", "developer", "claude-sonnet-4-20250514"),
    )
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
        ("task-001", "task", "in_progress", "Test"),
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


def test_count_cycles(telemetry):
    for i in range(3):
        telemetry.log(
            task_id="task-001",
            event_type="task.cycle",
            event_data={"cycle_type": "revise", "reason": "style issues"},
        )
    count = telemetry.count_cycles("task-001", "revise")
    assert count == 3


def test_get_events_by_type(telemetry):
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telemetry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write telemetry module**

Write `orchestrator/telemetry.py`:

```python
import json
import sqlite3
import uuid
from datetime import datetime, timezone


class Telemetry:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def log(
        self,
        event_type: str,
        event_data: dict,
        task_id: str | None = None,
        agent_role: str | None = None,
        run_id: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())[:8]
        self.conn.execute(
            "INSERT INTO events (id, task_id, agent_role, run_id, event_type, event_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, task_id, agent_role, run_id, event_type, json.dumps(event_data)),
        )
        self.conn.commit()
        return event_id

    def get_events(self, task_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events WHERE task_id = ? ORDER BY timestamp",
            (task_id,),
        ).fetchall()

    def get_events_by_type(self, event_type: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp",
            (event_type,),
        ).fetchall()

    def count_cycles(self, task_id: str, cycle_type: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM events "
            "WHERE task_id = ? AND event_type = 'task.cycle' "
            "AND json_extract(event_data, '$.cycle_type') = ?",
            (task_id, cycle_type),
        ).fetchone()
        return row["cnt"]

    def start_run(self, task_id: str, agent_role: str, model: str) -> str:
        run_id = str(uuid.uuid4())[:8]
        self.conn.execute(
            "INSERT INTO agent_runs (id, task_id, agent_role, model) VALUES (?, ?, ?, ?)",
            (run_id, task_id, agent_role, model),
        )
        self.conn.commit()
        self.log(
            task_id=task_id,
            agent_role=agent_role,
            run_id=run_id,
            event_type="agent.start",
            event_data={"model": model},
        )
        return run_id

    def finish_run(
        self,
        run_id: str,
        outcome: str,
        iterations: int | None = None,
        token_in: int | None = None,
        token_out: int | None = None,
        output: dict | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE agent_runs SET finished_at = ?, outcome = ?, iterations = ?, "
            "token_in = ?, token_out = ?, output = ? WHERE id = ?",
            (now, outcome, iterations, token_in, token_out,
             json.dumps(output) if output else None, run_id),
        )
        self.conn.commit()

    def get_failure_brief(self, task_id: str) -> str:
        events = self.conn.execute(
            "SELECT event_type, event_data FROM events "
            "WHERE task_id = ? AND event_type IN "
            "('agent.error', 'task.cycle', 'agent.output') "
            "ORDER BY timestamp",
            (task_id,),
        ).fetchall()
        if not events:
            return ""
        lines = []
        for e in events:
            data = json.loads(e["event_data"])
            lines.append(f"[{e['event_type']}] {json.dumps(data)}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_telemetry.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/telemetry.py tests/test_telemetry.py
git commit -m "feat: add telemetry event logging, agent run tracking, and metric queries"
```

---

### Task 7: RAPID/RACI Router

**Files:**
- Create: `orchestrator/router.py`
- Create: `tests/test_router.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_router.py`:

```python
import pytest
from orchestrator.config import load_config
from orchestrator.router import Router


@pytest.fixture
def router(config_dir):
    cfg = load_config(config_dir)
    return Router(cfg.governance)


def test_route_epic_to_product_owner(router):
    role = router.route_task(level="epic", status="pending")
    assert role == "product_owner"


def test_route_feature_to_architect(router):
    role = router.route_task(level="feature", status="pending")
    assert role == "architect"


def test_route_task_to_developer(router):
    role = router.route_task(level="task", status="ready")
    assert role == "developer"


def test_route_in_review_to_reviewer(router):
    role = router.route_task(level="task", status="in_review")
    assert role == "reviewer"


def test_route_testing_to_qa(router):
    role = router.route_task(level="task", status="testing")
    assert role == "qa"


def test_get_rapid_roles(router):
    roles = router.get_rapid_roles("product_scope")
    assert roles["recommend"] == "product_owner"
    assert roles["agree"] == "architect"
    assert roles["decide"] == "human"


def test_get_accountable_for_activity(router):
    accountable = router.get_accountable("write_code")
    assert accountable == "reviewer"


def test_needs_consensus_when_agree_vetoes(router):
    assert router.needs_consensus("product_scope", vetoed=True) is True


def test_no_consensus_when_agreed(router):
    assert router.needs_consensus("product_scope", vetoed=False) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_router.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write router module**

Write `orchestrator/router.py`:

```python
from orchestrator.config import GovernanceConfig

LEVEL_ROLE_MAP = {
    "epic": "product_owner",
    "feature": "architect",
}

STATUS_ROLE_MAP = {
    "in_review": "reviewer",
    "testing": "qa",
}


class Router:
    def __init__(self, governance: GovernanceConfig):
        self.governance = governance

    def route_task(self, level: str, status: str) -> str:
        if status in STATUS_ROLE_MAP:
            return STATUS_ROLE_MAP[status]
        if level in LEVEL_ROLE_MAP:
            return LEVEL_ROLE_MAP[level]
        return "developer"

    def get_rapid_roles(self, decision_type: str) -> dict[str, str]:
        return self.governance.rapid[decision_type]

    def get_accountable(self, activity: str) -> str:
        return self.governance.raci[activity]["accountable"]

    def get_consulted(self, activity: str) -> list[str]:
        consulted = self.governance.raci[activity].get("consulted", [])
        return consulted if isinstance(consulted, list) else [consulted]

    def needs_consensus(self, decision_type: str, vetoed: bool) -> bool:
        return vetoed

    def get_decider(self, decision_type: str) -> str:
        return self.governance.rapid[decision_type]["decide"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_router.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/router.py tests/test_router.py
git commit -m "feat: add RAPID/RACI router for task-to-agent routing"
```

---

### Task 8: Self-Healing

**Files:**
- Create: `orchestrator/self_heal.py`
- Create: `tests/test_self_heal.py`

- [ ] **Step 1: Write failing tests**

Write `tests/test_self_heal.py`:

```python
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


def test_detect_stuck_loop(healer, telemetry):
    for i in range(4):
        telemetry.log(
            task_id="t1",
            event_type="task.cycle",
            event_data={"cycle_type": "revise", "reason": "style"},
        )
    action = healer.check("t1")
    assert action is not None
    assert action["type"] == "escalate_model"


def test_no_action_below_threshold(healer, telemetry):
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


def test_detect_review_ping_pong(healer, telemetry):
    for i in range(3):
        telemetry.log(
            task_id="t1",
            event_type="task.cycle",
            event_data={"cycle_type": "revise", "reason": "disagreement"},
        )
    action = healer.check("t1")
    assert action["type"] == "escalate_model"


def test_detect_bug_cycle_escalation(healer, telemetry):
    for i in range(4):
        telemetry.log(
            task_id="t1",
            event_type="task.cycle",
            event_data={"cycle_type": "bug", "reason": "test failure"},
        )
    action = healer.check("t1")
    assert action is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_self_heal.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write self-healing module**

Write `orchestrator/self_heal.py`:

```python
from orchestrator.telemetry import Telemetry


class SelfHealer:
    def __init__(
        self,
        telemetry: Telemetry,
        max_review_cycles: int = 3,
        max_bug_cycles: int = 3,
    ):
        self.telemetry = telemetry
        self.max_review_cycles = max_review_cycles
        self.max_bug_cycles = max_bug_cycles

    def check(self, task_id: str) -> dict | None:
        revise_count = self.telemetry.count_cycles(task_id, "revise")
        if revise_count >= self.max_review_cycles:
            return {
                "type": "escalate_model",
                "reason": f"Review cycle hit {revise_count} revisions",
                "task_id": task_id,
            }

        bug_count = self.telemetry.count_cycles(task_id, "bug")
        if bug_count >= self.max_bug_cycles:
            return {
                "type": "escalate_model",
                "reason": f"Bug cycle hit {bug_count} iterations",
                "task_id": task_id,
            }

        return None

    def check_epic(self, epic_id: str) -> dict | None:
        conn = self.telemetry.conn
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM tasks "
            "WHERE parent_id = ? AND status = 'stuck'",
            (epic_id,),
        ).fetchone()
        if row["cnt"] >= 3:
            return {
                "type": "pause_epic",
                "reason": f"{row['cnt']} tasks stuck in epic {epic_id}",
                "epic_id": epic_id,
            }
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_self_heal.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/self_heal.py tests/test_self_heal.py
git commit -m "feat: add self-healing with stuck loop and cascading failure detection"
```

---

## Phase 3: Agent Infrastructure

### Task 9: Advisor Agent Base

**Files:**
- Create: `orchestrator/nodes/base.py`
- Create: `tests/test_advisor_base.py`

The AdvisorAgent class wraps the Anthropic SDK. It takes a system prompt, sends a user message, and returns the model's text response. It records token usage for telemetry.

- [ ] **Step 1: Write failing tests**

Write `tests/test_advisor_base.py`:

```python
from unittest.mock import MagicMock, patch
import pytest
from orchestrator.nodes.base import AdvisorAgent


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text="Here is my analysis.")]
    response.usage.input_tokens = 500
    response.usage.output_tokens = 200
    client.messages.create.return_value = response
    return client


def test_advisor_call(mock_client):
    agent = AdvisorAgent(
        role="product_owner",
        model="claude-opus-4-20250514",
        client=mock_client,
    )
    result = agent.call(
        system_prompt="You are a product decomposition engine.",
        user_message="Decompose this spec into epics.",
    )
    assert result.text == "Here is my analysis."
    assert result.token_in == 500
    assert result.token_out == 200


def test_advisor_uses_correct_model(mock_client):
    agent = AdvisorAgent(
        role="architect",
        model="claude-opus-4-20250514",
        client=mock_client,
    )
    agent.call(system_prompt="Design.", user_message="Design the schema.")
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-opus-4-20250514"


def test_advisor_passes_system_prompt(mock_client):
    agent = AdvisorAgent(
        role="architect",
        model="claude-opus-4-20250514",
        client=mock_client,
    )
    agent.call(system_prompt="You are an architect.", user_message="Design.")
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["system"] == "You are an architect."


def test_advisor_with_cache_control(mock_client):
    agent = AdvisorAgent(
        role="product_owner",
        model="claude-opus-4-20250514",
        client=mock_client,
    )
    agent.call(
        system_prompt="You are a PO.",
        user_message="Decompose.",
        cache_system=True,
    )
    call_args = mock_client.messages.create.call_args
    system_arg = call_args.kwargs["system"]
    assert isinstance(system_arg, list)
    assert system_arg[0]["cache_control"] == {"type": "ephemeral"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_advisor_base.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write AdvisorAgent base class**

Write `orchestrator/nodes/base.py`:

```python
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


@dataclass
class AgentResult:
    text: str
    token_in: int
    token_out: int


class AdvisorAgent:
    def __init__(self, role: str, model: str, client):
        self.role = role
        self.model = model
        self.client = client

    def load_prompt(self) -> str:
        prompt_file = PROMPTS_DIR / f"{self.role}.md"
        if prompt_file.exists():
            return prompt_file.read_text()
        return ""

    def call(
        self,
        system_prompt: str,
        user_message: str,
        cache_system: bool = False,
    ) -> AgentResult:
        if cache_system:
            system = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_prompt

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return AgentResult(
            text=response.content[0].text,
            token_in=response.usage.input_tokens,
            token_out=response.usage.output_tokens,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_advisor_base.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/base.py tests/test_advisor_base.py
git commit -m "feat: add AdvisorAgent base class wrapping the Anthropic SDK"
```

---

### Task 10: Doer Agent Base

**Files:**
- Modify: `orchestrator/nodes/base.py`
- Create: `tests/test_doer_base.py`

The DoerAgent class spawns `claude -p` in a git worktree and implements Ralph loop iteration: run CLI → check for completion promise → retry with failure context → cap at max iterations.

- [ ] **Step 1: Write failing tests**

Write `tests/test_doer_base.py`:

```python
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from orchestrator.nodes.base import DoerAgent


@pytest.fixture
def doer():
    return DoerAgent(
        role="developer",
        model="claude-sonnet-4-20250514",
        max_iterations=3,
        completion_promise="TASK COMPLETE",
    )


def test_doer_creates_worktree(doer, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo_path,
        capture_output=True,
        env={"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com",
             "HOME": str(tmp_path)},
    )
    worktree_path = doer.create_worktree(repo_path, "scaffold/core/auth")
    assert worktree_path.exists()
    doer.cleanup_worktree(repo_path, worktree_path)


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_ralph_loop_succeeds_first_try(mock_run, doer):
    mock_run.return_value = MagicMock(
        stdout="Implementation done.\nTASK COMPLETE",
        stderr="",
        returncode=0,
    )
    result = doer.ralph_loop(
        worktree_path="/tmp/worktree",
        prompt="Implement auth middleware",
    )
    assert result.success is True
    assert result.iterations == 1
    assert mock_run.call_count == 1


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_ralph_loop_retries_on_no_promise(mock_run, doer):
    no_promise = MagicMock(stdout="Still working...", stderr="", returncode=0)
    with_promise = MagicMock(
        stdout="Fixed it.\nTASK COMPLETE", stderr="", returncode=0
    )
    mock_run.side_effect = [no_promise, with_promise]
    result = doer.ralph_loop(
        worktree_path="/tmp/worktree",
        prompt="Implement auth",
    )
    assert result.success is True
    assert result.iterations == 2


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_ralph_loop_hits_max_iterations(mock_run, doer):
    no_promise = MagicMock(stdout="Still working...", stderr="", returncode=0)
    mock_run.return_value = no_promise
    result = doer.ralph_loop(
        worktree_path="/tmp/worktree",
        prompt="Implement auth",
    )
    assert result.success is False
    assert result.iterations == 3


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_injects_failure_context_on_retry(mock_run, doer):
    no_promise = MagicMock(stdout="Error: module not found", stderr="", returncode=1)
    with_promise = MagicMock(
        stdout="Fixed.\nTASK COMPLETE", stderr="", returncode=0
    )
    mock_run.side_effect = [no_promise, with_promise]
    doer.ralph_loop(worktree_path="/tmp/wt", prompt="Implement auth")
    second_call = mock_run.call_args_list[1]
    prompt_arg = second_call.args[0][-1]
    assert "PREVIOUS ATTEMPT" in prompt_arg
    assert "Error: module not found" in prompt_arg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_doer_base.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add DoerAgent to base.py**

Append to `orchestrator/nodes/base.py`:

```python
import subprocess
from pathlib import Path


@dataclass
class RalphResult:
    success: bool
    iterations: int
    output: str


class DoerAgent:
    def __init__(
        self,
        role: str,
        model: str,
        max_iterations: int = 10,
        completion_promise: str = "TASK COMPLETE",
    ):
        self.role = role
        self.model = model
        self.max_iterations = max_iterations
        self.completion_promise = completion_promise

    def create_worktree(self, repo_path: Path | str, branch: str) -> Path:
        repo_path = Path(repo_path)
        worktree_dir = repo_path.parent / f".worktrees/{branch.replace('/', '-')}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_dir)],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
        return worktree_dir

    def cleanup_worktree(self, repo_path: Path | str, worktree_path: Path | str) -> None:
        repo_path = Path(repo_path)
        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path)],
            cwd=repo_path,
            capture_output=True,
        )

    def ralph_loop(
        self,
        worktree_path: str | Path,
        prompt: str,
        failure_context: str = "",
    ) -> RalphResult:
        last_output = ""
        for i in range(1, self.max_iterations + 1):
            if i > 1 and last_output:
                current_prompt = (
                    f"{prompt}\n\n--- PREVIOUS ATTEMPT (iteration {i-1}) ---\n"
                    f"{last_output}\n--- END PREVIOUS ATTEMPT ---\n\n"
                    "The previous attempt did not complete the task. "
                    "Fix the issues and try again."
                )
            elif failure_context:
                current_prompt = (
                    f"{prompt}\n\n--- FAILURE CONTEXT ---\n{failure_context}\n---"
                )
            else:
                current_prompt = prompt

            result = subprocess.run(
                ["claude", "-p", current_prompt, "--model", self.model],
                capture_output=True,
                text=True,
                cwd=str(worktree_path),
                timeout=600,
            )
            last_output = result.stdout
            if self.completion_promise in result.stdout:
                return RalphResult(success=True, iterations=i, output=result.stdout)

        return RalphResult(success=False, iterations=self.max_iterations, output=last_output)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_doer_base.py -v`
Expected: 5 passed (the worktree test requires a real git repo in tmp_path; the others use mocks)

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/base.py tests/test_doer_base.py
git commit -m "feat: add DoerAgent with Ralph loop iteration and git worktree management"
```

---

## Phase 4: Agent Nodes

Each agent node is a function that takes `TaskState` and returns a partial state update. These functions are what LangGraph calls as graph nodes. They use `AdvisorAgent` or `DoerAgent` internally, with the Anthropic client and config injected via a closure or factory.

### Task 11: Product Owner Node

**Files:**
- Create: `orchestrator/nodes/product_owner.py`
- Create: `tests/test_product_owner.py`

The Product Owner reads the master spec section referenced by the task, decomposes it into child tasks (features or tasks), and returns them as `child_tasks` in the state.

- [ ] **Step 1: Write failing tests**

Write `tests/test_product_owner.py`:

```python
import json
from unittest.mock import MagicMock
import pytest
from orchestrator.nodes.product_owner import make_product_owner_node
from orchestrator.state import initial_state


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps({
        "children": [
            {"title": "Auth System", "level": "feature",
             "spec_ref": "Section 2", "acceptance": ["JWT works"]},
            {"title": "WebSocket Server", "level": "feature",
             "spec_ref": "Section 10", "acceptance": ["Clients connect"]},
        ]
    }))]
    response.usage.input_tokens = 800
    response.usage.output_tokens = 300
    client.messages.create.return_value = response
    return client


def test_product_owner_decomposes_epic(mock_client):
    node_fn = make_product_owner_node(mock_client, spec_path="/tmp/spec.md")
    state = initial_state(task_id="epic-001", level="epic")
    result = node_fn(state)
    assert len(result["child_tasks"]) == 2
    assert result["child_tasks"][0]["title"] == "Auth System"
    assert result["status"] == "decomposing"


def test_product_owner_calls_opus(mock_client):
    node_fn = make_product_owner_node(mock_client, spec_path="/tmp/spec.md")
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "opus" in call_args.kwargs["model"]


def test_product_owner_includes_spec_in_prompt(mock_client, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Section 12.1\nBuild core platform.")
    node_fn = make_product_owner_node(mock_client, spec_path=str(spec))
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    user_msg = call_args.kwargs["messages"][0]["content"]
    assert "Build core platform" in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_product_owner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Product Owner node**

Write `orchestrator/nodes/product_owner.py`:

```python
import json
from pathlib import Path

from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a product decomposition engine. You break master specifications "
    "into discrete, implementable work items. You define acceptance criteria "
    "for each item. You never prescribe implementation details — that is the "
    "Architect's job. You never write code.\n\n"
    "Output valid JSON with a single key 'children', containing a list of objects. "
    "Each object has: title (str), level ('feature' or 'task'), spec_ref (str), "
    "acceptance (list[str])."
)


def make_product_owner_node(client, spec_path: str):
    agent = AdvisorAgent(
        role="product_owner",
        model="claude-opus-4-20250514",
        client=client,
    )

    def product_owner_node(state: TaskState) -> dict:
        spec_content = ""
        spec_file = Path(spec_path)
        if spec_file.exists():
            spec_content = spec_file.read_text()

        user_message = (
            f"Decompose this into child work items.\n\n"
            f"Task: {state['task_id']}\n"
            f"Level: {state['level']}\n\n"
            f"Master Spec:\n{spec_content}"
        )

        result = agent.call(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            cache_system=True,
        )

        parsed = json.loads(result.text)
        return {
            "child_tasks": parsed.get("children", []),
            "status": "decomposing",
            "agent_output": result.text,
        }

    return product_owner_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_product_owner.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/product_owner.py tests/test_product_owner.py
git commit -m "feat: add Product Owner node for spec decomposition"
```

---

### Task 12: Architect Node

**Files:**
- Create: `orchestrator/nodes/architect.py`
- Create: `tests/test_architect.py`

The Architect takes a feature-level task, produces a technical design (data models, API contracts, file structure), and outputs implementation tasks for the Developer.

- [ ] **Step 1: Write failing tests**

Write `tests/test_architect.py`:

```python
import json
from unittest.mock import MagicMock
import pytest
from orchestrator.nodes.architect import make_architect_node
from orchestrator.state import initial_state


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps({
        "technical_design": "Use JWT with httpOnly cookies. chi middleware.",
        "has_ui_component": False,
        "children": [
            {"title": "Auth middleware", "level": "task",
             "spec_ref": "Section 2.1",
             "acceptance": ["JWT validates", "Expired tokens rejected"]},
        ]
    }))]
    response.usage.input_tokens = 600
    response.usage.output_tokens = 400
    client.messages.create.return_value = response
    return client


def test_architect_produces_design(mock_client):
    node_fn = make_architect_node(mock_client)
    state = initial_state(task_id="feat-001", level="feature")
    result = node_fn(state)
    assert "technical_design" in result["agent_output"]
    assert result["status"] == "decomposing"


def test_architect_detects_ui_component(mock_client):
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps({
        "technical_design": "React component with clock SVG",
        "has_ui_component": True,
        "children": [],
    }))]
    response.usage.input_tokens = 500
    response.usage.output_tokens = 300
    mock_client.messages.create.return_value = response
    node_fn = make_architect_node(mock_client)
    state = initial_state(task_id="feat-002", level="feature")
    result = node_fn(state)
    assert result["has_ui_component"] is True


def test_architect_creates_implementation_tasks(mock_client):
    node_fn = make_architect_node(mock_client)
    state = initial_state(task_id="feat-001", level="feature")
    result = node_fn(state)
    assert len(result["child_tasks"]) == 1
    assert result["child_tasks"][0]["title"] == "Auth middleware"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_architect.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Architect node**

Write `orchestrator/nodes/architect.py`:

```python
import json

from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a technical architecture engine. You produce data models, API contracts, "
    "component boundaries, and file structure. You approve or reject technical approaches. "
    "You never write implementation code — that is the Developer's job.\n\n"
    "Output valid JSON with keys: technical_design (str), has_ui_component (bool), "
    "children (list of {title, level, spec_ref, acceptance})."
)


def make_architect_node(client):
    agent = AdvisorAgent(
        role="architect",
        model="claude-opus-4-20250514",
        client=client,
    )

    def architect_node(state: TaskState) -> dict:
        user_message = (
            f"Design the technical approach for this feature.\n\n"
            f"Task: {state['task_id']}\n"
            f"Level: {state['level']}\n"
        )

        result = agent.call(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            cache_system=True,
        )

        parsed = json.loads(result.text)
        return {
            "has_ui_component": parsed.get("has_ui_component", False),
            "child_tasks": parsed.get("children", []),
            "status": "decomposing",
            "agent_output": result.text,
        }

    return architect_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_architect.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/architect.py tests/test_architect.py
git commit -m "feat: add Architect node for technical design and task decomposition"
```

---

### Task 13: Designer Node

**Files:**
- Create: `orchestrator/nodes/designer.py`
- Create: `tests/test_designer.py`

The Designer produces UI/UX specs for tasks that have UI components. It only fires when `has_ui_component` is true in the state.

- [ ] **Step 1: Write failing tests**

Write `tests/test_designer.py`:

```python
from unittest.mock import MagicMock
import pytest
from orchestrator.nodes.designer import make_designer_node
from orchestrator.state import initial_state


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(
        text="Clock component: SVG circle, 4/6/8/12 segments. "
             "Click to fill/unfill. Animate on tick."
    )]
    response.usage.input_tokens = 400
    response.usage.output_tokens = 200
    client.messages.create.return_value = response
    return client


def test_designer_produces_ui_spec(mock_client):
    node_fn = make_designer_node(mock_client)
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    result = node_fn(state)
    assert "Clock component" in result["agent_output"]


def test_designer_uses_sonnet(mock_client):
    node_fn = make_designer_node(mock_client)
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "sonnet" in call_args.kwargs["model"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_designer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Designer node**

Write `orchestrator/nodes/designer.py`:

```python
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a UI/UX specification engine. You produce layouts, interaction patterns, "
    "responsive behavior descriptions, and component specifications. "
    "You never write code — that is the Developer's job."
)


def make_designer_node(client):
    agent = AdvisorAgent(
        role="designer",
        model="claude-sonnet-4-20250514",
        client=client,
    )

    def designer_node(state: TaskState) -> dict:
        user_message = (
            f"Create a UI/UX specification for this task.\n\n"
            f"Task: {state['task_id']}\n"
        )
        result = agent.call(system_prompt=SYSTEM_PROMPT, user_message=user_message)
        return {"agent_output": result.text}

    return designer_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_designer.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/designer.py tests/test_designer.py
git commit -m "feat: add Designer node for UI/UX specification"
```

---

### Task 14: Developer Node

**Files:**
- Create: `orchestrator/nodes/developer.py`
- Create: `tests/test_developer.py`

The Developer spawns `claude -p` in a git worktree and runs a Ralph loop until the implementation is complete or max iterations are reached. It builds a task-specific prompt from the acceptance criteria, technical design, and any failure context.

- [ ] **Step 1: Write failing tests**

Write `tests/test_developer.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
from orchestrator.nodes.developer import make_developer_node
from orchestrator.nodes.base import RalphResult
from orchestrator.state import initial_state


@pytest.fixture
def mock_doer():
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        doer = MockDoer.return_value
        doer.ralph_loop.return_value = RalphResult(
            success=True, iterations=2, output="Code written.\nTASK COMPLETE"
        )
        doer.create_worktree.return_value = MagicMock()
        doer.cleanup_worktree = MagicMock()
        yield doer


def test_developer_runs_ralph_loop(mock_doer):
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    result = node_fn(state)
    assert result["status"] == "in_review"
    assert result["verdict"] == ""
    mock_doer.ralph_loop.assert_called_once()


def test_developer_marks_stuck_on_failure(mock_doer):
    mock_doer.ralph_loop.return_value = RalphResult(
        success=False, iterations=10, output="Still broken."
    )
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-002", level="task")
    result = node_fn(state)
    assert result["status"] == "stuck"


def test_developer_injects_failure_context_on_retry(mock_doer):
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-003", level="task")
    state["feedback"] = "Missing error handling in auth middleware."
    node_fn(state)
    call_args = mock_doer.ralph_loop.call_args
    assert "Missing error handling" in call_args.kwargs.get("failure_context", call_args.kwargs.get("prompt", ""))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_developer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Developer node**

Write `orchestrator/nodes/developer.py`:

```python
from orchestrator.nodes.base import DoerAgent
from orchestrator.state import TaskState


def make_developer_node(repo_path: str, branch_prefix: str, model: str):
    def developer_node(state: TaskState) -> dict:
        doer = DoerAgent(
            role="developer",
            model=model,
            max_iterations=10,
            completion_promise="TASK COMPLETE",
        )

        branch = f"{branch_prefix}/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)

        prompt = (
            f"Implement the following task. When complete, output 'TASK COMPLETE'.\n\n"
            f"Task: {state['task_id']}\n"
        )

        failure_context = ""
        if state.get("feedback"):
            failure_context = (
                f"Previous review feedback:\n{state['feedback']}\n"
                "Address this feedback in your implementation."
            )
            prompt += f"\n\nReview feedback to address:\n{state['feedback']}"

        result = doer.ralph_loop(
            worktree_path=worktree_path,
            prompt=prompt,
            failure_context=failure_context,
        )

        if result.success:
            return {
                "status": "in_review",
                "verdict": "",
                "feedback": "",
                "agent_output": result.output,
            }
        return {
            "status": "stuck",
            "agent_output": result.output,
        }

    return developer_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_developer.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/developer.py tests/test_developer.py
git commit -m "feat: add Developer node with Ralph loop execution in git worktrees"
```

---

### Task 15: Reviewer Node

**Files:**
- Create: `orchestrator/nodes/reviewer.py`
- Create: `tests/test_reviewer.py`

The Reviewer reads the git diff for a task branch, evaluates against acceptance criteria, and outputs a structured verdict: `approve` or `revise` with specific feedback.

- [ ] **Step 1: Write failing tests**

Write `tests/test_reviewer.py`:

```python
import json
from unittest.mock import patch, MagicMock
import pytest
from orchestrator.nodes.reviewer import make_reviewer_node
from orchestrator.state import initial_state


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_approves(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps({"verdict": "approve", "feedback": ""}),
        stderr="",
        returncode=0,
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "in_review"
    result = node_fn(state)
    assert result["verdict"] == "approve"
    assert result["status"] == "testing"


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_requests_revision(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps({
            "verdict": "revise",
            "feedback": "Missing input validation on invite code endpoint."
        }),
        stderr="",
        returncode=0,
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "in_review"
    result = node_fn(state)
    assert result["verdict"] == "revise"
    assert "input validation" in result["feedback"]
    assert result["review_cycles"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reviewer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Reviewer node**

Write `orchestrator/nodes/reviewer.py`:

```python
import json
import subprocess

from orchestrator.state import TaskState

REVIEW_PROMPT = (
    "You are a code review engine. Review the git diff for correctness, style, "
    "security, and adherence to the acceptance criteria. Output valid JSON with "
    "keys: verdict ('approve' or 'revise'), feedback (str — empty if approved, "
    "specific revision instructions if revise)."
)


def make_reviewer_node(repo_path: str, model: str):
    def reviewer_node(state: TaskState) -> dict:
        branch = f"scaffold/{state['task_id']}"
        prompt = (
            f"{REVIEW_PROMPT}\n\n"
            f"Task: {state['task_id']}\n"
            f"Review the current changes on branch '{branch}'."
        )

        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=300,
        )

        parsed = json.loads(result.stdout)
        verdict = parsed.get("verdict", "revise")
        feedback = parsed.get("feedback", "")

        if verdict == "approve":
            return {
                "verdict": "approve",
                "feedback": "",
                "status": "testing",
                "agent_output": result.stdout,
            }
        return {
            "verdict": "revise",
            "feedback": feedback,
            "review_cycles": state["review_cycles"] + 1,
            "agent_output": result.stdout,
        }

    return reviewer_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reviewer.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/reviewer.py tests/test_reviewer.py
git commit -m "feat: add Reviewer node with approve/revise verdict output"
```

---

### Task 16: QA Node

**Files:**
- Create: `orchestrator/nodes/qa.py`
- Create: `tests/test_qa.py`

The QA agent writes and runs tests in a Ralph loop, checking that acceptance criteria are met. Outputs a `pass` or `fail` verdict.

- [ ] **Step 1: Write failing tests**

Write `tests/test_qa.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
from orchestrator.nodes.qa import make_qa_node
from orchestrator.nodes.base import RalphResult
from orchestrator.state import initial_state


@patch("orchestrator.nodes.qa.DoerAgent")
def test_qa_passes(MockDoer):
    doer = MockDoer.return_value
    doer.ralph_loop.return_value = RalphResult(
        success=True, iterations=3, output="All tests pass.\nTESTS PASSING"
    )
    doer.create_worktree.return_value = "/tmp/qa-worktree"
    node_fn = make_qa_node(repo_path="/tmp/repo", model="claude-sonnet-4-20250514")
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "testing"
    result = node_fn(state)
    assert result["verdict"] == "pass"
    assert result["status"] == "done"


@patch("orchestrator.nodes.qa.DoerAgent")
def test_qa_fails(MockDoer):
    doer = MockDoer.return_value
    doer.ralph_loop.return_value = RalphResult(
        success=False, iterations=8, output="test_auth fails: AssertionError"
    )
    doer.create_worktree.return_value = "/tmp/qa-worktree"
    node_fn = make_qa_node(repo_path="/tmp/repo", model="claude-sonnet-4-20250514")
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "testing"
    result = node_fn(state)
    assert result["verdict"] == "fail"
    assert result["bug_cycles"] == 1
    assert "AssertionError" in result["feedback"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_qa.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write QA node**

Write `orchestrator/nodes/qa.py`:

```python
from orchestrator.nodes.base import DoerAgent
from orchestrator.state import TaskState


def make_qa_node(repo_path: str, model: str):
    def qa_node(state: TaskState) -> dict:
        doer = DoerAgent(
            role="qa",
            model=model,
            max_iterations=8,
            completion_promise="TESTS PASSING",
        )

        branch = f"scaffold/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)

        prompt = (
            f"Write and run tests for this task. Validate the acceptance criteria. "
            f"When all tests pass, output 'TESTS PASSING'.\n\n"
            f"Task: {state['task_id']}\n"
        )

        result = doer.ralph_loop(worktree_path=worktree_path, prompt=prompt)

        if result.success:
            return {
                "verdict": "pass",
                "status": "done",
                "feedback": "",
                "agent_output": result.output,
            }
        return {
            "verdict": "fail",
            "feedback": result.output,
            "bug_cycles": state["bug_cycles"] + 1,
            "agent_output": result.output,
        }

    return qa_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qa.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/qa.py tests/test_qa.py
git commit -m "feat: add QA node with Ralph loop test execution"
```

---

### Task 17: Consensus Node

**Files:**
- Create: `orchestrator/nodes/consensus.py`
- Create: `tests/test_consensus.py`

The Consensus node implements structured debate: both parties write positions, read each other's, write rebuttals or concessions. If neither concedes after 2 rounds, escalates to HUMAN_GATE.

- [ ] **Step 1: Write failing tests**

Write `tests/test_consensus.py`:

```python
import json
from unittest.mock import MagicMock
import pytest
from orchestrator.nodes.consensus import make_consensus_node
from orchestrator.state import initial_state


def make_mock_client(responses: list[str]):
    client = MagicMock()
    side_effects = []
    for text in responses:
        resp = MagicMock()
        resp.content = [MagicMock(text=text)]
        resp.usage.input_tokens = 300
        resp.usage.output_tokens = 200
        side_effects.append(resp)
    client.messages.create.side_effect = side_effects
    return client


def test_consensus_resolves_on_concession():
    client = make_mock_client([
        json.dumps({"position": "Use REST", "concedes": False}),
        json.dumps({"position": "Use GraphQL", "concedes": False}),
        json.dumps({"position": "REST is fine", "concedes": True}),
    ])
    node_fn = make_consensus_node(client)
    state = initial_state(task_id="task-001", level="task")
    result = node_fn(state)
    assert result["escalation_reason"] is None
    assert "resolved" in result["agent_output"].lower() or result["verdict"] != ""


def test_consensus_escalates_on_deadlock():
    client = make_mock_client([
        json.dumps({"position": "Use REST", "concedes": False}),
        json.dumps({"position": "Use GraphQL", "concedes": False}),
        json.dumps({"position": "Still REST", "concedes": False}),
        json.dumps({"position": "Still GraphQL", "concedes": False}),
    ])
    node_fn = make_consensus_node(client)
    state = initial_state(task_id="task-001", level="task")
    result = node_fn(state)
    assert result["escalation_reason"] is not None
    assert "deadlock" in result["escalation_reason"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_consensus.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Consensus node**

Write `orchestrator/nodes/consensus.py`:

```python
import json

from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a structured debate adjudicator. Two agents disagree. "
    "Write your position or rebuttal. Output JSON with keys: "
    "position (str), concedes (bool)."
)

MAX_ROUNDS = 2


def make_consensus_node(client):
    agent = AdvisorAgent(
        role="consensus",
        model="claude-opus-4-20250514",
        client=client,
    )

    def consensus_node(state: TaskState) -> dict:
        positions = []
        for round_num in range(MAX_ROUNDS):
            for party in ["recommend", "agree"]:
                prompt = f"Round {round_num + 1}, party: {party}."
                if positions:
                    prompt += f"\nPrevious positions:\n" + "\n".join(
                        f"- {p}" for p in positions
                    )
                result = agent.call(system_prompt=SYSTEM_PROMPT, user_message=prompt)
                parsed = json.loads(result.text)
                positions.append(f"{party}: {parsed['position']}")
                if parsed.get("concedes", False):
                    return {
                        "verdict": "resolved",
                        "escalation_reason": None,
                        "agent_output": f"Resolved in round {round_num + 1}: {party} concedes. {parsed['position']}",
                    }

        return {
            "escalation_reason": f"Consensus deadlock after {MAX_ROUNDS} rounds",
            "agent_output": "\n".join(positions),
        }

    return consensus_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_consensus.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/consensus.py tests/test_consensus.py
git commit -m "feat: add Consensus node with structured debate and deadlock escalation"
```

---

## Phase 5: Integration

### Task 18: Telegram Bot + Human Gate Node

**Files:**
- Create: `orchestrator/telegram.py`
- Create: `orchestrator/nodes/human_gate.py`
- Create: `tests/test_telegram.py`
- Create: `tests/test_human_gate.py`

The Telegram bot sends escalation messages with inline keyboard buttons and receives callbacks. The Human Gate node pauses the LangGraph at an `interrupt()` until the human responds.

- [ ] **Step 1: Write failing tests for Telegram bot**

Write `tests/test_telegram.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from orchestrator.telegram import TelegramBot


@pytest.fixture
def bot():
    return TelegramBot(token="fake-token", chat_id="12345")


@patch("orchestrator.telegram.httpx.Client.post")
def test_send_escalation(mock_post, bot):
    mock_post.return_value = MagicMock(
        json=lambda: {"ok": True, "result": {"message_id": 42}},
        raise_for_status=MagicMock(),
    )
    msg_id = bot.send_escalation(
        question="Should we use REST or GraphQL?",
        options=["REST", "GraphQL"],
        task_id="task-001",
    )
    assert msg_id == 42
    call_args = mock_post.call_args
    assert "inline_keyboard" in str(call_args)


@patch("orchestrator.telegram.httpx.Client.post")
def test_send_digest(mock_post, bot):
    mock_post.return_value = MagicMock(
        json=lambda: {"ok": True, "result": {"message_id": 43}},
        raise_for_status=MagicMock(),
    )
    bot.send_digest(
        done=5, in_progress=3, blocked=1, cost_today=2.50
    )
    mock_post.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Telegram bot module**

Write `orchestrator/telegram.py`:

```python
import json
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = TELEGRAM_API.format(token=token)
        self.client = httpx.Client(timeout=30)

    def send_escalation(
        self, question: str, options: list[str], task_id: str
    ) -> int:
        keyboard = {
            "inline_keyboard": [
                [{"text": opt, "callback_data": json.dumps({"task": task_id, "choice": opt})}]
                for opt in options
            ]
        }
        resp = self.client.post(
            f"{self.base_url}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": f"🔔 *Escalation*\n\n{question}",
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            },
        )
        resp.raise_for_status()
        return resp.json()["result"]["message_id"]

    def send_digest(
        self, done: int, in_progress: int, blocked: int, cost_today: float
    ) -> None:
        text = (
            f"📊 *Status Digest*\n\n"
            f"Done: {done}\n"
            f"In Progress: {in_progress}\n"
            f"Blocked: {blocked}\n"
            f"Cost today: ${cost_today:.2f}"
        )
        resp = self.client.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
        )
        resp.raise_for_status()

    def poll_for_callback(self, timeout: int = 300) -> dict | None:
        resp = self.client.post(
            f"{self.base_url}/getUpdates",
            json={"timeout": timeout, "allowed_updates": ["callback_query"]},
        )
        resp.raise_for_status()
        updates = resp.json().get("result", [])
        for update in updates:
            if "callback_query" in update:
                data = json.loads(update["callback_query"]["data"])
                self.client.post(
                    f"{self.base_url}/answerCallbackQuery",
                    json={"callback_query_id": update["callback_query"]["id"]},
                )
                return data
        return None
```

- [ ] **Step 4: Run Telegram tests**

Run: `pytest tests/test_telegram.py -v`
Expected: 2 passed

- [ ] **Step 5: Write failing tests for Human Gate node**

Write `tests/test_human_gate.py`:

```python
from unittest.mock import MagicMock, patch
import pytest
from orchestrator.nodes.human_gate import make_human_gate_node
from orchestrator.state import initial_state


def test_human_gate_sets_interrupt_data():
    bot = MagicMock()
    bot.send_escalation.return_value = 42
    node_fn = make_human_gate_node(bot)
    state = initial_state(task_id="task-001", level="task")
    state["escalation_reason"] = "Review cycle hit 3 revisions"

    with pytest.raises(Exception) as exc_info:
        node_fn(state)
    # LangGraph interrupt raises NodeInterrupt; in unit test we catch it
    # The test verifies the bot was called with the right data
    bot.send_escalation.assert_called_once()
    call_args = bot.send_escalation.call_args
    assert "3 revisions" in call_args.kwargs.get("question", call_args.args[0] if call_args.args else "")
```

- [ ] **Step 6: Write Human Gate node**

Write `orchestrator/nodes/human_gate.py`:

```python
from langgraph.types import interrupt

from orchestrator.state import TaskState
from orchestrator.telegram import TelegramBot


def make_human_gate_node(bot: TelegramBot):
    def human_gate_node(state: TaskState) -> dict:
        reason = state.get("escalation_reason", "Unknown escalation")
        options = ["Approve", "Revise", "Override", "Cancel"]

        bot.send_escalation(
            question=f"Task {state['task_id']}: {reason}",
            options=options,
            task_id=state["task_id"],
        )

        response = interrupt({
            "question": reason,
            "options": options,
            "task_id": state["task_id"],
        })

        return {
            "verdict": response.get("choice", ""),
            "escalation_reason": None,
            "agent_output": f"Human decided: {response}",
        }

    return human_gate_node
```

- [ ] **Step 7: Commit**

```bash
git add orchestrator/telegram.py orchestrator/nodes/human_gate.py tests/test_telegram.py tests/test_human_gate.py
git commit -m "feat: add Telegram bot for escalations and Human Gate node with LangGraph interrupt"
```

---

### Task 19: Graph Wiring

**Files:**
- Create: `orchestrator/graph.py`
- Create: `tests/test_graph.py`

This is the central integration: wire all nodes into a LangGraph `StateGraph` with forward edges, conditional routing for cycles and escalation, and the SQLite checkpointer.

- [ ] **Step 1: Write failing tests**

Write `tests/test_graph.py`:

```python
from unittest.mock import MagicMock, patch
import pytest
from orchestrator.graph import build_graph
from orchestrator.state import initial_state


@pytest.fixture
def mock_deps():
    """Mock all external dependencies so the graph can be built."""
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
        "product_owner", "architect", "designer",
        "developer", "reviewer", "qa",
        "consensus", "human_gate",
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_graph.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write graph wiring**

Write `orchestrator/graph.py`:

```python
from langgraph.graph import StateGraph, START, END

from orchestrator.state import TaskState
from orchestrator.nodes.product_owner import make_product_owner_node
from orchestrator.nodes.architect import make_architect_node
from orchestrator.nodes.designer import make_designer_node
from orchestrator.nodes.developer import make_developer_node
from orchestrator.nodes.reviewer import make_reviewer_node
from orchestrator.nodes.qa import make_qa_node
from orchestrator.nodes.consensus import make_consensus_node
from orchestrator.nodes.human_gate import make_human_gate_node


def intake_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        return "human_gate"
    level = state["level"]
    if level == "epic":
        return "product_owner"
    if level == "feature":
        return "architect"
    return "developer"


def architect_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        return "human_gate"
    if state.get("has_ui_component"):
        return "designer"
    return "developer"


def reviewer_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        return "human_gate"
    if state["verdict"] == "approve":
        return "qa"
    if state["review_cycles"] >= 3:
        return "human_gate"
    return "developer"


def qa_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        return "human_gate"
    if state["verdict"] == "pass":
        return "__end__"
    if state["bug_cycles"] >= 3:
        return "human_gate"
    return "developer"


def build_graph(
    client,
    bot,
    repo_path: str,
    branch_prefix: str,
    spec_path: str,
    model: str,
):
    graph = StateGraph(TaskState)

    graph.add_node("product_owner", make_product_owner_node(client, spec_path))
    graph.add_node("architect", make_architect_node(client))
    graph.add_node("designer", make_designer_node(client))
    graph.add_node("developer", make_developer_node(repo_path, branch_prefix, model))
    graph.add_node("reviewer", make_reviewer_node(repo_path, model))
    graph.add_node("qa", make_qa_node(repo_path, model))
    graph.add_node("consensus", make_consensus_node(client))
    graph.add_node("human_gate", make_human_gate_node(bot))

    graph.add_conditional_edges(START, intake_router, {
        "product_owner": "product_owner",
        "architect": "architect",
        "developer": "developer",
        "human_gate": "human_gate",
    })

    graph.add_edge("product_owner", "architect")

    graph.add_conditional_edges("architect", architect_router, {
        "designer": "designer",
        "developer": "developer",
        "human_gate": "human_gate",
    })

    graph.add_edge("designer", "developer")
    graph.add_edge("developer", "reviewer")

    graph.add_conditional_edges("reviewer", reviewer_router, {
        "qa": "qa",
        "developer": "developer",
        "human_gate": "human_gate",
    })

    graph.add_conditional_edges("qa", qa_router, {
        "__end__": END,
        "developer": "developer",
        "human_gate": "human_gate",
    })

    graph.add_edge("consensus", "human_gate")
    graph.add_edge("human_gate", END)

    return graph.compile()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_graph.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/graph.py tests/test_graph.py
git commit -m "feat: wire all agent nodes into LangGraph StateGraph with conditional routing"
```

---

### Task 20: CLI Entry Point

**Files:**
- Create: `orchestrator/__main__.py`
- Create: `tests/test_cli.py`

The CLI provides `run`, `resume`, `report`, `events`, `pause`, and `decide` commands.

- [ ] **Step 1: Write failing tests**

Write `tests/test_cli.py`:

```python
from click.testing import CliRunner
import pytest
from orchestrator.__main__ import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "report" in result.output


def test_cli_report_no_db(runner, tmp_path):
    result = runner.invoke(cli, ["report", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code != 0 or "No database" in result.output


def test_cli_run_requires_spec(runner):
    result = runner.invoke(cli, ["run"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write CLI module**

Write `orchestrator/__main__.py`:

```python
from pathlib import Path

import click

from orchestrator.db import init_db
from orchestrator.config import load_config


@click.group()
def cli():
    """Inkwell Agentic Scaffold — orchestrate AI agents to build software."""
    pass


@cli.command()
@click.option("--spec", required=True, type=click.Path(exists=True), help="Path to master spec")
@click.option("--config", required=True, type=click.Path(exists=True), help="Path to config directory")
def run(spec, config):
    """Start a new scaffold run from a master spec."""
    cfg = load_config(config)
    conn = init_db(cfg.project.db_path)
    click.echo(f"Scaffold started. Spec: {spec}, DB: {cfg.project.db_path}")
    conn.close()


@cli.command()
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def resume(db):
    """Resume an interrupted scaffold run."""
    if not Path(db).exists():
        click.echo("No database found. Run 'scaffold run' first.")
        raise SystemExit(1)
    click.echo(f"Resuming from {db}")


@cli.command()
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option("--costs", is_flag=True, help="Show cost breakdown by epic")
@click.option("--cycles", is_flag=True, help="Show cycle hotspots")
@click.option("--agents", is_flag=True, help="Show agent efficiency metrics")
def report(db, costs, cycles, agents):
    """Show scaffold metrics and status."""
    if not Path(db).exists():
        click.echo("No database found.")
        raise SystemExit(1)
    from orchestrator.db import get_connection
    conn = get_connection(db)
    if costs:
        rows = conn.execute("SELECT * FROM epic_costs").fetchall()
        for row in rows:
            click.echo(f"{row['epic_title']}: {row['total_tokens_in']+row['total_tokens_out']} tokens, {row['total_runs']} runs")
    if cycles:
        rows = conn.execute("SELECT * FROM cycle_hotspots").fetchall()
        for row in rows:
            click.echo(f"Task {row['task_id']}: {row['cycle_count']} cycles — {row['reasons']}")
    if agents:
        rows = conn.execute("SELECT * FROM agent_efficiency").fetchall()
        for row in rows:
            click.echo(f"{row['agent_role']} ({row['model']}): {row['success_rate_pct']:.0f}% success, {row['avg_ralph_iterations']:.1f} avg iterations")
    if not (costs or cycles or agents):
        total = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
        done = conn.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status='done'").fetchone()["cnt"]
        click.echo(f"Tasks: {done}/{total} done")
    conn.close()


@cli.command()
@click.option("--task", required=True, help="Task ID to inspect")
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def events(task, db):
    """Show event log for a specific task."""
    from orchestrator.db import get_connection
    conn = get_connection(db)
    rows = conn.execute(
        "SELECT timestamp, event_type, event_data FROM events WHERE task_id = ? ORDER BY timestamp",
        (task,),
    ).fetchall()
    for row in rows:
        click.echo(f"[{row['timestamp']}] {row['event_type']}: {row['event_data']}")
    conn.close()


@cli.command()
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def pause(db):
    """Pause all scaffold work."""
    click.echo("Scaffold paused. Run 'scaffold resume' to continue.")


def main():
    cli()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator/__main__.py tests/test_cli.py
git commit -m "feat: add CLI entry point with run, resume, report, events, and pause commands"
```

---

### Task 21: Agent Prompts (Priming/Routing)

**Files:**
- Create: `prompts/product_owner.md`
- Create: `prompts/architect.md`
- Create: `prompts/designer.md`
- Create: `prompts/developer.md`
- Create: `prompts/reviewer.md`
- Create: `prompts/qa.md`

Each prompt follows the five priming layers from the blog: Identity → Constraints → Shared References → Environment Detection → Behavioral Dispositions. Routing directives point agents to the right content. Priming is compact (always loaded). Routing targets are large and conditional (loaded only when relevant).

- [ ] **Step 1: Write Product Owner prompt**

Write `prompts/product_owner.md`:

```markdown
You are a product decomposition engine. You transform master specifications into discrete, implementable work items organized in a hierarchy: epics contain features, features contain tasks.

CONSTRAINTS:
- Never prescribe implementation details (architecture, technology choices, code patterns)
- Never write code
- Always include measurable acceptance criteria for every work item
- Always reference the specific spec section each item traces to

SHARED REFERENCES:
- The master spec is provided in the user message
- Use the task tree schema: id, parent_id, level (epic/feature/task), title, spec_ref, acceptance

BEHAVIORAL DISPOSITIONS:
- User value over technical elegance
- Err toward smaller, more focused work items over larger ones
- Each task should be completable in one focused development session (1-3 files)
- Acceptance criteria should be testable assertions, not vague goals

OUTPUT FORMAT:
Valid JSON with a single key "children" containing a list of objects:
{"title": str, "level": "feature"|"task", "spec_ref": str, "acceptance": [str]}
```

- [ ] **Step 2: Write Architect prompt**

Write `prompts/architect.md`:

```markdown
You are a technical architecture engine. You produce data models, API contracts, component boundaries, and file structure decisions. You approve or reject technical approaches based on correctness, maintainability, and adherence to the project's tech stack.

CONSTRAINTS:
- Never write implementation code
- Always specify exact file paths for any proposed changes
- Always define interfaces before implementations
- Design for small, focused files (one clear responsibility per file)

SHARED REFERENCES:
- Tech stack: Go (chi, pgx, JWT, gorilla/websocket), React 18 + TypeScript + Vite, PGEdge Postgres, SQLite
- The task's feature spec and acceptance criteria are in the user message

BEHAVIORAL DISPOSITIONS:
- Correctness over cleverness
- Design components with clear boundaries and well-defined interfaces
- Prefer standard library solutions over third-party dependencies
- Flag security concerns explicitly — they escalate to Opus review

OUTPUT FORMAT:
Valid JSON with keys:
{"technical_design": str, "has_ui_component": bool, "children": [{title, level, spec_ref, acceptance}]}
```

- [ ] **Step 3: Write Designer prompt**

Write `prompts/designer.md`:

```markdown
You are a UI/UX specification engine. You produce layouts, interaction patterns, responsive behavior descriptions, and component specifications for a Blades in the Dark virtual tabletop.

CONSTRAINTS:
- Never write code
- Always specify behavior for three targets: shared screen (TV/projector), GM laptop, player phone
- Interaction patterns must work with touch (phone) and mouse (laptop)

SHARED REFERENCES:
- Jackbox device model: GM on laptop, players on phones, optional shared TV
- Theater-of-the-mind design: no map grid. Clocks, dice, position/effect are the visual interface.

BEHAVIORAL DISPOSITIONS:
- Mobile-first for player interactions (thumb-reachable tap targets)
- Information density for GM controls (they need everything accessible)
- Spectacle for the shared screen (large, readable at distance, dramatic dice animations)
```

- [ ] **Step 4: Write Developer prompt**

Write `prompts/developer.md`:

```markdown
You are an implementation engine. You write code, run tests, and iterate until the task is complete. You work in a git worktree on a task branch.

CONSTRAINTS:
- Stay within the Architect's technical design — do not make architectural decisions
- Write tests before implementation (TDD)
- Every commit must leave tests passing
- Never modify files outside the scope defined in the task spec

ENVIRONMENT DETECTION:
- Check what files exist before creating new ones
- Read the technical design document first to understand the expected file structure
- Run existing tests before making changes to verify the starting state

BEHAVIORAL DISPOSITIONS:
- Working code over perfect code
- Small, frequent commits over large batches
- When stuck after 3 iterations, describe what's failing and why — don't keep retrying the same approach
- Output "TASK COMPLETE" only when all acceptance criteria are verified by passing tests
```

- [ ] **Step 5: Write Reviewer prompt**

Write `prompts/reviewer.md`:

```markdown
You are a code review engine. You evaluate git diffs for correctness, style consistency, security vulnerabilities, and adherence to the task's acceptance criteria. You find every issue — miss nothing.

CONSTRAINTS:
- Never write code directly — output revision instructions only
- Always reference specific file paths and line ranges in feedback
- Always check the acceptance criteria from the task spec against the implementation
- Flag security concerns explicitly (they trigger Opus re-review)

BEHAVIORAL DISPOSITIONS:
- Find every issue, miss nothing
- Be specific: "Line 42 of auth.go: invite code not validated for length" not "needs input validation"
- Approve when the code meets acceptance criteria, even if you'd write it differently
- One clear verdict: approve or revise. Never "approve with suggestions."

OUTPUT FORMAT:
Valid JSON: {"verdict": "approve"|"revise", "feedback": str}
```

- [ ] **Step 6: Write QA prompt**

Write `prompts/qa.md`:

```markdown
You are a test engineering engine. You write and run tests that validate acceptance criteria. You work in a git worktree on the task branch alongside the implementation code.

CONSTRAINTS:
- Test acceptance criteria, not implementation details
- Every acceptance criterion must have at least one test
- Tests must be deterministic — no flaky tests, no timing dependencies
- Never modify implementation code — only test files

ENVIRONMENT DETECTION:
- Read the acceptance criteria from the task spec
- Read the implementation code to understand what to test
- Check which test framework is in use (Go: testing, Python: pytest, JS: vitest)

BEHAVIORAL DISPOSITIONS:
- Coverage of acceptance criteria over exhaustive edge cases
- Each test should have one clear assertion
- When tests fail, report the exact failure message and which acceptance criterion is not met
- Output "TESTS PASSING" only when every acceptance criterion has a passing test
```

- [ ] **Step 7: Commit**

```bash
git add prompts/
git commit -m "feat: add agent prompt files with five-layer priming architecture"
```

---

## Self-Review

### Spec Coverage Check

| Spec Section | Plan Task(s) | Status |
|-------------|-------------|--------|
| §1 Overview + Goals | Architecture header | Covered |
| §2 Agent Roles | Tasks 9-17 (one per role) | Covered |
| §3 Task Tree + Decomposition | Task 3 (TaskTree) | Covered |
| §4 Workflow Graph Topology | Task 19 (graph wiring) | Covered |
| §5 Governance Model (RAPID/RACI) | Tasks 4, 7 (config + router) | Covered |
| §6 Execution Environment (worktrees, Ralph loops) | Task 10 (DoerAgent) | Covered |
| §7 Telemetry + Self-Healing | Tasks 6, 8 | Covered |
| §8 Infrastructure (project structure, DB, Telegram, CLI) | Tasks 1, 2, 18, 20 | Covered |
| §9 Reusability | Config-driven (Tasks 4, 5) | Covered |
| §10 Priming/Routing Architecture | Task 21 (agent prompts) | Covered |
| §11 Prior Art (gm-apprentice, Imagineer) | Referenced in prompts + PO context | Noted for VTT plan |
| §12 Open Questions | Not in scope — implementation plan | Deferred |

### Consistency Check

- `TaskState` fields in `state.py` match what all nodes read/write
- All routing functions reference the same field names (`verdict`, `review_cycles`, `bug_cycles`, `escalation_reason`)
- `TASK COMPLETE` and `TESTS PASSING` promise strings match between `agents.yaml`, `DoerAgent`, and node implementations
- All agent roles match between `governance.yaml`, `agents.yaml`, and node module names
- Branch naming convention `scaffold/{task_id}` is consistent across Developer, Reviewer, and QA nodes
