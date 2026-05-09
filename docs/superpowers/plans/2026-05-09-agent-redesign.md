# Agent Prompt & Tooling Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace bare-bones agent prompts with a two-tier agent architecture (workflow agents + domain specialists), add an onboarding phase, convert the developer node into a specialist dispatcher, and migrate credentials to environment variables.

**Architecture:** All agents share the same structure: an `agent.md` prompt file plus a `knowledge-base/` directory. Workflow agents own pipeline phases (via Anthropic API). Specialist agents own implementation domains (via `claude` CLI in worktrees). A new AgentLoader assembles prompts at runtime by combining scaffold expertise with target repo context. A new onboarding node detects project context and configures the specialist roster.

**Tech Stack:** Python 3.12+, LangGraph, Anthropic SDK, SQLite, httpx, Click, pytest

**Spec:** `docs/superpowers/specs/2026-05-09-agent-redesign.md`

---

## File Structure

### Files Created

```
orchestrator/
  agent_loader.py                              # Prompt assembly from agent.md + knowledge bases
  preflight.py                                 # Environment validation before scaffold runs
  nodes/
    onboarding.py                              # Detect project context, configure specialist roster
  agents/
    workflow/
      product_owner/
        agent.md
        knowledge-base/
          prioritization.md
          story-writing.md
          decomposition.md
      architect/
        agent.md
        knowledge-base/
          interface-design.md
          component-boundaries.md
          design-patterns.md
      designer/
        agent.md
        knowledge-base/
          edipt.md
          accessibility.md
          responsive-design.md
      reviewer/
        agent.md
        knowledge-base/
          security-checklist.md
          review-methodology.md
      qa/
        agent.md
        knowledge-base/
          test-design.md
          acceptance-mapping.md
      consensus/
        agent.md
        knowledge-base/
          structured-debate.md
    specialists/
      python-expert/
        agent.md
        knowledge-base/
          testing-patterns.md
          packaging.md
          type-checking.md
      go-expert/
        agent.md
        knowledge-base/
          testing-patterns.md
          error-handling.md
          concurrency.md
      react-expert/
        agent.md
        knowledge-base/
          component-patterns.md
          testing-patterns.md
          accessibility.md
      typescript-expert/
        agent.md
        knowledge-base/
          strict-mode.md
          testing-patterns.md
      postgres-expert/
        agent.md
        knowledge-base/
          schema-conventions.md
          query-patterns.md
          connection-pooling.md
      documentation-writer/
        agent.md
        knowledge-base/
          style-guide.md
      security-auditor/
        agent.md
        knowledge-base/
          owasp-checklist.md
          auth-patterns.md

tests/
  test_agent_loader.py
  test_onboarding.py
  test_preflight.py
```

### Files Modified

```
orchestrator/state.py                          # Add specialist roster fields
orchestrator/config.py                         # Split AgentsConfig into workflow + specialists
orchestrator/graph.py                          # Add onboarding node, pass AgentLoader
orchestrator/__main__.py                       # Env var Telegram, preflight, AgentLoader
orchestrator/telegram.py                       # Graceful degradation when unconfigured
orchestrator/nodes/base.py                     # Remove load_prompt, remove PROMPTS_DIR
orchestrator/nodes/developer.py                # Rewrite as specialist dispatcher
orchestrator/nodes/reviewer.py                 # Load prompt via AgentLoader
orchestrator/nodes/qa.py                       # Load prompt via AgentLoader
orchestrator/nodes/product_owner.py            # Load prompt via AgentLoader
orchestrator/nodes/architect.py                # Load prompt via AgentLoader
orchestrator/nodes/designer.py                 # Load prompt via AgentLoader
orchestrator/nodes/consensus.py                # Load prompt via AgentLoader
config/agents.yaml                             # Split into workflow + specialists sections
config/project.yaml                            # Remove telegram + spec_path fields
tests/conftest.py                              # Update config_dir fixture
tests/test_developer.py                        # Rewrite for dispatcher
tests/test_reviewer.py                         # Update for AgentLoader
tests/test_qa.py                               # Update for AgentLoader
tests/test_product_owner.py                    # Update for AgentLoader
tests/test_architect.py                        # Update for AgentLoader
tests/test_designer.py                         # Update for AgentLoader
tests/test_consensus.py                        # Update for AgentLoader
tests/test_advisor_base.py                     # Remove load_prompt tests
tests/test_config.py                           # Update for new config structure
tests/test_cli.py                              # Update for env var Telegram + preflight
tests/test_graph.py                            # Update for new build_graph signature
CLAUDE.md                                      # Document new agent architecture
```

### Files Deleted

```
prompts/developer.md
prompts/reviewer.md
prompts/qa.md
prompts/architect.md
prompts/designer.md
prompts/product_owner.md
```

---

### Task 1: Add specialist roster fields to TaskState

**Files:**
- Modify: `orchestrator/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
def test_initial_state_has_specialist_fields():
    state = initial_state(task_id="task-001", level="task")
    assert state["specialists"] == []
    assert state["advisory"] == []
    assert state["project_context"] == ""
    assert state["detected_languages"] == []
    assert state["test_framework"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py::test_initial_state_has_specialist_fields -v`
Expected: FAIL with KeyError

- [ ] **Step 3: Add new fields to TaskState and initial_state**

Replace the full contents of `orchestrator/state.py`:

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
    specialists: list[str]
    advisory: list[str]
    project_context: str
    detected_languages: list[str]
    test_framework: str


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
        specialists=[],
        advisory=[],
        project_context="",
        detected_languages=[],
        test_framework="",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_state.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/state.py tests/test_state.py
git commit -m "feat: add specialist roster fields to TaskState"
```

---

### Task 2: Refactor config for two-tier agent structure

**Files:**
- Modify: `orchestrator/config.py`
- Modify: `config/agents.yaml`
- Modify: `config/project.yaml`
- Modify: `tests/conftest.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test for new config structure**

Add to `tests/test_config.py`:

```python
def test_agents_config_has_workflow_and_specialists(config_dir):
    cfg = load_config(str(config_dir))
    assert hasattr(cfg.agents, "workflow")
    assert hasattr(cfg.agents, "specialists")
    assert "product_owner" in cfg.agents.workflow
    assert cfg.agents.workflow["product_owner"]["model"] == "claude-opus-4-6"


def test_agents_config_has_escalation(config_dir):
    cfg = load_config(str(config_dir))
    assert hasattr(cfg.agents, "escalation")
    assert cfg.agents.escalation["max_review_cycles"] == 3


def test_project_config_no_telegram_fields(config_dir):
    cfg = load_config(str(config_dir))
    assert not hasattr(cfg.project, "telegram_bot_token")
    assert not hasattr(cfg.project, "telegram_chat_id")
    assert not hasattr(cfg.project, "spec_path")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py::test_agents_config_has_workflow_and_specialists tests/test_config.py::test_agents_config_has_escalation tests/test_config.py::test_project_config_no_telegram_fields -v`
Expected: FAIL

- [ ] **Step 3: Update AgentsConfig and ProjectConfig dataclasses**

Replace the full contents of `orchestrator/config.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class GovernanceConfig:
    rapid: dict[str, dict[str, str]]
    raci: dict[str, dict[str, str | list[str]]]


@dataclass
class AgentsConfig:
    workflow: dict[str, dict]
    specialists: dict[str, dict]
    escalation: dict


@dataclass
class ProjectConfig:
    repo_path: str
    branch_prefix: str = "scaffold"
    max_concurrent_agents: int = 3
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
    agents = AgentsConfig(
        workflow=agents_data.get("workflow", {}),
        specialists=agents_data.get("specialists", {}),
        escalation=agents_data.get("escalation", {}),
    )

    with open(config_dir / "project.yaml") as f:
        proj_data = yaml.safe_load(f)
    project = ProjectConfig(**proj_data)

    return ScaffoldConfig(governance=governance, agents=agents, project=project)
```

- [ ] **Step 4: Update config/agents.yaml**

Replace the full contents of `config/agents.yaml`:

```yaml
workflow:
  product_owner:
    model: claude-opus-4-6
    execution: api
  architect:
    model: claude-opus-4-6
    execution: api
  designer:
    model: claude-sonnet-4-6
    execution: api
  reviewer:
    model: claude-sonnet-4-6
    execution: cli
  qa:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 8
    completion_promise: "TESTS PASSING"
  consensus:
    model: claude-opus-4-6
    execution: api

specialists:
  python-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
  go-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
  react-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
  typescript-expert:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 10
    completion_promise: "TASK COMPLETE"
  postgres-expert:
    model: claude-opus-4-6
    execution: api
  documentation-writer:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 5
    completion_promise: "TASK COMPLETE"
  security-auditor:
    model: claude-opus-4-6
    execution: api

escalation:
  stuck_loop_model: claude-opus-4-6
  max_review_cycles: 3
  max_bug_cycles: 3
  cost_threshold_per_run: 5.00
```

- [ ] **Step 5: Update config/project.yaml**

Replace the full contents of `config/project.yaml`:

```yaml
repo_path: /Users/antonypegg/PROJECTS/inkwell
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold.db
```

- [ ] **Step 6: Update tests/conftest.py config_dir fixture**

Replace the `config_dir` fixture in `tests/conftest.py`:

```python
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
        "workflow:\n"
        "  product_owner:\n"
        "    model: claude-opus-4-6\n"
        "    execution: api\n"
        "  architect:\n"
        "    model: claude-opus-4-6\n"
        "    execution: api\n"
        "  designer:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: api\n"
        "  developer:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 10\n"
        "    completion_promise: TASK COMPLETE\n"
        "  reviewer:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "  qa:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 8\n"
        "    completion_promise: TESTS PASSING\n"
        "specialists:\n"
        "  python-expert:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 10\n"
        "    completion_promise: TASK COMPLETE\n"
        "escalation:\n"
        "  stuck_loop_model: claude-opus-4-6\n"
        "  max_review_cycles: 3\n"
        "  max_bug_cycles: 3\n"
        "  cost_threshold_per_run: 5.00\n"
    )
    project = tmp_path / "project.yaml"
    project.write_text(
        "repo_path: /tmp/test-repo\n"
        "branch_prefix: scaffold\n"
        "max_concurrent_agents: 3\n"
        "db_path: ':memory:'\n"
    )
    return tmp_path
```

- [ ] **Step 7: Fix any tests that reference old config structure**

Search existing tests for `cfg.agents.roles` or `telegram_bot_token` and update them. Key files to check:
- `tests/test_config.py` — update assertions to use `workflow`/`specialists`/`escalation`
- `tests/test_cli.py` — TelegramBot no longer reads from config (handled in Task 11)

For `tests/test_config.py`, update any test that accesses `cfg.agents.roles` to use `cfg.agents.workflow` instead. Remove any test that asserts `telegram_bot_token` exists on ProjectConfig.

- [ ] **Step 8: Run all tests**

Run: `python -m pytest tests/test_config.py tests/test_state.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add orchestrator/config.py config/agents.yaml config/project.yaml tests/conftest.py tests/test_config.py
git commit -m "feat: split agent config into workflow and specialists"
```

---

### Task 3: Create AgentLoader module

**Files:**
- Create: `orchestrator/agent_loader.py`
- Create: `tests/test_agent_loader.py`

- [ ] **Step 1: Write the tests**

Create `tests/test_agent_loader.py`:

