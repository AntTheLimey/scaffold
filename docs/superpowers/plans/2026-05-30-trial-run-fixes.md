# Scaffold Trial Run Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the five bugs that caused the first Inkwell trial run to produce garbage, so the next run can actually build working code.

**Architecture:** Five independent fixes targeting: (1) reviewer runs in the wrong directory, (2) developer doesn't commit code to the branch, (3) specialist fallback ignores project languages, (4) task decomposition has no dependency ordering, (5) stale state cleanup. Each fix is a focused change to one or two source files plus tests.

**Tech Stack:** Python 3.12+, pytest, ruff, pyright, LangGraph

---

## Diagnosis

The first Inkwell trial run decomposed the master spec into 9 feature tasks. Results:

- **WebSocket hub** (011b4682-e8d): marked "done" but only wrote a README
- **Invite code auth** (8bba165c-99e): built a copy of the scaffold itself (2600 lines of Python scaffold code) instead of Inkwell code
- **7 other features**: timed out or produced nothing, all status "stuck"

Root causes traced to five bugs:

1. **Reviewer runs in `repo_path` (main branch), not the worktree** — `reviewer.py:41` uses `cwd=repo_path`. The developer writes code in a worktree on a feature branch, but the reviewer runs `claude -p` in the main repo checkout. It sees no diff, returns "revise" with "No diff provided", developer gets stuck in a loop.

2. **Developer doesn't git-commit before handing off to reviewer** — The DoerAgent runs `claude -p` which writes files in the worktree, but nothing in the scaffold commits those changes. The reviewer prompt says "review the git diff" but there is no diff on the branch because nothing was committed.

3. **Specialist fallback ignores detected languages** — When `specialists` list is empty AND `detect_specialist` returns nothing (no file extensions to match — common in greenfield repos), `developer.py:52` hardcodes `python-expert`. It should use `detected_languages` from state (populated by onboarding from CLAUDE.md) to pick the right specialist.

4. **No dependency ordering in task decomposition** — The dispatcher (`dispatcher.py:85-120`) iterates children sequentially but in the order the PO/architect returned them. There's no mechanism for the PO to declare dependencies ("schema before seed data") or for the dispatcher to respect them. Tasks run in arbitrary order.

5. **Stale worktrees and DB from previous runs** — 6 orphaned worktrees, a DB full of stuck tasks. No `scaffold clean` command exists.

## File Structure

Files to modify:

| File | Responsibility |
|------|---------------|
| `orchestrator/nodes/reviewer.py` | Bug 1: Switch reviewer to run in worktree, using the task's branch |
| `orchestrator/nodes/developer.py` | Bug 2: Add git add + commit after DoerAgent finishes |
| `orchestrator/nodes/developer.py` | Bug 3: Use `detected_languages` for specialist fallback |
| `orchestrator/nodes/product_owner.py` | Bug 4: Add `depends_on` field to PO output schema |
| `orchestrator/dispatcher.py` | Bug 4: Topological sort children by `depends_on` before executing |
| `orchestrator/__main__.py` | Bug 5: Add `scaffold clean` CLI command |
| `tests/test_reviewer.py` | Tests for bug 1 |
| `tests/test_developer.py` | Tests for bugs 2, 3 |
| `tests/test_dispatcher.py` | Tests for bug 4 |
| `tests/test_cli.py` | Tests for bug 5 |

---

### Task 1: Fix reviewer to run in worktree on the task's branch

The reviewer runs `claude -p` with `cwd=repo_path` (the main checkout). It needs to run in a temporary worktree checked out to the task's branch, so `claude` can see the code the developer wrote.

**Files:**
- Modify: `orchestrator/nodes/reviewer.py`
- Modify: `tests/test_reviewer.py`

- [ ] **Step 1: Write failing test — reviewer runs claude in worktree, not repo_path**

Add this test to `tests/test_reviewer.py`:

```python
@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_runs_in_worktree(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps({"verdict": "approve", "feedback": ""}),
        stderr="",
        returncode=0,
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-6",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    result = node_fn(state)

    # The claude subprocess should run in a worktree, not repo_path
    call_args = mock_run.call_args_list
    # First call: git worktree add
    # Second call: claude -p (should use worktree cwd)
    # Last call: git worktree remove
    claude_call = [c for c in call_args if "claude" in str(c.args[0])][0]
    assert claude_call.kwargs["cwd"] != "/tmp/repo"
    assert "scaffold-task-001" in str(claude_call.kwargs["cwd"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reviewer.py::test_reviewer_runs_in_worktree -v`
