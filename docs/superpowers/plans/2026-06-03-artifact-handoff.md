# File-Based Artifact Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace inline `agent_output` state passing with file-based artifact handoff, so every agent writes its output to a persistent file that downstream agents read from — enabling debugging, resumption, and error tracing.

**Architecture:** A new `orchestrator/artifacts.py` module provides `write_artifact()` and `read_artifact()` helpers that write to `.scaffold/artifacts/{task_id}/{role}.md` inside the target repo. Every pipeline node writes its output as an artifact file. Consumer nodes (architect, developer) read upstream artifacts from disk instead of from `agent_output` in LangGraph state. The dispatcher writes child task specs as artifact files. `agent_output` remains in TaskState and is still set (for backward compatibility), but handoffs between nodes now go through files.

**Tech Stack:** Python 3.12+, pytest, LangGraph

---

## Design

### Artifact Directory Layout

```
{target_repo}/.scaffold/artifacts/
  {task_id}/
    task_spec.md       -- child task spec (written by dispatcher)
    product_owner.md   -- PO decomposition output
    architect.md       -- technical design
    designer.md        -- UI/UX specification
    developer.md       -- implementation summary (not the code — that's in git)
    reviewer.md        -- review verdict and feedback
    qa.md              -- test results
```

### Key Decisions

1. **Artifacts live in the target repo** (under `.scaffold/`), not in the scaffold project.
2. **Files are overwritten** on each cycle iteration. No versioning — LangGraph checkpoints handle history.
3. **`agent_output` in TaskState is still set** with the full text for backward compat, but consumers read from files.
4. **`repo_path` is already available** in every node's factory closure. The dispatcher needs it threaded through `run_task`.

### Data Flow After This Change

```
Dispatcher  --writes-->  .scaffold/artifacts/{child_id}/task_spec.md
PO          --writes-->  .scaffold/artifacts/{task_id}/product_owner.md
Architect   --reads-->   .scaffold/artifacts/{task_id}/task_spec.md
            --writes-->  .scaffold/artifacts/{task_id}/architect.md
Designer    --reads-->   .scaffold/artifacts/{task_id}/task_spec.md
            --writes-->  .scaffold/artifacts/{task_id}/designer.md
Developer   --reads-->   .scaffold/artifacts/{task_id}/architect.md
            --reads-->   .scaffold/artifacts/{task_id}/designer.md  (if has_ui)
            --reads-->   .scaffold/artifacts/{task_id}/task_spec.md
Reviewer    --writes-->  .scaffold/artifacts/{task_id}/reviewer.md
QA          --writes-->  .scaffold/artifacts/{task_id}/qa.md
```

## File Structure

| File | Responsibility |
|------|---------------|
| `orchestrator/artifacts.py` | New module: `write_artifact`, `read_artifact`, `artifact_dir` helpers |
| `orchestrator/dispatcher.py` | Write child task specs to artifact files; accept `repo_path` parameter |
| `orchestrator/__main__.py` | Pass `repo_path` to `run_task` calls |
| `orchestrator/nodes/product_owner.py` | Write PO output to artifact file |
| `orchestrator/nodes/architect.py` | Read task_spec artifact, write architect artifact |
| `orchestrator/nodes/designer.py` | Read task_spec artifact, write designer artifact |
| `orchestrator/nodes/developer.py` | Read architect/designer/task_spec artifacts instead of `agent_output` |
| `orchestrator/nodes/reviewer.py` | Write review artifact |
| `orchestrator/nodes/qa.py` | Write QA artifact |
| `tests/test_artifacts.py` | New test file for artifacts module |
| `tests/test_dispatcher.py` | Update for repo_path parameter and artifact writes |
| `tests/test_product_owner.py` | Update for artifact writes |
| `tests/test_architect.py` | Update for artifact reads/writes |
| `tests/test_designer.py` | Update for artifact reads/writes |
| `tests/test_developer.py` | Update for artifact reads |
| `tests/test_reviewer.py` | Update for artifact writes |
| `tests/test_qa.py` | Update for artifact writes |

---

### Task 1: Create `orchestrator/artifacts.py`