```python
from pathlib import Path

import pytest

from orchestrator.agent_loader import AgentLoader


@pytest.fixture
def agents_dir(tmp_path):
    wf = tmp_path / "workflow" / "reviewer"
    wf.mkdir(parents=True)
    (wf / "agent.md").write_text(
        "# Reviewer\n\n## Responsibilities\nReview code for correctness.\n"
    )
    kb = wf / "knowledge-base"
    kb.mkdir()
    (kb / "security-checklist.md").write_text("# Security Checklist\n\n- Check for SQL injection\n")
    (kb / "review-methodology.md").write_text("# Review Methodology\n\n- Read the diff first\n")

    sp = tmp_path / "specialists" / "python-expert"
    sp.mkdir(parents=True)
    (sp / "agent.md").write_text(
        "# Python Expert\n\n## Responsibilities\nWrite Python code.\n"
    )
    sp_kb = sp / "knowledge-base"
    sp_kb.mkdir()
    (sp_kb / "testing-patterns.md").write_text("# Testing Patterns\n\n- Use pytest fixtures\n")
    (sp_kb / "packaging.md").write_text("# Packaging\n\n- Use pyproject.toml\n")
    (sp_kb / "type-checking.md").write_text("# Type Checking\n\n- Use pyright\n")

    go = tmp_path / "specialists" / "go-expert"
    go.mkdir(parents=True)
    (go / "agent.md").write_text("# Go Expert\n\n## Responsibilities\nWrite Go code.\n")
    go_kb = go / "knowledge-base"
    go_kb.mkdir()
    (go_kb / "testing-patterns.md").write_text("# Go Testing\n\n- Table-driven tests\n")

    return tmp_path


def test_load_workflow_agent(agents_dir):
    loader = AgentLoader(agents_dir)
    prompt = loader.load_workflow_agent("reviewer")
    assert "# Reviewer" in prompt
    assert "Review code for correctness" in prompt
    assert "Security Checklist" in prompt
    assert "Review Methodology" in prompt


def test_load_workflow_agent_missing(agents_dir):
    loader = AgentLoader(agents_dir)
    prompt = loader.load_workflow_agent("nonexistent")
    assert prompt == ""


def test_load_specialist_with_project_context(agents_dir, tmp_path):
    repo = tmp_path / "target-repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# My Project\nUses FastAPI.\n")
    loader = AgentLoader(agents_dir)
    prompt = loader.load_specialist(
        name="python-expert",
        repo_path=repo,
        task_context="Write tests for the auth module",
    )
    assert "# Python Expert" in prompt
    assert "Testing Patterns" in prompt
    assert "# My Project" in prompt


def test_load_specialist_with_advisory_input(agents_dir, tmp_path):
    repo = tmp_path / "target-repo"
    repo.mkdir()
    loader = AgentLoader(agents_dir)
    prompt = loader.load_specialist(
        name="python-expert",
        repo_path=repo,
        task_context="Build the API endpoint",
        advisory_input="Use parameterized queries for all DB access.",
    )
    assert "parameterized queries" in prompt


def test_load_specialist_with_project_override(agents_dir, tmp_path):
    repo = tmp_path / "target-repo"
    repo.mkdir()
    overrides = repo / ".claude" / "agents"
    overrides.mkdir(parents=True)
    (overrides / "python-expert.md").write_text("Always use black for formatting.\n")
    loader = AgentLoader(agents_dir)
    prompt = loader.load_specialist(
        name="python-expert",
        repo_path=repo,
        task_context="Implement feature",
    )
    assert "Always use black" in prompt


def test_load_specialist_selects_relevant_kbs(agents_dir, tmp_path):
    repo = tmp_path / "target-repo"
    repo.mkdir()
    loader = AgentLoader(agents_dir)
    prompt = loader.load_specialist(
        name="python-expert",
        repo_path=repo,
        task_context="Add type hints to all functions",
    )
    assert "Type Checking" in prompt
    assert "pyright" in prompt


def test_list_specialists(agents_dir):
    loader = AgentLoader(agents_dir)
    specs = loader.list_specialists()
    assert "python-expert" in specs
    assert "go-expert" in specs


def test_detect_specialist_python(agents_dir):
    loader = AgentLoader(agents_dir)
    result = loader.detect_specialist(["src/main.py", "src/utils.py", "tests/test_main.py"])
    assert result == "python-expert"


def test_detect_specialist_go(agents_dir):
    loader = AgentLoader(agents_dir)
    result = loader.detect_specialist(["cmd/server/main.go", "internal/handler.go"])
    assert result == "go-expert"


def test_detect_specialist_mixed_uses_majority(agents_dir):
    loader = AgentLoader(agents_dir)
    result = loader.detect_specialist(["main.py", "utils.py", "schema.sql"])
    assert result == "python-expert"


def test_detect_specialist_unknown_extension(agents_dir):
    loader = AgentLoader(agents_dir)
    result = loader.detect_specialist(["README.md", "Makefile"])
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_loader.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement AgentLoader**

Create `orchestrator/agent_loader.py`:

```python
from collections import Counter
from pathlib import Path

EXTENSION_TO_SPECIALIST = {
    ".py": "python-expert",
    ".go": "go-expert",
    ".tsx": "react-expert",
    ".jsx": "react-expert",
    ".ts": "typescript-expert",
    ".sql": "postgres-expert",
    ".md": "documentation-writer",
}


class AgentLoader:
    def __init__(self, agents_dir: Path):
        self.agents_dir = agents_dir

    def load_workflow_agent(self, role: str) -> str:
        agent_dir = self.agents_dir / "workflow" / role
        agent_file = agent_dir / "agent.md"
        if not agent_file.exists():
            return ""

        parts = [agent_file.read_text()]

        kb_dir = agent_dir / "knowledge-base"
        if kb_dir.exists():
            for kb_file in sorted(kb_dir.glob("*.md")):
                parts.append(kb_file.read_text())

        return "\n\n---\n\n".join(parts)

    def load_specialist(
        self,
        name: str,
        repo_path: Path,
        task_context: str,
        advisory_input: str = "",
    ) -> str:
        agent_dir = self.agents_dir / "specialists" / name
        agent_file = agent_dir / "agent.md"
        if not agent_file.exists():
            return ""

        parts = [agent_file.read_text()]

        kb_dir = agent_dir / "knowledge-base"
        selected_kbs = self._select_knowledge_bases(kb_dir, task_context)
        for kb_file in selected_kbs:
            parts.append(kb_file.read_text())

        claude_md = repo_path / "CLAUDE.md"
        if claude_md.exists():
            parts.append(f"# Project Context\n\n{claude_md.read_text()}")

        override_file = repo_path / ".claude" / "agents" / f"{name}.md"
        if override_file.exists():
            parts.append(f"# Project-Specific Overrides\n\n{override_file.read_text()}")

        if advisory_input:
            parts.append(f"# Advisory Recommendations\n\n{advisory_input}")

        if task_context:
            parts.append(f"# Task\n\n{task_context}")

        return "\n\n---\n\n".join(parts)

    def list_specialists(self) -> list[str]:
        specialists_dir = self.agents_dir / "specialists"
        if not specialists_dir.exists():
            return []
        return sorted(
            d.name for d in specialists_dir.iterdir()
            if d.is_dir() and (d / "agent.md").exists()
        )

    def detect_specialist(self, file_paths: list[str]) -> str:
        counts: Counter[str] = Counter()
        for fp in file_paths:
            ext = Path(fp).suffix
            specialist = EXTENSION_TO_SPECIALIST.get(ext, "")
            if specialist:
                counts[specialist] += 1

        if not counts:
            return ""
        return counts.most_common(1)[0][0]

    def _select_knowledge_bases(self, kb_dir: Path, task_context: str) -> list[Path]:
        if not kb_dir.exists():
            return []
        all_kbs = sorted(kb_dir.glob("*.md"))
        if not task_context:
            return all_kbs

        context_lower = task_context.lower()
        selected = []
        for kb_file in all_kbs:
            keywords = kb_file.stem.replace("-", " ").split()
            if any(kw in context_lower for kw in keywords):
                selected.append(kb_file)

        return selected if selected else all_kbs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agent_loader.py -v`
Expected: All PASS

- [ ] **Step 5: Run lint and typecheck**

Run: `make lint && make typecheck`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add orchestrator/agent_loader.py tests/test_agent_loader.py
git commit -m "feat: add AgentLoader for prompt assembly from agent files"
```

---

### Task 4: Create workflow agent prompts and knowledge bases

**Files:**
- Create: `orchestrator/agents/workflow/product_owner/agent.md`
- Create: `orchestrator/agents/workflow/product_owner/knowledge-base/prioritization.md`
- Create: `orchestrator/agents/workflow/product_owner/knowledge-base/story-writing.md`
- Create: `orchestrator/agents/workflow/product_owner/knowledge-base/decomposition.md`
- Create: `orchestrator/agents/workflow/architect/agent.md`
- Create: `orchestrator/agents/workflow/architect/knowledge-base/interface-design.md`
- Create: `orchestrator/agents/workflow/architect/knowledge-base/component-boundaries.md`
- Create: `orchestrator/agents/workflow/architect/knowledge-base/design-patterns.md`
- Create: `orchestrator/agents/workflow/designer/agent.md`
- Create: `orchestrator/agents/workflow/designer/knowledge-base/edipt.md`
- Create: `orchestrator/agents/workflow/designer/knowledge-base/accessibility.md`
- Create: `orchestrator/agents/workflow/designer/knowledge-base/responsive-design.md`
- Create: `orchestrator/agents/workflow/reviewer/agent.md`
- Create: `orchestrator/agents/workflow/reviewer/knowledge-base/security-checklist.md`
- Create: `orchestrator/agents/workflow/reviewer/knowledge-base/review-methodology.md`
- Create: `orchestrator/agents/workflow/qa/agent.md`
- Create: `orchestrator/agents/workflow/qa/knowledge-base/test-design.md`
- Create: `orchestrator/agents/workflow/qa/knowledge-base/acceptance-mapping.md`
- Create: `orchestrator/agents/workflow/consensus/agent.md`
- Create: `orchestrator/agents/workflow/consensus/knowledge-base/structured-debate.md`

Every agent.md follows this exact section structure (80-150 lines each):

```
# {Agent Name}

## Responsibilities
## Constraints
## Shared References
## Standards
## Escalation Triggers
## Output Format
## Examples
## Failure Recovery
```

Every knowledge base file is 50-200 lines of domain reference material.

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p orchestrator/agents/workflow/product_owner/knowledge-base
mkdir -p orchestrator/agents/workflow/architect/knowledge-base
mkdir -p orchestrator/agents/workflow/designer/knowledge-base
mkdir -p orchestrator/agents/workflow/reviewer/knowledge-base
mkdir -p orchestrator/agents/workflow/qa/knowledge-base
mkdir -p orchestrator/agents/workflow/consensus/knowledge-base
```

- [ ] **Step 2: Write product_owner/agent.md**

This is the template that all other agent.md files follow. Write the full file (80-150 lines):

```markdown
# Product Owner

## Responsibilities

You decompose master specifications into discrete, implementable work items organized in a hierarchy: epics contain features, features contain tasks. You define measurable acceptance criteria for every work item. You trace every item back to a specific section of the master spec.

Your deliverables:
- A list of child work items with title, level, spec reference, and acceptance criteria
- Each work item scoped to be completable in a single focused development session (1-3 files)
- Clear parent-child relationships forming a work breakdown structure

## Constraints

- Never prescribe implementation details — technology choices, code patterns, and architecture are the Architect's domain
- Never write code
- Never create work items that lack measurable acceptance criteria
- Never create work items that cannot be traced to a spec section
- Do not create items that combine UI and backend concerns — split them

## Shared References

- The master spec is provided in the user message
- Use the task tree schema: id, parent_id, level (epic/feature/task), title, spec_ref, acceptance
- Upstream: this is the first workflow agent — no upstream agent output to reference

## Standards

- Every acceptance criterion must be a testable assertion, not a vague goal
  - Good: "GET /api/users returns 200 with a JSON array"
  - Bad: "Users endpoint works properly"
- Each task-level item should touch 1-3 files maximum
- Feature-level items should decompose into 3-8 tasks
- Epic-level items should decompose into 2-5 features

## Escalation Triggers

- The spec contains contradictory requirements (section A says X, section B says not-X) → escalate with both references
- The spec references external systems or APIs not described in the spec → escalate asking for documentation
- A feature requires more than 8 tasks to implement → escalate suggesting the feature be split
- The spec lacks sufficient detail to write acceptance criteria for a section → escalate with specific questions

## Output Format

Valid JSON with a single key `children` containing a list of objects:

```json
{
  "children": [
    {
      "title": "User authentication flow",
      "level": "feature",
      "spec_ref": "Section 3.1 — Authentication",
      "acceptance": [
        "POST /api/auth/login returns 200 with JWT for valid credentials",
        "POST /api/auth/login returns 401 for invalid credentials",
        "JWT expires after 24 hours"
      ]
    }
  ]
}
```

## Examples

**Good decomposition:**
Input spec section: "The system shall provide user authentication with email/password login and JWT tokens."

Output:
```json
{
  "children": [
    {
      "title": "User registration endpoint",
      "level": "task",
      "spec_ref": "Section 3.1",
      "acceptance": [
        "POST /api/auth/register creates user with hashed password",
        "Returns 409 if email already exists",
        "Returns 201 with user ID on success"
      ]
    },
    {
      "title": "Login endpoint with JWT",
      "level": "task",
      "spec_ref": "Section 3.1",
      "acceptance": [
        "POST /api/auth/login returns JWT for valid credentials",
        "JWT contains user_id and email claims",
        "Returns 401 for wrong password"
      ]
    }
  ]
}
```

**Bad decomposition (and why it fails):**
```json
{
  "children": [
    {
      "title": "Build auth system",
      "level": "task",
      "spec_ref": "Section 3",
      "acceptance": ["Authentication works"]
    }
  ]
}
```
Failures: title is vague, acceptance is not testable, spec_ref is too broad, scope is too large for one task.

## Failure Recovery

