# AdvisorAgent Tool Use — Codebase Access for Strategic Agents

## Problem

Workflow agents (product_owner, architect, designer, reviewer, QA) use the Anthropic API via AdvisorAgent — a single request/response with no tool access. They carry sophisticated methodology knowledge bases but are operationally blind: they cannot read project files, search code, or inspect existing architecture.

In the Inkwell and scaffold self-hosted test runs, this blindness caused:

- **Overlapping decomposition**: The product owner split the API cost tracking spec into 3 features that all independently implemented the same changes to the same files, because it couldn't see the existing code structure.
- **Uninformed architecture**: The architect designed without seeing what modules, patterns, and dependencies already existed.
- **Excessive review cycles**: The reviewer sent work back 3 times partly because it couldn't cross-reference the implementation against the broader codebase.
- **Wasted budget**: Overlapping features consumed ~$5 of budget to produce ~$1.50 of useful work.

The ROADMAP ranks "AdvisorAgent tool use" as the highest-impact improvement (score 5.0).

## Requirements

1. **Multi-turn tool loop in AdvisorAgent** — When tool definitions are provided, `AdvisorAgent.call()` enters a conversation loop: send request → execute tool calls → return results → repeat until the model produces a final text response. When no tools are provided, behavior is unchanged (single-shot).

2. **Codebase access tools** — Three read-only tools scoped to the target repository:
   - `read_file` — Read a file by path, with optional offset/limit for large files
   - `list_directory` — List files and directories at a path
   - `grep` — Search for a pattern across files, returning matching lines with file:line context

