# Budget Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-specialist --max-budget-usd passthrough and scaffold-level cumulative cost tracking with automatic abort.

**Architecture:** Two independent controls. Per-specialist budget passes `--max-budget-usd` to the claude CLI subprocess — the CLI enforces it. Scaffold-level budget tracks cumulative cost from `cli.done` events in SQLite, checked between ralph_loop iterations and between dispatcher child tasks. `BudgetExceededError` provides clean abort.

**Tech Stack:** Python 3.12, pytest, SQLite, Click CLI

---

### Task 1: BudgetExceededError exception

**Files:**
- Create: `orchestrator/budget.py`
- Test: `tests/test_budget.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_budget.py
from orchestrator.budget import BudgetExceededError


def test_budget_exceeded_error_attributes():
    err = BudgetExceededError(spent=3.47, limit=5.00)
    assert err.spent == 3.47
    assert err.limit == 5.00


def test_budget_exceeded_error_message():
    err = BudgetExceededError(spent=3.47, limit=5.00)
    assert "$3.47" in str(err)
    assert "$5.00" in str(err)


def test_budget_exceeded_error_is_exception():
    err = BudgetExceededError(spent=1.0, limit=2.0)
    assert isinstance(err, Exception)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_budget.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write the implementation**

```python
# orchestrator/budget.py
class BudgetExceededError(Exception):
    def __init__(self, spent: float, limit: float):
        self.spent = spent
        self.limit = limit
        super().__init__(f"Budget exceeded: ${spent:.2f} spent, ${limit:.2f} limit")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_budget.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add orchestrator/budget.py tests/test_budget.py
git commit -m "feat: add BudgetExceededError exception class"
```

---

### Task 2: Telemetry.cumulative_cost() method

**Files:**
- Modify: `orchestrator/telemetry.py`
- Modify: `tests/test_telemetry.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_telemetry.py`:

```python
def test_cumulative_cost_with_no_events(telemetry):
    assert telemetry.cumulative_cost() == 0.0


def test_cumulative_cost_sums_cli_done_events(telemetry, db):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
        ("task-001", "task", "in_progress", "Test"),
    )
    db.commit()
    telemetry.log(
        task_id="task-001",
        agent_role="developer",
        event_type="cli.done",
        event_data={"iteration": 1, "success": True, "cost_usd": 0.12},
    )
    telemetry.log(
        task_id="task-001",
        agent_role="developer",
        event_type="cli.done",
        event_data={"iteration": 2, "success": True, "cost_usd": 0.08},
    )
    assert telemetry.cumulative_cost() == pytest.approx(0.20)