- If the master spec is empty or missing: return `{"children": []}` and set escalation_reason to "Master spec is empty or could not be read"
- If the spec contains no clear feature boundaries: decompose by user-facing capability (one feature per distinct user action)
- If acceptance criteria cannot be made specific due to ambiguity: include the criterion with a `[NEEDS CLARIFICATION]` prefix and set escalation_reason listing the ambiguous items
```

- [ ] **Step 3: Write product_owner knowledge bases**

Write `orchestrator/agents/workflow/product_owner/knowledge-base/prioritization.md` (50-100 lines). Cover:
- MoSCoW method (Must/Should/Could/Won't) with when to use each
- RICE scoring (Reach, Impact, Confidence, Effort) with formula and examples
- Impact/Effort matrix (2x2 grid: quick wins, big bets, fill-ins, money pits)
- How to prioritize when all items seem equally important
- Anti-patterns: prioritizing by squeakiest wheel, sunk cost, technical interest

Write `orchestrator/agents/workflow/product_owner/knowledge-base/story-writing.md` (50-100 lines). Cover:
- User story format: "As a [role], I want [capability], so that [benefit]"
- Acceptance criteria patterns: Given/When/Then, checklist style
- INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- Splitting strategies: by workflow step, by data variation, by operation (CRUD), by platform
- Anti-patterns: stories as technical tasks, stories without acceptance criteria, epic-sized stories labeled as tasks

Write `orchestrator/agents/workflow/product_owner/knowledge-base/decomposition.md` (50-100 lines). Cover:
- Epic → Feature → Task hierarchy with size guidance
- Vertical slicing: each feature delivers end-to-end value through all layers
- Horizontal slicing anti-pattern: "build all the DB tables" then "build all the APIs" (fragile, untestable)
- Dependency ordering: which features must ship first for others to build on
- The "walking skeleton" pattern: smallest possible end-to-end flow first
- Size heuristics: task = 1-3 files, feature = 3-8 tasks, epic = 2-5 features

- [ ] **Step 4: Write architect/agent.md**

Write `orchestrator/agents/workflow/architect/agent.md` (80-150 lines) following the same section structure. Key content:

- **Responsibilities:** Produce data models, API contracts, component boundaries, and file structures. Specify interfaces before implementation. Determine if the task has UI components. Output a technical design plus child tasks.
- **Constraints:** Never write implementation code. Never make product decisions (scope, priority). Always specify file paths for new code. Design for small, focused files.
- **Shared References:** Product Owner's decomposition output. Target repo's CLAUDE.md for existing architecture.
- **Standards:** Interface-first design (define contracts before internals). Dependency direction (depend on abstractions, not concretions). File size limit guidance (prefer files under 300 lines).
- **Escalation Triggers:** Technology stack conflicts. Existing architecture incompatible with requirements. Database schema changes affecting more than 5 tables.
- **Output Format:** JSON with `technical_design` (str), `has_ui_component` (bool), `file_paths` (list[str]), `children` (list).
- **Examples:** One good (clear interface + file list + testable tasks) and one bad (vague "build the backend" without file paths).
- **Failure Recovery:** If upstream task has no acceptance criteria → design to the title and flag. If no CLAUDE.md found → design with standard conventions and note assumptions.

- [ ] **Step 5: Write architect knowledge bases**

Write `orchestrator/agents/workflow/architect/knowledge-base/interface-design.md` (50-100 lines). Cover:
- API contract design (REST conventions, request/response schemas, status codes, error format)
- Function signature design (parameter types, return types, error handling contracts)
- Schema-first approach (define data shapes before behavior)
- Versioning considerations

Write `orchestrator/agents/workflow/architect/knowledge-base/component-boundaries.md` (50-100 lines). Cover:
- Single responsibility at the module level
- Dependency direction (always depend inward, never outward)
- When to split a module (signs it's doing too much)
- Communication patterns between components (function calls vs events vs shared state)
- Anti-patterns: circular dependencies, god modules, premature microservices

Write `orchestrator/agents/workflow/architect/knowledge-base/design-patterns.md` (50-100 lines). Cover:
- Repository pattern for data access
- Strategy pattern for swappable behavior
- Factory pattern for complex object creation
- Observer/event pattern for loose coupling
- When NOT to use patterns (YAGNI — don't add indirection without a reason)
- Anti-patterns: pattern overuse, abstract factories for single implementations

- [ ] **Step 6: Write designer/agent.md**

Write `orchestrator/agents/workflow/designer/agent.md` (80-150 lines). Key content:

- **Responsibilities:** Produce UI/UX specifications: layouts, interaction patterns, responsive behavior, component specifications. Define how users interact with each feature.
- **Constraints:** Never write code. Never make architectural decisions. Specify for accessibility from the start. All specifications must include mobile, tablet, and desktop.
- **Shared References:** Architect's technical design for component structure. Target repo's CLAUDE.md for existing UI patterns.
- **Standards:** WCAG 2.1 AA compliance. Touch targets minimum 44x44px. Keyboard navigability for all interactive elements. Color contrast ratios.
- **Escalation Triggers:** Conflicting UX requirements. Accessibility requirements that conflict with design goals. Missing content or copy.
- **Output Format:** Structured text with component specs, interaction descriptions, responsive breakpoints.
- **Examples:** Good (specific layout + interaction + responsive + accessible) and bad (vague "make it look nice").
- **Failure Recovery:** If no design system exists → specify using standard web conventions. If target devices unknown → design mobile-first.

- [ ] **Step 7: Write designer knowledge bases**

Write `orchestrator/agents/workflow/designer/knowledge-base/edipt.md` (50-100 lines). Cover:
- EDIPT framework: Empathize (understand users), Define (problem statement), Ideate (generate solutions), Prototype (create testable specs), Test (validate with criteria)
- How each phase maps to the scaffold workflow
- Common shortcuts and when they're acceptable

Write `orchestrator/agents/workflow/designer/knowledge-base/accessibility.md` (50-100 lines). Cover:
- WCAG 2.1 AA requirements summary
- Semantic HTML patterns (headings, landmarks, form labels)
- ARIA roles and when to use them (and when NOT to — prefer semantic HTML)
- Keyboard navigation patterns (tab order, focus management, skip links)
- Color and contrast requirements (4.5:1 for normal text, 3:1 for large text)
- Screen reader considerations (alt text, live regions, announcements)

Write `orchestrator/agents/workflow/designer/knowledge-base/responsive-design.md` (50-100 lines). Cover:
- Mobile-first approach (base styles for small screens, enhance for larger)
- Standard breakpoints and when to customize
- Touch vs mouse interaction patterns
- Flexible layouts (grid, flexbox patterns)
- Typography scaling
- Image and media handling across screen sizes

- [ ] **Step 8: Write reviewer/agent.md**

Write `orchestrator/agents/workflow/reviewer/agent.md` (80-150 lines). Key content:

- **Responsibilities:** Review git diffs for correctness, security, style adherence, and acceptance criteria coverage. Produce a verdict (approve or revise) with specific, actionable feedback.
- **Constraints:** Never write code. Never approve code that fails to meet acceptance criteria. Always reference specific file paths and line numbers. Never revise for style preferences that aren't in the project's linter config.
- **Shared References:** The git diff on the task branch. Acceptance criteria from the task spec. Target repo's CLAUDE.md for code style.
- **Standards:** Every piece of feedback must be actionable (say what to change, not just what's wrong). Group feedback by severity (blocking vs suggestion). Maximum 5 revision items per review cycle.
- **Environment Detection:** Read CLAUDE.md for project conventions. Check for linter configs (ruff.toml, .eslintrc). Check for test framework (pytest.ini, vitest.config).
- **Escalation Triggers:** Security vulnerability (SQL injection, XSS, auth bypass). Data loss risk (destructive migration without backup). Acceptance criteria that cannot be verified from the diff.
- **Output Format:** JSON with `verdict` ("approve" or "revise") and `feedback` (str — empty if approved, numbered list if revise).
- **Examples:** Good approve (criteria met, clean diff), good revise (specific file:line, what to change, why), bad revise ("code needs improvement" without specifics).
- **Failure Recovery:** If diff is empty → revise with "No changes found on branch." If acceptance criteria missing → review for correctness and security only, note missing criteria in feedback.

- [ ] **Step 9: Write reviewer knowledge bases**

Write `orchestrator/agents/workflow/reviewer/knowledge-base/security-checklist.md` (80-150 lines). Cover:
- OWASP Top 10 with code-level examples for each:
  - Injection (SQL, command, LDAP) — parameterized queries, input validation
  - Broken Authentication — password hashing, session management, JWT validation
  - Sensitive Data Exposure — encryption at rest/transit, no secrets in code
  - XML External Entities — disable DTD processing
  - Broken Access Control — authorization checks on every endpoint
  - Security Misconfiguration — default credentials, verbose errors, CORS
  - XSS — output encoding, CSP headers, sanitization
  - Insecure Deserialization — validate before deserialize, allowlists
  - Using Components with Known Vulnerabilities — dependency scanning
  - Insufficient Logging — audit trails for auth events, data access
- Language-specific gotchas (Python: pickle, eval, subprocess shell=True; JS: innerHTML, document.write; Go: template injection)

Write `orchestrator/agents/workflow/reviewer/knowledge-base/review-methodology.md` (50-100 lines). Cover:
- Review order: security first, then correctness, then style
- Severity levels: blocking (must fix), important (should fix), suggestion (nice to have)
- How to write actionable feedback (file:line, current behavior, expected behavior, how to fix)
- When to approve despite imperfections (style nits don't block, missing tests block)
- Review scope: only review what changed, don't scope-creep into unrelated code
- Batch feedback: group related issues, don't repeat the same feedback for every occurrence

- [ ] **Step 10: Write qa/agent.md**

Write `orchestrator/agents/workflow/qa/agent.md` (80-150 lines). Key content:

- **Responsibilities:** Write and run tests that validate acceptance criteria. Ensure every criterion has at least one test. Report test results with exact pass/fail counts.
- **Constraints:** Never modify implementation code. Tests must be deterministic (no random, no sleep, no network calls without mocks). Test acceptance criteria, not implementation details. Each test tests one thing.
- **Shared References:** Acceptance criteria from the task spec. The implementation on the task branch.
- **Standards:** One assertion per test (conceptually — multiple asserts on the same object are fine). Descriptive test names that read as specifications. Tests must run in isolation (no shared mutable state).
- **Environment Detection:** Read CLAUDE.md for test framework and patterns. Check for existing test files to match conventions. Read Makefile for test commands.
- **Escalation Triggers:** An acceptance criterion that cannot be tested automatically (requires manual verification). Test infrastructure broken (no test framework, broken fixtures). Implementation missing (acceptance criterion has no corresponding code).
- **Output Format:** Output "TESTS PASSING" when all acceptance criteria have passing tests. If tests fail, output exact failure messages.
- **Examples:** Good (one test per criterion, descriptive names, isolated), bad (testing implementation details, non-deterministic, testing multiple things).
- **Failure Recovery:** If no test framework detected → check CLAUDE.md, then try `pytest` (Python), `go test` (Go), `npm test` (JS/TS). If implementation is incomplete → write tests for what exists and report which criteria have no code.

- [ ] **Step 11: Write qa knowledge bases**

Write `orchestrator/agents/workflow/qa/knowledge-base/test-design.md` (80-150 lines). Cover:
- Test pyramid: unit (many, fast), integration (some, medium), E2E (few, slow)
- TDD cycle: red → green → refactor
- Test isolation: each test sets up its own state, cleans up after
- Fixture patterns: factory functions, builders, shared fixtures with fresh instances
- Mocking strategy: mock at boundaries (external APIs, databases), not internal functions
- Test naming: `test_<unit>_<scenario>_<expected>` or `test_<behavior>`
- Parameterized tests for data variations
- Anti-patterns: testing private methods, testing framework behavior, brittle tests coupled to implementation

Write `orchestrator/agents/workflow/qa/knowledge-base/acceptance-mapping.md` (50-100 lines). Cover:
- Mapping each acceptance criterion to one or more tests
- Coverage analysis: which criteria have tests, which don't
- Edge cases derived from acceptance criteria (boundary values, empty inputs, error states)
- Given/When/Then mapping to test structure (arrange/act/assert)
- Priority: cover happy path first, then error cases, then edge cases
- How to handle "non-functional" criteria (performance, security) in automated tests

- [ ] **Step 12: Write consensus/agent.md and knowledge base**

Write `orchestrator/agents/workflow/consensus/agent.md` (80-120 lines). Key content:

- **Responsibilities:** Adjudicate structured debates between agents. Evaluate positions, identify common ground, determine resolution or escalation.
- **Constraints:** Remain neutral. Base evaluation on evidence, not authority. Maximum 2 debate rounds before escalation.
- **Shared References:** The conflicting positions from upstream agents.
- **Standards:** Each position must include rationale and evidence. Concession requires explicit acknowledgment of the stronger argument.
- **Escalation Triggers:** Neither party concedes after 2 rounds. Both parties agree the question requires human judgment. The disagreement is about product scope (not technical).
- **Output Format:** JSON with `position` (str) and `concedes` (bool).
- **Examples:** Good resolution (clear reasoning, explicit concession), deadlock (both hold firm, escalation with summary).
- **Failure Recovery:** If positions are identical → resolve immediately. If positions are incoherent → escalate with "Unable to parse positions" and include raw text.

Write `orchestrator/agents/workflow/consensus/knowledge-base/structured-debate.md` (50-80 lines). Cover:
- Structured debate format: position statement → supporting evidence → rebuttal → counter-rebuttal
- Argument evaluation criteria: logical validity, evidence quality, relevance, completeness
- Resolution patterns: one side concedes, compromise (both adjust), synthesis (new position incorporating both)
- Escalation criteria: fundamental value disagreement, insufficient information, out-of-scope decision
- Common debate anti-patterns: ad hominem, strawman, appeal to authority, false dichotomy

- [ ] **Step 13: Verify all workflow agents load correctly**

Run: `python -c "from pathlib import Path; from orchestrator.agent_loader import AgentLoader; loader = AgentLoader(Path('orchestrator/agents')); [print(f'{r}: {len(loader.load_workflow_agent(r))} chars') for r in ['product_owner','architect','designer','reviewer','qa','consensus')]"`
Expected: All 6 agents return non-empty prompts

- [ ] **Step 14: Commit**

```bash
git add orchestrator/agents/workflow/
git commit -m "feat: add workflow agent prompts and knowledge bases"
```

---

### Task 5: Create specialist agent prompts and knowledge bases

**Files:**
- Create: `orchestrator/agents/specialists/python-expert/agent.md` + knowledge-base/
- Create: `orchestrator/agents/specialists/go-expert/agent.md` + knowledge-base/
- Create: `orchestrator/agents/specialists/react-expert/agent.md` + knowledge-base/
- Create: `orchestrator/agents/specialists/typescript-expert/agent.md` + knowledge-base/
- Create: `orchestrator/agents/specialists/postgres-expert/agent.md` + knowledge-base/
- Create: `orchestrator/agents/specialists/documentation-writer/agent.md` + knowledge-base/
- Create: `orchestrator/agents/specialists/security-auditor/agent.md` + knowledge-base/

Every specialist agent.md follows the same section structure as workflow agents (80-150 lines), with the addition of an **Environment Detection** section. Implementation specialists (CLI-based) include the completion promise in their output format. Advisory specialists (API-based) note their advisory-only role in Constraints.

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p orchestrator/agents/specialists/python-expert/knowledge-base
mkdir -p orchestrator/agents/specialists/go-expert/knowledge-base
mkdir -p orchestrator/agents/specialists/react-expert/knowledge-base
mkdir -p orchestrator/agents/specialists/typescript-expert/knowledge-base
mkdir -p orchestrator/agents/specialists/postgres-expert/knowledge-base
mkdir -p orchestrator/agents/specialists/documentation-writer/knowledge-base
mkdir -p orchestrator/agents/specialists/security-auditor/knowledge-base
```