Expected: FAIL — reviewer currently uses `cwd=repo_path`

- [ ] **Step 3: Write failing test — reviewer cleans up worktree**

Add to `tests/test_reviewer.py`:

```python
@patch("orchestrator.nodes.reviewer.subprocess.run")
def test_reviewer_cleans_up_worktree(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps({"verdict": "approve", "feedback": ""}),
        stderr="",
        returncode=0,
    )
    node_fn = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-6",
        agent_loader=_make_mock_loader(),
    )
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)

    # Last subprocess call should be git worktree remove
    last_call = mock_run.call_args_list[-1]
    assert "worktree" in str(last_call.args[0])
    assert "remove" in str(last_call.args[0])
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reviewer.py::test_reviewer_cleans_up_worktree -v`
Expected: FAIL

- [ ] **Step 5: Implement reviewer worktree support**

Modify `orchestrator/nodes/reviewer.py`. The reviewer needs to:
1. Create a temporary worktree checked out to the task's branch (the branch already exists — the developer created it)
2. Run `claude -p` in that worktree
3. Remove the worktree in a `finally` block

```python
import subprocess
from pathlib import Path

from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.json_utils import extract_json
from orchestrator.state import TaskState

REVIEW_PROMPT = (
    "You are a code review engine. Review the git diff for correctness, style, "
    "security, and adherence to the acceptance criteria. Output valid JSON with "
    "keys: verdict ('approve' or 'revise'), feedback (str — empty if approved, "
    "specific revision instructions if revise)."
)


def _reviewer_worktree_path(repo_path: str, branch: str) -> Path:
    slug = branch.replace("/", "-")
    return Path(repo_path).parent / f".worktrees/review-{slug}"


def make_reviewer_node(repo_path: str, branch_prefix: str, model: str, agent_loader: AgentLoader):
    def reviewer_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("reviewer", state["task_id"])
        branch = f"{branch_prefix}/{state['task_id']}"

        base_prompt = agent_loader.load_workflow_agent("reviewer") or REVIEW_PROMPT

        project_context = state.get("project_context", "")
        if project_context:
            base_prompt = f"{base_prompt}\n\n{project_context}"

        prompt = (
            f"{base_prompt}\n\n"
            f"Task: {state['task_id']}\n"
            f"Review the current changes on branch '{branch}'."
        )

        worktree_path = _reviewer_worktree_path(repo_path, branch)
        try:
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )

            if bus:
                bus.cli_start("reviewer", model, 1, state["task_id"])
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", model],
                capture_output=True,
                text=True,
                cwd=str(worktree_path),
                timeout=300,
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path)],
                cwd=repo_path,
                capture_output=True,
            )

        parsed = extract_json(result.stdout)
        verdict = parsed.get("verdict", "revise")
        feedback = parsed.get("feedback", "")
        if bus:
            bus.cli_done("reviewer", 1, verdict == "approve", state["task_id"])

        if verdict == "approve":
            if bus:
                bus.node_exit("reviewer", state["task_id"], "approved")
            return {
                "verdict": "approve",
                "feedback": "",
                "status": "testing",
                "agent_output": result.stdout,
            }
        if bus:
            bus.node_exit(
                "reviewer",
                state["task_id"],
                f"revise cycle={state['review_cycles'] + 1}",
            )
        return {
            "verdict": "revise",
            "feedback": feedback,
            "review_cycles": state["review_cycles"] + 1,
            "agent_output": result.stdout,
        }

    return reviewer_node
```

- [ ] **Step 6: Update existing tests to match new subprocess call pattern**

The existing tests mock `subprocess.run` with a single call. Now there are three calls (worktree add, claude, worktree remove). Update the mock to handle all three:

```python
def _make_subprocess_mock(stdout: str):
    """Create a mock that handles worktree add, claude, and worktree remove calls."""
    def side_effect(cmd, **kwargs):
        if "worktree" in cmd:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(stdout=stdout, stderr="", returncode=0)
    mock = MagicMock(side_effect=side_effect)
    return mock
```

Then update each existing test to use `_make_subprocess_mock` instead of directly setting `mock_run.return_value`. The assertion patterns need to filter for the `claude` call specifically (use `[c for c in mock_run.call_args_list if "claude" in str(c.args[0])]`).

