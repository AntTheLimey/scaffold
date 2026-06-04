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
  - **init.py** — project initialization: detection display, interview, CLAUDE.md generation
  - **router.py** — RAPID/RACI governance routing
  - **self_heal.py** — stuck loop and cascading failure detection
  - **telegram.py** — Telegram Bot API for human escalation
  - **db.py** — SQLite connection management
  - **config.py** — YAML config loading (governance, agents, project)
  - **task_tree.py** — task CRUD with status transitions and dependency queries
  - **telemetry.py** — event logging and agent run tracking
  - **budget.py** — model pricing table and token-to-dollar cost calculation
  - **dispatcher.py** — task dispatch with topological sort for depends_on ordering
  - **event_bus.py** — SQLite-backed event bus for observability (node enter/exit, API/CLI calls, costs, tool calls)
  - **json_utils.py** — JSON extraction from mixed text (agent output parsing)
  - **tools.py** — read-only codebase tools (read_file, list_directory, grep) for AdvisorAgent tool use
  - **artifacts.py** — file-based artifact handoff between pipeline nodes
- **config/** — YAML configuration (governance.yaml, agents.yaml, projects/)
- **db/** — SQLite schema (schema.sql)
- **tests/** — pytest test suite

## Agent Architecture

Two tiers of agents, all sharing the same structure (agent.md + knowledge-base/):

**Workflow agents** own phases of the orchestration pipeline. They use the Anthropic API (AdvisorAgent). They carry methodology knowledge bases. They do not write code. PO, architect, and designer have read-only codebase tools (read_file, list_directory, grep) for inspecting the target repo before making decisions.

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

The onboarding node detects project context and configures the specialist roster. The developer node selects the appropriate specialist using a cascading priority: architect-declared specialist → architect file paths → regex file extraction → onboarding roster → detected languages → python-expert fallback.

### Artifact Handoff

Pipeline nodes exchange context through persistent files at `{target_repo}/.scaffold/artifacts/{task_id}/{role}.md`. Each node writes its output as an artifact and downstream nodes read from these files (falling back to `agent_output` in LangGraph state for backward compatibility). The dispatcher writes child task specs to `task_spec.md`. Artifact I/O is best-effort — disk errors degrade persistence but don't abort orchestration. The `scaffold clean` command removes the `.scaffold/` directory.

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
scaffold init /path/to/repo --config config/   # Initialize a target repo
scaffold clean --repo /path --db scaffold.db  # Remove worktrees, branches, and DB from a previous run
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

Each agent entry has: `model`, `execution` (api or cli), and optionally `max_iterations`, `completion_promise`, `timeout`, and `max_budget_usd` for CLI agents.

### project.yaml

Per-project config in `config/projects/{name}.yaml`. Keys: `repo_path`, `branch_prefix`, `max_concurrent_agents`, `db_path`, `max_budget_usd`.

Legacy: a single `config/project.yaml` is supported for backward compatibility when `--project` is not provided.

Credentials are NOT stored in config files — use environment variables.