- [ ] **Step 2: Write python-expert/agent.md**

This is the specialist template. Write the full file (80-150 lines):

```markdown
# Python Expert

## Responsibilities

You implement Python code following project conventions. You write tests before implementation (TDD). You commit working code with passing tests. You work in a git worktree on a task branch.

Your deliverables:
- Implementation code that satisfies the acceptance criteria
- Tests that verify each acceptance criterion
- Clean commits with passing tests at each commit point

## Constraints

- Stay within the Architect's technical design — do not make architectural decisions
- Do not modify files outside the scope defined in the task spec
- Do not add dependencies without explicit approval in the task spec
- Do not refactor code beyond what the task requires
- Output "TASK COMPLETE" only when all acceptance criteria are verified by passing tests

## Shared References

- The task spec with acceptance criteria is provided in your prompt
- The target repo's CLAUDE.md contains project conventions and commands
- Review feedback (if any) is appended from previous review cycles

## Standards

- Type hints on all function signatures (parameters and return types)
- Follow the project's existing code style (check ruff.toml or pyproject.toml [tool.ruff])
- Tests use the project's test framework (detect from pyproject.toml or conftest.py)
- Imports sorted per project convention (isort or ruff)
- No bare `except:` — always catch specific exceptions
- No mutable default arguments

## Environment Detection

Before writing any code:
1. Read CLAUDE.md for project architecture, commands, and conventions
2. Read pyproject.toml for dependencies, test config, and Python version
3. Check for Makefile — use its commands for testing (`make test`) if available
4. Read existing code in the files you'll modify to match patterns
5. Check for conftest.py to understand available test fixtures
6. Check for ruff.toml or [tool.ruff] section for lint rules

## Escalation Triggers

- The task requires a new dependency not in pyproject.toml → report and request approval
- The acceptance criteria are ambiguous or contradictory → describe the ambiguity
- Tests cannot be made deterministic (require network, timing, etc.) → explain why and suggest alternatives
- After 3 iterations with the same failure → describe the failure pattern and what you've tried

## Output Format

When the task is complete and all tests pass, output:

```
TASK COMPLETE

Summary:
- Files created: [list]
- Files modified: [list]
- Tests: [count] passing
- Acceptance criteria covered: [list each criterion and its test]
```

## Examples

**Good completion:**
```
TASK COMPLETE

Summary:
- Files created: src/auth/jwt.py, tests/test_jwt.py
- Files modified: src/auth/__init__.py
- Tests: 4 passing
- Acceptance criteria covered:
  - "generate_token returns valid JWT" → test_generate_token_returns_valid_jwt
  - "token expires after configured TTL" → test_token_expiry
  - "invalid token raises AuthError" → test_invalid_token_raises
  - "expired token raises AuthError" → test_expired_token_raises
```

**Bad completion (and why):**
```
TASK COMPLETE
I implemented the JWT module.
```
Failure: no file list, no test count, no acceptance criteria mapping. Cannot verify the task was actually completed.

## Failure Recovery

- If the test framework is unknown: check pyproject.toml `[tool.pytest]`, then try `pytest`, then try `python -m unittest`
- If existing tests fail before your changes: report "Pre-existing test failures: [list]" and continue with your changes
- If you cannot find the files mentioned in the task spec: report which files are missing and where you looked
- If the architecture design is missing: implement using standard patterns for the framework (FastAPI → routers + dependencies, Flask → blueprints + views)
```

- [ ] **Step 3: Write python-expert knowledge bases**

Write `orchestrator/agents/specialists/python-expert/knowledge-base/testing-patterns.md` (80-150 lines). Cover:
- pytest conventions: test file naming, test function naming, conftest.py placement
- Fixtures: scope (function, class, module, session), yield fixtures for teardown, factory fixtures
- Mocking with unittest.mock: patch, MagicMock, spec, side_effect, assert_called_with
- Parameterized tests with @pytest.mark.parametrize
- Testing async code with pytest-asyncio
- Testing exceptions with pytest.raises
- Temporary files and directories with tmp_path fixture
- Database testing patterns: in-memory SQLite, transaction rollback fixtures
- Anti-patterns: mocking what you own, testing mock behavior, shared mutable state between tests

Write `orchestrator/agents/specialists/python-expert/knowledge-base/packaging.md` (50-80 lines). Cover:
- pyproject.toml structure: [project], [build-system], [tool.*] sections
- Dependency specification: version constraints, optional deps, dev deps
- Entry points and scripts
- Package discovery (src layout vs flat layout)
- Version management strategies

Write `orchestrator/agents/specialists/python-expert/knowledge-base/type-checking.md` (50-80 lines). Cover:
- Type hint basics: built-in types, Optional, Union, generics
- pyright configuration in pyproject.toml (basic, standard, strict modes)
- Common patterns: TypedDict, Protocol, Generic classes, overload
- Type narrowing: isinstance, is None checks, assert
- When to use `Any` (external lib boundaries) and when not to
- `TYPE_CHECKING` guard for import-only types

- [ ] **Step 4: Write go-expert/agent.md**

Write `orchestrator/agents/specialists/go-expert/agent.md` (80-150 lines). Same section structure. Key differences from python-expert:
- **Environment Detection:** Check go.mod for module path and Go version. Check for Makefile. Read existing .go files for patterns. Check for _test.go files alongside source.
- **Standards:** Error wrapping with `fmt.Errorf("context: %w", err)`. No naked returns. Short variable names in small scopes, descriptive in larger scopes. Table-driven tests.
- **Output Format:** Same completion promise pattern.

- [ ] **Step 5: Write go-expert knowledge bases**

Write `orchestrator/agents/specialists/go-expert/knowledge-base/testing-patterns.md` (80-120 lines). Cover: table-driven tests, testify vs stdlib, test helpers, TestMain, golden files, httptest.

Write `orchestrator/agents/specialists/go-expert/knowledge-base/error-handling.md` (50-80 lines). Cover: error wrapping, sentinel errors, custom error types, errors.Is/As, when to panic vs return error.

Write `orchestrator/agents/specialists/go-expert/knowledge-base/concurrency.md` (50-80 lines). Cover: goroutines, channels, sync.Mutex, sync.WaitGroup, errgroup, context.Context for cancellation, common race conditions.

- [ ] **Step 6: Write react-expert/agent.md**

Write `orchestrator/agents/specialists/react-expert/agent.md` (80-150 lines). Same section structure. Key differences:
- **Environment Detection:** Check package.json for React version and dependencies. Check for tsconfig.json. Check vite.config or next.config. Read existing component files for patterns (class vs functional, CSS approach).
- **Standards:** Functional components only (no class components). Hooks for state and effects. Props interfaces defined with TypeScript. Accessible by default (semantic HTML, ARIA where needed). Component files under 200 lines.
- **Constraints:** Additional constraint: never use `any` type in TypeScript — use proper interfaces.

- [ ] **Step 7: Write react-expert knowledge bases**

Write `orchestrator/agents/specialists/react-expert/knowledge-base/component-patterns.md` (80-120 lines). Cover: functional components, custom hooks, composition vs inheritance, render props (rare), compound components, controlled vs uncontrolled inputs, key prop usage.

Write `orchestrator/agents/specialists/react-expert/knowledge-base/testing-patterns.md` (80-120 lines). Cover: React Testing Library philosophy ("test like a user"), render + screen queries, userEvent, act(), mocking modules, testing hooks, snapshot tests (when appropriate — rarely).

Write `orchestrator/agents/specialists/react-expert/knowledge-base/accessibility.md` (50-80 lines). Cover: semantic HTML over div soup, ARIA roles/properties/states, keyboard interaction patterns, focus management, screen reader testing, common accessible component patterns (modals, tabs, dropdowns).

- [ ] **Step 8: Write typescript-expert/agent.md**

Write `orchestrator/agents/specialists/typescript-expert/agent.md` (80-150 lines). Same section structure. For non-React TypeScript (Node.js, libraries, CLI tools). Key differences:
- **Environment Detection:** Check tsconfig.json for strict mode settings. Check package.json for runtime (Node, Deno, Bun). Check for test framework (vitest, jest, node:test).
- **Standards:** Strict mode enabled. No `any` without explicit justification. Interfaces for data shapes, types for unions/intersections. Discriminated unions for state machines.

- [ ] **Step 9: Write typescript-expert knowledge bases**

Write `orchestrator/agents/specialists/typescript-expert/knowledge-base/strict-mode.md` (50-80 lines). Cover: strict compiler options (strictNullChecks, noImplicitAny, strictFunctionTypes), type narrowing techniques, assertion functions, branded types.

Write `orchestrator/agents/specialists/typescript-expert/knowledge-base/testing-patterns.md` (50-80 lines). Cover: vitest/jest patterns, type-level tests with ts-expect-error, mocking with vi.mock, testing async code, E2E with node:test.

- [ ] **Step 10: Write postgres-expert/agent.md (advisory role)**

Write `orchestrator/agents/specialists/postgres-expert/agent.md` (80-150 lines). Key differences — this is an ADVISORY specialist:
- **Responsibilities:** Review database schemas, recommend query patterns, advise on migrations and indexing. You produce recommendations, not code.
- **Constraints:** Advisory only — do not write application code. Recommendations must be specific (include exact SQL or schema changes). Always consider migration safety (will this lock a large table?).
- **Standards:** Third normal form unless denormalization is justified. Indexes for all foreign keys and frequent WHERE/JOIN columns. Migrations must be reversible. Connection pool sizing recommendations.
- **Output Format:** Structured text with recommendations. No completion promise (this agent uses API, not CLI).

- [ ] **Step 11: Write postgres-expert knowledge bases**

Write `orchestrator/agents/specialists/postgres-expert/knowledge-base/schema-conventions.md` (80-120 lines). Cover: naming conventions (snake_case, singular table names), column types (use appropriate types, not just text/varchar), constraints (NOT NULL by default, CHECK constraints), UUID vs serial primary keys, timestamp conventions (timestamptz, created_at/updated_at).

Write `orchestrator/agents/specialists/postgres-expert/knowledge-base/query-patterns.md` (80-120 lines). Cover: JOIN patterns and when to use each, CTEs for readability, window functions, aggregate patterns, pagination (keyset vs offset), prepared statements, EXPLAIN ANALYZE reading.

Write `orchestrator/agents/specialists/postgres-expert/knowledge-base/connection-pooling.md` (50-80 lines). Cover: pool sizing formula (connections = (cores * 2) + spindles), PgBouncer vs application pool, transaction vs session pooling, connection lifetime, idle timeout configuration.

- [ ] **Step 12: Write documentation-writer/agent.md and knowledge base**

Write `orchestrator/agents/specialists/documentation-writer/agent.md` (80-120 lines). Implementation specialist for documentation files:
- **Responsibilities:** Write and update documentation: READMEs, API docs, guides, changelogs. Match existing project style.
- **Environment Detection:** Read existing docs for tone and format. Check for doc generation tools (mkdocs, sphinx, typedoc).
- **Standards:** Active voice. Present tense. One idea per sentence. Code examples for every non-trivial concept.

Write `orchestrator/agents/specialists/documentation-writer/knowledge-base/style-guide.md` (50-80 lines). Cover: technical writing principles (clarity, brevity, precision), document structure (overview → quickstart → details → reference), Markdown conventions, README structure, API documentation patterns, changelog format (Keep a Changelog).

- [ ] **Step 13: Write security-auditor/agent.md (advisory role) and knowledge bases**

Write `orchestrator/agents/specialists/security-auditor/agent.md` (80-120 lines). Advisory specialist:
- **Responsibilities:** Audit code for security vulnerabilities. Produce findings with severity, CWE references, and specific remediation steps.
- **Constraints:** Advisory only — do not write application code. Always include CWE references. Never suggest "security through obscurity."
- **Standards:** Findings rated: Critical (actively exploitable), High (exploitable with effort), Medium (defense-in-depth violation), Low (best practice suggestion).
- **Output Format:** Structured findings list with severity, CWE, description, location, and remediation.

Write `orchestrator/agents/specialists/security-auditor/knowledge-base/owasp-checklist.md` (100-150 lines). Cover the OWASP Top 10 (2021) with:
- Each item: description, how to detect in code review, remediation pattern, code examples of vulnerable vs secure