- [ ] **Step 7: Run all reviewer tests**

Run: `.venv/bin/python -m pytest tests/test_reviewer.py -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add orchestrator/nodes/reviewer.py tests/test_reviewer.py
git commit -m "fix: reviewer runs in worktree so it can see the developer's changes"
```

---

### Task 2: Developer commits code before handoff to reviewer

The DoerAgent runs `claude -p` in a worktree, which creates/modifies files. But nothing stages or commits those files to the branch. The reviewer (now running in a worktree of the same branch) still won't see a diff unless the code is committed.

**Files:**
- Modify: `orchestrator/nodes/developer.py`
- Modify: `tests/test_developer.py`

- [ ] **Step 1: Write failing test — developer commits after successful ralph_loop**

Add to `tests/test_developer.py`:

```python
def test_developer_commits_after_success(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer runs git add + commit in the worktree after a successful ralph_loop."""
    mock_doer.return_value.ralph_loop.return_value = RalphResult(
        success=True, iterations=1, output="Code written.\nTASK COMPLETE"
    )
    mock_doer.return_value.create_worktree.return_value = Path("/tmp/worktree")

    with patch("orchestrator.nodes.developer.subprocess.run") as mock_subprocess:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        node_fn = make_developer_node(
            repo_path="/tmp/repo",
            branch_prefix="scaffold",
            agent_loader=agent_loader,
            agents_config=agents_config,
        )
        state = initial_state(task_id="task-020", level="task")
        state["specialists"] = ["python-expert"]
        state["agent_output"] = "Create main.py"

        node_fn(state)

        # Check git add -A was called in worktree
        git_calls = [c for c in mock_subprocess.call_args_list if "git" in str(c.args[0])]
        add_calls = [c for c in git_calls if "add" in c.args[0] and "-A" in c.args[0]]
        assert len(add_calls) == 1
        assert str(add_calls[0].kwargs.get("cwd", "")) == "/tmp/worktree"

        # Check git commit was called
        commit_calls = [c for c in git_calls if "commit" in c.args[0]]
        assert len(commit_calls) == 1
        assert str(commit_calls[0].kwargs.get("cwd", "")) == "/tmp/worktree"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_developer.py::test_developer_commits_after_success -v`
Expected: FAIL — no subprocess calls for git add/commit

- [ ] **Step 3: Write failing test — developer does NOT commit after failure**

```python
def test_developer_does_not_commit_on_failure(mock_doer, mock_advisor, agent_loader, agents_config):
    """Developer does not commit when ralph_loop fails (status=stuck)."""
    mock_doer.return_value.ralph_loop.return_value = RalphResult(
        success=False, iterations=10, output="Still broken."
    )

    with patch("orchestrator.nodes.developer.subprocess.run") as mock_subprocess:
        node_fn = make_developer_node(
            repo_path="/tmp/repo",
            branch_prefix="scaffold",
            agent_loader=agent_loader,
            agents_config=agents_config,
        )
        state = initial_state(task_id="task-021", level="task")
        state["specialists"] = ["python-expert"]
        state["agent_output"] = "Fix bugs"

        node_fn(state)

        # No git add/commit calls
        git_calls = [c for c in mock_subprocess.call_args_list if "git" in str(c.args[0])]
        commit_calls = [c for c in git_calls if "commit" in c.args[0]]
        assert len(commit_calls) == 0
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_developer.py::test_developer_does_not_commit_on_failure -v`
Expected: PASS (no commits happen now, and we want none on failure — so this should already pass). If it does, good — it's a guard rail test.

- [ ] **Step 5: Implement git add + commit in developer node**

