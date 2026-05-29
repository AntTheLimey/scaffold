# AdvisorAgent Tool Use Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give strategic workflow agents (product_owner, architect, designer) read-only codebase access via a multi-turn tool loop in AdvisorAgent, so they can make informed decisions.

**Architecture:** Extend `AdvisorAgent.call()` with optional `tools`, `tool_executor`, `task_id`, and `max_turns` parameters. When tools are provided, the method enters a conversation loop — calling the API, executing tool calls, feeding results back — until the model produces a final text response. Tool implementations live in a new `orchestrator/tools.py` module with three read-only, repo-scoped, bounded tools: `read_file`, `list_directory`, `grep`.

**Tech Stack:** Python 3.12, Anthropic SDK (`client.messages.create` with `tools` param), subprocess (for grep), pathlib (for path safety)

**Spec:** `docs/specs/advisor-tool-use.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `orchestrator/tools.py` | Create | Tool definitions (Anthropic format), implementations, `execute_tool` dispatcher |
| `orchestrator/nodes/base.py` | Modify | AdvisorAgent tool loop, `task_id`/`tools`/`tool_executor`/`max_turns` params |
| `orchestrator/nodes/product_owner.py` | Modify | Pass `repo_path`, tools + executor to `advisor.call()` |
| `orchestrator/nodes/architect.py` | Modify | Pass `repo_path`, tools + executor to `advisor.call()` |
| `orchestrator/nodes/designer.py` | Modify | Pass `repo_path`, tools + executor to `advisor.call()` |
| `orchestrator/graph.py` | Modify | Pass `repo_path` to PO, architect, designer factory functions |
| `tests/test_tools.py` | Create | Tool implementation + path safety tests |
| `tests/test_advisor_base.py` | Modify | Tool loop tests (single turn, multi-turn, max turns, cost aggregation, observability) |
| `tests/test_product_owner.py` | Modify | Verify tools are passed to `advisor.call()` |
| `tests/test_architect.py` | Modify | Verify tools are passed to `advisor.call()` |
| `tests/test_designer.py` | Modify | Verify tools are passed to `advisor.call()` |
| `tests/test_graph.py` | Modify | Verify `repo_path` passed to PO, architect, designer factories |

---

### Task 1: Create `orchestrator/tools.py` — Tool Implementations

**Files:**
- Create: `orchestrator/tools.py`
- Create: `tests/test_tools.py`

This task builds all three tool implementations, the Anthropic-format tool definitions, and the `execute_tool` dispatcher. All tools are read-only, repo-scoped, and bounded.

- [ ] **Step 1: Write tests for `read_file`**

Create `tests/test_tools.py`:

```python
import os
from pathlib import Path

import pytest

from orchestrator.tools import execute_tool, read_file


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "hello.py").write_text("line1\nline2\nline3\nline4\nline5\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.txt").write_text("nested content\n")
    return tmp_path


def test_read_file_returns_numbered_lines(repo):
    result = read_file(str(repo), "hello.py")
    assert "1\tline1" in result
    assert "5\tline5" in result


def test_read_file_offset_and_limit(repo):
    result = read_file(str(repo), "hello.py", offset=2, limit=2)
    assert "3\tline3" in result
    assert "4\tline4" in result
    assert "1\tline1" not in result
    assert "5\tline5" not in result


def test_read_file_nested(repo):
    result = read_file(str(repo), "sub/nested.txt")
    assert "nested content" in result


def test_read_file_not_found(repo):
    result = read_file(str(repo), "nope.py")
    assert "not found" in result.lower() or "error" in result.lower()


def test_read_file_path_traversal_blocked(repo):
    result = read_file(str(repo), "../../etc/passwd")
    assert "outside" in result.lower() or "error" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'orchestrator.tools'`

- [ ] **Step 3: Implement `read_file`**

Create `orchestrator/tools.py`:

```python
import subprocess
from pathlib import Path


def _resolve_safe(repo_path: str, relative: str) -> Path | str:
    """Resolve a relative path within repo_path. Returns error string if outside repo."""
    base = Path(repo_path).resolve()
    target = (base / relative).resolve()
    if not str(target).startswith(str(base)):
        return f"Error: path '{relative}' is outside the repository"
    return target


def read_file(repo_path: str, file_path: str, offset: int = 0, limit: int = 500) -> str:
    resolved = _resolve_safe(repo_path, file_path)
    if isinstance(resolved, str):
        return resolved
    if not resolved.is_file():
        return f"Error: file not found: {file_path}"
    lines = resolved.read_text().splitlines()
    selected = lines[offset : offset + limit]
    numbered = [f"{offset + i + 1}\t{line}" for i, line in enumerate(selected)]
    return "\n".join(numbered)