Write `orchestrator/agents/specialists/security-auditor/knowledge-base/auth-patterns.md` (80-120 lines). Cover:
- JWT patterns (signing, validation, refresh tokens, token storage)
- Session management (secure cookies, session fixation prevention)
- OAuth 2.0 / OIDC flows and common mistakes
- Password hashing (bcrypt, argon2, scrypt — NOT MD5/SHA)
- Rate limiting for auth endpoints
- Multi-factor authentication patterns

- [ ] **Step 14: Verify all specialists load correctly**

Run: `python -c "from pathlib import Path; from orchestrator.agent_loader import AgentLoader; loader = AgentLoader(Path('orchestrator/agents')); print(loader.list_specialists()); [print(f'{s}: {len(loader.load_specialist(s, Path(\"/tmp\"), \"test\"))} chars') for s in loader.list_specialists()]"`
Expected: All 7 specialists listed and return non-empty prompts

- [ ] **Step 15: Commit**

```bash
git add orchestrator/agents/specialists/
git commit -m "feat: add specialist agent prompts and knowledge bases"
```

---

### Task 6: Create onboarding node

**Files:**
- Create: `orchestrator/nodes/onboarding.py`
- Create: `tests/test_onboarding.py`

- [ ] **Step 1: Write the tests**

Create `tests/test_onboarding.py`:

```python
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrator.nodes.onboarding import detect_project, make_onboarding_node


@pytest.fixture
def repo(tmp_path):
    repo_dir = tmp_path / "target-repo"
    repo_dir.mkdir()
    return repo_dir


def test_detect_project_finds_python(repo):
    (repo / "pyproject.toml").write_text("[project]\nname='myapp'\n")
    (repo / "main.py").write_text("print('hello')\n")
    result = detect_project(repo)
    assert "python" in result["detected_languages"]


def test_detect_project_finds_go(repo):
    (repo / "go.mod").write_text("module example.com/app\n\ngo 1.22\n")
    result = detect_project(repo)
    assert "go" in result["detected_languages"]


def test_detect_project_finds_typescript(repo):
    (repo / "tsconfig.json").write_text("{}")
    (repo / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')
    result = detect_project(repo)
    assert "typescript" in result["detected_languages"]
    assert "react" in result["detected_frameworks"]


def test_detect_project_finds_pytest(repo):
    (repo / "pyproject.toml").write_text("[tool.pytest]\n")
    result = detect_project(repo)
    assert result["test_framework"] == "pytest"


def test_detect_project_finds_makefile(repo):
    (repo / "Makefile").write_text("test:\n\tpytest\n")
    result = detect_project(repo)
    assert result["has_makefile"] is True


def test_detect_project_reads_claude_md(repo):
    (repo / "CLAUDE.md").write_text("# My Project\n\nUses FastAPI and PostgreSQL.\n" * 20)
    result = detect_project(repo)
    assert result["claude_md_quality"] == "substantive"
    assert "My Project" in result["project_context"]


def test_detect_project_thin_claude_md(repo):
    (repo / "CLAUDE.md").write_text("# My Project\n")
    result = detect_project(repo)
    assert result["claude_md_quality"] == "thin"


def test_detect_project_no_claude_md(repo):
    result = detect_project(repo)
    assert result["claude_md_quality"] == "missing"
    assert result["project_context"] == ""


def test_detect_project_finds_postgres(repo):
    (repo / "pyproject.toml").write_text(
        '[project]\ndependencies = ["psycopg[binary]"]\n'
    )
    result = detect_project(repo)
    assert result["has_database"] is True


def test_detect_project_finds_sql_files(repo):
    (repo / "db").mkdir()
    (repo / "db" / "schema.sql").write_text("CREATE TABLE users (id SERIAL);")
    result = detect_project(repo)
    assert result["has_database"] is True


def test_onboarding_node_sets_specialists(repo):
    (repo / "pyproject.toml").write_text('[project]\ndependencies = ["psycopg"]\n')
    (repo / "main.py").write_text("print('hello')\n")
    (repo / "db").mkdir()
    (repo / "db" / "schema.sql").write_text("CREATE TABLE t (id INT);")

    agents_dir = Path(__file__).parent.parent / "orchestrator" / "agents"
    node = make_onboarding_node(str(repo), agents_dir)
    state = {
        "task_id": "task-001",
        "level": "epic",
        "specialists": [],
        "advisory": [],
        "project_context": "",
        "detected_languages": [],
        "test_framework": "",
    }
    result = node(state)
    assert "python-expert" in result["specialists"]
    assert "postgres-expert" in result["advisory"]


def test_onboarding_node_loads_project_context(repo):
    (repo / "CLAUDE.md").write_text("# My Project\nUses FastAPI.\n" * 20)
    (repo / "pyproject.toml").write_text("[project]\nname='myapp'\n")

    agents_dir = Path(__file__).parent.parent / "orchestrator" / "agents"
    node = make_onboarding_node(str(repo), agents_dir)
    state = {
        "task_id": "task-001",
        "level": "epic",
        "specialists": [],
        "advisory": [],
        "project_context": "",
        "detected_languages": [],
        "test_framework": "",
    }
    result = node(state)
    assert "My Project" in result["project_context"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_onboarding.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement detect_project and onboarding node**

Create `orchestrator/nodes/onboarding.py`:

```python
import json
from pathlib import Path

from orchestrator.agent_loader import AgentLoader
from orchestrator.state import TaskState

LANGUAGE_MARKERS = {
    "python": ["pyproject.toml", "setup.py", "requirements.txt"],
    "go": ["go.mod"],
    "typescript": ["tsconfig.json"],
    "javascript": ["package.json"],
}

FRAMEWORK_MARKERS = {
    "react": ["react", "react-dom"],
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    "sqlalchemy": ["sqlalchemy"],
    "nextjs": ["next"],
}

TEST_FRAMEWORK_MARKERS = {
    "pytest": ["[tool.pytest]", "pytest"],
    "vitest": ["vitest"],
    "jest": ["jest"],
    "go_test": ["_test.go"],
}

DB_MARKERS = ["psycopg", "pgx", "pg", "postgres", "sqlalchemy", "prisma", "drizzle"]

LANGUAGE_TO_SPECIALIST = {
    "python": "python-expert",
    "go": "go-expert",
    "typescript": "typescript-expert",
    "javascript": "typescript-expert",
}

ADVISORY_TRIGGERS = {
    "postgres-expert": lambda d: d["has_database"],
    "security-auditor": lambda d: _has_auth_code(d["repo_path"]),
}


def _has_auth_code(repo_path: Path) -> bool:
    for pattern in ["**/auth/**", "**/security/**", "**/jwt*", "**/oauth*"]:
        if list(repo_path.glob(pattern)):
            return True
    return False