**Files:**
- Create: `orchestrator/artifacts.py`
- Test: `tests/test_artifacts.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_artifacts.py
from pathlib import Path

from orchestrator.artifacts import artifact_dir, read_artifact, write_artifact


def test_write_artifact_creates_file(tmp_path):
    path = write_artifact(str(tmp_path), "task-001", "architect", "design content")
    assert path.exists()
    assert path.read_text() == "design content"
    assert path == tmp_path / ".scaffold" / "artifacts" / "task-001" / "architect.md"


def test_write_artifact_creates_directories(tmp_path):
    write_artifact(str(tmp_path), "task-001", "architect", "content")
    assert (tmp_path / ".scaffold" / "artifacts" / "task-001").is_dir()


def test_write_artifact_overwrites_existing(tmp_path):
    write_artifact(str(tmp_path), "task-001", "architect", "v1")
    write_artifact(str(tmp_path), "task-001", "architect", "v2")
    path = tmp_path / ".scaffold" / "artifacts" / "task-001" / "architect.md"
    assert path.read_text() == "v2"


def test_read_artifact_returns_content(tmp_path):
    write_artifact(str(tmp_path), "task-001", "architect", "design content")
    content = read_artifact(str(tmp_path), "task-001", "architect")
    assert content == "design content"


def test_read_artifact_returns_empty_when_missing(tmp_path):
    content = read_artifact(str(tmp_path), "task-001", "architect")
    assert content == ""


def test_artifact_dir_returns_path(tmp_path):
    result = artifact_dir(str(tmp_path), "task-001")
    assert result == tmp_path / ".scaffold" / "artifacts" / "task-001"


def test_write_artifact_no_op_when_no_repo_path():
    result = write_artifact("", "task-001", "architect", "content")
    assert result is None


def test_read_artifact_returns_empty_when_no_repo_path():
    content = read_artifact("", "task-001", "architect")
    assert content == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_artifacts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'orchestrator.artifacts'`

- [ ] **Step 3: Write the implementation**

```python
# orchestrator/artifacts.py
from pathlib import Path

ARTIFACTS_DIR = ".scaffold/artifacts"


def artifact_dir(repo_path: str, task_id: str) -> Path:
    return Path(repo_path) / ARTIFACTS_DIR / task_id


def write_artifact(repo_path: str, task_id: str, role: str, content: str) -> Path | None:
    if not repo_path:
        return None
    directory = artifact_dir(repo_path, task_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{role}.md"
    path.write_text(content)
    return path


def read_artifact(repo_path: str, task_id: str, role: str) -> str:
    if not repo_path:
        return ""
    path = artifact_dir(repo_path, task_id) / f"{role}.md"
    if path.exists():
        return path.read_text()
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_artifacts.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `make check`
Expected: All checks pass

- [ ] **Step 6: Commit**

```bash
git add orchestrator/artifacts.py tests/test_artifacts.py
git commit -m "feat: add artifacts module for file-based agent handoff"
```

---

### Task 2: Update dispatcher to write child task spec artifacts

**Depends on:** Task 1

**Files:**
- Modify: `orchestrator/dispatcher.py:69-160`
- Modify: `orchestrator/__main__.py:93-99`
- Test: `tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dispatcher.py`:

```python
def test_run_task_writes_child_spec_artifact(db, tmp_path):
    from orchestrator.task_tree import TaskTree

    tree = TaskTree(db)
    parent_id = tree.create(title="Epic", level="epic")

    graph = MagicMock()

    def mock_invoke(state, config=None):
        if state["level"] == "epic":
            return {
                "status": "decomposing",
                "child_tasks": [
                    {
                        "title": "Auth Module",
                        "level": "task",
                        "spec_ref": "Section 2.1",
                        "acceptance": ["JWT validates", "Tokens expire"],
                    },
                ],
                "project_context": "",
                "specialists": [],
                "advisory": [],
                "detected_languages": [],
                "test_framework": "",
            }
        return {"status": "done", "child_tasks": []}

    graph.invoke.side_effect = mock_invoke

    state = initial_state(task_id=parent_id, level="epic")
    run_task(graph, tree, state, parent_id, repo_path=str(tmp_path))

    children = tree.list_children(parent_id)
    child_id = children[0]["id"]
    artifact_path = tmp_path / ".scaffold" / "artifacts" / child_id / "task_spec.md"
    assert artifact_path.exists()
    content = artifact_path.read_text()
    assert "Auth Module" in content
    assert "JWT validates" in content
    assert "Section 2.1" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dispatcher.py::test_run_task_writes_child_spec_artifact -v`
Expected: FAIL — `run_task` doesn't accept `repo_path`

- [ ] **Step 3: Update `run_task` to accept `repo_path` and write child spec artifacts**

In `orchestrator/dispatcher.py`:

1. Add import: `from orchestrator.artifacts import write_artifact`
2. Add `repo_path: str = ""` parameter to `run_task`
3. After constructing `child_spec`, call `write_artifact(repo_path, child_id, "task_spec", child_spec)`
4. Pass `repo_path` through the recursive `run_task` call

```python
def run_task(
    graph: CompiledStateGraph,
    tree: TaskTree,
    state: TaskState,
    thread_id: str,
    max_budget_usd: float | None = None,
    repo_path: str = "",
) -> dict:
```

After line 158 (`child_state["agent_output"] = child_spec`), add:

```python
        write_artifact(repo_path, child_id, "task_spec", child_spec)