```

- [ ] **Step 4: Run `read_file` tests to verify they pass**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_tools.py::test_read_file_returns_numbered_lines tests/test_tools.py::test_read_file_offset_and_limit tests/test_tools.py::test_read_file_nested tests/test_tools.py::test_read_file_not_found tests/test_tools.py::test_read_file_path_traversal_blocked -v`
Expected: 5 passed

- [ ] **Step 5: Write tests for `list_directory`**

Append to `tests/test_tools.py`:

```python
from orchestrator.tools import list_directory


def test_list_directory_root(repo):
    result = list_directory(str(repo))
    assert "hello.py" in result
    assert "sub/" in result


def test_list_directory_subdir(repo):
    result = list_directory(str(repo), "sub")
    assert "nested.txt" in result


def test_list_directory_not_found(repo):
    result = list_directory(str(repo), "nope")
    assert "not found" in result.lower() or "error" in result.lower()


def test_list_directory_path_traversal_blocked(repo):
    result = list_directory(str(repo), "../../")
    assert "outside" in result.lower() or "error" in result.lower()
```

- [ ] **Step 6: Implement `list_directory`**

Add to `orchestrator/tools.py`:

```python
def list_directory(repo_path: str, path: str = ".") -> str:
    resolved = _resolve_safe(repo_path, path)
    if isinstance(resolved, str):
        return resolved
    if not resolved.is_dir():
        return f"Error: directory not found: {path}"
    entries = sorted(resolved.iterdir())
    lines = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{entry.name}{suffix}")
    return "\n".join(lines)
```

- [ ] **Step 7: Run `list_directory` tests**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_tools.py -k list_directory -v`
Expected: 4 passed

- [ ] **Step 8: Write tests for `grep`**

Append to `tests/test_tools.py`:

```python
from orchestrator.tools import grep


def test_grep_finds_pattern(repo):
    result = grep(str(repo), "line3")
    assert "hello.py" in result
    assert "line3" in result


def test_grep_respects_path(repo):
    result = grep(str(repo), "content", path="sub")
    assert "nested.txt" in result


def test_grep_max_results(repo):
    # Write a file with many matches
    (repo / "many.txt").write_text("\n".join(f"match {i}" for i in range(100)))
    result = grep(str(repo), "match", max_results=5)
    assert result.count("\n") <= 5


def test_grep_no_matches(repo):
    result = grep(str(repo), "zzzznotfound")
    assert result == "" or "no matches" in result.lower()


def test_grep_path_traversal_blocked(repo):
    result = grep(str(repo), "root", path="../../etc")
    assert "outside" in result.lower() or "error" in result.lower()