3. **Per-role tool assignment** — Each workflow node that uses AdvisorAgent passes the appropriate tool set:
   - product_owner, architect, designer: all three codebase tools
   - consensus: no tools (adjudicates arguments, doesn't need codebase access)
   - reviewer, QA: not applicable (these use DoerAgent/CLI and already have codebase access)

4. **Accurate cost tracking across turns** — `AgentResult` must report cumulative `token_in`, `token_out`, and `cost_usd` across all turns in the loop. Budget checks use the aggregate cost.

5. **Tool call observability** — Emit `tool.call` events from the AdvisorAgent loop using the same event type that DoerAgent already emits, so tool usage appears in `scaffold report --tools`.

6. **Safety constraints** — Tools are read-only, repo-scoped (reject path traversal outside `repo_path`), and bounded (max file lines, max grep results, max conversation turns).

## Architecture

### New module: `orchestrator/tools.py`

Contains tool definitions (Anthropic API format), implementations (plain Python functions), and an executor that dispatches tool calls.

```python
# Tool implementations — all take repo_path as first arg for scoping
def read_file(repo_path: str, file_path: str, offset: int = 0, limit: int = 500) -> str
def list_directory(repo_path: str, path: str = ".") -> str
def grep(repo_path: str, pattern: str, path: str = ".", max_results: int = 50) -> str

# Tool definitions — Anthropic API format dicts
CODEBASE_TOOLS: list[dict]  # [read_file_def, list_directory_def, grep_def]

# Executor — routes tool name to implementation, binds repo_path
def execute_tool(name: str, inputs: dict, repo_path: str) -> str
```

**Path safety**: `read_file` and `list_directory` resolve the requested path relative to `repo_path` and reject any result that falls outside it (via `Path.resolve()` comparison). `grep` runs `grep -rn` as a subprocess, scoped to `repo_path`.

**Bounding**: `read_file` defaults to 500 lines max per call. `grep` defaults to 50 results max. These prevent context window blowout from large files or broad searches.

### Modify: `orchestrator/nodes/base.py` — AdvisorAgent

`AdvisorAgent.call()` gains two optional parameters:

```python
def call(
    self,
    system_prompt: str,
    user_message: str,
    cache_system: bool = False,
    tools: list[dict] | None = None,           # NEW
    tool_executor: Callable | None = None,      # NEW
    max_turns: int = 25,                        # NEW
) -> AgentResult:
```

When `tools` is provided, the method enters a loop:

1. Call `client.messages.create()` with `tools=tools`
2. Check `response.stop_reason`:
   - If `"tool_use"`: extract tool call blocks, call `tool_executor(name, inputs)` for each, build `tool_result` content blocks, append assistant + user messages, loop back to step 1
   - If `"end_of_turn"`: extract the final text, return `AgentResult`
3. If turn count exceeds `max_turns`, return whatever text has been produced

Token accounting: accumulate `input_tokens` and `output_tokens` across all turns. Compute `cost_usd` from the totals.

When `tools` is None, the method executes exactly as today — single API call, no loop.

### Modify: workflow nodes

Each of the three API-based workflow nodes (product_owner, architect, designer) gains `repo_path` in its factory function signature. The node:

1. Imports `CODEBASE_TOOLS` and `execute_tool` from `orchestrator/tools`
2. Creates a bound executor: `executor = functools.partial(execute_tool, repo_path=repo_path)`
3. Passes `tools=CODEBASE_TOOLS, tool_executor=executor` to `advisor.call()`

The consensus node is unchanged — no tools.

### Modify: `orchestrator/graph.py`

Pass `repo_path` to `make_product_owner_node()`, `make_architect_node()`, and `make_designer_node()`. The value is already available in `build_graph()`. Reviewer and QA are CLI-based and unchanged.

### Observability

Inside the AdvisorAgent tool loop, after executing each tool call:

```python
bus = get_bus()
if bus:
    bus.tool_call(self.role, tool_name, task_id)
```

This requires passing `task_id` into `AdvisorAgent.call()`. Add it as an optional parameter (default `""`), passed by each node from `state["task_id"]`.

## Tool Definitions

### read_file

```json
{
  "name": "read_file",
  "description": "Read the contents of a file in the project repository. Returns numbered lines. Use offset and limit for large files.",
  "input_schema": {
    "type": "object",
    "properties": {
      "file_path": {
        "type": "string",
        "description": "Path relative to the repository root"
      },
      "offset": {
        "type": "integer",
        "description": "Line number to start reading from (0-based). Default: 0",
        "default": 0
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of lines to read. Default: 500",
        "default": 500
      }
    },
    "required": ["file_path"]
  }
}
```

### list_directory

```json
{
  "name": "list_directory",
  "description": "List files and directories at a path in the project repository. Returns entries with type indicators (dir/ or file).",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Directory path relative to the repository root. Default: root",
        "default": "."
      }
    },
    "required": []
  }
}
```

### grep

```json
{
  "name": "grep",
  "description": "Search for a text pattern across files in the project repository. Returns matching lines with file:line_number prefix.",
  "input_schema": {
    "type": "object",
    "properties": {
      "pattern": {
        "type": "string",
        "description": "Search pattern (grep basic regex)"
      },
      "path": {
        "type": "string",
        "description": "Directory or file to search within, relative to repo root. Default: entire repo",
        "default": "."
      },
      "max_results": {
        "type": "integer",
        "description": "Maximum number of matching lines to return. Default: 50",
        "default": 50
      }
    },
    "required": ["pattern"]
  }
}
```

## Safety

- **Read-only**: No tool can modify files, run arbitrary commands, or write to disk.
- **Repo-scoped**: All paths are resolved relative to `repo_path`. Traversal attempts (`../../etc/passwd`) are rejected with an error message.
- **Bounded**: File reads capped at 500 lines, grep at 50 results, conversation at 25 turns. All configurable per call.
- **Subprocess safety**: `grep` uses `subprocess.run()` with explicit argument lists (no shell=True). The pattern is passed as a positional argument, not interpolated into a shell string.
- **Error handling**: Tool failures (file not found, permission denied, invalid path) return error text to the model rather than raising exceptions — the model can recover and try a different approach.

## Cost Impact

Tool-using agents will consume more tokens per invocation (multiple API turns vs one). Based on the test run, strategic agents currently use ~200-800 input tokens and ~300-900 output tokens per call. With tool use, expect 3-10x more tokens per invocation as the agent explores the codebase.

This is acceptable because:
- Strategic agents run once per task (not in a loop like DoerAgent)
- Better-informed decisions reduce downstream waste (fewer review cycles, no overlapping features)
- The existing budget system tracks cumulative cost across all turns
- The max_turns cap (25) prevents runaway exploration

## Constraints

- Must not break existing behavior when no tools are passed
- Must not require changes to specialist agents (DoerAgent) or their prompts
- Tool implementations must not make network calls (web search is deferred)
- Tests must not make real API calls — mock the Anthropic client
- Path traversal protection must be tested explicitly

## Files

| File | Action | Purpose |
|------|--------|---------|
| `orchestrator/tools.py` | Create | Tool definitions, implementations, executor |
| `orchestrator/nodes/base.py` | Modify | AdvisorAgent tool loop, task_id parameter |
| `orchestrator/nodes/product_owner.py` | Modify | Pass tools + repo_path |
| `orchestrator/nodes/architect.py` | Modify | Pass tools + repo_path |
| `orchestrator/nodes/designer.py` | Modify | Pass tools + repo_path |
| `orchestrator/graph.py` | Modify | Pass repo_path to PO, architect, designer node factories |
| `tests/test_tools.py` | Create | Tool implementation tests (path safety, read, grep, list) |
| `tests/test_advisor_base.py` | Modify | Tool loop tests (single turn, multi-turn, max turns, cost aggregation) |
| `tests/test_product_owner.py` | Modify | Verify tools are passed |
| `tests/test_architect.py` | Modify | Verify tools are passed |
| `tests/test_designer.py` | Modify | Verify tools are passed |
| `tests/test_graph.py` | Modify | Verify repo_path passed to new node factories |
| `ROADMAP.md` | Modify | Mark "AdvisorAgent tool use" as Done |
