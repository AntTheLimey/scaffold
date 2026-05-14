# Observability: Tool Call Logging + Wallclock Time

**Date:** 2026-05-13
**Status:** Spec
**Scope:** DoerAgent tool call logging, wallclock time surfacing, report improvements

---

## Problem

The scaffold has an event bus and telemetry system that tracks agent runs,
token usage, and routing decisions. Three gaps remain:

1. **No tool call visibility.** CLI specialist agents (DoerAgent) use tools
   like Read, Edit, and Bash via the `claude` subprocess, but we don't log
   which tools were called or how often. This makes it impossible to
   understand what an agent actually did during a run.

2. **Wallclock time not surfaced.** The `agent_runs` table has `started_at`
   and `finished_at` timestamps, and the `agent_efficiency` view computes
   `avg_wall_clock_ms`, but the `report` CLI command doesn't display
   duration anywhere.

3. **No tool usage aggregation.** There's no way to answer "which tools
   does each agent type use and how often?" — useful for understanding
   agent behavior patterns and spotting inefficiencies.

## Approach

Inline integration: add tool call logging directly where the data already
lives — inside `DoerAgent.ralph_loop()` — following the established pattern
of nodes emitting events via `bus.emit()`.

AdvisorAgents are out of scope. They don't use tools today (no `tools`
parameter passed to the Anthropic API). Adding tool use to workflow agents
is a separate roadmap item.

---

## Design

### 1. Switch DoerAgent to JSON output

Add `--output-format stream-json --verbose` to the `claude` subprocess
call in `DoerAgent.ralph_loop()`.

**Why stream-json, not json?** The `--output-format json` mode returns a
single JSON object with the final result text and aggregate metrics, but
does NOT include individual tool call records. The `stream-json` format
(which requires `--verbose`) emits one JSONL line per event, including
`assistant` messages with `tool_use` content blocks that contain tool
names. This is the only way to get per-tool-call data from the CLI.

**Current command:**
```
["claude", "--model", self.model, "-p", current_prompt]
```

**New command:**
```
["claude", "--model", self.model, "--output-format", "stream-json", "--verbose", "-p", current_prompt]
```

**JSONL response handling:**

`result.stdout` contains multiple JSONL lines. Each line is a JSON object
with a `type` field. The relevant types are:

- `{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", ...}]}}`
  — emitted when the agent calls a tool. Extract `name` from each
  `tool_use` content block.
- `{"type": "result", "result": "final text...", "num_turns": 2, "total_cost_usd": 0.09, ...}`
  — emitted at the end. Contains the final text output.

Parse each line, collect tool names from `assistant`/`tool_use` blocks,
and extract the final text from the `result` line.

Extract text content for:
- `completion_promise` checking (same logic, reading from the `result`
  line's `result` field instead of raw stdout)
- `last_output` for retry context on subsequent iterations
- `RalphResult.output` (stays as a string — downstream unchanged)

**Fallback:** If JSONL parsing fails (no `result` line found), fall back
to raw stdout behavior. The agent still works; tool call events are
skipped for that iteration. Log a warning via `click.echo(..., err=True)`.

A `parse_cli_output(stdout: str)` helper function encapsulates the JSONL
parsing. It returns a dataclass with `result_text`, `tool_names`, and
`cost_usd` fields. This keeps the ralph_loop method clean and makes
parsing independently testable.

### 2. Emit `tool.call` events

After parsing the JSON response, iterate over tool use records and emit
one `tool.call` event per tool invocation:

```python
bus.tool_call(
    agent_role="developer",
    tool_name="Edit",
    task_id=task_id,
    run_id=run_id,
)
```

**Event data shape in the `events` table:**
```json
{"tool_name": "Edit"}
```

We log tool names only — not input values or output content. Tool inputs
often contain code, file contents, or large diffs that would bloat the
events table without adding queryable value.

### 3. New EventBus convenience method

Add `tool_call()` to `EventBus`, following the pattern of `cli_start()`,
`cli_done()`, etc:

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

### 4. New SQL view: `tool_usage`

Aggregates tool call events by agent role and tool name:

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

### 5. Wallclock time in report CLI

**`format_duration()` helper:**

Converts milliseconds to human-readable format:
- Under 60s: `45s`
- 60s and over: `2m 34s`
- 60m and over: `1h 12m`

**`--agents` output change:**

Current:
```
developer (claude-sonnet-4-20250514): 85% success, 1.3 avg iterations
```

New:
```
developer (claude-sonnet-4-20250514): 85% success, 1.3 avg iterations, avg 4m 12s
```

**`--costs` output change:**

Add total wallclock time per epic (sum of all agent run durations).

**New `--tools` flag:**

Displays the `tool_usage` view grouped by agent role:

```
developer:
  Edit       47
  Read       23
  Bash       12
  Write       3
```

### 6. Update `epic_costs` view

Add wallclock time aggregation:

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

Note: the existing `epic_costs` view has no `WHERE` filter. We keep it
that way — runs without `finished_at` contribute NULL to the wallclock
sum, which `SUM()` ignores. Token counts from in-progress runs are still
included, matching current behavior.
---

## Files changed

| File | Change |
|------|--------|
| `orchestrator/nodes/base.py` | Add `--output-format json`. Parse JSON response. Extract text for completion_promise. Emit `tool.call` events. Handle parse failures gracefully. |
| `orchestrator/event_bus.py` | Add `tool_call()` convenience method. |
| `db/schema.sql` | Add `tool_usage` view. Update `epic_costs` view with wallclock column. |
| `orchestrator/__main__.py` | Add `format_duration()`. Add wallclock display to `--agents` and `--costs`. Add `--tools` flag. |
| `tests/test_base.py` | Test JSON parsing, tool call event emission, completion_promise detection from JSON, fallback on parse failure. |
| `tests/test_event_bus.py` | Test `tool_call()` method. |
| `tests/test_main.py` | Test `format_duration()`, `--tools` output, wallclock display in `--agents` and `--costs`. |

## Files unchanged

- `orchestrator/telemetry.py` — events table already handles arbitrary
  event types, no changes needed.
- `orchestrator/state.py` — graph state unchanged.
- `orchestrator/graph.py` — no routing changes.
- `RalphResult` dataclass — `.output` stays as a string (extracted text
  from JSON), so developer node and agent_runs storage are unaffected.

## Risks

**JSONL output format.** The `claude` CLI's `stream-json` format may
change between versions. Mitigated by: graceful fallback to raw stdout
on parse failure, tests against documented structure, isolated parser
function.

**completion_promise detection.** Currently scans raw stdout. After this
change, scans the `result` field from the final JSONL line. If the promise
string only appears in tool output (not in the agent's final response),
detection changes. In practice `completion_promise` is a phrase the agent
writes deliberately, so this is low risk.

## Out of scope

- AdvisorAgent tool use (separate roadmap item, highest priority)
- Cost estimation / budget caps (separate roadmap item)
- Web dashboard (separate roadmap item)
- Per-iteration token tracking from CLI agents (could be added later
  using the same JSON parsing, but not in this PR)