```

- [ ] **Step 9: Implement `grep`**

Add to `orchestrator/tools.py`:

```python
def grep(repo_path: str, pattern: str, path: str = ".", max_results: int = 50) -> str:
    resolved = _resolve_safe(repo_path, path)
    if isinstance(resolved, str):
        return resolved
    if not resolved.exists():
        return f"Error: path not found: {path}"
    cmd = ["grep", "-rn", "--include=*", pattern, str(resolved)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    lines = result.stdout.splitlines()[:max_results]
    base = Path(repo_path).resolve()
    output = []
    for line in lines:
        # Make paths relative to repo
        if str(base) in line:
            line = line.replace(str(base) + "/", "")
        output.append(line)
    return "\n".join(output)
```

- [ ] **Step 10: Run `grep` tests**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_tools.py -k grep -v`
Expected: 5 passed

- [ ] **Step 11: Write tests for `execute_tool` and `CODEBASE_TOOLS`**

Append to `tests/test_tools.py`:

```python
from orchestrator.tools import CODEBASE_TOOLS, execute_tool


def test_execute_tool_dispatches_read_file(repo):
    result = execute_tool("read_file", {"file_path": "hello.py"}, str(repo))
    assert "line1" in result


def test_execute_tool_dispatches_list_directory(repo):
    result = execute_tool("list_directory", {"path": "."}, str(repo))
    assert "hello.py" in result


def test_execute_tool_dispatches_grep(repo):
    result = execute_tool("grep", {"pattern": "line1"}, str(repo))
    assert "hello.py" in result


def test_execute_tool_unknown_tool(repo):
    result = execute_tool("delete_everything", {}, str(repo))
    assert "unknown" in result.lower() or "error" in result.lower()


def test_codebase_tools_has_three_definitions():
    assert len(CODEBASE_TOOLS) == 3
    names = {t["name"] for t in CODEBASE_TOOLS}
    assert names == {"read_file", "list_directory", "grep"}


def test_codebase_tools_have_input_schema():
    for tool in CODEBASE_TOOLS:
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
```

- [ ] **Step 12: Implement `execute_tool` and `CODEBASE_TOOLS`**

Add to `orchestrator/tools.py`:

```python
CODEBASE_TOOLS: list[dict] = [
    {
        "name": "read_file",
        "description": (
            "Read the contents of a file in the project repository. "
            "Returns numbered lines. Use offset and limit for large files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path relative to the repository root",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-based). Default: 0",
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read. Default: 500",
                    "default": 500,
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "list_directory",
        "description": (
            "List files and directories at a path in the project repository. "
            "Returns entries with type indicators (dir/ or file)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to the repository root. Default: root",
                    "default": ".",
                },
            },
            "required": [],
        },
    },
    {
        "name": "grep",
        "description": (
            "Search for a text pattern across files in the project repository. "
            "Returns matching lines with file:line_number prefix."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (grep basic regex)",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search within, relative to repo root. Default: entire repo",
                    "default": ".",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matching lines to return. Default: 50",
                    "default": 50,
                },
            },
            "required": ["pattern"],
        },
    },
]

_TOOL_DISPATCH = {
    "read_file": lambda inputs, rp: read_file(rp, **inputs),
    "list_directory": lambda inputs, rp: list_directory(rp, **inputs),
    "grep": lambda inputs, rp: grep(rp, **inputs),
}


def execute_tool(name: str, inputs: dict, repo_path: str) -> str:
    handler = _TOOL_DISPATCH.get(name)
    if handler is None:
        return f"Error: unknown tool '{name}'"
    try:
        return handler(inputs, repo_path)
    except Exception as exc:
        return f"Error executing {name}: {exc}"
```

- [ ] **Step 13: Run all tool tests**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_tools.py -v`
Expected: 20 passed

- [ ] **Step 14: Commit**

```bash
git add orchestrator/tools.py tests/test_tools.py
git commit -m "feat: add read_file, list_directory, grep codebase tools

Three read-only, repo-scoped, bounded tools for AdvisorAgent
to explore target repositories. Includes execute_tool dispatcher
and Anthropic-format CODEBASE_TOOLS definitions."
```

---

### Task 2: Extend `AdvisorAgent.call()` with Multi-Turn Tool Loop

**Files:**
- Modify: `orchestrator/nodes/base.py:64-100`
- Modify: `tests/test_advisor_base.py`

This task adds `tools`, `tool_executor`, `task_id`, and `max_turns` parameters to `AdvisorAgent.call()`. When tools are provided, the method loops: call API → execute tool calls → feed results → repeat until the model stops calling tools or `max_turns` is reached. Token accounting is cumulative. Tool calls emit `tool.call` events.

- [ ] **Step 1: Write test for single-shot behavior unchanged (no tools)**

Add to `tests/test_advisor_base.py`:

```python
def test_advisor_call_without_tools_unchanged(mock_client):
    """Existing single-shot behavior is preserved when no tools are passed."""
    agent = AdvisorAgent(role="architect", model="claude-opus-4-6", client=mock_client)
    result = agent.call(system_prompt="Design.", user_message="Design the schema.")
    assert result.text == "Here is my analysis."
    # Single API call, no loop
    assert mock_client.messages.create.call_count == 1
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "tools" not in call_kwargs
```

- [ ] **Step 2: Run test — should pass with current code**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py::test_advisor_call_without_tools_unchanged -v`
Expected: PASS (existing behavior)

- [ ] **Step 3: Write test for single-turn tool use (model calls one tool, then responds)**

Add to `tests/test_advisor_base.py`:

```python
from unittest.mock import MagicMock, call

import pytest

from orchestrator.nodes.base import AdvisorAgent, AgentResult


def _make_tool_use_response(tool_name, tool_id, tool_input, token_in=300, token_out=100):
    """Build a mock response where the model calls a tool."""
    response = MagicMock()
    response.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.id = tool_id
    tool_block.input = tool_input
    response.content = [tool_block]
    response.usage.input_tokens = token_in
    response.usage.output_tokens = token_out
    return response


def _make_text_response(text, token_in=200, token_out=150):
    """Build a mock response where the model gives a final text answer."""
    response = MagicMock()
    response.stop_reason = "end_of_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    response.content = [text_block]
    response.usage.input_tokens = token_in
    response.usage.output_tokens = token_out
    return response


def test_advisor_single_turn_tool_use():
    client = MagicMock()
    # Turn 1: model calls read_file. Turn 2: model gives text response.
    client.messages.create.side_effect = [
        _make_tool_use_response("read_file", "tool_1", {"file_path": "main.py"}),
        _make_text_response("The codebase uses Flask."),
    ]
    executor = MagicMock(return_value="1\timport flask\n2\tapp = Flask(__name__)")
    tools = [{"name": "read_file", "input_schema": {}}]

    agent = AdvisorAgent(role="architect", model="claude-opus-4-6", client=client)
    result = agent.call(
        system_prompt="Design.",
        user_message="What framework is used?",
        tools=tools,
        tool_executor=executor,
    )
    assert result.text == "The codebase uses Flask."
    assert client.messages.create.call_count == 2
    executor.assert_called_once_with("read_file", {"file_path": "main.py"})
    # Cumulative tokens: 300+200 in, 100+150 out
    assert result.token_in == 500
    assert result.token_out == 250
```

- [ ] **Step 4: Run test — should fail (no tools param yet)**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py::test_advisor_single_turn_tool_use -v`
Expected: FAIL — `TypeError: AdvisorAgent.call() got an unexpected keyword argument 'tools'`

- [ ] **Step 5: Implement the tool loop in `AdvisorAgent.call()`**

Modify `orchestrator/nodes/base.py`. Replace the `AdvisorAgent.call()` method (lines 70–100) with:

```python
    def call(
        self,
        system_prompt: str,
        user_message: str,
        cache_system: bool = False,
        tools: list[dict] | None = None,
        tool_executor: callable | None = None,
        task_id: str = "",
        max_turns: int = 25,
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

        messages = [{"role": "user", "content": user_message}]

        if tools is None:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages,
            )
            token_in = response.usage.input_tokens
            token_out = response.usage.output_tokens
            return AgentResult(
                text=response.content[0].text,
                token_in=token_in,
                token_out=token_out,
                cost_usd=cost_for_tokens(self.model, token_in, token_out),
            )

        total_in = 0
        total_out = 0
        bus = get_bus()
        for _turn in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages,
                tools=tools,
            )
            total_in += response.usage.input_tokens
            total_out += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                text = ""
                for block in response.content:
                    if getattr(block, "type", None) == "text":
                        text = block.text
                        break
                return AgentResult(
                    text=text,
                    token_in=total_in,
                    token_out=total_out,
                    cost_usd=cost_for_tokens(self.model, total_in, total_out),
                )

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                output = tool_executor(block.name, block.input)
                if bus:
                    bus.tool_call(self.role, block.name, task_id)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        text = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text = block.text
                break
        return AgentResult(
            text=text,
            token_in=total_in,
            token_out=total_out,
            cost_usd=cost_for_tokens(self.model, total_in, total_out),
        )