Add `import subprocess` to `orchestrator/nodes/developer.py` (it's not currently imported there — DoerAgent handles subprocess internally).

After the `ralph_loop` call succeeds (inside the `try` block, after `result = doer.ralph_loop(...)`), add git add + commit:

```python
        try:
            result = doer.ralph_loop(
                worktree_path=worktree_path,
                prompt=prompt,
                failure_context=failure_context,
                task_id=state["task_id"],
                scaffold_budget_usd=scaffold_budget_usd,
            )

            if result.success:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(worktree_path),
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", f"feat: {state['task_id']} implementation"],
                    cwd=str(worktree_path),
                    capture_output=True,
                )
        finally:
            doer.cleanup_worktree(repo_path, worktree_path)
```

Note: `git commit` does not use `check=True` because it returns non-zero if there's nothing to commit (which is fine — the developer may have committed during its own run via Claude Code).

- [ ] **Step 6: Run new and existing developer tests**

Run: `.venv/bin/python -m pytest tests/test_developer.py -v`
Expected: All pass. The existing tests mock DoerAgent so they won't hit the new subprocess calls. The new tests specifically patch `subprocess.run` to verify the calls.

- [ ] **Step 7: Commit**

```bash
git add orchestrator/nodes/developer.py tests/test_developer.py
git commit -m "fix: developer commits code to branch before reviewer handoff"
```

---

### Task 3: Specialist fallback uses detected_languages instead of hardcoding python-expert

When `specialists` list is empty and `detect_specialist` returns nothing (greenfield repo, no file extensions to match), `developer.py:52` hardcodes `python-expert`. It should check `state["detected_languages"]` (populated by onboarding from CLAUDE.md) and use the first matching specialist.

**Files:**
- Modify: `orchestrator/nodes/developer.py`
- Modify: `tests/test_developer.py`

- [ ] **Step 1: Write failing test — fallback uses detected_languages**

Add to `tests/test_developer.py`:

```python
def test_developer_fallback_uses_detected_languages(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer falls back to detected_languages when no specialist detected from files."""
    agents_config.specialists["go-expert"] = {
        "model": "claude-sonnet-4-6",
        "execution": "cli",
        "max_iterations": 10,
        "completion_promise": "TASK COMPLETE",
    }
    agent_loader.detect_specialist.return_value = ""

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-030", level="task")
    state["specialists"] = []
    state["detected_languages"] = ["go", "typescript"]
    state["agent_output"] = "Build the auth endpoint"

    node_fn(state)

    mock_doer.assert_called_once()
    assert mock_doer.call_args.kwargs["role"] == "go-expert"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_developer.py::test_developer_fallback_uses_detected_languages -v`
Expected: FAIL — currently falls back to `python-expert`

- [ ] **Step 3: Write failing test — fallback still uses python-expert when no languages detected**

```python
def test_developer_fallback_python_when_no_languages(
    mock_doer, mock_advisor, agent_loader, agents_config
):
    """Developer falls back to python-expert when detected_languages is also empty."""
    agent_loader.detect_specialist.return_value = ""

    node_fn = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=agent_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-031", level="task")
    state["specialists"] = []
    state["detected_languages"] = []
    state["agent_output"] = "Do something"

    node_fn(state)

    mock_doer.assert_called_once()
    assert mock_doer.call_args.kwargs["role"] == "python-expert"
```

- [ ] **Step 4: Run test — should pass (guards existing behavior)**

Run: `.venv/bin/python -m pytest tests/test_developer.py::test_developer_fallback_python_when_no_languages -v`
Expected: PASS — this is the current behavior

- [ ] **Step 5: Implement language-aware specialist fallback**

In `orchestrator/nodes/developer.py`, import the `LANGUAGE_TO_SPECIALIST` mapping from onboarding (or duplicate it locally to avoid circular imports). Replace the final fallback:

Change the block starting at line 49 (`if not specialist_name and specialist_names:`) through line 52 (`specialist_name = "python-expert"`):

```python
        if not specialist_name and specialist_names:
            specialist_name = specialist_names[0]
        if not specialist_name:
            detected_langs = state.get("detected_languages", [])
            for lang in detected_langs:
                candidate = LANGUAGE_TO_SPECIALIST.get(lang)
                if candidate and candidate in agents_config.specialists:
                    specialist_name = candidate
                    break
        if not specialist_name:
            specialist_name = "python-expert"
```

Add the mapping at module level:

```python
LANGUAGE_TO_SPECIALIST: dict[str, str] = {
    "python": "python-expert",
    "go": "go-expert",
    "typescript": "typescript-expert",
    "javascript": "typescript-expert",
}
```

- [ ] **Step 6: Run all developer tests**

Run: `.venv/bin/python -m pytest tests/test_developer.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add orchestrator/nodes/developer.py tests/test_developer.py
git commit -m "fix: specialist fallback uses detected project languages instead of hardcoding python"
```

---

### Task 4: Task dependency ordering in dispatcher

The PO decomposes specs into child tasks but has no way to express dependencies. The dispatcher runs them in whatever order the PO returned. This means "campaign creation" might run before "database schema" — guaranteed failure.

Two changes needed:
1. PO output schema gains an optional `depends_on` field (list of sibling task titles)
2. Dispatcher topologically sorts children by `depends_on` before executing

**Files:**
- Modify: `orchestrator/nodes/product_owner.py` (schema instruction update)
- Modify: `orchestrator/dispatcher.py` (topological sort)
- Modify: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing test — dispatcher respects depends_on ordering**

Add to `tests/test_dispatcher.py`:

```python
def test_dispatcher_respects_depends_on_ordering(db):
    """Children with depends_on run after their dependencies."""
    execution_order = []

    def mock_invoke(state, config):
        title = state.get("agent_output", "").split("\n")[0].replace("# ", "")
        execution_order.append(title)
        return {
            "status": "done",
            "child_tasks": [],
            "agent_output": state.get("agent_output", ""),
            "project_context": "",
            "specialists": [],
            "advisory": [],
            "detected_languages": [],
            "test_framework": "",
        }

    graph = MagicMock()
    graph.invoke = mock_invoke
    tree = TaskTree(db)
    root_id = tree.create(title="Root", level="epic")

    state = initial_state(task_id=root_id, level="epic")
    state["child_tasks"] = [
        {"title": "Seed data", "level": "task", "depends_on": ["Database schema"]},
        {"title": "Database schema", "level": "task"},
        {"title": "Auth", "level": "task", "depends_on": ["Database schema"]},
    ]
    state["status"] = "decomposing"

    # Patch graph.invoke to handle decomposed state
    original_run_task = run_task.__wrapped__ if hasattr(run_task, "__wrapped__") else None

    run_task(graph, tree, state, root_id)

    # Database schema must come before Seed data and Auth
    schema_idx = execution_order.index("Database schema")
    seed_idx = execution_order.index("Seed data")
    auth_idx = execution_order.index("Auth")
    assert schema_idx < seed_idx
    assert schema_idx < auth_idx
```

Note: This test will need adjustment depending on how `run_task` handles children. The key assertion: children with `depends_on` execute after the tasks they depend on.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatcher.py::test_dispatcher_respects_depends_on_ordering -v`
Expected: FAIL — dispatcher processes children in original order

- [ ] **Step 3: Implement topological sort in dispatcher**

Add a `_topo_sort` function to `orchestrator/dispatcher.py`:

```python
def _topo_sort(children: list[dict]) -> list[dict]:
    """Sort children by depends_on. Tasks with no dependencies come first.
    Falls back to original order if depends_on is not used or on cycles."""
    if not any(c.get("depends_on") for c in children if isinstance(c, dict)):
        return children

    title_to_idx: dict[str, int] = {}
    for i, c in enumerate(children):
        if isinstance(c, dict):
            title_to_idx[c.get("title", "")] = i

    # Build adjacency: task -> set of tasks it must come after
    in_degree: dict[int, int] = {i: 0 for i in range(len(children))}
    graph: dict[int, list[int]] = {i: [] for i in range(len(children))}
    for i, c in enumerate(children):
        if not isinstance(c, dict):
            continue
        for dep_title in c.get("depends_on", []):
            dep_idx = title_to_idx.get(dep_title)
            if dep_idx is not None:
                graph[dep_idx].append(i)
                in_degree[i] += 1

    # Kahn's algorithm
    queue = [i for i in range(len(children)) if in_degree[i] == 0]
    sorted_indices: list[int] = []
    while queue:
        # Stable sort: pick the lowest original index among ready tasks
        queue.sort()
        node = queue.pop(0)
        sorted_indices.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_indices) != len(children):
        return children  # cycle detected, fall back to original order

    return [children[i] for i in sorted_indices]
