# Observability: Tool Call Logging + Wallclock Time — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Log every tool call from CLI specialist agents, surface wallclock time in reports, and add a tool usage aggregation view.

**Architecture:** Extend the existing EventBus + Telemetry pattern. Add a JSONL parser for claude CLI `stream-json` output, a new `tool.call` event type, a `tool_usage` SQL view, and wallclock display in the `report` CLI command.

**Tech Stack:** Python 3.12, SQLite, Click CLI, pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `orchestrator/nodes/base.py` | DoerAgent subprocess call + JSONL parsing + tool call emission |
| `orchestrator/event_bus.py` | `tool_call()` convenience method |
| `db/schema.sql` | `tool_usage` view, updated `epic_costs` view |
| `orchestrator/__main__.py` | `format_duration()`, wallclock in `--agents`/`--costs`, `--tools` flag |
| `tests/test_event_bus.py` | Test `tool_call()` |
| `tests/test_doer_base.py` | Test JSONL parsing, tool call events, completion_promise from JSONL, fallback |
| `tests/test_cli.py` | Test `format_duration()`, `--tools`, wallclock display |

---

### Task 1: EventBus `tool_call()` Method

**Files:**
- Modify: `orchestrator/event_bus.py:90-104`
- Test: `tests/test_event_bus.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_event_bus.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_event_bus.py::test_tool_call_event tests/test_event_bus.py::test_tool_call_event_without_run_id -v`

Expected: FAIL with `AttributeError: 'EventBus' object has no attribute 'tool_call'`

- [ ] **Step 3: Implement `tool_call()` method**

Add to `orchestrator/event_bus.py`, after the `escalation()` method (after line 104):

```python
def tool_call(
    self,
    agent_role: str,
    tool_name: str,
    task_id: str,
    run_id: str | None = None,
) -> None:
    self.emit(
        "tool.call",
        agent_role=agent_role,
        task_id=task_id,
        run_id=run_id,
        tool_name=tool_name,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_event_bus.py -v`

Expected: All tests PASS (including the two new ones)

- [ ] **Step 5: Commit**

```bash
cd /Users/antonypegg/PROJECTS/scaffold && git add orchestrator/event_bus.py tests/test_event_bus.py && git commit -m "feat: add tool_call() convenience method to EventBus"
```

---

### Task 2: JSONL Parser for CLI Output

**Files:**
- Modify: `orchestrator/nodes/base.py:1-10`
- Test: `tests/test_doer_base.py`

The `parse_cli_output()` function parses the JSONL stream from `claude --output-format stream-json --verbose`. It returns a dataclass with the extracted data. This is independent of DoerAgent so we can test it in isolation.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_doer_base.py`:

```python
from orchestrator.nodes.base import CliOutput, parse_cli_output


SAMPLE_JSONL = "\n".join([
    '{"type":"system","subtype":"init","session_id":"abc"}',
    '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"t1","input":{"file_path":"/tmp/f.py"}}]}}',
    '{"type":"user","subtype":"tool_result"}',
    '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t2","input":{"file_path":"/tmp/f.py","old_string":"a","new_string":"b"}}]}}',
    '{"type":"user","subtype":"tool_result"}',
    '{"type":"assistant","message":{"content":[{"type":"text","text":"Done.\\nTASK COMPLETE"}]}}',
    '{"type":"result","result":"Done.\\nTASK COMPLETE","num_turns":3,"total_cost_usd":0.12}',
])


def test_parse_cli_output_extracts_tool_names():
    output = parse_cli_output(SAMPLE_JSONL)
    assert output.tool_names == ["Read", "Edit"]


def test_parse_cli_output_extracts_result_text():
    output = parse_cli_output(SAMPLE_JSONL)
    assert "TASK COMPLETE" in output.result_text


def test_parse_cli_output_extracts_cost():
    output = parse_cli_output(SAMPLE_JSONL)
    assert output.cost_usd == pytest.approx(0.12)


def test_parse_cli_output_fallback_on_invalid_json():
    raw = "This is plain text output.\nTASK COMPLETE"
    output = parse_cli_output(raw)
    assert output.result_text == raw
    assert output.tool_names == []
    assert output.cost_usd is None