```

- [ ] **Step 6: Run single-turn tool test**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py::test_advisor_single_turn_tool_use -v`
Expected: PASS

- [ ] **Step 7: Run all existing advisor tests to verify no regression**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py -v`
Expected: All PASS (including the new `test_advisor_call_without_tools_unchanged`)

- [ ] **Step 8: Write test for multi-turn tool use**

Add to `tests/test_advisor_base.py`:

```python
def test_advisor_multi_turn_tool_use():
    client = MagicMock()
    # Turn 1: list_directory. Turn 2: read_file. Turn 3: final text.
    client.messages.create.side_effect = [
        _make_tool_use_response("list_directory", "t1", {"path": "."}),
        _make_tool_use_response("read_file", "t2", {"file_path": "app.py"}, token_in=400, token_out=120),
        _make_text_response("Architecture looks good.", token_in=500, token_out=300),
    ]
    executor = MagicMock(side_effect=["app.py\nlib/", "1\timport os"])
    tools = [{"name": "list_directory", "input_schema": {}}, {"name": "read_file", "input_schema": {}}]

    agent = AdvisorAgent(role="architect", model="claude-opus-4-6", client=client)
    result = agent.call(
        system_prompt="Design.",
        user_message="Review the architecture.",
        tools=tools,
        tool_executor=executor,
    )
    assert result.text == "Architecture looks good."
    assert client.messages.create.call_count == 3
    assert executor.call_count == 2
    # Cumulative: 300+400+500=1200 in, 100+120+300=520 out
    assert result.token_in == 1200
    assert result.token_out == 520
```

- [ ] **Step 9: Run multi-turn test**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py::test_advisor_multi_turn_tool_use -v`
Expected: PASS

