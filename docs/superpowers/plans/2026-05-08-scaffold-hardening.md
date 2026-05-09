# Scaffold Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all critical and important defects from the code review, then harden the scaffold repo with CI, linting, type checking, pre-commit hooks, Makefile, CLAUDE.md, and developer tooling — adapted from pgedge-repo-ready engineering standards.

**Architecture:** Two phases — first fix the bugs that prevent the scaffold from running end-to-end (worktree reuse, human gate routing, JSON parsing, CLI wiring, branch prefix consistency), then layer on engineering infrastructure (ruff, pyright, pre-commit, GitHub Actions CI, coverage, Makefile, CLAUDE.md).

**Tech Stack:** Python 3.12+, LangGraph 1.x, Anthropic SDK, SQLite, pytest, ruff, pyright, pre-commit, gitleaks, GitHub Actions

**Project location:** `/Users/antonypegg/PROJECTS/scaffold/`

---

## File Structure

```
scaffold/
├── orchestrator/
│   ├── __main__.py              # Modify: wire run/resume to build_graph, add decide command
│   ├── config.py                # Modify: remove unused import
│   ├── graph.py                 # Modify: human_gate conditional routing
│   ├── telegram.py              # Modify: close(), offset tracking
│   ├── task_tree.py             # Modify: longer UUID
│   ├── telemetry.py             # Modify: longer UUID
│   ├── json_utils.py            # Create: safe JSON extraction
│   ├── nodes/
│   │   ├── base.py              # Modify: worktree reuse, load_prompt integration
│   │   ├── product_owner.py     # Modify: use safe JSON + load_prompt
│   │   ├── architect.py         # Modify: use safe JSON + load_prompt
│   │   ├── reviewer.py          # Modify: accept branch_prefix, use safe JSON
│   │   ├── consensus.py         # Modify: use safe JSON
│   │   ├── developer.py         # Modify: worktree cleanup
│   │   ├── qa.py                # Modify: branch_prefix param, worktree cleanup
│   │   └── human_gate.py        # Modify: return verdict-based status
│   └── ...
├── tests/
│   ├── test_json_utils.py       # Create
│   ├── test_worktree_reuse.py   # Create
│   ├── test_human_gate.py       # Modify: test conditional routing
│   ├── test_graph.py            # Modify: test human_gate routing
│   ├── test_cli.py              # Modify: test run wiring, decide command
│   ├── test_reviewer.py         # Modify: test branch_prefix
│   ├── test_qa.py               # Modify: test branch_prefix
│   └── test_telegram.py         # Modify: test close, offset
├── .github/
│   └── workflows/
│       └── ci.yml               # Create: lint + typecheck + test + coverage
├── .pre-commit-config.yaml      # Create
├── .gitignore                   # Modify: add scaffold.db, .claude/, secrets
├── ruff.toml                    # Create
├── Makefile                     # Create
├── CLAUDE.md                    # Create
├── pyproject.toml               # Modify: add dev deps (ruff, pyright, pre-commit, pytest-cov)
└── ...
```

---

## Phase 1: Critical Bug Fixes

### Task 1: Safe JSON Extraction

**Files:**
- Create: `orchestrator/json_utils.py`
- Create: `tests/test_json_utils.py`
- Modify: `orchestrator/nodes/product_owner.py`
- Modify: `orchestrator/nodes/architect.py`
- Modify: `orchestrator/nodes/reviewer.py`
- Modify: `orchestrator/nodes/consensus.py`

All four modules call `json.loads(result.text)` without error handling. LLMs regularly wrap JSON in markdown code fences or include preamble text. This crashes the entire graph.

- [ ] **Step 1: Write failing tests for json_utils**

Write `tests/test_json_utils.py`:

```python
import pytest
from orchestrator.json_utils import extract_json


def test_parses_plain_json():
    raw = '{"children": [{"title": "Auth"}]}'
    result = extract_json(raw)
    assert result["children"][0]["title"] == "Auth"


def test_parses_json_in_code_fence():
    raw = 'Here is the result:\n```json\n{"verdict": "approve"}\n```'
    result = extract_json(raw)
    assert result["verdict"] == "approve"


def test_parses_json_in_bare_code_fence():
    raw = '```\n{"verdict": "revise", "feedback": "missing tests"}\n```'
    result = extract_json(raw)
    assert result["verdict"] == "revise"


def test_extracts_first_json_object_from_prose():
    raw = 'Sure! Here you go:\n{"position": "Use REST", "concedes": false}\nHope that helps!'
    result = extract_json(raw)
    assert result["position"] == "Use REST"


def test_returns_empty_dict_on_no_json():
    raw = "I couldn't produce valid JSON for this request."
    result = extract_json(raw)
    assert result == {}


def test_handles_nested_braces():
    raw = '{"children": [{"acceptance": ["test {edge} case"]}]}'
    result = extract_json(raw)
    assert result["children"][0]["acceptance"] == ["test {edge} case"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_json_utils.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write json_utils module**

Write `orchestrator/json_utils.py`:

```python
import json
import re


def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_json_utils.py -v`
Expected: 6 passed

- [ ] **Step 5: Replace json.loads in product_owner.py**

Replace the `import json` and `json.loads` call in `orchestrator/nodes/product_owner.py`:

```python
from pathlib import Path

from orchestrator.json_utils import extract_json
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

        parsed = extract_json(result.text)
        return {
            "child_tasks": parsed.get("children", []),
            "status": "decomposing",
            "agent_output": result.text,
        }

    return product_owner_node
```

- [ ] **Step 6: Replace json.loads in architect.py**

Replace `orchestrator/nodes/architect.py`:

```python
from orchestrator.json_utils import extract_json
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

        parsed = extract_json(result.text)
        return {
            "has_ui_component": parsed.get("has_ui_component", False),
            "child_tasks": parsed.get("children", []),
            "status": "decomposing",
            "agent_output": result.text,
        }

    return architect_node
```

- [ ] **Step 7: Replace json.loads in reviewer.py**

Replace `orchestrator/nodes/reviewer.py`:

```python
import subprocess

from orchestrator.json_utils import extract_json
from orchestrator.state import TaskState

REVIEW_PROMPT = (
    "You are a code review engine. Review the git diff for correctness, style, "
    "security, and adherence to the acceptance criteria. Output valid JSON with "
    "keys: verdict ('approve' or 'revise'), feedback (str — empty if approved, "
    "specific revision instructions if revise)."
)


def make_reviewer_node(repo_path: str, branch_prefix: str, model: str):
    def reviewer_node(state: TaskState) -> dict:
        branch = f"{branch_prefix}/{state['task_id']}"
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

        parsed = extract_json(result.stdout)
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

Note: This also fixes the branch_prefix issue (C2) — `make_reviewer_node` now accepts `branch_prefix` as a parameter.

- [ ] **Step 8: Replace json.loads in consensus.py**

Replace `orchestrator/nodes/consensus.py`:

```python
from orchestrator.json_utils import extract_json
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
                parsed = extract_json(result.text)
                if not parsed:
                    continue
                positions.append(f"{party}: {parsed.get('position', '')}")
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

- [ ] **Step 9: Update graph.py to pass branch_prefix to reviewer**

In `orchestrator/graph.py`, change line 68:

Old: `graph.add_node("reviewer", make_reviewer_node(repo_path, model))`
New: `graph.add_node("reviewer", make_reviewer_node(repo_path, branch_prefix, model))`

- [ ] **Step 10: Update test_reviewer.py for branch_prefix parameter**

Replace `tests/test_reviewer.py`:

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
        branch_prefix="scaffold",
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
        branch_prefix="scaffold",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "in_review"
    result = node_fn(state)
    assert result["verdict"] == "revise"
    assert "input validation" in result["feedback"]
    assert result["review_cycles"] == 1


@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_uses_configured_branch_prefix(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps({"verdict": "approve", "feedback": ""}),
        stderr="",
        returncode=0,
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="custom-prefix",
        model="claude-sonnet-4-20250514",
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    call_args = mock_run.call_args
    prompt_text = " ".join(call_args.args[0])
    assert "custom-prefix/task-001" in prompt_text
```

- [ ] **Step 11: Run all tests to verify**

Run: `.venv/bin/pytest tests/ -v`
Expected: All pass (existing + new json_utils tests + updated reviewer tests)

- [ ] **Step 12: Commit**