def test_parse_cli_output_fallback_on_missing_result_line():
    partial = '{"type":"system","subtype":"init"}\n{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]}}'
    output = parse_cli_output(partial)
    assert output.result_text == partial
    assert output.tool_names == []
    assert output.cost_usd is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_doer_base.py::test_parse_cli_output_extracts_tool_names tests/test_doer_base.py::test_parse_cli_output_extracts_result_text tests/test_doer_base.py::test_parse_cli_output_extracts_cost tests/test_doer_base.py::test_parse_cli_output_fallback_on_invalid_json tests/test_doer_base.py::test_parse_cli_output_fallback_on_missing_result_line -v`

Expected: FAIL with `ImportError: cannot import name 'CliOutput' from 'orchestrator.nodes.base'`

- [ ] **Step 3: Implement `CliOutput` dataclass and `parse_cli_output()` function**

Add to `orchestrator/nodes/base.py`, after the existing imports (line 3):

```python
import json as _json

@dataclass
class CliOutput:
    result_text: str
    tool_names: list[str]
    cost_usd: float | None


def parse_cli_output(stdout: str) -> CliOutput:
    tool_names: list[str] = []
    result_text: str | None = None
    cost_usd: float | None = None
    found_jsonl = False
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = _json.loads(line)
        except (ValueError, TypeError):
            continue
        found_jsonl = True
        obj_type = obj.get("type")
        if obj_type == "assistant":
            for block in obj.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    tool_names.append(block["name"])
        elif obj_type == "result":
            result_text = obj.get("result", "")
            cost_usd = obj.get("total_cost_usd")
    if not found_jsonl or result_text is None:
        return CliOutput(result_text=stdout, tool_names=[], cost_usd=None)
    return CliOutput(result_text=result_text, tool_names=tool_names, cost_usd=cost_usd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_doer_base.py -v`

Expected: All tests PASS (existing + 5 new)

- [ ] **Step 5: Commit**

```bash
cd /Users/antonypegg/PROJECTS/scaffold && git add orchestrator/nodes/base.py tests/test_doer_base.py && git commit -m "feat: add JSONL parser for claude CLI stream-json output"
```

---

### Task 3: Wire DoerAgent to Use stream-json and Emit Tool Events

**Files:**
- Modify: `orchestrator/nodes/base.py:109-152`
- Test: `tests/test_doer_base.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_doer_base.py`:

```python
STREAM_JSON_SUCCESS = "\n".join([
    '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"t1","input":{"file_path":"/tmp/f.py"}}]}}',
    '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t2","input":{"file_path":"/tmp/f.py","old_string":"a","new_string":"b"}}]}}',
    '{"type":"assistant","message":{"content":[{"type":"text","text":"Done.\\nTASK COMPLETE"}]}}',
    '{"type":"result","result":"Done.\\nTASK COMPLETE","num_turns":2,"total_cost_usd":0.05}',
])


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_uses_stream_json_format(mock_run, doer):
    mock_run.return_value = MagicMock(
        stdout=STREAM_JSON_SUCCESS,
        stderr="",
        returncode=0,
    )
    doer.ralph_loop(worktree_path="/tmp/wt", prompt="Do the thing")
    cmd = mock_run.call_args.args[0]
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "--verbose" in cmd


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_detects_promise_from_jsonl(mock_run, doer):
    mock_run.return_value = MagicMock(
        stdout=STREAM_JSON_SUCCESS,
        stderr="",
        returncode=0,
    )
    result = doer.ralph_loop(worktree_path="/tmp/wt", prompt="Do the thing")
    assert result.success is True
    assert result.iterations == 1
    assert "TASK COMPLETE" in result.output


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_emits_tool_call_events(mock_run, doer):
    mock_run.return_value = MagicMock(
        stdout=STREAM_JSON_SUCCESS,
        stderr="",
        returncode=0,
    )
    mock_bus = MagicMock()
    with patch("orchestrator.nodes.base.get_bus", return_value=mock_bus):
        doer.ralph_loop(worktree_path="/tmp/wt", prompt="Do it", task_id="t-1")
    tool_calls = [
        c for c in mock_bus.method_calls if c[0] == "tool_call"
    ]
    assert len(tool_calls) == 2
    assert tool_calls[0].args == ("developer", "Read", "t-1")
    assert tool_calls[1].args == ("developer", "Edit", "t-1")


@patch("orchestrator.nodes.base.subprocess.run")
def test_doer_falls_back_on_plain_text_output(mock_run, doer):
    mock_run.return_value = MagicMock(
        stdout="Plain text output.\nTASK COMPLETE",
        stderr="",
        returncode=0,
    )
    result = doer.ralph_loop(worktree_path="/tmp/wt", prompt="Do it")
    assert result.success is True
    assert result.output == "Plain text output.\nTASK COMPLETE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_doer_base.py::test_doer_uses_stream_json_format tests/test_doer_base.py::test_doer_detects_promise_from_jsonl tests/test_doer_base.py::test_doer_emits_tool_call_events tests/test_doer_base.py::test_doer_falls_back_on_plain_text_output -v`

Expected: `test_doer_uses_stream_json_format` FAILS (no `--output-format` in command). Others may fail too.

- [ ] **Step 3: Update `ralph_loop()` to use stream-json and emit tool events**

Replace the subprocess call and output handling in `orchestrator/nodes/base.py` `ralph_loop()` method. The full updated method:

```python
def ralph_loop(
    self,
    worktree_path: str | Path,
    prompt: str,
    failure_context: str = "",
    task_id: str = "",
) -> RalphResult:
    from orchestrator.event_bus import get_bus

    bus = get_bus()
    last_output = ""
    for i in range(1, self.max_iterations + 1):
        if bus:
            bus.cli_start(self.role, self.model, i, task_id)
        if i > 1 and last_output:
            current_prompt = (
                f"{prompt}\n\n--- PREVIOUS ATTEMPT (iteration {i - 1}) ---\n"
                f"{last_output}\n--- END PREVIOUS ATTEMPT ---\n\n"
                "The previous attempt did not complete the task. "
                "Fix the issues and try again."
            )
        elif failure_context:
            current_prompt = f"{prompt}\n\n--- FAILURE CONTEXT ---\n{failure_context}\n---"
        else:
            current_prompt = prompt

        success = False
        try:
            result = subprocess.run(
                [
                    "claude",
                    "--model",
                    self.model,
                    "--output-format",
                    "stream-json",
                    "--verbose",
                    "-p",
                    current_prompt,
                ],
                capture_output=True,
                text=True,
                cwd=str(worktree_path),
                timeout=600,
            )
            parsed = parse_cli_output(result.stdout)
            last_output = parsed.result_text
            success = self.completion_promise in parsed.result_text
            if bus:
                for tool_name in parsed.tool_names:
                    bus.tool_call(self.role, tool_name, task_id)
        finally:
            if bus:
                bus.cli_done(self.role, i, success, task_id)
        if success:
            return RalphResult(success=True, iterations=i, output=parsed.result_text)

    return RalphResult(success=False, iterations=self.max_iterations, output=last_output)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_doer_base.py -v`

Expected: All tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest -x -q`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/antonypegg/PROJECTS/scaffold && git add orchestrator/nodes/base.py tests/test_doer_base.py && git commit -m "feat: wire DoerAgent to stream-json output with tool call events"
```

---

### Task 4: SQL Views — `tool_usage` and Updated `epic_costs`

**Files:**
- Modify: `db/schema.sql:67-78`

- [ ] **Step 1: Add `tool_usage` view to schema**

Add at the end of `db/schema.sql` (after the `agent_efficiency` view):

```sql
CREATE VIEW IF NOT EXISTS tool_usage AS
SELECT
    agent_role,
    json_extract(event_data, '$.tool_name') as tool_name,
    COUNT(*) as call_count
FROM events
WHERE event_type = 'tool.call'
GROUP BY agent_role, json_extract(event_data, '$.tool_name')
ORDER BY agent_role, call_count DESC;
```

- [ ] **Step 2: Update `epic_costs` view to include wallclock time**

Replace the existing `epic_costs` view in `db/schema.sql` (lines 67-78) with:

```sql
CREATE VIEW IF NOT EXISTS epic_costs AS
SELECT
    t2.title as epic_title,
    t.parent_id as epic_id,
    SUM(ar.token_in) as total_tokens_in,
    SUM(ar.token_out) as total_tokens_out,
    SUM(CAST((julianday(ar.finished_at) - julianday(ar.started_at)) * 86400000 AS INTEGER))
        as total_wall_clock_ms,
    COUNT(DISTINCT ar.id) as total_runs,
    COUNT(DISTINCT t.id) as total_tasks
FROM tasks t
JOIN agent_runs ar ON t.id = ar.task_id
LEFT JOIN tasks t2 ON t.parent_id = t2.id
GROUP BY t.parent_id;
```

- [ ] **Step 3: Verify schema loads without errors**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.executescript(open('db/schema.sql').read()); print('Schema OK'); print('Views:', [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='view'\").fetchall()])"`

Expected: `Schema OK` with `tool_usage` in the views list

- [ ] **Step 4: Run full test suite (schema change may affect fixtures)**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest -x -q`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/antonypegg/PROJECTS/scaffold && git add db/schema.sql && git commit -m "feat: add tool_usage view and wallclock time to epic_costs"
```

---

### Task 5: `format_duration()` Helper

**Files:**
- Modify: `orchestrator/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
from orchestrator.__main__ import format_duration


def test_format_duration_seconds():
    assert format_duration(45000) == "45s"


def test_format_duration_minutes():
    assert format_duration(154000) == "2m 34s"


def test_format_duration_hours():
    assert format_duration(4320000) == "1h 12m"


def test_format_duration_zero():
    assert format_duration(0) == "0s"


def test_format_duration_none():
    assert format_duration(None) == "-"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_cli.py::test_format_duration_seconds tests/test_cli.py::test_format_duration_minutes tests/test_cli.py::test_format_duration_hours tests/test_cli.py::test_format_duration_zero tests/test_cli.py::test_format_duration_none -v`

Expected: FAIL with `ImportError: cannot import name 'format_duration'`

- [ ] **Step 3: Implement `format_duration()`**

Add to `orchestrator/__main__.py`, before the `report` command:

```python
def format_duration(ms: int | None) -> str:
    if ms is None:
        return "-"
    total_seconds = int(ms / 1000)
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes:02d}m"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_cli.py::test_format_duration_seconds tests/test_cli.py::test_format_duration_minutes tests/test_cli.py::test_format_duration_hours tests/test_cli.py::test_format_duration_zero tests/test_cli.py::test_format_duration_none -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/antonypegg/PROJECTS/scaffold && git add orchestrator/__main__.py tests/test_cli.py && git commit -m "feat: add format_duration() helper for human-readable wallclock time"
```

---

### Task 6: Wallclock Time in `--agents` and `--costs` Report Output

**Files:**
- Modify: `orchestrator/__main__.py:215-245`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
import sqlite3
from pathlib import Path


def _make_report_db(tmp_path):
    db_path = tmp_path / "scaffold.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "db" / "schema.sql"
    conn.executescript(schema.read_text())
    conn.execute(
        "INSERT INTO tasks (id, level, status, title) VALUES ('epic-1', 'epic', 'done', 'Auth Epic')"
    )
    conn.execute(
        "INSERT INTO tasks (id, parent_id, level, status, title) "
        "VALUES ('task-1', 'epic-1', 'task', 'done', 'Implement login')"
    )
    conn.execute(
        "INSERT INTO agent_runs (id, task_id, agent_role, model, started_at, finished_at, "
        "iterations, token_in, token_out, outcome) VALUES "
        "('run-1', 'task-1', 'developer', 'claude-sonnet-4-6', "
        "'2026-05-13T10:00:00', '2026-05-13T10:04:12', 1, 5000, 2000, 'success')"
    )
    conn.commit()
    conn.close()
    return db_path


def test_report_agents_shows_wallclock(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    result = runner.invoke(cli, ["report", "--agents", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "4m" in result.output


def test_report_costs_shows_wallclock(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    result = runner.invoke(cli, ["report", "--costs", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "4m" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_cli.py::test_report_agents_shows_wallclock tests/test_cli.py::test_report_costs_shows_wallclock -v`

Expected: FAIL — output doesn't contain wallclock time

- [ ] **Step 3: Update `--agents` output to include wallclock**

In `orchestrator/__main__.py`, update the `--agents` section of the `report` command (around line 231-239):

```python
    if agents:
        rows = conn.execute("SELECT * FROM agent_efficiency").fetchall()
        for row in rows:
            success_rate = row["success_rate_pct"]
            avg_iters = row["avg_ralph_iterations"]
            wall = format_duration(row["avg_wall_clock_ms"])
            msg = (
                f"{row['agent_role']} ({row['model']}): {success_rate:.0f}% success, "
                f"{avg_iters:.1f} avg iterations, avg {wall}"
            )
            click.echo(msg)
```

- [ ] **Step 4: Update `--costs` output to include wallclock**

In `orchestrator/__main__.py`, update the `--costs` section (around line 221-225):

```python
    if costs:
        rows = conn.execute("SELECT * FROM epic_costs").fetchall()
        for row in rows:
            total_tokens = row["total_tokens_in"] + row["total_tokens_out"]
            wall = format_duration(row["total_wall_clock_ms"])
            click.echo(
                f"{row['epic_title']}: {total_tokens} tokens, "
                f"{row['total_runs']} runs, {wall}"
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_cli.py -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/antonypegg/PROJECTS/scaffold && git add orchestrator/__main__.py tests/test_cli.py && git commit -m "feat: surface wallclock time in report --agents and --costs"
```

---

### Task 7: `--tools` Report Flag

**Files:**
- Modify: `orchestrator/__main__.py:210-214`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
def test_report_tools_shows_usage(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e1', 'task-1', 'developer', 'tool.call', '{\"tool_name\": \"Edit\"}')"
    )
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e2', 'task-1', 'developer', 'tool.call', '{\"tool_name\": \"Edit\"}')"
    )
    conn.execute(
        "INSERT INTO events (id, task_id, agent_role, event_type, event_data) "
        "VALUES ('e3', 'task-1', 'developer', 'tool.call', '{\"tool_name\": \"Read\"}')"
    )
    conn.commit()
    conn.close()
    result = runner.invoke(cli, ["report", "--tools", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "developer" in result.output
    assert "Edit" in result.output
    assert "Read" in result.output


def test_report_tools_empty(runner, tmp_path):
    db_path = _make_report_db(tmp_path)
    result = runner.invoke(cli, ["report", "--tools", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "No tool" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_cli.py::test_report_tools_shows_usage tests/test_cli.py::test_report_tools_empty -v`

Expected: FAIL — `--tools` flag doesn't exist

- [ ] **Step 3: Add `--tools` flag to report command**

In `orchestrator/__main__.py`, add the `--tools` option to the `report` command and implement the handler:

Add after the existing `--agents` option (line 214):

```python
@click.option("--tools", is_flag=True, help="Show tool usage by agent")
```

Update the function signature:

```python
def report(db, costs, cycles, agents, tools):
```

Add the tools handler after the `agents` block (before the default block):

```python
    if tools:
        rows = conn.execute("SELECT * FROM tool_usage").fetchall()
        if not rows:
            click.echo("No tool usage recorded.")
        else:
            current_role = None
            for row in rows:
                if row["agent_role"] != current_role:
                    current_role = row["agent_role"]
                    click.echo(f"{current_role}:")
                click.echo(f"  {row['tool_name']:<12} {row['call_count']}")
```

Update the default condition:

```python
    if not (costs or cycles or agents or tools):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_cli.py -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/antonypegg/PROJECTS/scaffold && git add orchestrator/__main__.py tests/test_cli.py && git commit -m "feat: add --tools flag to report command for tool usage breakdown"
```

---

### Task 8: Final Validation

**Files:** None (verification only)

- [ ] **Step 1: Run the full check suite**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && make check`

Expected: lint + typecheck + all tests PASS

- [ ] **Step 2: Fix any lint or type errors**

If pyright or ruff report issues, fix them and commit:

```bash
cd /Users/antonypegg/PROJECTS/scaffold && make format && make lint && make typecheck
```

- [ ] **Step 3: Verify all new code is covered by tests**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest --cov=orchestrator --cov-report=term-missing -q`

Check that `parse_cli_output`, `tool_call`, `format_duration`, and the updated `ralph_loop` have test coverage.

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
cd /Users/antonypegg/PROJECTS/scaffold && git add -u && git commit -m "fix: address lint and type issues"
```
