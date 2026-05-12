# Configuration Reference

Scaffold is configured through a directory of YAML files passed via the `--config` flag. All configuration is explicit — no secrets are stored in config files; use environment variables instead.

---

## Config Directory Structure

```
config/
  governance.yaml         # Decision framework (RAPID + RACI)
  agents.yaml             # Agent definitions (workflow, specialists, escalation)
  projects/
    webapp.yaml           # Per-project config (multi-project setup)
    api.yaml              # Per-project config (multi-project setup)
  project.yaml            # Legacy single-project config (backward compat)
```

Pass the directory to any scaffold command with `--config config/`. For multi-project setups, also pass `--project {name}` to select the correct project file.

---

## governance.yaml

Defines the decision framework used by the router to assign work and resolve disagreements. Contains two top-level sections: `rapid` and `raci`.

### RAPID Framework

Maps each decision type to the roles involved. RAPID is an acronym:

| Role key | Meaning |
|----------|---------|
| `recommend` | Proposes a course of action |
| `agree` | Must consent before the decision is executed |
| `perform` | Carries out the decision |
| `input` | Consulted but does not block the decision |
| `decide` | Makes the final call |

When `decide` is `human`, the orchestrator escalates rather than proceeding autonomously.

**Decision types:**

| Key | What it governs |
|-----|----------------|
| `product_scope` | Feature boundaries and requirements |
| `architecture` | System design and technical approach |
| `ui_ux` | Interface and user experience choices |
| `data_model` | Schema and data structure decisions |
| `priority` | Task ordering and resource allocation |

**Example:**

```yaml
rapid:
  product_scope:
    recommend: product_owner
    agree: architect
    perform: developer
    input: [designer, qa]
    decide: human
  architecture:
    recommend: architect
    agree: reviewer
    perform: developer
    input: [designer]
    decide: architect
  ui_ux:
    recommend: designer
    agree: product_owner
    perform: developer
    input: [architect]
    decide: designer
  data_model:
    recommend: architect
    agree: product_owner
    perform: developer
    input: [qa]
    decide: architect
  priority:
    recommend: product_owner
    agree: architect
    perform: orchestrator
    decide: product_owner
```

### RACI Framework

Maps each activity to responsibility assignments. RACI is an acronym:

| Role key | Meaning |
|----------|---------|
| `responsible` | Does the work |
| `accountable` | Owns the outcome; signs off on completion |
| `consulted` | Provides expertise; two-way communication |
| `informed` | Notified of outcome; one-way communication |

**Activities:**

| Key | What it covers |
|-----|---------------|
| `write_code` | Implementation of features |
| `code_review` | Review of submitted changes |
| `write_tests` | Test authoring and coverage |
| `merge` | Merging completed work into the target branch |
| `bug_fix` | Diagnosis and repair of failures |

**Example:**

```yaml
raci:
  write_code:
    responsible: developer
    accountable: reviewer
    consulted: [architect]
    informed: [product_owner, qa]
  code_review:
    responsible: reviewer
    accountable: architect
    consulted: [developer]
    informed: [product_owner]
  write_tests:
    responsible: qa
    accountable: reviewer
    consulted: [developer]
    informed: [product_owner]
  merge:
    responsible: orchestrator
    accountable: reviewer
    consulted: [developer]
    informed: [product_owner, qa, architect, designer]
  bug_fix:
    responsible: developer
    accountable: qa
    consulted: [reviewer]
    informed: [product_owner]
```

---

## agents.yaml

Defines all agents used by the orchestrator. Three top-level sections: `workflow`, `specialists`, and `escalation`.

### Common Agent Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | string | Yes | Model identifier to use for this agent |
| `execution` | string | Yes | `api` for direct API calls; `cli` for the `claude` CLI in a git worktree |
| `max_iterations` | int | CLI only | Maximum iterations before the loop is considered stuck |
| `completion_promise` | string | CLI only | Exact string the agent must output to signal successful completion |

### workflow

Pipeline-phase agents that own discrete stages of the orchestration graph. Workflow agents do not write code. They produce structured outputs (plans, reviews, decisions) consumed by the next stage.

**Roles:**