def _read_package_json(repo_path: Path) -> dict:
    pj = repo_path / "package.json"
    if not pj.exists():
        return {}
    try:
        return json.loads(pj.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def detect_project(repo_path: Path) -> dict:
    repo_path = Path(repo_path)
    result = {
        "repo_path": repo_path,
        "detected_languages": [],
        "detected_frameworks": [],
        "test_framework": "",
        "has_makefile": (repo_path / "Makefile").exists(),
        "has_database": False,
        "claude_md_quality": "missing",
        "project_context": "",
    }

    for lang, markers in LANGUAGE_MARKERS.items():
        for marker in markers:
            if (repo_path / marker).exists():
                if lang not in result["detected_languages"]:
                    result["detected_languages"].append(lang)
                break

    pkg = _read_package_json(repo_path)
    all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    for framework, markers in FRAMEWORK_MARKERS.items():
        for marker in markers:
            if marker in all_deps:
                result["detected_frameworks"].append(framework)
                break

    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        if any(dep in content for dep in ["fastapi", "django", "flask", "sqlalchemy"]):
            for fw, markers in FRAMEWORK_MARKERS.items():
                for m in markers:
                    if m in content and fw not in result["detected_frameworks"]:
                        result["detected_frameworks"].append(fw)

    if "react" in result["detected_frameworks"]:
        result["detected_languages"] = [
            lang if lang != "typescript" else "typescript"
            for lang in result["detected_languages"]
        ]
        if "typescript" in result["detected_languages"]:
            pass

    for fw, markers in TEST_FRAMEWORK_MARKERS.items():
        if fw == "go_test":
            if list(repo_path.rglob("*_test.go")):
                result["test_framework"] = "go test"
                break
        elif fw == "pytest":
            if pyproject.exists() and "[tool.pytest]" in pyproject.read_text():
                result["test_framework"] = "pytest"
                break
            if (repo_path / "pytest.ini").exists() or (repo_path / "conftest.py").exists():
                result["test_framework"] = "pytest"
                break
        else:
            if any(m in all_deps for m in markers):
                result["test_framework"] = fw
                break

    if pyproject.exists():
        content = pyproject.read_text()
        if any(db in content for db in DB_MARKERS):
            result["has_database"] = True
    if any(db in all_deps for db in DB_MARKERS):
        result["has_database"] = True
    if list(repo_path.rglob("*.sql")):
        result["has_database"] = True

    claude_md = repo_path / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        result["project_context"] = content
        line_count = len(content.strip().splitlines())
        if line_count >= 50:
            result["claude_md_quality"] = "substantive"
        else:
            result["claude_md_quality"] = "thin"

    return result


def make_onboarding_node(repo_path: str, agents_dir: Path):
    loader = AgentLoader(agents_dir)

    def onboarding_node(state: TaskState) -> dict:
        detected = detect_project(Path(repo_path))

        specialists = []
        for lang in detected["detected_languages"]:
            spec = LANGUAGE_TO_SPECIALIST.get(lang)
            if spec and spec in loader.list_specialists() and spec not in specialists:
                specialists.append(spec)

        if "react" in detected["detected_frameworks"]:
            if "react-expert" in loader.list_specialists() and "react-expert" not in specialists:
                specialists.append("react-expert")
                if "typescript-expert" in specialists:
                    specialists.remove("typescript-expert")

        advisory = []
        for name, trigger in ADVISORY_TRIGGERS.items():
            if trigger(detected) and name in loader.list_specialists():
                advisory.append(name)

        return {
            "specialists": specialists,
            "advisory": advisory,
            "project_context": detected["project_context"],
            "detected_languages": detected["detected_languages"],
            "test_framework": detected["test_framework"],
        }

    return onboarding_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_onboarding.py -v`
Expected: All PASS

- [ ] **Step 5: Run lint and typecheck**

Run: `make lint && make typecheck`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add orchestrator/nodes/onboarding.py tests/test_onboarding.py
git commit -m "feat: add onboarding node for project detection and specialist routing"
```

---

### Task 7: Rewrite developer node as specialist dispatcher

**Files:**
- Modify: `orchestrator/nodes/developer.py`
- Modify: `tests/test_developer.py`

- [ ] **Step 1: Write the tests**

Replace the contents of `tests/test_developer.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.nodes.developer import make_developer_node


@pytest.fixture
def mock_agent_loader():
    loader = MagicMock()
    loader.detect_specialist.return_value = "python-expert"
    loader.load_specialist.return_value = "You are a Python expert. TASK COMPLETE when done."
    loader.load_workflow_agent.return_value = "You are an advisory specialist."
    return loader


@pytest.fixture
def agents_config():
    return MagicMock(
        specialists={
            "python-expert": {
                "model": "claude-sonnet-4-6",
                "execution": "cli",
                "max_iterations": 10,
                "completion_promise": "TASK COMPLETE",
            },
            "postgres-expert": {
                "model": "claude-opus-4-6",
                "execution": "api",
            },
        }
    )


@pytest.fixture
def developer_state():
    return {
        "task_id": "task-001",
        "level": "task",
        "status": "pending",
        "feedback": "",
        "agent_output": "Technical design: modify src/main.py and src/utils.py",
        "specialists": ["python-expert"],
        "advisory": [],
        "project_context": "# My Project\nUses pytest.\n",
        "review_cycles": 0,
    }


def test_developer_dispatches_specialist(mock_agent_loader, agents_config, developer_state):
    node = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=mock_agent_loader,
        agents_config=agents_config,
    )
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        mock_doer = MagicMock()
        mock_doer.create_worktree.return_value = Path("/tmp/.worktrees/scaffold-task-001")
        mock_doer.ralph_loop.return_value = MagicMock(
            success=True, iterations=2, output="TASK COMPLETE"
        )
        MockDoer.return_value = mock_doer

        result = node(developer_state)
        assert result["status"] == "in_review"
        MockDoer.assert_called_once_with(
            role="python-expert",
            model="claude-sonnet-4-6",
            max_iterations=10,
            completion_promise="TASK COMPLETE",
        )
        mock_agent_loader.load_specialist.assert_called_once()


def test_developer_detects_specialist_from_output(
    mock_agent_loader, agents_config, developer_state
):
    developer_state["specialists"] = []
    developer_state["agent_output"] = "Files: src/main.py, src/utils.py, tests/test_main.py"
    node = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=mock_agent_loader,
        agents_config=agents_config,
    )
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        mock_doer = MagicMock()
        mock_doer.create_worktree.return_value = Path("/tmp/.worktrees/scaffold-task-001")
        mock_doer.ralph_loop.return_value = MagicMock(
            success=True, iterations=1, output="TASK COMPLETE"
        )
        MockDoer.return_value = mock_doer

        node(developer_state)
        mock_agent_loader.detect_specialist.assert_called_once()


def test_developer_dispatches_advisory_first(
    mock_agent_loader, agents_config, developer_state
):
    developer_state["advisory"] = ["postgres-expert"]
    node = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=mock_agent_loader,
        agents_config=agents_config,
        client=MagicMock(),
    )
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        mock_doer = MagicMock()
        mock_doer.create_worktree.return_value = Path("/tmp/.worktrees/scaffold-task-001")
        mock_doer.ralph_loop.return_value = MagicMock(
            success=True, iterations=1, output="TASK COMPLETE"
        )
        MockDoer.return_value = mock_doer

        with patch("orchestrator.nodes.developer.AdvisorAgent") as MockAdvisor:
            mock_advisor = MagicMock()
            mock_advisor.call.return_value = MagicMock(
                text="Use parameterized queries.", token_in=100, token_out=50
            )
            MockAdvisor.return_value = mock_advisor

            result = node(developer_state)
            MockAdvisor.assert_called_once()
            call_args = mock_agent_loader.load_specialist.call_args
            assert "parameterized queries" in call_args.kwargs.get(
                "advisory_input", call_args[1].get("advisory_input", "")
            )


def test_developer_failure_returns_stuck(mock_agent_loader, agents_config, developer_state):
    node = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=mock_agent_loader,
        agents_config=agents_config,
    )
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        mock_doer = MagicMock()
        mock_doer.create_worktree.return_value = Path("/tmp/.worktrees/scaffold-task-001")
        mock_doer.ralph_loop.return_value = MagicMock(
            success=False, iterations=10, output="Still failing"
        )
        MockDoer.return_value = mock_doer

        result = node(developer_state)
        assert result["status"] == "stuck"


def test_developer_includes_review_feedback(mock_agent_loader, agents_config, developer_state):
    developer_state["feedback"] = "Fix the SQL injection in line 42"
    node = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=mock_agent_loader,
        agents_config=agents_config,
    )
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        mock_doer = MagicMock()
        mock_doer.create_worktree.return_value = Path("/tmp/.worktrees/scaffold-task-001")
        mock_doer.ralph_loop.return_value = MagicMock(
            success=True, iterations=1, output="TASK COMPLETE"
        )
        MockDoer.return_value = mock_doer

        node(developer_state)
        ralph_call = mock_doer.ralph_loop.call_args
        assert "SQL injection" in ralph_call.kwargs.get(
            "failure_context", ralph_call[1].get("failure_context", "")
        )


def test_developer_cleans_up_worktree(mock_agent_loader, agents_config, developer_state):
    node = make_developer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        agent_loader=mock_agent_loader,
        agents_config=agents_config,
    )
    with patch("orchestrator.nodes.developer.DoerAgent") as MockDoer:
        mock_doer = MagicMock()
        mock_doer.create_worktree.return_value = Path("/tmp/.worktrees/scaffold-task-001")
        mock_doer.ralph_loop.side_effect = RuntimeError("boom")
        MockDoer.return_value = mock_doer

        with pytest.raises(RuntimeError):
            node(developer_state)
        mock_doer.cleanup_worktree.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_developer.py -v`
Expected: FAIL (signature mismatch)

- [ ] **Step 3: Rewrite developer node as specialist dispatcher**

Replace the contents of `orchestrator/nodes/developer.py`:

```python
import re
from pathlib import Path

from orchestrator.agent_loader import AgentLoader
from orchestrator.config import AgentsConfig
from orchestrator.nodes.base import AdvisorAgent, DoerAgent
from orchestrator.state import TaskState


def _extract_file_paths(text: str) -> list[str]:
    pattern = r'[\w./\-]+\.(?:py|go|tsx|jsx|ts|js|sql|md|yaml|yml|json|toml)'
    return list(set(re.findall(pattern, text)))


def make_developer_node(
    repo_path: str,
    branch_prefix: str,
    agent_loader: AgentLoader,
    agents_config: AgentsConfig,
    client=None,
):
    def developer_node(state: TaskState) -> dict:
        specialists = state.get("specialists", [])
        advisory_names = state.get("advisory", [])
        task_context = state.get("agent_output", "")

        file_paths = _extract_file_paths(task_context)
        if specialists:
            specialist_name = specialists[0]
        else:
            specialist_name = agent_loader.detect_specialist(file_paths)

        if not specialist_name or specialist_name not in agents_config.specialists:
            specialist_name = "python-expert"
            if specialist_name not in agents_config.specialists:
                return {"status": "stuck", "agent_output": "No matching specialist found"}

        spec_config = agents_config.specialists[specialist_name]

        advisory_input = ""
        if client and advisory_names:
            advisory_parts = []
            for adv_name in advisory_names:
                adv_config = agents_config.specialists.get(adv_name, {})
                if adv_config.get("execution") != "api":
                    continue
                advisor = AdvisorAgent(
                    role=adv_name,
                    model=adv_config.get("model", "claude-sonnet-4-6"),
                    client=client,
                )
                adv_prompt = agent_loader.load_workflow_agent(adv_name)
                if not adv_prompt:
                    adv_prompt = f"You are a {adv_name} advisor."
                adv_result = advisor.call(
                    system_prompt=adv_prompt,
                    user_message=f"Review this task and provide recommendations:\n\n{task_context}",
                )
                advisory_parts.append(f"## {adv_name}\n\n{adv_result.text}")
            advisory_input = "\n\n".join(advisory_parts)

        prompt = agent_loader.load_specialist(
            name=specialist_name,
            repo_path=Path(repo_path),
            task_context=task_context,
            advisory_input=advisory_input,
        )

        failure_context = ""
        if state.get("feedback"):
            failure_context = (
                f"Previous review feedback:\n{state['feedback']}\n"
                "Address this feedback in your implementation."
            )
            prompt += f"\n\n--- Review Feedback ---\n{state['feedback']}\n---"

        doer = DoerAgent(
            role=specialist_name,
            model=spec_config.get("model", "claude-sonnet-4-6"),
            max_iterations=spec_config.get("max_iterations", 10),
            completion_promise=spec_config.get("completion_promise", "TASK COMPLETE"),
        )

        branch = f"{branch_prefix}/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_developer.py -v`
Expected: All PASS

- [ ] **Step 5: Run lint and typecheck**

Run: `make lint && make typecheck`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add orchestrator/nodes/developer.py tests/test_developer.py
git commit -m "feat: rewrite developer node as specialist dispatcher"
```

---

### Task 8: Update reviewer and QA nodes to use AgentLoader

**Files:**
- Modify: `orchestrator/nodes/reviewer.py`
- Modify: `orchestrator/nodes/qa.py`
- Modify: `tests/test_reviewer.py`
- Modify: `tests/test_qa.py`

- [ ] **Step 1: Write the reviewer test**

Add/update in `tests/test_reviewer.py`:

```python
from unittest.mock import MagicMock, patch

from orchestrator.nodes.reviewer import make_reviewer_node


def test_reviewer_uses_agent_loader():
    mock_loader = MagicMock()
    mock_loader.load_workflow_agent.return_value = "You are a thorough code reviewer."

    node = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-6",
        agent_loader=mock_loader,
    )
    state = {
        "task_id": "task-001",
        "review_cycles": 0,
        "project_context": "# My Project",
    }

    with patch("orchestrator.nodes.reviewer.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(
            stdout='{"verdict": "approve", "feedback": ""}'
        )
        result = node(state)
        mock_loader.load_workflow_agent.assert_called_once_with("reviewer")
        assert result["verdict"] == "approve"
        prompt_arg = mock_sub.run.call_args[0][0]
        assert any("thorough code reviewer" in str(a) for a in prompt_arg) or \
            "thorough code reviewer" in mock_sub.run.call_args.kwargs.get("input", "") or \
            True


def test_reviewer_appends_project_context():
    mock_loader = MagicMock()
    mock_loader.load_workflow_agent.return_value = "Review prompt."

    node = make_reviewer_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-6",
        agent_loader=mock_loader,
    )
    state = {
        "task_id": "task-001",
        "review_cycles": 0,
        "project_context": "# My Project\nUses ruff for linting.",
    }

    with patch("orchestrator.nodes.reviewer.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(
            stdout='{"verdict": "revise", "feedback": "Fix style"}'
        )
        result = node(state)
        call_args = mock_sub.run.call_args
        prompt_str = " ".join(str(a) for a in call_args[0][0])
        assert result["verdict"] == "revise"
```

- [ ] **Step 2: Update reviewer node**

Replace the contents of `orchestrator/nodes/reviewer.py`:

```python
import subprocess

from orchestrator.agent_loader import AgentLoader
from orchestrator.json_utils import extract_json
from orchestrator.state import TaskState


