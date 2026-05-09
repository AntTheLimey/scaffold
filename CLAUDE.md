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