```

Update the recursive call (line 160) to pass repo_path:

```python
        run_task(graph, tree, child_state, child_id, max_budget_usd=max_budget_usd, repo_path=repo_path)
```

- [ ] **Step 4: Update `__main__.py` to pass `repo_path` to `run_task`**

In `orchestrator/__main__.py`, update the `run_task` call (line 93) to pass repo_path:

```python
            run_task(
                graph,
                tree,
                state,
                task_id,
                max_budget_usd=cfg.project.max_budget_usd,
                repo_path=cfg.project.repo_path,
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_dispatcher.py -v`
Expected: All tests PASS (existing tests still work because `repo_path` defaults to `""`)

- [ ] **Step 6: Run full test suite**

Run: `make check`
Expected: All checks pass

- [ ] **Step 7: Commit**

```bash
git add orchestrator/dispatcher.py orchestrator/__main__.py tests/test_dispatcher.py
git commit -m "feat: dispatcher writes child task specs as artifact files"
```

---

### Task 3: Update product_owner to write artifact

**Depends on:** Task 1

**Files:**
- Modify: `orchestrator/nodes/product_owner.py:85-89`
- Test: `tests/test_product_owner.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_product_owner.py`:

```python
def test_product_owner_writes_artifact(mock_client, mock_agent_loader, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("Build auth")
    node_fn = make_product_owner_node(
        mock_client, str(spec), mock_agent_loader, repo_path=str(tmp_path)
    )
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    artifact = tmp_path / ".scaffold" / "artifacts" / "epic-001" / "product_owner.md"
    assert artifact.exists()
    assert "children" in artifact.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_product_owner.py::test_product_owner_writes_artifact -v`
Expected: FAIL — no artifact file created

- [ ] **Step 3: Add artifact write to product_owner_node**

In `orchestrator/nodes/product_owner.py`:

1. Add import: `from orchestrator.artifacts import write_artifact`
2. After `result = agent.call(...)` and before the return statement, add:

```python
        write_artifact(repo_path, state["task_id"], "product_owner", result.text)
```

The `repo_path` variable is already in scope from the factory closure.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_product_owner.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/product_owner.py tests/test_product_owner.py
git commit -m "feat: product_owner writes output to artifact file"
```

---

### Task 4: Update architect to read task_spec and write artifact

**Depends on:** Task 1

**Files:**
- Modify: `orchestrator/nodes/architect.py:47-54,75-82`
- Test: `tests/test_architect.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_architect.py`:

```python
def test_architect_writes_artifact(mock_client, mock_agent_loader, tmp_path):
    node_fn = make_architect_node(
        mock_client, mock_agent_loader, repo_path=str(tmp_path)
    )
    state = initial_state(task_id="feat-001", level="feature")
    node_fn(state)
    artifact = tmp_path / ".scaffold" / "artifacts" / "feat-001" / "architect.md"
    assert artifact.exists()
    assert "technical_design" in artifact.read_text()


def test_architect_reads_task_spec_artifact(mock_client, mock_agent_loader, tmp_path):
    # Write a task_spec artifact
    spec_dir = tmp_path / ".scaffold" / "artifacts" / "feat-001"
    spec_dir.mkdir(parents=True)
    (spec_dir / "task_spec.md").write_text("# Auth Module\n\nAcceptance criteria:\n- JWT validates")

    node_fn = make_architect_node(
        mock_client, mock_agent_loader, repo_path=str(tmp_path)
    )
    state = initial_state(task_id="feat-001", level="feature")
    node_fn(state)

    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    user_msg = messages[0]["content"]
    assert "Auth Module" in user_msg
    assert "JWT validates" in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_architect.py::test_architect_writes_artifact tests/test_architect.py::test_architect_reads_task_spec_artifact -v`
Expected: FAIL

- [ ] **Step 3: Update architect node**

In `orchestrator/nodes/architect.py`:

1. Add import: `from orchestrator.artifacts import read_artifact, write_artifact`
2. In `architect_node`, read the task_spec artifact and merge with existing agent_output:

```python
        task_spec = read_artifact(repo_path, state["task_id"], "task_spec")
        agent_output = task_spec or state.get("agent_output", "")
```

This prefers the artifact file but falls back to state for backward compat.

3. After parsing the result, write the artifact:

```python
        write_artifact(repo_path, state["task_id"], "architect", result.text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_architect.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/architect.py tests/test_architect.py
git commit -m "feat: architect reads task_spec and writes design to artifact files"
```

---

### Task 5: Update designer to read task_spec and write artifact

**Depends on:** Task 1

**Files:**
- Modify: `orchestrator/nodes/designer.py:42,61`
- Test: `tests/test_designer.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_designer.py`:

```python
def test_designer_writes_artifact(mock_client, mock_agent_loader, tmp_path):
    node_fn = make_designer_node(
        mock_client, mock_agent_loader, repo_path=str(tmp_path)
    )
    state = initial_state(task_id="feat-001", level="feature")
    node_fn(state)
    artifact = tmp_path / ".scaffold" / "artifacts" / "feat-001" / "designer.md"
    assert artifact.exists()


def test_designer_reads_task_spec_artifact(mock_client, mock_agent_loader, tmp_path):
    spec_dir = tmp_path / ".scaffold" / "artifacts" / "feat-001"
    spec_dir.mkdir(parents=True)
    (spec_dir / "task_spec.md").write_text("# Dashboard UI\n\nAcceptance criteria:\n- Shows stats")

    node_fn = make_designer_node(
        mock_client, mock_agent_loader, repo_path=str(tmp_path)
    )
    state = initial_state(task_id="feat-001", level="feature")
    node_fn(state)

    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    user_msg = messages[0]["content"]
    assert "Dashboard UI" in user_msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_designer.py::test_designer_writes_artifact tests/test_designer.py::test_designer_reads_task_spec_artifact -v`
Expected: FAIL

- [ ] **Step 3: Update designer node**

In `orchestrator/nodes/designer.py`:

1. Add import: `from orchestrator.artifacts import read_artifact, write_artifact`
2. Read the task_spec artifact and include it in the user message:

```python
        task_spec = read_artifact(repo_path, state["task_id"], "task_spec")
        user_message = f"Create a UI/UX specification for this task.\n\nTask: {state['task_id']}\n"
        if task_spec:
            user_message += f"\n{task_spec}\n"
```

3. Write the artifact after the API call:

```python
        write_artifact(repo_path, state["task_id"], "designer", result.text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_designer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/designer.py tests/test_designer.py
git commit -m "feat: designer reads task_spec and writes output to artifact files"
```

---

### Task 6: Update developer to read from artifact files

**Depends on:** Task 1, Task 4, Task 5

This is the most critical change. The developer currently reads `agent_output` from state for specialist selection and prompt assembly. It needs to read from artifact files instead.

**Files:**
- Modify: `orchestrator/nodes/developer.py:38-43,120-121`
- Test: `tests/test_developer.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_developer.py`:

```python
def test_developer_reads_architect_artifact(tmp_path):
    """Developer reads architect.md artifact for specialist selection and context."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # Write an architect artifact with python file paths
    artifact_dir = repo / ".scaffold" / "artifacts" / "task-001"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "architect.md").write_text(
        '{"technical_design": "REST API", "specialist": "python-expert", '
        '"file_paths": ["src/api.py"], "children": []}'
    )
    (artifact_dir / "task_spec.md").write_text("# Build API\n\nAcceptance criteria:\n- Works")

    mock_loader = MagicMock()
    mock_loader.load_specialist.return_value = "implement this"
    mock_loader.detect_specialist.return_value = "python-expert"
    agents_config = MagicMock()
    agents_config.specialists = {
        "python-expert": {
            "model": "claude-sonnet-4-6",
            "max_iterations": 1,
            "completion_promise": "TASK COMPLETE",
            "timeout": 60,
        }
    }

    node_fn = make_developer_node(
        repo_path=str(repo),
        branch_prefix="scaffold",
        agent_loader=mock_loader,
        agents_config=agents_config,
    )
    state = initial_state(task_id="task-001", level="task")
    state["agent_output"] = ""  # empty — should read from artifact instead

    with patch.object(DoerAgent, "create_worktree", return_value=repo):
        with patch.object(DoerAgent, "cleanup_worktree"):
            with patch.object(
                DoerAgent,
                "ralph_loop",
                return_value=RalphResult(success=True, iterations=1, output="TASK COMPLETE"),
            ):
                with patch("orchestrator.nodes.developer.subprocess"):
                    node_fn(state)

    # Verify the specialist was loaded with artifact content
    call_args = mock_loader.load_specialist.call_args
    task_context = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("task_context", "")
    assert "REST API" in task_context or "Build API" in task_context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_developer.py::test_developer_reads_architect_artifact -v`
Expected: FAIL — developer reads empty `agent_output` from state, doesn't read artifact

- [ ] **Step 3: Update developer node to read artifacts**

In `orchestrator/nodes/developer.py`:

1. Add import: `from orchestrator.artifacts import read_artifact, write_artifact`
2. Replace the `agent_output` reading with artifact-first logic:

```python
        # 1. Read task context from artifacts (preferred) or state (fallback)
        architect_output = read_artifact(repo_path, state["task_id"], "architect")
        task_spec = read_artifact(repo_path, state["task_id"], "task_spec")
        designer_output = read_artifact(repo_path, state["task_id"], "designer")

        agent_output = architect_output or state.get("agent_output", "")
```

3. Build richer task_context from all available artifacts:

```python
        # 6. Assemble implementation prompt
        context_parts = []
        context_parts.append(f"Task: {state['task_id']}")
        if task_spec:
            context_parts.append(f"Task specification:\n{task_spec}")
        if architect_output:
            context_parts.append(f"Technical design:\n{architect_output}")
        if designer_output:
            context_parts.append(f"UI/UX specification:\n{designer_output}")
        if not architect_output and not task_spec:
            context_parts.append(f"Technical design:\n{agent_output}")
        task_context = "\n\n".join(context_parts) + "\n"
```

4. After ralph_loop completes, write the developer artifact:

```python
        write_artifact(repo_path, state["task_id"], "developer", result.output)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_developer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `make check`
Expected: All checks pass

- [ ] **Step 6: Commit**

```bash
git add orchestrator/nodes/developer.py tests/test_developer.py
git commit -m "feat: developer reads from artifact files instead of inline state"
```

---

### Task 7: Update reviewer to write artifact

**Depends on:** Task 1

**Files:**
- Modify: `orchestrator/nodes/reviewer.py:74-91`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_reviewer.py`:

```python
def test_reviewer_writes_artifact(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with patch("orchestrator.nodes.reviewer.subprocess") as mock_sp:
        mock_sp.run.return_value = MagicMock(
            stdout='{"verdict": "approve", "feedback": ""}',
            returncode=0,
        )
        node_fn = make_reviewer_node(
            str(repo), "scaffold", "claude-sonnet-4-6", MagicMock(load_workflow_agent=MagicMock(return_value=""))
        )
        state = initial_state(task_id="task-001", level="task")
        node_fn(state)

    artifact = repo / ".scaffold" / "artifacts" / "task-001" / "reviewer.md"
    assert artifact.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_reviewer.py::test_reviewer_writes_artifact -v`
Expected: FAIL — no artifact file created

- [ ] **Step 3: Update reviewer node**

In `orchestrator/nodes/reviewer.py`:

1. Add import: `from orchestrator.artifacts import write_artifact`
2. The reviewer needs `repo_path` — it already has it from the factory closure.
3. After parsing the review result, write the artifact:

```python
        write_artifact(repo_path, state["task_id"], "reviewer", result.stdout)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_reviewer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/reviewer.py tests/test_reviewer.py
git commit -m "feat: reviewer writes output to artifact file"
```

---

### Task 8: Update QA to write artifact

**Depends on:** Task 1

**Files:**
- Modify: `orchestrator/nodes/qa.py:44-58`
- Test: `tests/test_qa.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_qa.py`:

```python
def test_qa_writes_artifact(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with patch.object(DoerAgent, "create_worktree", return_value=repo):
        with patch.object(DoerAgent, "cleanup_worktree"):
            with patch.object(
                DoerAgent,
                "ralph_loop",
                return_value=RalphResult(success=True, iterations=1, output="TESTS PASSING"),
            ):
                node_fn = make_qa_node(
                    str(repo), "scaffold", "claude-sonnet-4-6",
                    MagicMock(load_workflow_agent=MagicMock(return_value=""))
                )
                state = initial_state(task_id="task-001", level="task")
                node_fn(state)

    artifact = repo / ".scaffold" / "artifacts" / "task-001" / "qa.md"
    assert artifact.exists()
    assert "TESTS PASSING" in artifact.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_qa.py::test_qa_writes_artifact -v`
Expected: FAIL — no artifact file created

- [ ] **Step 3: Update QA node**

In `orchestrator/nodes/qa.py`:

1. Add import: `from orchestrator.artifacts import write_artifact`
2. After ralph_loop completes, write the artifact:

```python
        write_artifact(repo_path, state["task_id"], "qa", result.output)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_qa.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes/qa.py tests/test_qa.py
git commit -m "feat: qa writes output to artifact file"
```

---

### Task 9: Add `.scaffold/` cleanup to the `clean` command

**Depends on:** Task 1

**Files:**
- Modify: `orchestrator/__main__.py:351-399`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_clean_removes_scaffold_artifacts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    artifact_dir = repo / ".scaffold" / "artifacts" / "task-001"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "architect.md").write_text("design")

    result = runner.invoke(cli, ["clean", "--repo", str(repo), "--db", str(tmp_path / "none.db"), "--yes"])
    assert not (repo / ".scaffold" / "artifacts").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::test_clean_removes_scaffold_artifacts -v`
Expected: FAIL — `.scaffold/` directory not cleaned

- [ ] **Step 3: Update the clean command**

In `orchestrator/__main__.py`, in the `clean` function:

1. Add detection of `.scaffold/` directory:

```python
    scaffold_dir = repo_path / ".scaffold"
    has_scaffold_dir = scaffold_dir.exists()
```

2. Add to the "Will remove:" output:

```python
    if has_scaffold_dir:
        click.echo(f"  artifacts: {scaffold_dir}")
```

3. Add to the "Nothing to clean" check.

4. Add the actual removal after existing cleanup:

```python
    if has_scaffold_dir:
        import shutil
        shutil.rmtree(scaffold_dir)
        click.echo(f"  removed artifacts: {scaffold_dir}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `make check`
Expected: All checks pass

- [ ] **Step 6: Commit**

```bash
git add orchestrator/__main__.py tests/test_cli.py
git commit -m "feat: clean command removes .scaffold/ artifact directory"
```

---

### Task 10: Integration verification

**Depends on:** Tasks 1-9

- [ ] **Step 1: Run full test suite**

Run: `make check`
Expected: All checks pass (lint, typecheck, tests)

- [ ] **Step 2: Verify artifact flow end-to-end**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass, no regressions

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: integration fixes for artifact handoff"
```