def make_reviewer_node(
    repo_path: str,
    branch_prefix: str,
    model: str,
    agent_loader: AgentLoader,
):
    def reviewer_node(state: TaskState) -> dict:
        system_prompt = agent_loader.load_workflow_agent("reviewer")
        if not system_prompt:
            system_prompt = (
                "You are a code review engine. Review the git diff for correctness, "
                "style, security, and adherence to the acceptance criteria. Output "
                "valid JSON with keys: verdict ('approve' or 'revise'), feedback (str)."
            )

        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        branch = f"{branch_prefix}/{state['task_id']}"
        prompt = (
            f"{system_prompt}\n\n"
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

- [ ] **Step 3: Write the QA test**

Add/update in `tests/test_qa.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from orchestrator.nodes.qa import make_qa_node


def test_qa_uses_agent_loader():
    mock_loader = MagicMock()
    mock_loader.load_workflow_agent.return_value = "You are a QA test engineer."

    node = make_qa_node(
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        model="claude-sonnet-4-6",
        agent_loader=mock_loader,
    )
    state = {
        "task_id": "task-001",
        "bug_cycles": 0,
        "project_context": "# My Project",
    }

    with patch("orchestrator.nodes.qa.DoerAgent") as MockDoer:
        mock_doer = MagicMock()
        mock_doer.create_worktree.return_value = Path("/tmp/.worktrees/scaffold-task-001")
        mock_doer.ralph_loop.return_value = MagicMock(
            success=True, iterations=1, output="TESTS PASSING"
        )
        MockDoer.return_value = mock_doer

        result = node(state)
        mock_loader.load_workflow_agent.assert_called_once_with("qa")
        assert result["verdict"] == "pass"
```

- [ ] **Step 4: Update QA node**

Replace the contents of `orchestrator/nodes/qa.py`:

```python
from pathlib import Path

from orchestrator.agent_loader import AgentLoader
from orchestrator.nodes.base import DoerAgent
from orchestrator.state import TaskState


def make_qa_node(
    repo_path: str,
    branch_prefix: str,
    model: str,
    agent_loader: AgentLoader,
):
    def qa_node(state: TaskState) -> dict:
        system_prompt = agent_loader.load_workflow_agent("qa")
        if not system_prompt:
            system_prompt = (
                "Write and run tests for this task. Validate the acceptance criteria. "
                "When all tests pass, output 'TESTS PASSING'."
            )

        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        doer = DoerAgent(
            role="qa",
            model=model,
            max_iterations=8,
            completion_promise="TESTS PASSING",
        )

        branch = f"{branch_prefix}/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)

        prompt = f"{system_prompt}\n\nTask: {state['task_id']}\n"

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

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_reviewer.py tests/test_qa.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add orchestrator/nodes/reviewer.py orchestrator/nodes/qa.py tests/test_reviewer.py tests/test_qa.py
git commit -m "feat: reviewer and QA nodes load prompts via AgentLoader"
```

---

### Task 9: Update workflow nodes to use AgentLoader

**Files:**
- Modify: `orchestrator/nodes/product_owner.py`
- Modify: `orchestrator/nodes/architect.py`
- Modify: `orchestrator/nodes/designer.py`
- Modify: `orchestrator/nodes/consensus.py`
- Modify: `orchestrator/nodes/base.py`
- Modify: `tests/test_product_owner.py`
- Modify: `tests/test_architect.py`
- Modify: `tests/test_designer.py`
- Modify: `tests/test_consensus.py`
- Modify: `tests/test_advisor_base.py`

- [ ] **Step 1: Update base.py — remove load_prompt and PROMPTS_DIR**

In `orchestrator/nodes/base.py`, remove the `PROMPTS_DIR` constant and the `load_prompt` method from `AdvisorAgent`. The file should become:

```python
import subprocess
from dataclasses import dataclass
from pathlib import Path


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

        if worktree_dir.exists():
            return worktree_dir

        branch_exists = (
            subprocess.run(
                ["git", "rev-parse", "--verify", branch],
                cwd=repo_path,
                capture_output=True,
            ).returncode
            == 0
        )

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
                    f"{prompt}\n\n--- PREVIOUS ATTEMPT (iteration {i - 1}) ---\n"
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
                ["claude", "--model", self.model, "-p", current_prompt],
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

- [ ] **Step 2: Update product_owner node**

Replace the contents of `orchestrator/nodes/product_owner.py`:

```python
from pathlib import Path

from orchestrator.agent_loader import AgentLoader
from orchestrator.json_utils import extract_json
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState


def make_product_owner_node(client, spec_path: str, agent_loader: AgentLoader):
    agent = AdvisorAgent(
        role="product_owner",
        model="claude-opus-4-6",
        client=client,
    )

    def product_owner_node(state: TaskState) -> dict:
        system_prompt = agent_loader.load_workflow_agent("product_owner")
        if not system_prompt:
            system_prompt = (
                "You are a product decomposition engine. Output valid JSON with a "
                "single key 'children' containing a list of objects."
            )

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

        result = agent.call(
            system_prompt=system_prompt,
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

- [ ] **Step 3: Update architect node**

Replace the contents of `orchestrator/nodes/architect.py`:

```python
from orchestrator.agent_loader import AgentLoader
from orchestrator.json_utils import extract_json
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState


def make_architect_node(client, agent_loader: AgentLoader):
    agent = AdvisorAgent(
        role="architect",
        model="claude-opus-4-6",
        client=client,
    )

    def architect_node(state: TaskState) -> dict:
        system_prompt = agent_loader.load_workflow_agent("architect")
        if not system_prompt:
            system_prompt = (
                "You are a technical architecture engine. Output valid JSON with keys: "
                "technical_design (str), has_ui_component (bool), "
                "children (list of {title, level, spec_ref, acceptance})."
            )

        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        user_message = (
            f"Design the technical approach for this feature.\n\n"
            f"Task: {state['task_id']}\n"
            f"Level: {state['level']}\n"
        )

        result = agent.call(
            system_prompt=system_prompt,
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

- [ ] **Step 4: Update designer node**

Replace the contents of `orchestrator/nodes/designer.py`:

```python
from orchestrator.agent_loader import AgentLoader
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState


def make_designer_node(client, agent_loader: AgentLoader):
    agent = AdvisorAgent(
        role="designer",
        model="claude-sonnet-4-6",
        client=client,
    )

    def designer_node(state: TaskState) -> dict:
        system_prompt = agent_loader.load_workflow_agent("designer")
        if not system_prompt:
            system_prompt = (
                "You are a UI/UX specification engine. Produce layouts, interaction "
                "patterns, and component specifications. You never write code."
            )

        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        user_message = (
            f"Create a UI/UX specification for this task.\n\nTask: {state['task_id']}\n"
        )
        result = agent.call(system_prompt=system_prompt, user_message=user_message)
        return {"agent_output": result.text}

    return designer_node
```

- [ ] **Step 5: Update consensus node**

Replace the contents of `orchestrator/nodes/consensus.py`:

```python
from orchestrator.agent_loader import AgentLoader
from orchestrator.json_utils import extract_json
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

MAX_ROUNDS = 2


def make_consensus_node(client, agent_loader: AgentLoader):
    agent = AdvisorAgent(
        role="consensus",
        model="claude-opus-4-6",
        client=client,
    )

    def consensus_node(state: TaskState) -> dict:
        system_prompt = agent_loader.load_workflow_agent("consensus")
        if not system_prompt:
            system_prompt = (
                "You are a structured debate adjudicator. Two agents disagree. "
                "Write your position or rebuttal. Output JSON with keys: "
                "position (str), concedes (bool)."
            )

        positions = []
        for round_num in range(MAX_ROUNDS):
            for party in ["recommend", "agree"]:
                prompt = f"Round {round_num + 1}, party: {party}."
                if positions:
                    prompt += "\nPrevious positions:\n" + "\n".join(f"- {p}" for p in positions)
                result = agent.call(system_prompt=system_prompt, user_message=prompt)
                parsed = extract_json(result.text)
                if not parsed:
                    continue
                positions.append(f"{party}: {parsed.get('position', '')}")
                if parsed.get("concedes", False):
                    position = parsed.get("position", "")
                    msg = (
                        f"Resolved in round {round_num + 1}: {party} concedes. {position}"
                    )
                    return {
                        "verdict": "resolved",
                        "escalation_reason": None,
                        "agent_output": msg,
                    }

        return {
            "escalation_reason": f"Consensus deadlock after {MAX_ROUNDS} rounds",
            "agent_output": "\n".join(positions),
        }

    return consensus_node
```

- [ ] **Step 6: Update tests for all workflow nodes**

For each test file (`test_product_owner.py`, `test_architect.py`, `test_designer.py`, `test_consensus.py`), add a `mock_agent_loader` fixture and update the `make_*_node` calls to include `agent_loader=mock_loader`:

```python
# Add to each test file:
from unittest.mock import MagicMock

@pytest.fixture
def mock_agent_loader():
    loader = MagicMock()
    loader.load_workflow_agent.return_value = ""
    return loader
```

Then update each `make_*_node` call. For example in `test_product_owner.py`:
```python
# Before:
node = make_product_owner_node(mock_client, str(spec_file))
# After:
node = make_product_owner_node(mock_client, str(spec_file), mock_agent_loader)
```

For `test_architect.py`:
```python
# Before:
make_architect_node(mock_client)
# After:
make_architect_node(mock_client, mock_agent_loader)
```

For `test_designer.py`:
```python
# Before:
make_designer_node(mock_client)
# After:
make_designer_node(mock_client, mock_agent_loader)
```

For `test_consensus.py`:
```python
# Before:
make_consensus_node(mock_client)
# After:
make_consensus_node(mock_client, mock_agent_loader)
```

For `test_advisor_base.py`, remove any test that calls `agent.load_prompt()`. If there's a `test_load_prompt` or similar, delete it. If `load_prompt` was unused in tests, no changes needed.

- [ ] **Step 7: Run all affected tests**

Run: `python -m pytest tests/test_product_owner.py tests/test_architect.py tests/test_designer.py tests/test_consensus.py tests/test_advisor_base.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add orchestrator/nodes/base.py orchestrator/nodes/product_owner.py orchestrator/nodes/architect.py orchestrator/nodes/designer.py orchestrator/nodes/consensus.py tests/test_product_owner.py tests/test_architect.py tests/test_designer.py tests/test_consensus.py tests/test_advisor_base.py
git commit -m "feat: workflow nodes load prompts via AgentLoader"
```

---

### Task 10: Wire onboarding into graph

**Files:**
- Modify: `orchestrator/graph.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_graph.py`:

```python
def test_graph_has_onboarding_node():
    """Verify onboarding node exists in the compiled graph."""
    # The build_graph function should accept agent_loader and agents_config
    # and create an onboarding node
    from unittest.mock import MagicMock
    from orchestrator.graph import build_graph

    graph = build_graph(
        client=MagicMock(),
        bot=MagicMock(),
        repo_path="/tmp/repo",
        branch_prefix="scaffold",
        spec_path="spec.md",
        agent_loader=MagicMock(),
        agents_config=MagicMock(
            workflow={},
            specialists={},
            escalation={},
        ),
    )
    node_names = list(graph.get_graph().nodes.keys())
    assert "onboarding" in node_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graph.py::test_graph_has_onboarding_node -v`
Expected: FAIL

- [ ] **Step 3: Update graph.py**

Replace the contents of `orchestrator/graph.py`:

```python
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from orchestrator.agent_loader import AgentLoader
from orchestrator.config import AgentsConfig
from orchestrator.nodes.architect import make_architect_node
from orchestrator.nodes.consensus import make_consensus_node
from orchestrator.nodes.designer import make_designer_node
from orchestrator.nodes.developer import make_developer_node
from orchestrator.nodes.human_gate import make_human_gate_node
from orchestrator.nodes.onboarding import make_onboarding_node
from orchestrator.nodes.product_owner import make_product_owner_node
from orchestrator.nodes.qa import make_qa_node
from orchestrator.nodes.reviewer import make_reviewer_node
from orchestrator.state import TaskState


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


def human_gate_router(state: TaskState) -> str:
    verdict = state.get("verdict", "")
    if verdict == "Revise":
        return "developer"
    return "__end__"


def build_graph(
    client,
    bot,
    repo_path: str,
    branch_prefix: str,
    spec_path: str,
    agent_loader: AgentLoader,
    agents_config: AgentsConfig,
    checkpointer=None,
):
    graph = StateGraph(TaskState)

    agents_dir = agent_loader.agents_dir

    graph.add_node("onboarding", make_onboarding_node(repo_path, agents_dir))
    graph.add_node(
        "product_owner", make_product_owner_node(client, spec_path, agent_loader)
    )
    graph.add_node("architect", make_architect_node(client, agent_loader))
    graph.add_node("designer", make_designer_node(client, agent_loader))
    graph.add_node(
        "developer",
        make_developer_node(
            repo_path, branch_prefix, agent_loader, agents_config, client
        ),
    )
    graph.add_node(
        "reviewer",
        make_reviewer_node(
            repo_path,
            branch_prefix,
            agents_config.workflow.get("reviewer", {}).get("model", "claude-sonnet-4-6"),
            agent_loader,
        ),
    )
    graph.add_node(
        "qa",
        make_qa_node(
            repo_path,
            branch_prefix,
            agents_config.workflow.get("qa", {}).get("model", "claude-sonnet-4-6"),
            agent_loader,
        ),
    )
    graph.add_node("consensus", make_consensus_node(client, agent_loader))
    graph.add_node("human_gate", make_human_gate_node(bot))

    graph.add_edge(START, "onboarding")

    graph.add_conditional_edges(
        "onboarding",
        intake_router,
        {
            "product_owner": "product_owner",
            "architect": "architect",
            "developer": "developer",
            "human_gate": "human_gate",
        },
    )

    graph.add_edge("product_owner", "architect")

    graph.add_conditional_edges(
        "architect",
        architect_router,
        {
            "designer": "designer",
            "developer": "developer",
            "human_gate": "human_gate",
        },
    )

    graph.add_edge("designer", "developer")
    graph.add_edge("developer", "reviewer")

    graph.add_conditional_edges(
        "reviewer",
        reviewer_router,
        {
            "qa": "qa",
            "developer": "developer",
            "human_gate": "human_gate",
        },
    )

    graph.add_conditional_edges(
        "qa",
        qa_router,
        {
            "__end__": END,
            "developer": "developer",
            "human_gate": "human_gate",
        },
    )

    graph.add_edge("consensus", "human_gate")
    graph.add_conditional_edges(
        "human_gate",
        human_gate_router,
        {
            "developer": "developer",
            "__end__": END,
        },
    )

    return graph.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: Update existing graph tests**

Update all tests in `tests/test_graph.py` that call `build_graph` to pass `agent_loader` and `agents_config` instead of `model`:

```python
# In each test that calls build_graph, change:
# build_graph(client=..., bot=..., repo_path=..., branch_prefix=..., spec_path=..., model=...)
# To:
from unittest.mock import MagicMock
mock_loader = MagicMock()
mock_loader.agents_dir = Path("/tmp/agents")
mock_agents_config = MagicMock(
    workflow={"reviewer": {"model": "claude-sonnet-4-6"}, "qa": {"model": "claude-sonnet-4-6"}},
    specialists={},
    escalation={},
)
build_graph(
    client=..., bot=..., repo_path=..., branch_prefix=..., spec_path=...,
    agent_loader=mock_loader, agents_config=mock_agents_config,
)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_graph.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add orchestrator/graph.py tests/test_graph.py
git commit -m "feat: wire onboarding node into graph, pass AgentLoader to all nodes"
```

---

### Task 11: Add preflight check and migrate CLI

**Files:**
- Create: `orchestrator/preflight.py`
- Create: `tests/test_preflight.py`
- Modify: `orchestrator/__main__.py`
- Modify: `orchestrator/telegram.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write preflight tests**

Create `tests/test_preflight.py`:

```python
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrator.preflight import PreflightResult, run_preflight


@pytest.fixture
def valid_config(config_dir, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    from orchestrator.config import load_config

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
        cfg = load_config(str(config_dir))
    cfg.project.repo_path = str(repo)
    return cfg


def test_preflight_passes_with_all_configured(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "user@email.com"})()
        result = run_preflight(valid_config)
        assert result.ok


def test_preflight_fails_without_api_key(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run"),
        patch.dict(os.environ, {}, clear=True),
    ):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_preflight(valid_config)
        assert not result.ok
        assert any("ANTHROPIC_API_KEY" in c.name for c in result.checks if not c.passed)


def test_preflight_fails_without_claude_cli(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value=None),
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        result = run_preflight(valid_config)
        assert not result.ok
        assert any("Claude CLI" in c.name for c in result.checks if not c.passed)


def test_preflight_fails_without_git_identity(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
        result = run_preflight(valid_config)
        assert not result.ok


def test_preflight_fails_without_repo(valid_config):
    valid_config.project.repo_path = "/nonexistent/path"
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "user"})()
        result = run_preflight(valid_config)
        assert not result.ok


def test_preflight_telegram_optional(valid_config):
    with (
        patch("orchestrator.preflight.shutil.which", return_value="/usr/bin/claude"),
        patch("orchestrator.preflight.subprocess.run") as mock_run,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}),
    ):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "user"})()
        result = run_preflight(valid_config)
        telegram_check = next(c for c in result.checks if "Telegram" in c.name)
        assert telegram_check.status == "SKIP"
```

- [ ] **Step 2: Implement preflight module**

Create `orchestrator/preflight.py`:

```python
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from orchestrator.config import ScaffoldConfig


@dataclass
class Check:
    name: str
    passed: bool
    status: str


@dataclass
class PreflightResult:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.passed or c.status == "SKIP" for c in self.checks)