| Role | Default Model | Execution | Purpose |
|------|--------------|-----------|---------|
| `product_owner` | claude-opus-4-6 | api | Translates requirements into a structured feature brief |
| `architect` | claude-opus-4-6 | api | Produces technical design and task breakdown |
| `designer` | claude-sonnet-4-6 | api | Defines UI/UX approach; optional stage |
| `reviewer` | claude-sonnet-4-6 | cli | Reviews completed implementation; can reject and send back |
| `qa` | claude-sonnet-4-6 | cli | Runs and verifies tests; can reject and send back |
| `consensus` | claude-opus-4-6 | api | Resolves disagreements between other workflow agents |

**Example:**

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
```

### specialists

Domain implementation agents dispatched by the developer node based on the file types in the task. Two categories:

**Implementation specialists** (`execution: cli`) — spawned in isolated git worktrees and write code directly. They must declare `max_iterations` and `completion_promise`.

**Advisory specialists** (`execution: api`) — provide recommendations via API calls without modifying the repository.

**Available specialists:**

| Name | Default Model | Execution | Purpose |
|------|--------------|-----------|---------|
| `python-expert` | claude-sonnet-4-6 | cli | Python implementation |
| `go-expert` | claude-sonnet-4-6 | cli | Go implementation |
| `react-expert` | claude-sonnet-4-6 | cli | React/JSX implementation |
| `typescript-expert` | claude-sonnet-4-6 | cli | TypeScript implementation |
| `postgres-expert` | claude-opus-4-6 | api | Database schema advisory |
| `documentation-writer` | claude-sonnet-4-6 | cli | Documentation authoring |
| `security-auditor` | claude-opus-4-6 | api | Security review advisory |

**Example:**

```yaml
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
```

### escalation

Thresholds that trigger automatic human escalation via Telegram (or a logged warning if Telegram is not configured).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `stuck_loop_model` | string | — | Model used to analyse a stuck loop before escalating |
| `max_review_cycles` | int | 3 | Number of reviewer rejections before escalating to human |
| `max_bug_cycles` | int | 3 | Number of QA failures before escalating to human |
| `cost_threshold_per_run` | float | — | Maximum USD cost per run; escalates if exceeded |

**Example:**

```yaml
escalation:
  stuck_loop_model: claude-opus-4-6
  max_review_cycles: 3
  max_bug_cycles: 3
  cost_threshold_per_run: 5.00
```

---

## Project Config

Project config specifies the target repository and runtime parameters. It is loaded from one of two locations depending on how the command is invoked.

### Multi-project (recommended): `config/projects/{name}.yaml`

Created by `scaffold init /path/to/repo --config config/ --project {name}`. Selected at runtime with `--project {name}`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `repo_path` | string | (required) | Absolute path to the target repository |
| `branch_prefix` | string | `scaffold` | Prefix applied to all worktree branch names |
| `max_concurrent_agents` | int | `3` | Maximum number of specialist agents running in parallel |
| `db_path` | string | `scaffold_{name}.db` | Path to the SQLite database for this project |

**Example (`config/projects/webapp.yaml`):**

```yaml
repo_path: /Users/you/projects/webapp
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold_webapp.db
```

### Legacy: `config/project.yaml`

Supported for backward compatibility. Used automatically when `--project` is not passed. Contains the same fields as the per-project format.

**Example:**

```yaml
repo_path: /Users/you/projects/myapp
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold.db
```

---

## Environment Variables

Credentials and external service tokens are never stored in config files. Set them in the shell environment before running scaffold.

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | API key used for all agent calls |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot token; required for human escalation notifications |
| `TELEGRAM_CHAT_ID` | No | Telegram chat ID to send escalation messages to |

If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` are absent, escalation events are logged locally but no notification is sent.

---

## Agent Prompt Customization

Target repositories can override or extend any agent's behaviour without modifying scaffold itself. Place Markdown files in `.claude/agents/` inside the target repo:

| File | Effect |
|------|--------|
| `.claude/agents/{specialist-name}.md` | Appended to that specialist's assembled prompt at runtime |
| `.claude/agents/_project.md` | Appended to every agent's prompt; use for project-wide conventions |

`scaffold init` creates `.claude/agents/_project.md` automatically during onboarding. Edit it to capture stack conventions, coding standards, and constraints that every agent should respect.

**Example override path:** `.claude/agents/python-expert.md`

```markdown
# Python conventions for this project

- All modules must have `__all__` defined.
- Use `structlog` for logging, not the stdlib `logging` module.
- Target Python 3.12; do not use 3.11-compatible workarounds.
```
