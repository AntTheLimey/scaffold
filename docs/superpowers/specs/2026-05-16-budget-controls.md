# Budget Controls: Per-Specialist Caps + Scaffold-Level Cumulative Cost

**Date:** 2026-05-16
**Status:** Spec
**Scope:** Per-specialist --max-budget-usd passthrough, scaffold-level cumulative cost tracking, budget-exceeded abort

---

## Problem

The scaffold can burn tokens unproductively. A stuck DoerAgent specialist
loops up to 10 iterations at ~$0.10+ each. Multiple specialists across
multiple child tasks can compound this. There is no way to:

1. Cap how much a single specialist session can spend.
2. Cap how much an entire scaffold run can spend.
3. See how much a run has cost so far.

`CliOutput.cost_usd` is already parsed from the claude CLI's stream-json
output but never stored or checked. The `escalation.cost_threshold_per_run`
config field exists but is not enforced anywhere.

## Approach

Two independent but complementary controls:

**Per-specialist budget** — passthrough to `claude --max-budget-usd`. The
CLI already enforces per-session spending limits. We just need to plumb
the config value through to the subprocess command.

**Scaffold-level cumulative budget** — track reported costs from CLI calls
via the event bus (extending the existing `cli.done` event), query the
cumulative total from SQLite, and abort the run when the threshold is
exceeded. Resume-safe because events persist in the database.

AdvisorAgent API call costs are NOT tracked. The Anthropic API returns
token counts but not dollar amounts. These calls are small relative to
CLI specialist sessions. API cost estimation via a price lookup table can
be added later.

---

## Design

### 1. Per-specialist --max-budget-usd passthrough

Add optional `max_budget_usd` to specialist config in `agents.yaml`:

```yaml
specialists:
  python-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    max_budget_usd: 2.00
    completion_promise: "TASK COMPLETE"
```

Add `max_budget_usd: float | None = None` to DoerAgent constructor.

In `ralph_loop()`, when `self.max_budget_usd` is set, add
`--max-budget-usd` and `str(self.max_budget_usd)` to the subprocess
command list. This is a per-session cap — each ralph_loop iteration
gets its own budget. If the CLI exceeds it, the subprocess exits with
a non-zero return code and no `result` JSONL line. The existing fallback
logic handles this (falls back to raw stdout, `completion_promise` not
found, iteration continues or exhausts).

The developer node reads `max_budget_usd` from `spec_config` and passes
it to the DoerAgent constructor.

### 2. Scaffold-level cumulative cost tracking

#### 2a. Store cost in cli.done events

`ralph_loop()` already emits `cli.done` events via `bus.cli_done()`.
Extend `cli_done()` to accept an optional `cost_usd` parameter and
include it in the event data:

```python
def cli_done(
    self,
    agent_role: str,
    iteration: int,
    success: bool,
    task_id: str,
    cost_usd: float | None = None,
) -> None:
    self.emit(
        "cli.done",
        agent_role=agent_role,
        task_id=task_id,
        iteration=iteration,
        success=success,
        cost_usd=cost_usd,
    )
```

`ralph_loop()` passes `parsed.cost_usd` to `bus.cli_done()` after each
iteration.

#### 2b. Cumulative cost query

Add `cumulative_cost()` to `Telemetry`:

```python
def cumulative_cost(self) -> float:
    row = self.conn.execute(
        "SELECT COALESCE(SUM(json_extract(event_data, '$.cost_usd')), 0.0) "
        "as total FROM events WHERE event_type = 'cli.done'"
    ).fetchone()
    return row["total"]
```

This returns the total reported cost across all CLI calls in the database.
Resume-safe: a resumed run picks up where spending left off.

#### 2c. Budget check methods

Add to `EventBus`:

```python
def check_budget(self, limit: float) -> None:
    spent = self.telemetry.cumulative_cost()
    if spent >= limit:
        raise BudgetExceededError(spent, limit)
```

New exception in `orchestrator/budget.py`:

```python
class BudgetExceededError(Exception):
    def __init__(self, spent: float, limit: float):
        self.spent = spent
        self.limit = limit
        super().__init__(
            f"Budget exceeded: ${spent:.2f} spent, ${limit:.2f} limit"
        )
```

#### 2d. Check points

**In ralph_loop** — after each iteration, before starting the next:

```python
if bus and budget_limit:
    bus.check_budget(budget_limit)
```

The `budget_limit` comes from the scaffold-level config, passed into
DoerAgent or ralph_loop as a parameter.

**In dispatcher.run_task** — between child tasks in the recursive loop:

```python
if budget_limit:
    bus = get_bus()
    if bus:
        bus.check_budget(budget_limit)
```

`BudgetExceededError` propagates up the call stack. `run_task()` catches
it, sets the task status to `stuck`, emits a `budget.exceeded` event,
and returns. The parent run_task also catches it and stops processing
remaining children.

### 3. Config changes

**ProjectConfig** gets `max_budget_usd`:

```python
@dataclass
class ProjectConfig:
    repo_path: str
    branch_prefix: str = "scaffold"
    max_concurrent_agents: int = 3
    db_path: str = "scaffold.db"
    max_budget_usd: float | None = None
```

Set in project YAML:

```yaml
repo_path: /Users/antonypegg/PROJECTS/inkwell
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold_inkwell.db
max_budget_usd: 5.00
```

**escalation.cost_threshold_per_run** — remove from agents.yaml. It was
never enforced and is replaced by `project.max_budget_usd`.

### 4. Plumbing the budget limit

The scaffold-level `max_budget_usd` needs to reach two places:

1. **DoerAgent.ralph_loop** — for between-iteration checks.
2. **dispatcher.run_task** — for between-child-task checks.

For DoerAgent: add `scaffold_budget_usd: float | None = None` parameter
to `ralph_loop()`. The developer node passes `cfg.project.max_budget_usd`
through. This requires the developer node factory to receive the project
config (or just the budget value).

For the dispatcher: `run_task()` gets a `max_budget_usd: float | None`
parameter. The CLI `run` command passes `cfg.project.max_budget_usd`
into `run_task()`.

### 5. Report: cumulative cost display

**`report --costs`** — add cumulative cost line:

```
Total spend: $3.47
```

Query: `SELECT COALESCE(SUM(...), 0.0) FROM events WHERE event_type = 'cli.done'`

This reuses the same `Telemetry.cumulative_cost()` method.

### 6. Console output on budget exceeded

When `BudgetExceededError` is caught in `run_task()`:

```
[14:23:01] BUDGET        | budget.exceeded | task-abc-123 | spent=$3.47  limit=$5.00
```

This uses the existing event bus console format. The task is marked
`stuck` and the run terminates cleanly.

---

## Files changed

| File | Change |
|------|--------|
| `orchestrator/budget.py` | New file. `BudgetExceededError` exception class. |
| `orchestrator/nodes/base.py` | DoerAgent: add `max_budget_usd` constructor param, pass `--max-budget-usd` to CLI. ralph_loop: add `scaffold_budget_usd` param, pass `cost_usd` to `cli_done`, check budget between iterations. |
| `orchestrator/event_bus.py` | `cli_done()`: add `cost_usd` param. New `check_budget()` method. |
| `orchestrator/telemetry.py` | New `cumulative_cost()` method. |
| `orchestrator/config.py` | `ProjectConfig`: add `max_budget_usd` field. |
| `orchestrator/nodes/developer.py` | Pass `max_budget_usd` from specialist config to DoerAgent. Pass scaffold budget to `ralph_loop()`. |
| `orchestrator/dispatcher.py` | `run_task()`: add `max_budget_usd` param, check budget between children, catch `BudgetExceededError`. |
| `orchestrator/__main__.py` | Pass `max_budget_usd` to `run_task()`. Add cumulative cost to `report --costs`. |
| `config/agents.yaml` | Remove `cost_threshold_per_run`. Add `max_budget_usd` examples to specialists. |
| `config/projects/inkwell.yaml` | Add `max_budget_usd: 5.00`. |
| `tests/test_budget.py` | Test `BudgetExceededError`. |
| `tests/test_base.py` | Test `--max-budget-usd` passthrough, cost_usd in cli_done, budget check in ralph_loop. |
| `tests/test_event_bus.py` | Test `cli_done` with cost_usd, `check_budget()`. |
| `tests/test_telemetry.py` | Test `cumulative_cost()`. |
| `tests/test_dispatcher.py` | Test budget check between children, BudgetExceededError handling. |
| `tests/test_main.py` | Test cumulative cost in report --costs. |

## Files unchanged

- `db/schema.sql` — no schema migration. Cost data stored in event_data JSON.
- `orchestrator/graph.py` — no routing changes.
- `orchestrator/state.py` — no state changes.
- `orchestrator/self_heal.py` — budget is separate from stuck-loop detection.

## Risks

**CLI --max-budget-usd behavior.** If the claude CLI hits the budget mid-session,
it exits without a clean `result` JSONL line. The existing parse_cli_output
fallback handles this — `cost_usd` will be None for that iteration, and the
iteration counts as a failure (completion_promise not found). Low risk.

**Resume cost accuracy.** Cumulative cost queries the events table, which
persists across resume. If the database is deleted between runs, cost history
is lost. This is expected behavior — the database IS the run history.

**API costs not tracked.** AdvisorAgent costs are invisible to the budget
system. For Inkwell runs, CLI specialist costs dominate (~90%+ of spend).
This is acceptable for now. Adding API cost tracking later requires either
a price lookup table or waiting for the Anthropic SDK to expose cost directly.

## Out of scope

- API-based agent cost tracking (needs price lookup table)
- Cost estimation before running (separate roadmap item)
- Web dashboard cost display (separate roadmap item)
- Per-task cost breakdown in report (natural follow-up)