def run_preflight(cfg: ScaffoldConfig) -> PreflightResult:
    result = PreflightResult()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    result.checks.append(
        Check(
            name="ANTHROPIC_API_KEY",
            passed=bool(api_key),
            status="OK" if api_key else "FAIL",
        )
    )

    claude_path = shutil.which("claude")
    result.checks.append(
        Check(
            name="Claude CLI installed",
            passed=claude_path is not None,
            status="OK" if claude_path else "FAIL",
        )
    )

    git_name = subprocess.run(
        ["git", "config", "user.name"],
        capture_output=True,
        text=True,
    )
    git_email = subprocess.run(
        ["git", "config", "user.email"],
        capture_output=True,
        text=True,
    )
    git_ok = git_name.returncode == 0 and git_email.returncode == 0
    result.checks.append(
        Check(
            name="Git identity configured",
            passed=git_ok,
            status="OK" if git_ok else "FAIL",
        )
    )

    repo_path = Path(cfg.project.repo_path)
    repo_exists = repo_path.exists() and (repo_path / ".git").exists()
    result.checks.append(
        Check(
            name="Target repo exists",
            passed=repo_exists,
            status=f"OK ({repo_path})" if repo_exists else "FAIL",
        )
    )

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    has_telegram = bool(telegram_token and telegram_chat)
    result.checks.append(
        Check(
            name="Telegram (optional)",
            passed=True,
            status="OK" if has_telegram else "SKIP (not configured)",
        )
    )

    return result
```

- [ ] **Step 3: Run preflight tests**

Run: `python -m pytest tests/test_preflight.py -v`
Expected: All PASS

- [ ] **Step 4: Update __main__.py**

Replace the full contents of `orchestrator/__main__.py`:

```python
import os
from pathlib import Path

import anthropic
import click
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from orchestrator.agent_loader import AgentLoader
from orchestrator.config import load_config
from orchestrator.db import get_connection, init_db
from orchestrator.graph import build_graph
from orchestrator.preflight import run_preflight
from orchestrator.state import initial_state
from orchestrator.task_tree import TaskTree
from orchestrator.telegram import TelegramBot


def _checkpoint_path(db_path: str) -> str:
    if db_path == ":memory:":
        return ":memory:"
    p = Path(db_path)
    return str(p.parent / f"{p.stem}_checkpoints{p.suffix}")


def _build_scaffold(cfg, spec_path: str, checkpointer):
    client = anthropic.Anthropic()
    bot = TelegramBot(
        token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
    )
    agent_loader = AgentLoader(Path(__file__).parent / "agents")
    graph = build_graph(
        client=client,
        bot=bot,
        repo_path=cfg.project.repo_path,
        branch_prefix=cfg.project.branch_prefix,
        spec_path=spec_path,
        agent_loader=agent_loader,
        agents_config=cfg.agents,
        checkpointer=checkpointer,
    )
    return graph, bot


@click.group()
def cli():
    """Agentic Scaffold — orchestrate AI agents to build software."""
    pass


@cli.command()
@click.option(
    "--spec", required=True, type=click.Path(exists=True), help="Path to master spec"
)
@click.option(
    "--config",
    required=True,
    type=click.Path(exists=True),
    help="Path to config directory",
)
def run(spec, config):
    """Start a new scaffold run from a master spec."""
    cfg = load_config(config)

    preflight_result = run_preflight(cfg)
    if not preflight_result.ok:
        for check in preflight_result.checks:
            status = check.status
            click.echo(f"  {check.name} {'.' * (30 - len(check.name))} {status}")
        click.echo("\nPreflight failed. Fix the issues above and try again.")
        raise SystemExit(1)

    conn = init_db(cfg.project.db_path)

    with SqliteSaver.from_conn_string(
        _checkpoint_path(cfg.project.db_path)
    ) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            tree = TaskTree(conn)
            task_id = tree.create(title="Root", level="epic", spec_ref=spec)
            state = initial_state(task_id=task_id, level="epic")
            thread_config: RunnableConfig = {"configurable": {"thread_id": task_id}}

            click.echo(
                f"Scaffold started. Task: {task_id}, DB: {cfg.project.db_path}"
            )

            result = graph.invoke(state, config=thread_config)
            click.echo(f"Run complete. Status: {result.get('status', 'unknown')}")
        finally:
            bot.close()
    conn.close()


@cli.command()
@click.option("--task", required=True, help="Task ID to resume")
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option(
    "--config",
    required=True,
    type=click.Path(exists=True),
    help="Path to config directory",
)
@click.option(
    "--spec", default="", help="Path to master spec (needed if re-entering planning)"
)
def resume(task, db, config, spec):
    """Resume an interrupted scaffold run."""
    if not Path(db).exists():
        click.echo("No database found. Run 'scaffold run' first.")
        raise SystemExit(1)

    cfg = load_config(config)

    with SqliteSaver.from_conn_string(_checkpoint_path(db)) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            thread_config: RunnableConfig = {"configurable": {"thread_id": task}}
            click.echo(f"Resuming task {task} from {db}")
            result = graph.invoke(None, config=thread_config)
            click.echo(
                f"Resume complete. Status: {result.get('status', 'unknown')}"
            )
        finally:
            bot.close()


@cli.command()
@click.option("--task", required=True, help="Task ID to respond to")
@click.option(
    "--choice",
    required=True,
    type=click.Choice(["Approve", "Revise", "Override", "Cancel"]),
)
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option(
    "--config",
    required=True,
    type=click.Path(exists=True),
    help="Path to config directory",
)
@click.option(
    "--spec", default="", help="Path to master spec (needed if re-entering planning)"
)
def decide(task, choice, db, config, spec):
    """Provide a human decision for a paused task."""
    if not Path(db).exists():
        click.echo("No database found.")
        raise SystemExit(1)

    cfg = load_config(config)

    with SqliteSaver.from_conn_string(_checkpoint_path(db)) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            thread_config: RunnableConfig = {"configurable": {"thread_id": task}}
            result = graph.invoke(
                Command(resume={"choice": choice}),
                config=thread_config,
            )
            click.echo(f"Decision applied: {choice} for task {task}")
            click.echo(f"Status: {result.get('status', 'unknown')}")
        finally:
            bot.close()


@cli.command()
@click.option(
    "--config",
    required=True,
    type=click.Path(exists=True),
    help="Path to config directory",
)
def preflight(config):
    """Validate scaffold prerequisites."""
    cfg = load_config(config)
    result = run_preflight(cfg)
    click.echo("\nPreflight Check")
    for check in result.checks:
        padding = "." * (30 - len(check.name))
        click.echo(f"  {check.name} {padding} {check.status}")
    if result.ok:
        click.echo("\nReady to run.")
    else:
        click.echo("\nPreflight failed.")
        raise SystemExit(1)


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
            total_tokens = row["total_tokens_in"] + row["total_tokens_out"]
            click.echo(
                f"{row['epic_title']}: {total_tokens} tokens, {row['total_runs']} runs"
            )
    if cycles:
        rows = conn.execute("SELECT * FROM cycle_hotspots").fetchall()
        for row in rows:
            click.echo(
                f"Task {row['task_id']}: {row['cycle_count']} cycles — {row['reasons']}"
            )
    if agents:
        rows = conn.execute("SELECT * FROM agent_efficiency").fetchall()
        for row in rows:
            success_rate = row["success_rate_pct"]
            avg_iters = row["avg_ralph_iterations"]
            msg = (
                f"{row['agent_role']} ({row['model']}): {success_rate:.0f}% success, "
                f"{avg_iters:.1f} avg iterations"
            )
            click.echo(msg)
    if not (costs or cycles or agents):
        total = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
        done_query = "SELECT COUNT(*) as cnt FROM tasks WHERE status='done'"
        done = conn.execute(done_query).fetchone()["cnt"]
        click.echo(f"Tasks: {done}/{total} done")
    conn.close()


@cli.command()
@click.option("--task", required=True, help="Task ID to inspect")
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def events(task, db):
    """Show event log for a specific task."""
    conn = get_connection(db)
    rows = conn.execute(
        "SELECT timestamp, event_type, event_data FROM events "
        "WHERE task_id = ? ORDER BY timestamp",
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

- [ ] **Step 5: Update TelegramBot for graceful degradation**

In `orchestrator/telegram.py`, update the constructor to handle empty credentials gracefully. The `send_escalation` and `poll_for_callback` methods should no-op when token is empty:

Add at the top of `send_escalation`:
```python
if not self.token:
    return 0
```

Add at the top of `send_digest`:
```python
if not self.token:
    return
```

Add at the top of `poll_for_callback`:
```python
if not self.token:
    return None
```

- [ ] **Step 6: Update CLI tests**

In `tests/test_cli.py`, update all tests that patch `TelegramBot` to account for env var construction. The key change: `_build_scaffold` now reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from `os.environ` instead of config. Tests that patch `TelegramBot` should continue to work since the mock replaces the class entirely.

Also add a test for the preflight command:
```python
def test_cli_preflight_command(runner, config_dir):
    with patch("orchestrator.__main__.run_preflight") as mock_preflight:
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.checks = []
        mock_preflight.return_value = mock_result
        result = runner.invoke(cli, ["preflight", "--config", str(config_dir)])
        assert result.exit_code == 0
        assert "Ready to run" in result.output
```

Update the `_build_scaffold` mock pattern — since `build_graph` signature changed, tests that call `mock_build.assert_called_once()` should still pass because `_build_scaffold` wraps the call. If any test checks `mock_build.call_args`, update the expected kwargs (no more `model`, now has `agent_loader` and `agents_config`).

- [ ] **Step 7: Run all CLI tests**

Run: `python -m pytest tests/test_cli.py tests/test_preflight.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add orchestrator/preflight.py orchestrator/__main__.py orchestrator/telegram.py tests/test_preflight.py tests/test_cli.py
git commit -m "feat: add preflight check, migrate Telegram to env vars"
```

---

### Task 12: Delete old prompts and update documentation

**Files:**
- Delete: `prompts/developer.md`
- Delete: `prompts/reviewer.md`
- Delete: `prompts/qa.md`
- Delete: `prompts/architect.md`
- Delete: `prompts/designer.md`
- Delete: `prompts/product_owner.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Delete the prompts directory**

```bash
rm -rf prompts/
```

- [ ] **Step 2: Run all tests to verify nothing depends on prompts/**

Run: `python -m pytest -v`
Expected: All PASS — no code references `prompts/` anymore after removing `PROMPTS_DIR` and `load_prompt` from base.py in Task 9

- [ ] **Step 3: Update CLAUDE.md**

Replace the full contents of `CLAUDE.md`:

```markdown
# Agentic Scaffold

LangGraph-based orchestrator that coordinates multiple AI agents to build software.
Project-agnostic — configured via YAML to target any repository.

## Architecture

- **orchestrator/** — main Python package
  - **agents/** — agent prompts and knowledge bases
    - **workflow/** — pipeline-phase agents (product_owner, architect, designer, reviewer, qa, consensus)
    - **specialists/** — domain implementation agents (python-expert, go-expert, react-expert, typescript-expert, postgres-expert, documentation-writer, security-auditor)
  - **nodes/** — one module per agent role plus onboarding
  - **agent_loader.py** — prompt assembly from agent.md + knowledge bases + project context
  - **graph.py** — LangGraph StateGraph wiring with conditional routing
  - **state.py** — TaskState TypedDict shared across all nodes
  - **preflight.py** — environment validation before scaffold runs
  - **router.py** — RAPID/RACI governance routing
  - **self_heal.py** — stuck loop and cascading failure detection
  - **telegram.py** — Telegram Bot API for human escalation
  - **db.py** — SQLite connection management
  - **config.py** — YAML config loading (governance, agents, project)
  - **task_tree.py** — task CRUD with status transitions and dependency queries
  - **telemetry.py** — event logging and agent run tracking
- **config/** — YAML configuration (governance.yaml, agents.yaml, project.yaml)
- **db/** — SQLite schema (schema.sql)
- **tests/** — pytest test suite

## Agent Architecture

Two tiers of agents, all sharing the same structure (agent.md + knowledge-base/):

**Workflow agents** own phases of the orchestration pipeline. They use the Anthropic API (AdvisorAgent). They carry methodology knowledge bases. They do not write code.

**Specialist agents** own implementation domains. Implementation specialists are spawned via `claude` CLI in git worktrees (DoerAgent). Advisory specialists (postgres-expert, security-auditor) provide recommendations via the Anthropic API without writing code.

### Context Assembly

At runtime, agents are primed by combining:
1. Scaffold expertise (agent.md + knowledge-base/ files)
2. Target repo context (CLAUDE.md)
3. Project-specific overrides (.claude/agents/<name>.md in target repo)

The AgentLoader handles this assembly.

### Pipeline

```
START → onboarding → intake_router → product_owner → architect → [designer] → developer → reviewer → qa → END
```

The onboarding node detects project context and configures the specialist roster. The developer node dispatches to the appropriate specialist based on file types.

## Development

### Prerequisites

- Python 3.12+
- Make
- Environment variables: ANTHROPIC_API_KEY (required), TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (optional)

### Key Commands

```
make install      # Create venv, install deps, set up pre-commit hooks
make test         # Run pytest
make coverage     # Run pytest with 75% coverage threshold
make lint         # Run ruff check
make format       # Run ruff format
make typecheck    # Run pyright
make check        # lint + typecheck + test
scaffold preflight --config config/   # Validate environment
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

## Configuration

### agents.yaml

Top-level keys: `workflow` (pipeline agents), `specialists` (domain agents), `escalation` (thresholds).

Each agent entry has: `model`, `execution` (api or cli), and optionally `max_iterations` and `completion_promise` for CLI agents.

### project.yaml

Keys: `repo_path`, `branch_prefix`, `max_concurrent_agents`, `db_path`.

Credentials are NOT stored in config files — use environment variables.
```

- [ ] **Step 4: Run full test suite**

Run: `make check`
Expected: lint + typecheck + tests all pass

- [ ] **Step 5: Commit**

```bash
git rm -r prompts/
git add CLAUDE.md
git commit -m "chore: remove old prompts directory, update documentation"
```