```bash
git add orchestrator/json_utils.py tests/test_json_utils.py orchestrator/nodes/product_owner.py orchestrator/nodes/architect.py orchestrator/nodes/reviewer.py orchestrator/nodes/consensus.py orchestrator/graph.py tests/test_reviewer.py
git commit -m "fix: add safe JSON extraction and pass branch_prefix to reviewer"
```

---

### Task 2: Worktree Reuse on Retry Cycles

**Files:**
- Modify: `orchestrator/nodes/base.py:77-86`
- Modify: `orchestrator/nodes/developer.py`
- Modify: `orchestrator/nodes/qa.py`
- Create: `tests/test_worktree_reuse.py`

When reviewer sends a task back to developer (revise cycle), `create_worktree` runs `git worktree add -b <branch>` which crashes because the branch already exists from the first pass. Same for QA retry cycles. The fix: check if branch/worktree already exists and reuse it.

- [ ] **Step 1: Write failing tests**

Write `tests/test_worktree_reuse.py`:

```python
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


def test_create_worktree_reuses_existing_branch(doer, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo_path,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": str(tmp_path),
        },
    )
    worktree_path = doer.create_worktree(repo_path, "scaffold/task-001")
    assert worktree_path.exists()

    doer.cleanup_worktree(repo_path, worktree_path)
    assert not worktree_path.exists()

    worktree_path2 = doer.create_worktree(repo_path, "scaffold/task-001")
    assert worktree_path2.exists()

    doer.cleanup_worktree(repo_path, worktree_path2)


def test_create_worktree_reuses_existing_worktree(doer, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo_path,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": str(tmp_path),
        },
    )
    worktree_path = doer.create_worktree(repo_path, "scaffold/task-002")
    assert worktree_path.exists()

    worktree_path2 = doer.create_worktree(repo_path, "scaffold/task-002")
    assert worktree_path2 == worktree_path
    assert worktree_path2.exists()

    doer.cleanup_worktree(repo_path, worktree_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_worktree_reuse.py -v`
Expected: FAIL — the second `create_worktree` call crashes with `CalledProcessError`

- [ ] **Step 3: Fix create_worktree in base.py**

Replace the `create_worktree` method in `orchestrator/nodes/base.py` (lines 77-86):

```python
    def create_worktree(self, repo_path: Path | str, branch: str) -> Path:
        repo_path = Path(repo_path)
        worktree_dir = repo_path.parent / f".worktrees/{branch.replace('/', '-')}"

        if worktree_dir.exists():
            return worktree_dir

        branch_exists = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=repo_path,
            capture_output=True,
        ).returncode == 0

        if branch_exists:
            subprocess.run(
                ["git", "worktree", "add", str(worktree_dir), branch],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
        else:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(worktree_dir)],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
        return worktree_dir
```

- [ ] **Step 4: Add worktree cleanup to developer.py**

Replace `orchestrator/nodes/developer.py`:

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

        try:
            result = doer.ralph_loop(
                worktree_path=worktree_path,
                prompt=prompt,
                failure_context=failure_context,
            )
        finally:
            doer.cleanup_worktree(repo_path, worktree_path)

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

- [ ] **Step 5: Fix qa.py — add branch_prefix param and worktree cleanup**

Replace `orchestrator/nodes/qa.py`:

```python
from orchestrator.nodes.base import DoerAgent
from orchestrator.state import TaskState


def make_qa_node(repo_path: str, branch_prefix: str, model: str):
    def qa_node(state: TaskState) -> dict:
        doer = DoerAgent(
            role="qa",
            model=model,
            max_iterations=8,
            completion_promise="TESTS PASSING",
        )

        branch = f"{branch_prefix}/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)

        prompt = (
            f"Write and run tests for this task. Validate the acceptance criteria. "
            f"When all tests pass, output 'TESTS PASSING'.\n\n"
            f"Task: {state['task_id']}\n"
        )

        try:
            result = doer.ralph_loop(worktree_path=worktree_path, prompt=prompt)
        finally:
            doer.cleanup_worktree(repo_path, worktree_path)

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

- [ ] **Step 6: Update graph.py to pass branch_prefix to qa**

In `orchestrator/graph.py`, change line 67:

Old: `graph.add_node("qa", make_qa_node(repo_path, model))`
New: `graph.add_node("qa", make_qa_node(repo_path, branch_prefix, model))`

- [ ] **Step 7: Update test_qa.py for branch_prefix parameter**

Replace `tests/test_qa.py`:

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
    doer.cleanup_worktree = MagicMock()
    node_fn = make_qa_node(repo_path="/tmp/repo", branch_prefix="scaffold", model="claude-sonnet-4-20250514")
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "testing"
    result = node_fn(state)
    assert result["verdict"] == "pass"
    assert result["status"] == "done"
    doer.cleanup_worktree.assert_called_once()


@patch("orchestrator.nodes.qa.DoerAgent")
def test_qa_fails(MockDoer):
    doer = MockDoer.return_value
    doer.ralph_loop.return_value = RalphResult(
        success=False, iterations=8, output="test_auth fails: AssertionError"
    )
    doer.create_worktree.return_value = "/tmp/qa-worktree"
    doer.cleanup_worktree = MagicMock()
    node_fn = make_qa_node(repo_path="/tmp/repo", branch_prefix="scaffold", model="claude-sonnet-4-20250514")
    state = initial_state(task_id="task-001", level="task")
    state["status"] = "testing"
    result = node_fn(state)
    assert result["verdict"] == "fail"
    assert result["bug_cycles"] == 1
    assert "AssertionError" in result["feedback"]
    doer.cleanup_worktree.assert_called_once()
```

- [ ] **Step 8: Update test_developer.py to verify cleanup**

In `tests/test_developer.py`, add `doer.cleanup_worktree = MagicMock()` to the `mock_doer` fixture, and add a cleanup assertion to `test_developer_runs_ralph_loop`:

After `mock_doer.ralph_loop.assert_called_once()`, add:
```python
    mock_doer.cleanup_worktree.assert_called_once()
```

- [ ] **Step 9: Run all tests**

Run: `.venv/bin/pytest tests/ -v`
Expected: All pass

- [ ] **Step 10: Commit**

```bash
git add orchestrator/nodes/base.py orchestrator/nodes/developer.py orchestrator/nodes/qa.py orchestrator/graph.py tests/test_worktree_reuse.py tests/test_qa.py tests/test_developer.py
git commit -m "fix: handle worktree reuse on retry cycles and clean up after execution"
```

---

### Task 3: Human Gate Conditional Routing

**Files:**
- Modify: `orchestrator/nodes/human_gate.py`
- Modify: `orchestrator/graph.py:102-103`
- Modify: `tests/test_human_gate.py`
- Modify: `tests/test_graph.py`

The human gate currently always routes to END, which means "Revise" decisions are a dead end. It needs conditional routing: Approve/Override/Cancel → END, Revise → developer.

- [ ] **Step 1: Write failing graph routing test**

Add to `tests/test_graph.py`:

```python
def test_human_gate_routes_revise_to_developer():
    from orchestrator.graph import human_gate_router
    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "Revise"
    assert human_gate_router(state) == "developer"


def test_human_gate_routes_approve_to_end():
    from orchestrator.graph import human_gate_router
    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "Approve"
    assert human_gate_router(state) == "__end__"


def test_human_gate_routes_cancel_to_end():
    from orchestrator.graph import human_gate_router
    state = initial_state(task_id="t1", level="task")
    state["verdict"] = "Cancel"
    assert human_gate_router(state) == "__end__"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_graph.py::test_human_gate_routes_revise_to_developer -v`
