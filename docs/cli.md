# Scaffold CLI Reference

## Entry Point

```
scaffold <command> [options]
```

Installed via `pip install -e .`. Entry point: `orchestrator.__main__:main`.

---

## Commands

- [run](#run) — Start a new run from a master spec
- [resume](#resume) — Resume an interrupted run
- [decide](#decide) — Provide a human decision for an escalated task
- [init](#init) — Initialize a target repo for scaffold
- [preflight](#preflight) — Validate prerequisites
- [report](#report) — Show metrics and status
- [events](#events) — Show the event log for a task
- [pause](#pause) — Pause scaffold work

---

## run

Start a new scaffold run from a master spec.

```
scaffold run --spec <path> --config <path> [--project <name>]
```

### Options

| Option | Required | Type | Description |
|--------|----------|------|-------------|
| `--spec` | Yes | path (must exist) | Path to the master spec file |
| `--config` | Yes | path (must exist) | Path to the scaffold config directory |
| `--project` | No | string | Project name; resolves to `config/projects/{name}.yaml` |

### Behavior

1. Loads config, applying the project override if `--project` is given
2. Runs preflight validation
3. Initializes the SQLite database
4. Creates a LangGraph checkpointer
5. Builds the orchestration graph
6. Creates a root task at epic level
7. Invokes the graph
8. Outputs the task ID and database path

### Example

```
scaffold run --spec specs/my-app.md --config config/ --project webapp
```

---

## resume

Resume an interrupted run from a saved checkpoint.

```
scaffold resume --task <id> --config <path> [--db <path>] [--spec <path>] [--project <name>]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--task` | Yes | — | Task ID to resume |
| `--config` | Yes | — | Path to the scaffold config directory |
| `--db` | No | `scaffold.db` | Path to the database file |
| `--spec` | No | — | Spec path, required only when re-entering planning |
| `--project` | No | — | Project name; resolves to `config/projects/{name}.yaml` |

### Example

```
scaffold resume --task abc123 --config config/ --project webapp
```

---

## decide

Provide a human decision for a task that has been escalated for review.

```
scaffold decide --task <id> --choice <value> --config <path> [--db <path>] [--spec <path>] [--project <name>]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--task` | Yes | — | Task ID awaiting a decision |
| `--choice` | Yes | — | Decision value (see below) |
| `--config` | Yes | — | Path to the scaffold config directory |
| `--db` | No | `scaffold.db` | Path to the database file |
| `--spec` | No | — | Spec path, required only when re-entering planning |
| `--project` | No | — | Project name; resolves to `config/projects/{name}.yaml` |

### Choice Values

| Value | Meaning |
|-------|---------|
| `Approve` | Accept the task output and continue |
| `Revise` | Send the task back for revision |
| `Override` | Force-accept the output regardless of validation |
| `Cancel` | Cancel the task |

### Example

```
scaffold decide --task abc123 --choice Approve --config config/
```

---

## init

Initialize a target repository for use with scaffold. Performs automatic detection, runs a short interactive interview, and writes the necessary config files.

```
scaffold init <repo_path> [--config <path>]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `repo_path` | Yes (positional, must exist) | Path to the target repository |

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--config` | No | `config/` | Scaffold config directory |

### Behavior

1. Detects languages, frameworks, test setup, database usage, Makefile presence, and existing `CLAUDE.md`
2. Displays a detection summary
3. Runs an interactive interview with three questions:
   - Project description
   - Coding conventions
   - Off-limits areas
4. If `CLAUDE.md` already exists and is substantive (50 or more lines), prompts to overwrite, augment, or skip
5. Generates `CLAUDE.md` in the target repository
6. Creates `config/projects/{name}.yaml`
7. Creates `.claude/agents/_project.md` if conventions or off-limits were provided

### Example

```
scaffold init /path/to/my-repo --config config/
```

### Output Example

```
Detected:
  Languages ............. Python, TypeScript
  Frameworks ............ FastAPI, React
  Test framework ........ pytest
  Database .............. yes
  Makefile .............. yes
  CLAUDE.md ............. missing

Created:
  /path/to/my-repo/CLAUDE.md (47 lines)
  config/projects/my-repo.yaml
```

---

## preflight

Validate that all prerequisites for running scaffold are in place.

```
scaffold preflight --config <path>
```

### Options

| Option | Required | Description |
|--------|----------|-------------|
| `--config` | Yes | Path to the scaffold config directory |

### Checks

| Check | Required | Notes |
|-------|----------|-------|
| `ANTHROPIC_API_KEY` env var | Yes | Run will not proceed without it |
| `claude` CLI installed | Yes | Must be available on `$PATH` |
| Git identity configured | Yes | `user.name` and `user.email` must be set |
| Target repo exists with `.git` | Yes | Repo must be a valid Git repository |
| Telegram configured | No | SKIP result is acceptable |

### Example

```
scaffold preflight --config config/
```

---

## report

Show run metrics and status information from the database.

```
scaffold report [--db <path>] [--costs] [--cycles] [--agents]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--db` | No | `scaffold.db` | Path to the database file |
| `--costs` | No | — | Show cost breakdown by epic (tokens, run count) |
| `--cycles` | No | — | Show cycle hotspots (tasks with excessive revisions) |
| `--agents` | No | — | Show agent efficiency (success rate, average iterations) |

When called with no flags, outputs the overall task completion count.

### Examples

```
scaffold report --db scaffold_webapp.db --costs
scaffold report --agents
```

---

## events

Show the event log for a specific task.

```
scaffold events --task <id> [--db <path>]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--task` | Yes | — | Task ID to inspect |
| `--db` | No | `scaffold.db` | Path to the database file |

### Output Format

```
[timestamp] event_type: event_data
```

### Example

```
scaffold events --task abc123 --db scaffold_webapp.db
```

---

## pause

Pause scaffold work. The run can be resumed later with `scaffold resume`.

```
scaffold pause [--db <path>]
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--db` | No | `scaffold.db` | Path to the database file |

### Example

```
scaffold pause --db scaffold_webapp.db
```

---

## Multi-Project Usage

When managing multiple projects from a single config directory, pass `--project` to `run`, `resume`, and `decide`. Each project gets its own YAML file under `config/projects/`.

```
scaffold init /path/to/webapp --config config/
scaffold init /path/to/api --config config/

scaffold run --spec specs/webapp.md --config config/ --project webapp
scaffold run --spec specs/api.md --config config/ --project api

scaffold resume --task abc123 --config config/ --project webapp
scaffold decide --task def456 --choice Revise --config config/ --project api
```