- [ ] **Step 10: Write test for max_turns cap**

Add to `tests/test_advisor_base.py`:

```python
def test_advisor_max_turns_cap():
    client = MagicMock()
    # Model keeps calling tools forever — cap at 2 turns
    client.messages.create.return_value = _make_tool_use_response(
        "grep", "t1", {"pattern": "TODO"}
    )
    executor = MagicMock(return_value="main.py:5:TODO fix this")
    tools = [{"name": "grep", "input_schema": {}}]

    agent = AdvisorAgent(role="product_owner", model="claude-opus-4-6", client=client)
    result = agent.call(
        system_prompt="Decompose.",
        user_message="Find TODOs.",
        tools=tools,
        tool_executor=executor,
        max_turns=2,
    )
    assert client.messages.create.call_count == 2
    # Returns whatever text is available (empty string if model never produced text)
    assert isinstance(result.text, str)
```

- [ ] **Step 11: Run max_turns test**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py::test_advisor_max_turns_cap -v`
Expected: PASS

- [ ] **Step 12: Write test for tool call observability events**

Add to `tests/test_advisor_base.py`:

```python
from unittest.mock import patch


def test_advisor_tool_loop_emits_tool_call_events():
    client = MagicMock()
    client.messages.create.side_effect = [
        _make_tool_use_response("read_file", "t1", {"file_path": "a.py"}),
        _make_tool_use_response("grep", "t2", {"pattern": "import"}),
        _make_text_response("Done."),
    ]
    executor = MagicMock(return_value="content")
    tools = [{"name": "read_file", "input_schema": {}}, {"name": "grep", "input_schema": {}}]
    mock_bus = MagicMock()

    with patch("orchestrator.nodes.base.get_bus", return_value=mock_bus):
        agent = AdvisorAgent(role="architect", model="claude-opus-4-6", client=client)
        agent.call(
            system_prompt="Design.",
            user_message="Check imports.",
            tools=tools,
            tool_executor=executor,
            task_id="feat-001",
        )

    tool_calls = [c for c in mock_bus.tool_call.call_args_list]
    assert len(tool_calls) == 2
    assert tool_calls[0] == call("architect", "read_file", "feat-001")
    assert tool_calls[1] == call("architect", "grep", "feat-001")
```

- [ ] **Step 13: Run observability test**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py::test_advisor_tool_loop_emits_tool_call_events -v`
Expected: PASS

- [ ] **Step 14: Write test for cost aggregation across turns**

Add to `tests/test_advisor_base.py`:

```python
def test_advisor_tool_loop_cost_aggregation():
    client = MagicMock()
    client.messages.create.side_effect = [
        _make_tool_use_response("read_file", "t1", {"file_path": "a.py"}, token_in=1000, token_out=500),
        _make_text_response("Analysis complete.", token_in=2000, token_out=800),
    ]
    executor = MagicMock(return_value="file content")
    tools = [{"name": "read_file", "input_schema": {}}]

    agent = AdvisorAgent(role="product_owner", model="claude-opus-4-6", client=client)
    result = agent.call(
        system_prompt="Decompose.",
        user_message="Analyze.",
        tools=tools,
        tool_executor=executor,
    )
    assert result.token_in == 3000
    assert result.token_out == 1300
    # claude-opus-4-6: $15/$75 per MTok
    expected_cost = (3000 * 15.0 + 1300 * 75.0) / 1_000_000
    assert result.cost_usd == pytest.approx(expected_cost)
```

- [ ] **Step 15: Run cost test**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py::test_advisor_tool_loop_cost_aggregation -v`
Expected: PASS

- [ ] **Step 16: Run full advisor test suite**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_advisor_base.py -v`
Expected: All PASS

- [ ] **Step 17: Commit**

```bash
git add orchestrator/nodes/base.py tests/test_advisor_base.py
git commit -m "feat: add multi-turn tool loop to AdvisorAgent

When tools are provided, AdvisorAgent.call() enters a conversation
loop: call API, execute tools, feed results back, repeat until the
model produces a final text response or max_turns is reached.
Cumulative token accounting and tool.call event emission."
```

---

### Task 3: Wire Tools into Workflow Nodes

**Files:**
- Modify: `orchestrator/nodes/product_owner.py`
- Modify: `orchestrator/nodes/architect.py`
- Modify: `orchestrator/nodes/designer.py`
- Modify: `orchestrator/graph.py`
- Modify: `tests/test_product_owner.py`
- Modify: `tests/test_architect.py`
- Modify: `tests/test_designer.py`
- Modify: `tests/test_graph.py`

