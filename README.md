# Agentic Scaffold

A [LangGraph](https://github.com/langchain-ai/langgraph)-based orchestrator that coordinates multiple agents through a structured pipeline to build software. Project-agnostic -- configured via YAML to target any repository.

Agents are organized into two tiers: **workflow agents** own pipeline phases and carry methodology knowledge, while **specialist agents** own implementation domains and write code in isolated git worktrees.

## Key Features

- **Multi-agent pipeline** -- onboarding, product owner, architect, designer, developer, reviewer, QA
- **Two-tier agents** -- workflow (API-based, methodology) and specialists (CLI-based, code)
- **Git worktree isolation** -- each task gets its own branch and working directory
- **Ralph loop** -- iterative implementation with completion-promise detection
- **RAPID/RACI governance** -- configurable decision routing across agent roles
- **Human-in-the-loop** -- Telegram notifications or CLI decisions at gate points
- **Resumable execution** -- LangGraph checkpointing with SQLite persistence
- **Self-healing** -- stuck-loop and cascading-failure detection with automatic escalation
- **Multi-project support** -- run against multiple repositories from one scaffold install
- **`scaffold init`** -- interactive project setup with language/framework auto-detection

## Architecture

### Pipeline

```
START --> onboarding --> product_owner --> architect --> [designer] --> developer --> reviewer --> qa --> END
```

Conditional routing controls the flow:

- **Intake router** -- onboarding routes epics to product_owner, features to architect, tasks to developer
- **Architect router** -- skips designer when there is no UI component
- **Review loop** -- reviewer sends rejected work back to developer (up to 3 cycles, then escalates)
- **Bug loop** -- QA sends failing work back to developer (up to 3 cycles, then escalates)
- **Human gate** -- any agent can escalate; humans respond with Approve, Revise, Override, or Cancel
- **Consensus node** -- resolves multi-agent disagreements before human escalation

### Two-Tier Agents

| Tier | Agents | Execution | Role |
|------|--------|-----------|------|
| Workflow | product_owner, architect, designer, reviewer, qa, consensus | Anthropic API | Own pipeline phases, produce plans and assessments |
| Specialist | python-expert, go-expert, react-expert, typescript-expert, postgres-expert, documentation-writer, security-auditor | CLI in worktrees (impl) or API (advisory) | Own implementation domains, write and test code |

### Context Assembly

At runtime, each agent is primed by combining:

1. Scaffold expertise -- `agent.md` + `knowledge-base/` files from `orchestrator/agents/`
2. Target repo context -- the project's `CLAUDE.md`
3. Project-specific overrides -- `.claude/agents/<name>.md` in the target repo

The `AgentLoader` handles this assembly.

## Quick Start

### Prerequisites

- Python 3.12+
- Make
- `claude` CLI
- Git

### Install

```sh
git clone <repo-url> && cd scaffold
make install
```

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | API access for workflow agents |
| `TELEGRAM_BOT_TOKEN` | No | Human-in-the-loop via Telegram |
| `TELEGRAM_CHAT_ID` | No | Telegram chat for notifications |

### Initialize a Target Repo

```sh
scaffold init /path/to/your/repo
```

This auto-detects the project's languages and frameworks, walks you through an interactive setup, and creates a project config under `config/projects/`.

### Run Preflight

```sh
scaffold preflight --config config/
```

### Run Scaffold

```sh
scaffold run --spec spec.md --config config/ --project myapp
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `scaffold run` | Start a new run from a spec |
| `scaffold resume` | Resume an interrupted run |
| `scaffold decide` | Provide a human decision for a paused task |
| `scaffold init` | Initialize a target repo with auto-detection |
| `scaffold preflight` | Validate prerequisites and environment |
| `scaffold report` | Show metrics (costs, cycles, agent efficiency) |
| `scaffold events` | Show event log for a specific task |
| `scaffold pause` | Pause execution |

Run any command with `--help` for full option details.

## Configuration

Three YAML files control scaffold behavior:

| File | Purpose |
|------|---------|
| `config/governance.yaml` | RAPID/RACI decision framework -- who recommends, agrees, performs, inputs, and decides for each domain |
| `config/agents.yaml` | Agent models, execution modes (API or CLI), iteration limits, and completion promises |
| `config/projects/{name}.yaml` | Per-project repo path, branch prefix, concurrency limits, and database path |

Credentials are never stored in config files -- use environment variables.

## Project Structure

```
orchestrator/               Main package
  agents/                   Agent prompts and knowledge bases
    workflow/               Pipeline-phase agents (product_owner, architect, ...)
    specialists/            Domain implementation agents (python-expert, ...)
  nodes/                    Graph node implementations (one per pipeline phase)
  agent_loader.py           Prompt assembly from agent.md + knowledge bases
  graph.py                  LangGraph StateGraph wiring and routing
  state.py                  TaskState TypedDict shared across all nodes
  config.py                 YAML config loading
  router.py                 RAPID/RACI governance routing
  self_heal.py              Stuck-loop and failure detection
  task_tree.py              Task CRUD with status transitions
  telegram.py               Telegram Bot API integration
  telemetry.py              Event logging and agent run tracking
  db.py                     SQLite connection management
  preflight.py              Environment validation
  init.py                   Project initialization and detection
config/                     YAML configuration files
db/                         SQLite schema (schema.sql)
tests/                      pytest test suite (one file per module)
```

## Development

```sh
make install      # Create venv, install deps, set up pre-commit hooks
make check        # lint + typecheck + test
make test         # pytest
make coverage     # pytest with 75% coverage threshold
make lint         # ruff check
make format       # ruff format
make typecheck    # pyright
make clean        # Remove build artifacts
```

### Testing

- All tests in `tests/` -- one test file per source module
- Tests use in-memory SQLite via the `db` fixture in `conftest.py`
- Agent nodes use `unittest.mock` to avoid real API/CLI calls
- Coverage threshold: 75%

### Code Style

- Linter/formatter: [ruff](https://docs.astral.sh/ruff/) (Python 3.12 target, 100-char line length)
- Type checker: [pyright](https://github.com/microsoft/pyright) in standard mode
- Commits: conventional format (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`)

## Documentation

- [CLI Reference](docs/cli.md) -- all commands with options and examples
- [Configuration](docs/configuration.md) -- YAML config file reference
- [Architecture](docs/architecture.md) -- pipeline flow, nodes, state management
- [Agents](docs/agents.md) -- agent tiers, prompt assembly, customization

## License

See [LICENSE](LICENSE) for details.