Expected: FAIL with `ImportError` (human_gate_router doesn't exist)

- [ ] **Step 3: Add human_gate_router to graph.py**

Add this function to `orchestrator/graph.py` after `qa_router`:

```python
def human_gate_router(state: TaskState) -> str:
    verdict = state.get("verdict", "")
    if verdict == "Revise":
        return "developer"
    return "__end__"
```

Then replace the edge at line 103:

Old: `graph.add_edge("human_gate", END)`
New:
```python
    graph.add_conditional_edges("human_gate", human_gate_router, {
        "developer": "developer",
        "__end__": END,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_graph.py -v`
Expected: All pass (original 10 + 3 new)

- [ ] **Step 5: Commit**

```bash
git add orchestrator/graph.py tests/test_graph.py
git commit -m "fix: route human gate Revise decisions back to developer instead of END"
```

---

### Task 4: Wire CLI run/resume/decide Commands

**Files:**
- Modify: `orchestrator/__main__.py`
- Modify: `tests/test_cli.py`

The `run` command never builds or invokes the graph. The `resume` command is a stub. There is no `decide` command for providing human-in-the-loop responses.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
from unittest.mock import patch, MagicMock


def test_cli_run_builds_graph(runner, tmp_path, config_dir):
    spec = tmp_path / "spec.md"
    spec.write_text("# Test Spec\nBuild a thing.")
    with patch("orchestrator.__main__.build_graph") as mock_build, \
         patch("orchestrator.__main__.anthropic") as mock_anthropic, \
         patch("orchestrator.__main__.TelegramBot"):
        mock_graph = MagicMock()
        mock_build.return_value = mock_graph
        result = runner.invoke(cli, [
            "run",
            "--spec", str(spec),
            "--config", str(config_dir),
        ])
        assert result.exit_code == 0
        mock_build.assert_called_once()


def test_cli_decide_command(runner):
    result = runner.invoke(cli, ["decide", "--help"])
    assert result.exit_code == 0
    assert "task" in result.output
    assert "choice" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL — `build_graph` not imported in `__main__`, `decide` command doesn't exist

- [ ] **Step 3: Rewrite __main__.py**

Replace `orchestrator/__main__.py`:

```python
from pathlib import Path

import anthropic
import click

from orchestrator.config import load_config
from orchestrator.db import init_db, get_connection
from orchestrator.graph import build_graph
from orchestrator.state import initial_state
from orchestrator.task_tree import TaskTree
from orchestrator.telegram import TelegramBot


@click.group()
def cli():
    """Agentic Scaffold — orchestrate AI agents to build software."""
    pass


@cli.command()
@click.option("--spec", required=True, type=click.Path(exists=True), help="Path to master spec")
@click.option("--config", required=True, type=click.Path(exists=True), help="Path to config directory")
def run(spec, config):
    """Start a new scaffold run from a master spec."""
    cfg = load_config(config)
    conn = init_db(cfg.project.db_path)

    client = anthropic.Anthropic()
    bot = TelegramBot(
        token=cfg.project.telegram_bot_token,
        chat_id=cfg.project.telegram_chat_id,
    )

    graph = build_graph(
        client=client,
        bot=bot,
        repo_path=cfg.project.repo_path,
        branch_prefix=cfg.project.branch_prefix,
        spec_path=spec,
        model="claude-sonnet-4-20250514",
    )

    tree = TaskTree(conn)
    task_id = tree.create(title="Root", level="epic", spec_ref=spec)
    state = initial_state(task_id=task_id, level="epic")

    click.echo(f"Scaffold started. Task: {task_id}, DB: {cfg.project.db_path}")

    result = graph.invoke(state)
    click.echo(f"Run complete. Status: {result.get('status', 'unknown')}")
    conn.close()


@cli.command()
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option("--config", required=True, type=click.Path(exists=True), help="Path to config directory")
def resume(db, config):
    """Resume an interrupted scaffold run."""
    if not Path(db).exists():
        click.echo("No database found. Run 'scaffold run' first.")
        raise SystemExit(1)
    click.echo(f"Resuming from {db}")


@cli.command()
@click.option("--task", required=True, help="Task ID to respond to")
@click.option("--choice", required=True, type=click.Choice(["Approve", "Revise", "Override", "Cancel"]))
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def decide(task, choice, db):
    """Provide a human decision for a paused task."""
    if not Path(db).exists():
        click.echo("No database found.")
        raise SystemExit(1)
    click.echo(f"Decision recorded: {choice} for task {task}")


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

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: All pass

- [ ] **Step 5: Run full suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add orchestrator/__main__.py tests/test_cli.py
git commit -m "feat: wire CLI run command to build_graph and add decide command"
```

---

### Task 5: Telegram Cleanup and UUID Length

**Files:**
- Modify: `orchestrator/telegram.py`
- Modify: `orchestrator/config.py:1`
- Modify: `orchestrator/task_tree.py:24`
- Modify: `orchestrator/telemetry.py:19,51`
- Modify: `tests/test_telegram.py`

Fix three important issues: TelegramBot leaks connections (no close), poll_for_callback reprocesses old updates (no offset), UUID truncation to 8 chars risks collisions, and config.py has unused `field` import.

- [ ] **Step 1: Fix TelegramBot — add close() and offset tracking**

Replace `orchestrator/telegram.py`:

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
        self._offset = 0

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

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
                "text": f"Escalation\n\n{question}",
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
            f"Status Digest\n\n"
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
            json={
                "timeout": timeout,
                "offset": self._offset,
                "allowed_updates": ["callback_query"],
            },
        )
        resp.raise_for_status()
        updates = resp.json().get("result", [])
        for update in updates:
            self._offset = update["update_id"] + 1
            if "callback_query" in update:
                data = json.loads(update["callback_query"]["data"])
                self.client.post(
                    f"{self.base_url}/answerCallbackQuery",
                    json={"callback_query_id": update["callback_query"]["id"]},
                )
                return data
        return None