Each of the three workflow nodes gains a `repo_path` parameter and passes `tools=CODEBASE_TOOLS`, `tool_executor=partial(execute_tool, repo_path=repo_path)`, and `task_id=state["task_id"]` to `advisor.call()`. The graph passes `repo_path` to each factory.

- [ ] **Step 1: Write test for product_owner passing tools**

Add to `tests/test_product_owner.py`:

```python
def test_product_owner_passes_tools_to_advisor(mock_client, mock_agent_loader):
    node_fn = make_node(mock_client, mock_agent_loader, repo_path="/tmp/repo")
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "tools" in call_args.kwargs
    tool_names = {t["name"] for t in call_args.kwargs["tools"]}
    assert tool_names == {"read_file", "list_directory", "grep"}
```

- [ ] **Step 2: Run test — should fail (no repo_path param yet)**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_product_owner.py::test_product_owner_passes_tools_to_advisor -v`
Expected: FAIL — `TypeError: make_product_owner_node() got an unexpected keyword argument 'repo_path'`

- [ ] **Step 3: Modify `product_owner.py`**

Update `orchestrator/nodes/product_owner.py`:
- Add import: `import functools` and `from orchestrator.tools import CODEBASE_TOOLS, execute_tool`
- Add `repo_path: str` parameter to `make_product_owner_node()`
- In `product_owner_node()`, create the executor and pass tools to `advisor.call()`:

```python
import functools
from pathlib import Path

from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.json_utils import extract_json
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState
from orchestrator.tools import CODEBASE_TOOLS, execute_tool

SYSTEM_PROMPT = (
    "You are a product decomposition engine. You break master specifications "
    "into discrete, implementable work items. You define acceptance criteria "
    "for each item. You never prescribe implementation details — that is the "
    "Architect's job. You never write code.\n\n"
    "Output valid JSON with a single key 'children', containing a list of objects. "
    "Each object has: title (str), level ('feature' or 'task'), spec_ref (str), "
    "acceptance (list[str])."
)


def make_product_owner_node(
    client,
    spec_path: str,
    agent_loader: AgentLoader,
    model: str = "claude-opus-4-6",
    scaffold_budget_usd: float | None = None,
    repo_path: str = "",
):
    agent = AdvisorAgent(
        role="product_owner",
        model=model,
        client=client,
    )
    tool_executor = functools.partial(execute_tool, repo_path=repo_path) if repo_path else None
    tools = CODEBASE_TOOLS if repo_path else None

    def product_owner_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("product_owner", state["task_id"], state["level"])
        system_prompt = agent_loader.load_workflow_agent("product_owner")
        if not system_prompt:
            system_prompt = SYSTEM_PROMPT
        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

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

        if bus:
            bus.api_call_start(
                "product_owner", model, len(system_prompt) + len(user_message), state["task_id"]
            )
        result = agent.call(
            system_prompt=system_prompt,
            user_message=user_message,
            cache_system=True,
            tools=tools,
            tool_executor=tool_executor,
            task_id=state["task_id"],
        )
        if bus:
            bus.api_call_done(
                "product_owner", model, result.token_in, result.token_out, state["task_id"]
            )
            if scaffold_budget_usd is not None:
                bus.check_budget(scaffold_budget_usd)

        parsed = extract_json(result.text)
        children = parsed.get("children", [])
        if bus:
            bus.node_exit("product_owner", state["task_id"], f"{len(children)} children decomposed")
        return {
            "child_tasks": children,
            "status": "decomposing",
            "agent_output": result.text,
        }

    return product_owner_node
```

- [ ] **Step 4: Update `make_node` helper in test and run**

Update the `make_node` helper in `tests/test_product_owner.py` to pass `repo_path`:

```python
def make_node(mock_client, mock_agent_loader, spec_path="/tmp/spec.md", repo_path="/tmp/repo", **kwargs):
    return make_product_owner_node(
        mock_client, spec_path=spec_path, agent_loader=mock_agent_loader, repo_path=repo_path, **kwargs
    )
```

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_product_owner.py -v`
Expected: All PASS (including new tool test)

- [ ] **Step 5: Write test for architect passing tools**

Add to `tests/test_architect.py`:

```python
def test_architect_passes_tools_to_advisor(mock_client, mock_agent_loader):
    node_fn = make_architect_node(mock_client, mock_agent_loader, repo_path="/tmp/repo")
    state = initial_state(task_id="feat-001", level="feature")
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "tools" in call_args.kwargs
    tool_names = {t["name"] for t in call_args.kwargs["tools"]}
    assert tool_names == {"read_file", "list_directory", "grep"}
```