```

Then in `run_task`, before the `for child in children:` loop, add:

```python
    children = _topo_sort(children)
```

- [ ] **Step 4: Update PO system prompt to include depends_on**

In `orchestrator/nodes/product_owner.py`, update `SYSTEM_PROMPT` to include `depends_on`:

Change the output format description from:
```
"Each object has: title (str), level ('feature' or 'task'), spec_ref (str), "
"acceptance (list[str])."
```
to:
```
"Each object has: title (str), level ('feature' or 'task'), spec_ref (str), "
"acceptance (list[str]), depends_on (list[str] — titles of sibling tasks that "
"must complete first; omit or empty list if no dependencies)."
```

- [ ] **Step 5: Write test for _topo_sort directly**

Add to `tests/test_dispatcher.py`:

```python
from orchestrator.dispatcher import _topo_sort


def test_topo_sort_basic():
    children = [
        {"title": "B", "depends_on": ["A"]},
        {"title": "A"},
        {"title": "C", "depends_on": ["A", "B"]},
    ]
    result = _topo_sort(children)
    titles = [c["title"] for c in result]
    assert titles.index("A") < titles.index("B")
    assert titles.index("B") < titles.index("C")


def test_topo_sort_no_dependencies():
    children = [
        {"title": "A"},
        {"title": "B"},
        {"title": "C"},
    ]
    result = _topo_sort(children)
    assert [c["title"] for c in result] == ["A", "B", "C"]