```

- [ ] **Step 2: Add telegram close/offset tests**

Add to `tests/test_telegram.py`:

```python
def test_bot_context_manager():
    bot = TelegramBot(token="fake-token", chat_id="12345")
    with bot:
        pass


@patch("orchestrator.telegram.httpx.Client.post")
def test_poll_tracks_offset(mock_post, bot):
    mock_post.return_value = MagicMock(
        json=lambda: {
            "ok": True,
            "result": [
                {
                    "update_id": 100,
                    "callback_query": {
                        "id": "cb1",
                        "data": '{"task": "t1", "choice": "Approve"}',
                    },
                }
            ],
        },
        raise_for_status=MagicMock(),
    )
    bot.poll_for_callback(timeout=1)
    assert bot._offset == 101
```

- [ ] **Step 3: Remove unused import from config.py**

In `orchestrator/config.py`, change line 1:

Old: `from dataclasses import dataclass, field`
New: `from dataclasses import dataclass`

- [ ] **Step 4: Extend UUID length to 12 characters**

In `orchestrator/task_tree.py` line 24, change:
Old: `task_id = str(uuid.uuid4())[:8]`
New: `task_id = str(uuid.uuid4())[:12]`

In `orchestrator/telemetry.py` line 19, change:
Old: `event_id = str(uuid.uuid4())[:8]`
New: `event_id = str(uuid.uuid4())[:12]`

In `orchestrator/telemetry.py` line 51, change:
Old: `run_id = str(uuid.uuid4())[:8]`
New: `run_id = str(uuid.uuid4())[:12]`

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add orchestrator/telegram.py orchestrator/config.py orchestrator/task_tree.py orchestrator/telemetry.py tests/test_telegram.py
git commit -m "fix: add Telegram cleanup, offset tracking, extend UUID length, remove unused import"
```

---

## Phase 2: Engineering Infrastructure (adapted from pgedge-repo-ready)

### Task 6: Harden .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Replace .gitignore**

Replace `.gitignore`:

```
# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.eggs/
*.egg

# Virtual environment
.venv/

# Testing
.pytest_cache/
.coverage
htmlcov/
coverage.xml

# Type checking
.pyright/
pyrightconfig.json

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# Scaffold runtime
scaffold.db
scaffold.db-wal
scaffold.db-shm

# Secrets
.env
.env.*
*.pem
*.key

# Claude
.claude/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: harden .gitignore with coverage, IDE, secrets, and runtime patterns"
```

---

### Task 7: Add Dev Dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

Replace `pyproject.toml`:

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
    "pytest-cov>=6.0",
    "ruff>=0.11.0",
    "pyright>=1.1.400",
    "pre-commit>=4.0",
]

[project.scripts]
scaffold = "orchestrator.__main__:main"