def test_cumulative_cost_ignores_null_cost(telemetry, db):
    db.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES (?, ?, ?, ?)",
        ("task-001", "task", "in_progress", "Test"),
    )
    db.commit()
    telemetry.log(
        task_id="task-001",
        agent_role="developer",
        event_type="cli.done",
        event_data={"iteration": 1, "success": True, "cost_usd": 0.10},
    )
    telemetry.log(
        task_id="task-001",
        agent_role="developer",
        event_type="cli.done",
        event_data={"iteration": 2, "success": False},
    )
    assert telemetry.cumulative_cost() == pytest.approx(0.10)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_telemetry.py::test_cumulative_cost_with_no_events tests/test_telemetry.py::test_cumulative_cost_sums_cli_done_events tests/test_telemetry.py::test_cumulative_cost_ignores_null_cost -v`
Expected: FAIL with AttributeError

- [ ] **Step 3: Write the implementation**

Add to `orchestrator/telemetry.py`, after the `get_failure_brief` method:

```python
def cumulative_cost(self) -> float:
    row = self.conn.execute(
        "SELECT COALESCE("
        "SUM(json_extract(event_data, '$.cost_usd')), 0.0"
        ") as total FROM events WHERE event_type = 'cli.done'"
    ).fetchone()
    return float(row["total"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_telemetry.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/telemetry.py tests/test_telemetry.py
git commit -m "feat: add cumulative_cost query to Telemetry"
```

---

### Task 3: EventBus cli_done cost_usd + check_budget

**Files:**
- Modify: `orchestrator/event_bus.py`
- Modify: `tests/test_event_bus.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_event_bus.py`:

```python
from orchestrator.budget import BudgetExceededError


def test_cli_done_with_cost_usd():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.cli_done("python-expert", 1, True, "t-12", cost_usd=0.12)
    events = _get_events(conn)
    assert len(events) == 1
    data = json.loads(events[0]["event_data"])
    assert data["cost_usd"] == 0.12


def test_cli_done_without_cost_usd():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.cli_done("python-expert", 1, True, "t-13")
    events = _get_events(conn)
    data = json.loads(events[0]["event_data"])
    assert "cost_usd" not in data or data["cost_usd"] is None


def test_check_budget_passes_when_under_limit():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.cli_done("developer", 1, True, "t-14", cost_usd=0.10)
    bus.check_budget(5.00)


def test_check_budget_raises_when_over_limit():
    conn = _make_db()
    bus = EventBus(conn)
    with patch("orchestrator.event_bus.click"):
        bus.cli_done("developer", 1, True, "t-15", cost_usd=3.00)
        bus.cli_done("developer", 2, True, "t-15", cost_usd=3.00)
    with pytest.raises(BudgetExceededError) as exc_info:
        bus.check_budget(5.00)
    assert exc_info.value.spent >= 5.00
    assert exc_info.value.limit == 5.00
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_event_bus.py::test_cli_done_with_cost_usd tests/test_event_bus.py::test_check_budget_passes_when_under_limit tests/test_event_bus.py::test_check_budget_raises_when_over_limit -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

In `orchestrator/event_bus.py`, update `cli_done`:

```python
def cli_done(
    self,
    agent_role: str,
    iteration: int,
    success: bool,
    task_id: str,
    cost_usd: float | None = None,
) -> None:
    kwargs: dict[str, object] = {
        "iteration": iteration,
        "success": success,
    }
    if cost_usd is not None:
        kwargs["cost_usd"] = cost_usd
    self.emit(
        "cli.done",
        agent_role=agent_role,
        task_id=task_id,
        **kwargs,
    )
```

Add new `check_budget` method:

```python
def check_budget(self, limit: float) -> None:
    from orchestrator.budget import BudgetExceededError

    spent = self.telemetry.cumulative_cost()
    if spent >= limit:
        raise BudgetExceededError(spent, limit)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_event_bus.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: ALL PASS (existing `test_cli_events` still passes because `cost_usd` is optional)

- [ ] **Step 6: Commit**

```bash
git add orchestrator/event_bus.py tests/test_event_bus.py
git commit -m "feat: add cost_usd to cli_done events and check_budget method"
```

---

### Task 4: DoerAgent --max-budget-usd passthrough + ralph_loop budget check

**Files:**
- Modify: `orchestrator/nodes/base.py`
- Modify: `tests/test_doer_base.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_doer_base.py`:

```python
from orchestrator.budget import BudgetExceededError


def test_doer_passes_max_budget_to_cli():
    doer = DoerAgent(
        role="developer",
        model="claude-sonnet-4-6",
        max_iterations=3,
        completion_promise="TASK COMPLETE",
        max_budget_usd=2.00,
    )
    with patch("orchestrator.nodes.base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="Done.\nTASK COMPLETE", stderr="", returncode=0
        )
        doer.ralph_loop(worktree_path="/tmp/wt", prompt="Do it")
    cmd = mock_run.call_args.args[0]
    assert "--max-budget-usd" in cmd
    idx = cmd.index("--max-budget-usd")
    assert cmd[idx + 1] == "2.0"


def test_doer_omits_max_budget_when_none():
    doer = DoerAgent(
        role="developer",
        model="claude-sonnet-4-6",
        max_iterations=3,
        completion_promise="TASK COMPLETE",
    )
    with patch("orchestrator.nodes.base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="Done.\nTASK COMPLETE", stderr="", returncode=0
        )
        doer.ralph_loop(worktree_path="/tmp/wt", prompt="Do it")
    cmd = mock_run.call_args.args[0]
    assert "--max-budget-usd" not in cmd


def test_doer_passes_cost_usd_to_cli_done():
    doer = DoerAgent(
        role="developer",
        model="claude-sonnet-4-6",
        max_iterations=3,
        completion_promise="TASK COMPLETE",
    )
    mock_bus = MagicMock()
    with (
        patch("orchestrator.nodes.base.subprocess.run") as mock_run,
        patch("orchestrator.nodes.base.get_bus", return_value=mock_bus),
    ):
        mock_run.return_value = MagicMock(
            stdout=STREAM_JSON_SUCCESS, stderr="", returncode=0
        )
        doer.ralph_loop(worktree_path="/tmp/wt", prompt="Do it", task_id="t-1")
    cli_done_calls = [c for c in mock_bus.method_calls if c[0] == "cli_done"]
    assert len(cli_done_calls) == 1
    assert cli_done_calls[0].kwargs.get("cost_usd") == pytest.approx(0.05)


def test_doer_checks_scaffold_budget_between_iterations():
    doer = DoerAgent(
        role="developer",
        model="claude-sonnet-4-6",
        max_iterations=5,
        completion_promise="TASK COMPLETE",
    )
    mock_bus = MagicMock()
    call_count = 0

    def budget_side_effect(limit):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise BudgetExceededError(spent=5.50, limit=5.00)

    mock_bus.check_budget.side_effect = budget_side_effect

    with (
        patch("orchestrator.nodes.base.subprocess.run") as mock_run,
        patch("orchestrator.nodes.base.get_bus", return_value=mock_bus),
    ):
        mock_run.return_value = MagicMock(
            stdout="Still working...", stderr="", returncode=0
        )
        with pytest.raises(BudgetExceededError):
            doer.ralph_loop(
                worktree_path="/tmp/wt",
                prompt="Do it",
                task_id="t-1",
                scaffold_budget_usd=5.00,
            )
    assert mock_run.call_count == 2


def test_doer_no_budget_check_when_scaffold_budget_none():
    doer = DoerAgent(
        role="developer",
        model="claude-sonnet-4-6",
        max_iterations=3,
        completion_promise="TASK COMPLETE",
    )
    mock_bus = MagicMock()
    with (
        patch("orchestrator.nodes.base.subprocess.run") as mock_run,
        patch("orchestrator.nodes.base.get_bus", return_value=mock_bus),
    ):
        mock_run.return_value = MagicMock(
            stdout="Done.\nTASK COMPLETE", stderr="", returncode=0
        )
        doer.ralph_loop(worktree_path="/tmp/wt", prompt="Do it", task_id="t-1")
    mock_bus.check_budget.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_doer_base.py::test_doer_passes_max_budget_to_cli tests/test_doer_base.py::test_doer_passes_cost_usd_to_cli_done tests/test_doer_base.py::test_doer_checks_scaffold_budget_between_iterations -v`
Expected: FAIL

- [ ] **Step 3: Write the implementation**

In `orchestrator/nodes/base.py`:

Update `DoerAgent.__init__` to accept `max_budget_usd`:

```python
class DoerAgent:
    def __init__(
        self,
        role: str,
        model: str,
        max_iterations: int = 10,
        completion_promise: str = "TASK COMPLETE",
        max_budget_usd: float | None = None,
    ):
        self.role = role
        self.model = model
        self.max_iterations = max_iterations
        self.completion_promise = completion_promise
        self.max_budget_usd = max_budget_usd
```

Update `ralph_loop` signature to accept `scaffold_budget_usd`:

```python
def ralph_loop(
    self,
    worktree_path: str | Path,
    prompt: str,
    failure_context: str = "",
    task_id: str = "",
    scaffold_budget_usd: float | None = None,
) -> RalphResult:
```

In the subprocess command list inside `ralph_loop`, build the command dynamically:

```python
cmd = [
    "claude",
    "--model",
    self.model,
    "--output-format",
    "stream-json",
    "--verbose",
    "-p",
    current_prompt,
]
if self.max_budget_usd is not None:
    cmd[1:1] = ["--max-budget-usd", str(self.max_budget_usd)]
```

Note: insert `--max-budget-usd` before the positional args. Actually, it's cleaner to build the command like this:

```python
cmd = ["claude", "--model", self.model]
if self.max_budget_usd is not None:
    cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])