def test_topo_sort_cycle_falls_back():
    children = [
        {"title": "A", "depends_on": ["B"]},
        {"title": "B", "depends_on": ["A"]},
    ]
    result = _topo_sort(children)
    assert result == children  # original order preserved
```

- [ ] **Step 6: Run all dispatcher tests**

Run: `.venv/bin/python -m pytest tests/test_dispatcher.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add orchestrator/nodes/product_owner.py orchestrator/dispatcher.py tests/test_dispatcher.py
git commit -m "feat: task decomposition supports dependency ordering via depends_on"
```

---

### Task 5: Add `scaffold clean` CLI command

The previous run left 6 orphaned worktrees and a stale DB. Need a command to clean up before the next run.

**Files:**
- Modify: `orchestrator/__main__.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test — clean command exists**

Add to `tests/test_cli.py`:

```python
from click.testing import CliRunner
from orchestrator.__main__ import cli


def test_clean_command_exists():
    runner = CliRunner()
    result = runner.invoke(cli, ["clean", "--help"])
    assert result.exit_code == 0
    assert "Clean up" in result.output or "clean" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py::test_clean_command_exists -v`
Expected: FAIL — no "clean" command

- [ ] **Step 3: Write failing test — clean removes worktrees and DB**

```python
@patch("orchestrator.__main__.subprocess.run")
@patch("orchestrator.__main__.Path.exists", return_value=True)
@patch("orchestrator.__main__.Path.unlink")
def test_clean_removes_db_and_worktrees(mock_unlink, mock_exists, mock_subprocess):
    mock_subprocess.return_value = MagicMock(
        stdout="/tmp/.worktrees/scaffold-task-001 abc1234 [scaffold/task-001]\n"
               "/tmp/repo abc1234 [main]\n",
        returncode=0,
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["clean", "--repo", "/tmp/repo", "--db", "test.db", "--yes"])
    assert result.exit_code == 0
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py::test_clean_removes_db_and_worktrees -v`
Expected: FAIL

- [ ] **Step 5: Implement clean command**

Add to `orchestrator/__main__.py`:

```python
@cli.command()
@click.option("--repo", required=True, type=click.Path(exists=True), help="Path to target repo")
@click.option("--db", default="scaffold.db", help="Path to scaffold database to remove")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def clean(repo, db, yes):
    """Clean up worktrees and database from a previous run."""
    import subprocess as sp

    repo_path = Path(repo).resolve()

    # List scaffold worktrees
    result = sp.run(
        ["git", "worktree", "list"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    worktree_lines = [
        line for line in result.stdout.splitlines()
        if "scaffold" in line.lower() and str(repo_path) not in line.split()[0]
    ]

    # List scaffold branches
    branch_result = sp.run(
        ["git", "branch", "--list", "scaffold/*"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    branches = [b.strip().lstrip("+ ") for b in branch_result.stdout.splitlines() if b.strip()]

    db_path = Path(db)
    checkpoint_path = Path(_checkpoint_path(db))

    if not worktree_lines and not branches and not db_path.exists():
        click.echo("Nothing to clean.")
        return

    click.echo("Will remove:")
    for line in worktree_lines:
        click.echo(f"  worktree: {line.split()[0]}")
    for branch in branches:
        click.echo(f"  branch: {branch}")
    if db_path.exists():
        click.echo(f"  database: {db}")
    if checkpoint_path.exists():
        click.echo(f"  checkpoints: {checkpoint_path}")

    if not yes:
        click.confirm("Proceed?", abort=True)

    for line in worktree_lines:
        wt_path = line.split()[0]
        sp.run(
            ["git", "worktree", "remove", "--force", wt_path],
            cwd=str(repo_path),
            capture_output=True,
        )
        click.echo(f"  removed worktree: {wt_path}")

    sp.run(["git", "worktree", "prune"], cwd=str(repo_path), capture_output=True)

    for branch in branches:
        sp.run(
            ["git", "branch", "-D", branch],
            cwd=str(repo_path),
            capture_output=True,
        )
        click.echo(f"  deleted branch: {branch}")

    if db_path.exists():
        db_path.unlink()
        click.echo(f"  removed database: {db}")
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        click.echo(f"  removed checkpoints: {checkpoint_path}")

    # Also clean WAL/SHM files
    for suffix in ["-wal", "-shm"]:
        wal_path = Path(f"{db}{suffix}")
        if wal_path.exists():
            wal_path.unlink()

    click.echo("Clean complete.")
```