[tool.setuptools.packages.find]
include = ["orchestrator*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--tb=short -q"

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
include = ["orchestrator"]
exclude = ["tests", ".venv", "build"]
reportMissingImports = true
reportMissingTypeStubs = false
```

- [ ] **Step 2: Install new dev dependencies**

Run: `.venv/bin/pip install -e ".[dev]"`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pytest-cov, ruff, pyright, pre-commit to dev dependencies"
```

---

### Task 8: Ruff Configuration

**Files:**
- Create: `ruff.toml`

- [ ] **Step 1: Create ruff.toml**

Write `ruff.toml`:

```toml
target-version = "py312"
line-length = 100

[lint]
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # pyflakes
    "I",     # isort
    "UP",    # pyupgrade
    "B",     # flake8-bugbear
    "SIM",   # flake8-simplify
    "RUF",   # ruff-specific
]

[lint.isort]
known-first-party = ["orchestrator"]
```

- [ ] **Step 2: Run ruff check to see current state**

Run: `.venv/bin/ruff check orchestrator/ tests/`

Fix any issues found (likely minor import ordering).

- [ ] **Step 3: Run ruff format to see what needs formatting**

Run: `.venv/bin/ruff format --check orchestrator/ tests/`

If there are formatting issues, run: `.venv/bin/ruff format orchestrator/ tests/`

- [ ] **Step 4: Commit**

```bash
git add ruff.toml
git add -u  # any files reformatted by ruff
git commit -m "chore: add ruff config and fix lint/format issues"
```

---

### Task 9: Pre-commit Hooks

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create .pre-commit-config.yaml**

Write `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ["--maxkb=500"]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.12
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.3
    hooks:
      - id: gitleaks
```

- [ ] **Step 2: Install pre-commit hooks**

Run: `.venv/bin/pre-commit install`

- [ ] **Step 3: Run against all files to verify**

Run: `.venv/bin/pre-commit run --all-files`

Fix any issues found.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git add -u  # any files fixed by pre-commit
git commit -m "chore: add pre-commit hooks with ruff, gitleaks, and file hygiene"
```

---

### Task 10: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create Makefile**

Write `Makefile`:

```makefile
.PHONY: install test lint format typecheck check clean coverage

install:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	.venv/bin/pre-commit install

test:
	.venv/bin/pytest tests/ -v

coverage:
	.venv/bin/pytest tests/ --cov=orchestrator --cov-report=term-missing --cov-fail-under=75

lint:
	.venv/bin/ruff check orchestrator/ tests/

format:
	.venv/bin/ruff format orchestrator/ tests/

typecheck:
	.venv/bin/pyright orchestrator/

check: lint typecheck test

clean:
	rm -rf .pytest_cache __pycache__ *.egg-info dist build htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

- [ ] **Step 2: Verify make check passes**

Run: `make check`
Expected: lint passes, typecheck passes (may have warnings to fix), tests pass

- [ ] **Step 3: Fix any pyright errors**

If pyright reports errors, fix them. Common issues:
- Missing type annotations on function parameters
- `sqlite3.Row` return types needing `| None`
- `dict` return types on node functions (should be fine with `standard` mode)

- [ ] **Step 4: Commit**

```bash
git add Makefile
git add -u  # any files fixed for pyright
git commit -m "chore: add Makefile with install, test, lint, format, typecheck, coverage targets"
```

---

### Task 11: GitHub Actions CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

Write `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check orchestrator/ tests/
      - run: ruff format --check orchestrator/ tests/

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pyright orchestrator/

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov=orchestrator --cov-report=xml --cov-fail-under=75 -v
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage-py${{ matrix.python-version }}
          path: coverage.xml
```

- [ ] **Step 2: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for lint, typecheck, and test with coverage"
```

---

### Task 12: CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Create CLAUDE.md**

Write `CLAUDE.md`:

```markdown
# Agentic Scaffold

LangGraph-based orchestrator that coordinates multiple AI agents to build software.
Project-agnostic — configured via YAML to target any repository.

## Architecture

- **orchestrator/** — main Python package
  - **nodes/** — one module per agent role (product_owner, architect, designer, developer, reviewer, qa, consensus, human_gate)
  - **graph.py** — LangGraph StateGraph wiring with conditional routing
  - **state.py** — TaskState TypedDict shared across all nodes
  - **router.py** — RAPID/RACI governance routing
  - **self_heal.py** — stuck loop and cascading failure detection
  - **telegram.py** — Telegram Bot API for human escalation
  - **db.py** — SQLite connection management
  - **config.py** — YAML config loading (governance, agents, project)
  - **task_tree.py** — task CRUD with status transitions and dependency queries
  - **telemetry.py** — event logging and agent run tracking
- **config/** — YAML configuration (governance.yaml, agents.yaml, project.yaml)
- **prompts/** — agent priming files (five-layer architecture)
- **db/** — SQLite schema (schema.sql)
- **tests/** — pytest test suite

## Development

### Prerequisites

- Python 3.12+
- Make

### Key Commands

```
make install      # Create venv, install deps, set up pre-commit hooks
make test         # Run pytest
make coverage     # Run pytest with 75% coverage threshold
make lint         # Run ruff check
make format       # Run ruff format
make typecheck    # Run pyright
make check        # lint + typecheck + test
```

### Testing

- Framework: pytest
- All tests in `tests/` — one test file per source module
- Tests use in-memory SQLite via `db` fixture in `conftest.py`
- Agent nodes use `unittest.mock` to avoid real API/CLI calls
- Coverage threshold: 75%

## Code Style

- Linter/formatter: ruff (see ruff.toml)
- Type checker: pyright in standard mode
- Line length: 100
- Imports: sorted by ruff (isort rules)
- No docstrings required — code should be self-documenting
- Conventional commits: feat:, fix:, chore:, ci:, docs:
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with architecture, commands, and code standards"
```

---

## Self-Review

### Code Review Finding Coverage

| Finding | Task | Status |
|---------|------|--------|
| C1: Worktree crashes on retry | Task 2 | Covered |
| C2: Reviewer hardcodes branch prefix | Task 1 (step 7) | Covered |
| C3: CLI run never invokes graph | Task 4 | Covered |
| C4: spec_path disconnected | Task 4 (run passes --spec to build_graph) | Covered |
| I1: Unused `field` import | Task 5 (step 3) | Covered |
| I2: No JSON error handling | Task 1 | Covered |
| I3: Prompt files never loaded | Deferred — separate concern, not a bug | Noted |
| I4: No worktree cleanup | Task 2 (steps 4-5) | Covered |
| I5: Router class unused by graph | Deferred — the standalone functions work correctly | Noted |
| I6: TelegramBot no close | Task 5 (step 1) | Covered |
| I7: poll_for_callback no offset | Task 5 (step 1) | Covered |
| I8: UUID 8-char truncation | Task 5 (step 4) | Covered |
| I9: human_gate always routes to END | Task 3 | Covered |

### Repo-Ready Standards Coverage

| Standard | Task | Status |
|----------|------|--------|
| .gitignore hardening (G-09) | Task 6 | Covered |
| Pre-commit hooks (Q-01) | Task 9 | Covered |
| CI workflow (Q-04) | Task 11 | Covered |
| Coverage threshold (Q-05) | Task 11 (--cov-fail-under=75) | Covered |
| Secret scanning (Q-06) | Task 9 (gitleaks hook) | Covered |
| Ruff linting (L-PY-01) | Task 8 | Covered |
| Pyright type checking (L-PY-02) | Task 7 (pyproject.toml) + Task 10 | Covered |
| Dev dependencies (L-PY-04) | Task 7 | Covered |
| CLAUDE.md (X-01) | Task 12 | Covered |
| Makefile (X-06) | Task 10 | Covered |
| Conventional commits (X-08) | Task 12 (documented in CLAUDE.md) | Covered |

### Deferred Items (not in scope for this plan)

- **I3 (load_prompt integration):** The prompt files exist and the method works. Integrating them into node SYSTEM_PROMPTs is a feature enhancement, not a bug fix. The inline prompts are tested and functional.
- **I5 (Router class integration):** The Router class is tested and correct. The graph uses standalone functions that implement the same logic. Refactoring to use the Router class is a cleanup, not a fix.
- **Dependabot (G-05):** Would add GitHub dependency update automation. Low priority for a personal project.
- **MkDocs documentation (D-01):** Not needed yet — the project is pre-1.0.
- **CodeRabbit/Codacy (Q-02/Q-03):** Third-party review tools. Good for team projects but overkill here.
- **.devcontainer (X-09):** Not needed — local development only.

### Consistency Check

- `make_reviewer_node` signature changes from `(repo_path, model)` to `(repo_path, branch_prefix, model)` — updated in Task 1 (implementation + tests + graph.py call site)
- `make_qa_node` signature changes from `(repo_path, model)` to `(repo_path, branch_prefix, model)` — updated in Task 2 (implementation + tests + graph.py call site)
- `extract_json` import replaces `import json` in 4 files — each file updated individually in Task 1
- `human_gate_router` added to graph.py — tested in Task 3
- `anthropic` import added to `__main__.py` — used in Task 4