cmd.extend(["--output-format", "stream-json", "--verbose", "-p", current_prompt])
```

Pass `cost_usd` to `bus.cli_done()` — change the `finally` block's `cli_done` call:

```python
if bus:
    bus.cli_done(self.role, i, success, task_id, cost_usd=parsed.cost_usd)
```

Add scaffold budget check after the finally block, before checking success:

```python
if bus and scaffold_budget_usd is not None:
    bus.check_budget(scaffold_budget_usd)
```

This raises `BudgetExceededError` which propagates out of `ralph_loop`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_doer_base.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/base.py tests/test_doer_base.py
git commit -m "feat: DoerAgent --max-budget-usd passthrough and scaffold budget check"
```

---

### Task 5: ProjectConfig.max_budget_usd + config file updates

**Files:**
- Modify: `orchestrator/config.py`
- Modify: `config/agents.yaml`
- Modify: `config/projects/inkwell.yaml`
- Modify: `tests/test_config.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_project_config_max_budget_usd(tmp_path):
    governance = tmp_path / "governance.yaml"
    governance.write_text("rapid: {}\nraci: {}\n")
    agents = tmp_path / "agents.yaml"
    agents.write_text("workflow: {}\nspecialists: {}\nescalation: {}\n")
    project = tmp_path / "project.yaml"
    project.write_text(
        "repo_path: /tmp/test\n"
        "branch_prefix: scaffold\n"
        "max_concurrent_agents: 3\n"
        "db_path: ':memory:'\n"
        "max_budget_usd: 5.00\n"
    )
    cfg = load_config(str(tmp_path))
    assert cfg.project.max_budget_usd == 5.00


def test_project_config_max_budget_usd_defaults_none(config_dir):
    cfg = load_config(config_dir)
    assert cfg.project.max_budget_usd is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py::test_project_config_max_budget_usd tests/test_config.py::test_project_config_max_budget_usd_defaults_none -v`