- [ ] **Step 6: Modify `architect.py`**

Update `orchestrator/nodes/architect.py` with the same pattern as product_owner:
- Add imports: `import functools`, `from orchestrator.tools import CODEBASE_TOOLS, execute_tool`
- Add `repo_path: str = ""` parameter to `make_architect_node()`
- Create executor and pass tools/executor/task_id to `advisor.call()`

```python
import functools

from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.json_utils import extract_json
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState
from orchestrator.tools import CODEBASE_TOOLS, execute_tool

SYSTEM_PROMPT = (
    "You are a technical architecture engine. You produce data models, API contracts, "
    "component boundaries, and file structure. You approve or reject technical approaches. "
    "You never write implementation code — that is the Developer's job.\n\n"
    "Output valid JSON with keys: technical_design (str), has_ui_component (bool), "
    "children (list of {title, level, spec_ref, acceptance})."
)


def make_architect_node(
    client,
    agent_loader: AgentLoader,
    model: str = "claude-opus-4-6",
    scaffold_budget_usd: float | None = None,
    repo_path: str = "",
):
    agent = AdvisorAgent(
        role="architect",
        model=model,
        client=client,
    )
    tool_executor = functools.partial(execute_tool, repo_path=repo_path) if repo_path else None
    tools = CODEBASE_TOOLS if repo_path else None

    def architect_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("architect", state["task_id"], state["level"])
        system_prompt = agent_loader.load_workflow_agent("architect")
        if not system_prompt:
            system_prompt = SYSTEM_PROMPT
        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        user_message = (
            f"Design the technical approach for this feature.\n\n"
            f"Task: {state['task_id']}\n"
            f"Level: {state['level']}\n"
        )

        if bus:
            bus.api_call_start(
                "architect", model, len(system_prompt) + len(user_message), state["task_id"]
            )
        result = agent.call(
            system_prompt=system_prompt,
            user_message=user_message,
            cache_system=True,
            tools=tools,
            tool_executor=tool_executor,
            task_id=state["task_id"],
        )
        if bus:
            bus.api_call_done(
                "architect", model, result.token_in, result.token_out, state["task_id"]
            )
            if scaffold_budget_usd is not None:
                bus.check_budget(scaffold_budget_usd)

        parsed = extract_json(result.text)
        output = {
            "has_ui_component": parsed.get("has_ui_component", False),
            "child_tasks": parsed.get("children", []),
            "status": "decomposing",
            "agent_output": result.text,
        }
        if bus:
            bus.node_exit(
                "architect",
                state["task_id"],
                f"has_ui={output['has_ui_component']} children={len(output['child_tasks'])}",
            )
        return output

    return architect_node
```

- [ ] **Step 7: Run architect tests**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_architect.py -v`
Expected: All PASS

- [ ] **Step 8: Write test for designer passing tools**

Add to `tests/test_designer.py`:

```python
def test_designer_passes_tools_to_advisor(mock_client, mock_agent_loader):
    node_fn = make_designer_node(mock_client, mock_agent_loader, repo_path="/tmp/repo")
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "tools" in call_args.kwargs
    tool_names = {t["name"] for t in call_args.kwargs["tools"]}
    assert tool_names == {"read_file", "list_directory", "grep"}
```

- [ ] **Step 9: Modify `designer.py`**

Update `orchestrator/nodes/designer.py` with the same pattern:

```python
import functools

from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState
from orchestrator.tools import CODEBASE_TOOLS, execute_tool

SYSTEM_PROMPT = (
    "You are a UI/UX specification engine. You produce layouts, interaction patterns, "
    "responsive behavior descriptions, and component specifications. "
    "You never write code — that is the Developer's job."
)


def make_designer_node(
    client,
    agent_loader: AgentLoader,
    model: str = "claude-sonnet-4-6",
    scaffold_budget_usd: float | None = None,
    repo_path: str = "",
):
    agent = AdvisorAgent(
        role="designer",
        model=model,
        client=client,
    )
    tool_executor = functools.partial(execute_tool, repo_path=repo_path) if repo_path else None
    tools = CODEBASE_TOOLS if repo_path else None

    def designer_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("designer", state["task_id"])
        system_prompt = agent_loader.load_workflow_agent("designer")
        if not system_prompt:
            system_prompt = SYSTEM_PROMPT
        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        user_message = f"Create a UI/UX specification for this task.\n\nTask: {state['task_id']}\n"
        if bus:
            bus.api_call_start(
                "designer", model, len(system_prompt) + len(user_message), state["task_id"]
            )
        result = agent.call(
            system_prompt=system_prompt,
            user_message=user_message,
            tools=tools,
            tool_executor=tool_executor,
            task_id=state["task_id"],
        )
        if bus:
            bus.api_call_done(
                "designer", model, result.token_in, result.token_out, state["task_id"]
            )
            if scaffold_budget_usd is not None:
                bus.check_budget(scaffold_budget_usd)
            bus.node_exit("designer", state["task_id"])
        return {"agent_output": result.text}

    return designer_node