- [ ] **Step 6: Run cli tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add orchestrator/__main__.py tests/test_cli.py
git commit -m "feat: add scaffold clean command for worktree and DB cleanup"
```

---

### Task 6: Increase default timeout and budget for Inkwell

The 600s default timeout is too short for bootstrapping a greenfield project. The $5 budget is also too tight for a 9-task run with Opus advisors.

**Files:**
- Modify: `config/agents.yaml`
- Modify: `config/projects/inkwell.yaml`

- [ ] **Step 1: Update specialist timeouts in agents.yaml**

Change all CLI specialist timeouts from `900` to `1800`:

```yaml
specialists:
  python-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
    timeout: 1800
  go-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
    timeout: 1800
  react-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
    timeout: 1800
  typescript-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
    timeout: 1800
```

- [ ] **Step 2: Update inkwell project budget**

Change `config/projects/inkwell.yaml`:

```yaml
repo_path: /Users/antonypegg/PROJECTS/inkwell
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold_inkwell.db
max_budget_usd: 25.00
```

- [ ] **Step 3: Commit**

```bash
git add config/agents.yaml config/projects/inkwell.yaml
git commit -m "chore: increase specialist timeout to 1800s and inkwell budget to $25"
```

---

### Task 7: Clean up stale Inkwell state

Before the next trial run, remove the 6 orphaned worktrees and stale DB.

**Files:** None (CLI commands only)

- [ ] **Step 1: Run the new clean command**

```bash
.venv/bin/python -m orchestrator clean --repo /Users/antonypegg/PROJECTS/inkwell --db scaffold_inkwell.db --yes
```

If Task 5 isn't merged yet, do it manually:

```bash
cd /Users/antonypegg/PROJECTS/inkwell
git worktree remove --force /Users/antonypegg/PROJECTS/.worktrees/scaffold-011b4682-e8d
git worktree remove --force /Users/antonypegg/PROJECTS/.worktrees/scaffold-39fbf4dd-1a9
git worktree remove --force /Users/antonypegg/PROJECTS/.worktrees/scaffold-8bba165c-99e
git worktree remove --force /Users/antonypegg/PROJECTS/.worktrees/scaffold-9538ef0f-84f
git worktree remove --force /Users/antonypegg/PROJECTS/.worktrees/scaffold-ad5ed04d-cc9
git worktree remove --force /Users/antonypegg/PROJECTS/.worktrees/scaffold-c91d5764-31e
git worktree prune
git branch -D scaffold/011b4682-e8d scaffold/39fbf4dd-1a9 scaffold/8bba165c-99e scaffold/9538ef0f-84f scaffold/ad5ed04d-cc9 scaffold/c91d5764-31e scaffold/166998d6-05d scaffold/5d4e232a-edf
cd /Users/antonypegg/PROJECTS/scaffold
rm -f scaffold_inkwell.db scaffold_inkwell_checkpoints.db scaffold_inkwell.db-wal scaffold_inkwell.db-shm
```

- [ ] **Step 2: Verify clean state**

```bash
cd /Users/antonypegg/PROJECTS/inkwell && git worktree list && git branch -a
```

Expected: Only `main` branch, single worktree entry pointing at the main checkout.

---

### Task 8: Run full test suite and lint

**Files:** None

- [ ] **Step 1: Run tests**

```bash
cd /Users/antonypegg/PROJECTS/scaffold
.venv/bin/python -m pytest tests/ -v
```

Expected: All pass

- [ ] **Step 2: Run linter**

```bash
.venv/bin/ruff check orchestrator/ tests/
.venv/bin/ruff format --check orchestrator/ tests/
```

Expected: Clean

- [ ] **Step 3: Run type checker**

```bash
.venv/bin/pyright orchestrator/
```

Expected: Clean (or only pre-existing issues)