Expected: FAIL (ProjectConfig doesn't accept max_budget_usd)

- [ ] **Step 3: Write the implementation**

In `orchestrator/config.py`, update `ProjectConfig`:

```python
@dataclass
class ProjectConfig:
    repo_path: str
    branch_prefix: str = "scaffold"
    max_concurrent_agents: int = 3
    db_path: str = "scaffold.db"
    max_budget_usd: float | None = None
```

- [ ] **Step 4: Update config files**

In `config/agents.yaml`, remove the unused `cost_threshold_per_run` from escalation:

```yaml
escalation:
  stuck_loop_model: claude-opus-4-6
  max_review_cycles: 3
  max_bug_cycles: 3
```

In `config/projects/inkwell.yaml`, add budget:

```yaml
repo_path: /Users/antonypegg/PROJECTS/inkwell
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold_inkwell.db
max_budget_usd: 5.00
```

- [ ] **Step 5: Update conftest.py config_dir fixture**

In `tests/conftest.py`, remove `cost_threshold_per_run` from the agents.yaml fixture and ensure project.yaml doesn't include `max_budget_usd` (so default None tests work):

Update the escalation section in the `config_dir` fixture:

```python
        "escalation:\n"
        "  stuck_loop_model: claude-opus-4-6\n"
        "  max_review_cycles: 3\n"
        "  max_bug_cycles: 3\n"
```

- [ ] **Step 6: Update test_config.py for removed cost_threshold_per_run**

The existing `test_agents_config_has_escalation` test checks `cost_threshold_per_run`. Update it:

```python
def test_agents_config_has_escalation(config_dir):
    cfg = load_config(config_dir)
    escalation = cfg.agents.escalation
    assert escalation["stuck_loop_model"] == "claude-opus-4-6"
    assert escalation["max_review_cycles"] == 3
    assert escalation["max_bug_cycles"] == 3
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 8: Run full test suite**

Run: `python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add orchestrator/config.py config/agents.yaml config/projects/inkwell.yaml tests/test_config.py tests/conftest.py
git commit -m "feat: add max_budget_usd to ProjectConfig, remove unused cost_threshold_per_run"
```

---

### Task 6: Developer node plumbing

**Files:**
- Modify: `orchestrator/nodes/developer.py`
- Modify: `orchestrator/graph.py`
- Modify: `tests/test_developer.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_developer.py`:

```python
def test_developer_passes_max_budget_to_doer(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    agents_config.specialists["python-expert"]["max_budget_usd"] = 2.00
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-010", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Update main.py"

    node_fn(state)

    mock_doer.assert_called_once_with(
        role="python-expert",
        model="claude-sonnet-4-6",
        max_iterations=10,
        completion_promise="TASK COMPLETE",
        max_budget_usd=2.00,
    )


def test_developer_passes_scaffold_budget_to_ralph_loop(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
        scaffold_budget_usd=10.00,
    )
    state = initial_state(task_id="task-011", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Update main.py"

    node_fn(state)

    ralph_call = mock_doer.return_value.ralph_loop.call_args
    assert ralph_call.kwargs.get("scaffold_budget_usd") == 10.00


def test_developer_no_scaffold_budget_by_default(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-012", level="task")
    state["specialists"] = ["python-expert"]
    state["agent_output"] = "Update main.py"

    node_fn(state)

    ralph_call = mock_doer.return_value.ralph_loop.call_args
    assert ralph_call.kwargs.get("scaffold_budget_usd") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_developer.py::test_developer_passes_max_budget_to_doer tests/test_developer.py::test_developer_passes_scaffold_budget_to_ralph_loop -v`
Expected: FAIL

- [ ] **Step 3: Update developer node**

In `orchestrator/nodes/developer.py`, update `make_developer_node` to accept `scaffold_budget_usd`:

```python
def make_developer_node(
    repo_path: str,
    branch_prefix: str,
    agent_loader: AgentLoader,
    agents_config: AgentsConfig,
    client=None,
    scaffold_budget_usd: float | None = None,
):
```

In the DoerAgent construction (step 8 of the existing code), add `max_budget_usd`:

```python
doer = DoerAgent(
    role=specialist_name,
    model=spec_config["model"],
    max_iterations=spec_config.get("max_iterations", 10),
    completion_promise=spec_config.get("completion_promise", "TASK COMPLETE"),
    max_budget_usd=spec_config.get("max_budget_usd"),
)
```

In the `ralph_loop` call (step 9), pass `scaffold_budget_usd`:

```python
result = doer.ralph_loop(
    worktree_path=worktree_path,
    prompt=prompt,
    failure_context=failure_context,
    task_id=state["task_id"],
    scaffold_budget_usd=scaffold_budget_usd,
)
```

- [ ] **Step 4: Update existing developer tests**

The existing tests that verify `mock_doer.assert_called_once_with(...)` need `max_budget_usd=None` added. Update each assertion in the existing tests:

- `test_developer_dispatches_correct_specialist`: add `max_budget_usd=None`
- `test_developer_matches_specialist_by_file_type`: add `max_budget_usd=None`
- `test_developer_detects_specialist_from_agent_output`: add `max_budget_usd=None`
- `test_developer_fallback_to_python_expert`: add `max_budget_usd=None`

Example (same change for all four):
```python
mock_doer.assert_called_once_with(
    role="python-expert",
    model="claude-sonnet-4-6",
    max_iterations=10,
    completion_promise="TASK COMPLETE",
    max_budget_usd=None,
)
```

- [ ] **Step 5: Update graph.py to pass scaffold_budget_usd**

In `orchestrator/graph.py`, update `build_graph` signature to accept `scaffold_budget_usd`:

```python
def build_graph(
    client,
    bot,
    repo_path: str,
    branch_prefix: str,
    spec_path: str,
    agent_loader: AgentLoader,
    agents_config: AgentsConfig,
    checkpointer=None,
    scaffold_budget_usd: float | None = None,
):
```

Update the developer node creation:

```python
graph.add_node(
    "developer",
    make_developer_node(
        repo_path, branch_prefix, agent_loader, agents_config, client,
        scaffold_budget_usd=scaffold_budget_usd,
    ),
)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_developer.py -v`
Expected: ALL PASS

Run: `python -m pytest tests/test_graph.py -v`
Expected: ALL PASS (build_graph's new param is optional with default None)

- [ ] **Step 7: Commit**

```bash
git add orchestrator/nodes/developer.py orchestrator/graph.py tests/test_developer.py
git commit -m "feat: plumb budget through developer node and graph builder"
```

---

### Task 7: Dispatcher budget check between children

**Files:**
- Modify: `orchestrator/dispatcher.py`
- Modify: `tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatcher.py`:

```python
from orchestrator.budget import BudgetExceededError


def test_run_task_checks_budget_between_children(db):
    from orchestrator.event_bus import EventBus, init_event_bus

    bus = init_event_bus(db)
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    parent_id = tree.create(title="Epic", level="epic")

    graph = MagicMock()
    child_count = 0

    def mock_invoke(state, config=None):
        nonlocal child_count
        if state["level"] == "epic":
            return {
                "status": "decomposing",
                "child_tasks": [
                    {"title": "Child A", "level": "task"},
                    {"title": "Child B", "level": "task"},
                ],
                "project_context": "",
                "specialists": [],
                "advisory": [],
                "detected_languages": [],
                "test_framework": "",
            }
        child_count += 1
        if child_count == 1:
            bus.cli_done("developer", 1, True, state["task_id"], cost_usd=4.00)
        return {"status": "done", "child_tasks": []}

    graph.invoke.side_effect = mock_invoke

    state = initial_state(task_id=parent_id, level="epic")
    result = run_task(graph, tree, state, parent_id, max_budget_usd=5.00)

    parent = tree.get(parent_id)
    assert parent["status"] == "blocked"
    children = tree.list_children(parent_id)
    done_children = [c for c in children if c["status"] == "done"]
    assert len(done_children) == 1


def test_run_task_catches_budget_exceeded_from_graph(db):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    task_id = tree.create(title="Expensive task", level="task")

    graph = MagicMock()
    graph.invoke.side_effect = BudgetExceededError(spent=6.00, limit=5.00)

    state = initial_state(task_id=task_id, level="task")
    result = run_task(graph, tree, state, task_id, max_budget_usd=5.00)

    assert result["status"] == "stuck"
    row = tree.get(task_id)
    assert row["status"] == "stuck"


def test_run_task_no_budget_check_when_none(db):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    task_id = tree.create(title="Leaf task", level="task")

    graph = MagicMock()
    graph.invoke.return_value = {"status": "done", "child_tasks": []}

    state = initial_state(task_id=task_id, level="task")
    result = run_task(graph, tree, state, task_id)

    assert result["status"] == "done"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dispatcher.py::test_run_task_checks_budget_between_children tests/test_dispatcher.py::test_run_task_catches_budget_exceeded_from_graph -v`
Expected: FAIL (run_task doesn't accept max_budget_usd)

- [ ] **Step 3: Write the implementation**

In `orchestrator/dispatcher.py`, update `run_task` to accept and check budget:

```python
from orchestrator.budget import BudgetExceededError
```

Update the function signature:

```python
def run_task(
    graph: CompiledStateGraph,
    tree: TaskTree,
    state: TaskState,
    thread_id: str,
    max_budget_usd: float | None = None,
) -> dict:
```

Update the try/except around `graph.invoke` to also catch `BudgetExceededError`:

```python
try:
    result = graph.invoke(state, config=config)
except BudgetExceededError:
    tree.update_status(state["task_id"], "stuck")
    if bus:
        bus.emit(
            "budget.exceeded",
            task_id=state["task_id"],
        )
    return {"status": "stuck", "child_tasks": []}
except Exception as exc:
    tree.update_status(state["task_id"], "stuck")
    if bus:
        bus.emit(
            "task.error",
            task_id=state["task_id"],
            error=str(exc),
        )
    return {"status": "stuck", "child_tasks": []}
```

In the children loop, after each `run_task(graph, tree, child_state, child_id)` call, add a budget check:

```python
run_task(graph, tree, child_state, child_id, max_budget_usd=max_budget_usd)

if max_budget_usd is not None and bus:
    try:
        bus.check_budget(max_budget_usd)
    except BudgetExceededError:
        bus.emit("budget.exceeded", task_id=state["task_id"])
        break
```

After the break, the existing final status logic handles it — remaining children weren't processed so `child_statuses` will have fewer entries, but all processed ones are checked. Actually, we need to handle this carefully. After break, the for loop exits. We need the child_statuses list to reflect what happened. Let me revise:

After the child loop's `run_task` call and status append:

```python
child_row = tree.get(child_id)
child_statuses.append(child_row["status"] if child_row else "stuck")

if max_budget_usd is not None and bus:
    try:
        bus.check_budget(max_budget_usd)
    except BudgetExceededError:
        bus.emit("budget.exceeded", task_id=state["task_id"])
        break
```

When we break, remaining children are unprocessed. The final status will be "blocked" because not all children are "done", which is correct behavior.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dispatcher.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add orchestrator/dispatcher.py tests/test_dispatcher.py
git commit -m "feat: budget check in dispatcher between child tasks"
```

---

### Task 8: CLI plumbing + report cumulative cost

**Files:**
- Modify: `orchestrator/__main__.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
def test_report_costs_shows_cumulative_spend(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e1', 'task-1', 'developer', 'cli.done', "
        "'{\"iteration\": 1, \"success\": true, \"cost_usd\": 0.12}')"
    )
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e2', 'task-1', 'developer', 'cli.done', "
        "'{\"iteration\": 2, \"success\": true, \"cost_usd\": 0.08}')"
    )
    conn.commit()
    conn.close()
    result = runner.invoke(cli, ["report", "--costs", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "$0.20" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_report_costs_shows_cumulative_spend -v`
Expected: FAIL

- [ ] **Step 3: Update __main__.py**

In the `run` command, pass `scaffold_budget_usd` to `build_graph` and `run_task`:

```python
graph, bot = _build_scaffold(cfg, spec, checkpointer)
```

Update `_build_scaffold` to accept and pass budget:

```python
def _build_scaffold(cfg, spec_path: str, checkpointer):
    # ... existing code ...
    graph = build_graph(
        client=client,
        bot=bot,
        repo_path=cfg.project.repo_path,
        branch_prefix=cfg.project.branch_prefix,
        spec_path=spec_path,
        agent_loader=agent_loader,
        agents_config=cfg.agents,
        checkpointer=checkpointer,
        scaffold_budget_usd=cfg.project.max_budget_usd,
    )
    return graph, bot
```

In the `run` command, pass budget to `run_task`:

```python
run_task(graph, tree, state, task_id, max_budget_usd=cfg.project.max_budget_usd)
```

Add `BudgetExceededError` handling in the `run` command:

```python
from orchestrator.budget import BudgetExceededError
```

Wrap the run_task call:

```python
try:
    run_task(graph, tree, state, task_id, max_budget_usd=cfg.project.max_budget_usd)
    click.echo("Run complete.")
except BudgetExceededError as e:
    click.echo(f"Run stopped: {e}")
```

In `report --costs`, add cumulative spend line:

```python
if costs:
    rows = conn.execute("SELECT * FROM epic_costs").fetchall()
    for row in rows:
        total_tokens = row["total_tokens_in"] + row["total_tokens_out"]
        wall = format_duration(row["total_wall_clock_ms"])
        click.echo(
            f"{row['epic_title']}: {total_tokens} tokens, {row['total_runs']} runs, {wall}"
        )
    total_cost = conn.execute(
        "SELECT COALESCE("
        "SUM(json_extract(event_data, '$.cost_usd')), 0.0"
        ") as total FROM events WHERE event_type = 'cli.done'"
    ).fetchone()["total"]
    click.echo(f"Total spend: ${total_cost:.2f}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 6: Run linter and type checker**

Run: `make check`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add orchestrator/__main__.py tests/test_cli.py
git commit -m "feat: plumb budget through CLI, show cumulative spend in report"
```

---

### Task 9: Final validation

- [ ] **Step 1: Run full test suite with coverage**

Run: `make coverage`
Expected: PASS with 75%+ coverage

- [ ] **Step 2: Run linter and type checker**

Run: `make check`
Expected: PASS

- [ ] **Step 3: Manual verification**

Verify the changes work together by reviewing the full diff:

Run: `git diff main --stat`

Check that:
- `BudgetExceededError` is importable
- `cli_done` events include `cost_usd` when provided
- `--max-budget-usd` appears in subprocess command when configured
- Budget check prevents new iterations after limit exceeded
- Report shows cumulative spend

- [ ] **Step 4: Update ROADMAP.md**

Move "Observability" to Completed. Update "Cost estimation and budgets" status to "In Progress" or "Done" and adjust the description to reflect what was built.