```

- [ ] **Step 10: Run designer tests**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_designer.py -v`
Expected: All PASS

- [ ] **Step 11: Write test for graph passing repo_path to factories**

Add to `tests/test_graph.py`:

```python
from unittest.mock import patch


def test_graph_passes_repo_path_to_strategic_nodes(mock_deps):
    with patch("orchestrator.graph.make_product_owner_node") as mock_po, \
         patch("orchestrator.graph.make_architect_node") as mock_arch, \
         patch("orchestrator.graph.make_designer_node") as mock_des:
        mock_po.return_value = lambda state: state
        mock_arch.return_value = lambda state: state
        mock_des.return_value = lambda state: state
        build_graph(**mock_deps)
        # Check repo_path was passed to all three
        po_kwargs = mock_po.call_args
        assert po_kwargs.kwargs.get("repo_path") == "/tmp/repo" or \
               (len(po_kwargs.args) > 0 and "/tmp/repo" in str(po_kwargs))
        arch_kwargs = mock_arch.call_args
        assert arch_kwargs.kwargs.get("repo_path") == "/tmp/repo" or \
               (len(arch_kwargs.args) > 0 and "/tmp/repo" in str(arch_kwargs))
        des_kwargs = mock_des.call_args
        assert des_kwargs.kwargs.get("repo_path") == "/tmp/repo" or \
               (len(des_kwargs.args) > 0 and "/tmp/repo" in str(des_kwargs))
```

- [ ] **Step 12: Modify `graph.py` to pass `repo_path`**

Update `orchestrator/graph.py` — add `repo_path=repo_path` to the three factory calls:

For `make_product_owner_node`:
```python
    graph.add_node(
        "product_owner",
        make_product_owner_node(
            client, spec_path, agent_loader, po_model,
            scaffold_budget_usd=scaffold_budget_usd,
            repo_path=repo_path,
        ),
    )
```

For `make_architect_node`:
```python
    graph.add_node(
        "architect",
        make_architect_node(
            client,
            agent_loader,
            _model("architect", "claude-opus-4-6"),
            scaffold_budget_usd=scaffold_budget_usd,
            repo_path=repo_path,
        ),
    )
```

For `make_designer_node`:
```python
    graph.add_node(
        "designer",
        make_designer_node(
            client,
            agent_loader,
            _model("designer", "claude-sonnet-4-6"),
            scaffold_budget_usd=scaffold_budget_usd,
            repo_path=repo_path,
        ),
    )
```

- [ ] **Step 13: Run graph tests**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/test_graph.py -v`
Expected: All PASS

- [ ] **Step 14: Run full test suite**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 15: Run linting and type checking**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && make check`
Expected: lint, typecheck, test all pass

- [ ] **Step 16: Commit**

```bash
git add orchestrator/nodes/product_owner.py orchestrator/nodes/architect.py orchestrator/nodes/designer.py orchestrator/graph.py tests/test_product_owner.py tests/test_architect.py tests/test_designer.py tests/test_graph.py
git commit -m "feat: wire codebase tools into PO, architect, designer nodes

Each strategic workflow node now passes CODEBASE_TOOLS and a
repo-scoped executor to AdvisorAgent.call(), enabling multi-turn
codebase exploration. Graph passes repo_path to all three factories."
```

---

### Task 4: Final Validation and ROADMAP Update

**Files:**
- Modify: `ROADMAP.md` (if it exists and has an entry for this)

- [ ] **Step 1: Run full test suite with coverage**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && make coverage`
Expected: All tests pass, coverage ≥ 75%

- [ ] **Step 2: Run `make check` (lint + typecheck + test)**

Run: `cd /Users/antonypegg/PROJECTS/scaffold && make check`
Expected: All clean

- [ ] **Step 3: Update ROADMAP.md**

If `ROADMAP.md` has an entry for "AdvisorAgent tool use", mark it as Done.

- [ ] **Step 4: Final commit**

```bash
git add ROADMAP.md
git commit -m "docs: mark AdvisorAgent tool use as done in ROADMAP"
```
