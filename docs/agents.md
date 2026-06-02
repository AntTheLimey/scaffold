# Agents Reference

This document covers the agent system in the Agentic Scaffold: directory layout, the two tiers of agents, how prompts are assembled at runtime, how specialists are selected, and how to extend or customize the system.

---

## Directory Structure

```
orchestrator/agents/
├── workflow/
│   ├── product_owner/
│   │   ├── agent.md
│   │   └── knowledge-base/
│   │       ├── decomposition.md
│   │       ├── prioritization.md
│   │       └── story-writing.md
│   ├── architect/
│   │   ├── agent.md
│   │   └── knowledge-base/
│   │       ├── component-boundaries.md
│   │       ├── design-patterns.md
│   │       └── interface-design.md
│   ├── designer/
│   │   ├── agent.md
│   │   └── knowledge-base/
│   │       ├── accessibility.md
│   │       ├── edipt.md
│   │       └── responsive-design.md
│   ├── reviewer/
│   │   ├── agent.md
│   │   └── knowledge-base/
│   │       ├── review-methodology.md
│   │       └── security-checklist.md
│   ├── qa/
│   │   ├── agent.md
│   │   └── knowledge-base/
│   │       ├── acceptance-mapping.md
│   │       └── test-design.md
│   └── consensus/
│       ├── agent.md
│       └── knowledge-base/
│           └── structured-debate.md
└── specialists/
    ├── python-expert/
    │   ├── agent.md
    │   └── knowledge-base/
    │       ├── packaging.md
    │       ├── testing-patterns.md
    │       └── type-checking.md
    ├── go-expert/
    │   ├── agent.md
    │   └── knowledge-base/
    │       ├── concurrency.md
    │       ├── error-handling.md
    │       └── testing-patterns.md
    ├── react-expert/
    │   ├── agent.md
    │   └── knowledge-base/
    │       ├── accessibility.md
    │       ├── component-patterns.md
    │       └── testing-patterns.md
    ├── typescript-expert/
    │   ├── agent.md
    │   └── knowledge-base/
    │       ├── strict-mode.md
    │       └── testing-patterns.md
    ├── postgres-expert/
    │   ├── agent.md
    │   └── knowledge-base/
    │       ├── connection-pooling.md
    │       ├── query-patterns.md
    │       └── schema-conventions.md
    ├── documentation-writer/
    │   ├── agent.md
    │   └── knowledge-base/
    │       └── style-guide.md
    └── security-auditor/
        ├── agent.md
        └── knowledge-base/
            ├── auth-patterns.md
            └── owasp-checklist.md
```

---

## Two Agent Tiers

### Workflow Agents

Workflow agents own phases of the orchestration pipeline. They are called via the API (AdvisorAgent class), return structured text or JSON, and never write code. Each carries a knowledge base of methodology files that are always loaded in full.

| Agent | Purpose | Model | Execution |
|-------|---------|-------|-----------|
| product_owner | Decompose epics into features and tasks with acceptance criteria | Opus | API |
| architect | Technical design: data models, API contracts, component boundaries, UI detection | Opus | API |
| designer | UI/UX specification | Sonnet | API |
| reviewer | Code review against acceptance criteria; returns approve/revise verdict | Sonnet | CLI |
| qa | Test validation in a git worktree; returns pass/fail verdict | Sonnet | CLI |
| consensus | Deadlock resolution via structured debate | Opus | API |

The reviewer and qa agents use the CLI execution path (DoerAgent) rather than the API, so they operate inside git worktrees and can inspect code directly.

### Specialist Agents

Specialist agents own implementation domains. They divide into two subtypes based on execution model.

**Implementation specialists** write code via the `claude` CLI in git worktrees (DoerAgent class). They iterate until they emit their completion promise or exhaust their iteration budget.

| Specialist | File Types | Max Iterations | Completion Promise | Timeout | Budget Cap |
|------------|-----------|----------------|--------------------|---------|-----------:|
| python-expert | `.py` | 10 | `TASK COMPLETE` | 1800s | $2.00 |
| go-expert | `.go` | 10 | `TASK COMPLETE` | 1800s | $2.00 |
| react-expert | `.tsx`, `.jsx` | 10 | `TASK COMPLETE` | 1800s | $2.00 |
| typescript-expert | `.ts`, `.js` | 10 | `TASK COMPLETE` | 1800s | $2.00 |
| documentation-writer | `.md` | 5 | `TASK COMPLETE` | — | $2.00 |

**Advisory specialists** provide recommendations via the API (AdvisorAgent class) without writing code. They are dispatched in parallel before the implementation specialist runs, and their output is appended to the specialist's assembled prompt.

| Specialist | Triggered By | Purpose |
|------------|-------------|---------|
| postgres-expert | Database detected in project | Query patterns, schema advice, connection pooling |
| security-auditor | Auth/security paths found in repo | Security review, vulnerability analysis |

---

## Prompt Assembly

The `AgentLoader` (`orchestrator/agent_loader.py`) assembles prompts at runtime by layering context sources. The separator between sections is `\n\n---\n\n`.

### Workflow Agent Assembly

1. `agent.md` — base system prompt
2. All files in `knowledge-base/` — sorted alphabetically, concatenated

Knowledge-base files for workflow agents are always loaded in full; no keyword filtering is applied.

### Specialist Agent Assembly

1. `agent.md` — base system prompt
2. Selected knowledge-base files — filtered by keyword matching against task context (see below)
3. `CLAUDE.md` from the target repo — project documentation and conventions
4. `.claude/agents/{name}.md` from the target repo — project-specific override for this specialist
5. Advisory input — recommendations from any advisory specialists dispatched for this task
6. Task context — task ID and technical design output from the architect

### Knowledge Base Selection

For specialists, knowledge-base files are selected by matching task context words against KB filenames:

- The task context string is split into words (lowercased).
- Each KB filename stem is split on `-` to produce keywords (e.g., `testing-patterns` → `testing`, `patterns`).
- A KB file is included if any of its keywords appear in the task context words.
- If no files match, all KB files are included as a fallback.

Example: a task mentioning "testing" causes `testing-patterns.md` to be included. A task with no recognisable keywords gets the full knowledge base.

---

## Specialist Detection

The developer node (`orchestrator/nodes/developer.py`) selects which implementation specialist to use based on the file types referenced in the architect's output.

### Extension Mapping

| Extension | Specialist |
|-----------|-----------|
| `.py` | python-expert |
| `.go` | go-expert |
| `.tsx` | react-expert |
| `.jsx` | react-expert |
| `.ts` | typescript-expert |
| `.js` | typescript-expert |
| `.sql` | postgres-expert |
| `.md` | documentation-writer |

The mapping is defined in `EXTENSION_TO_SPECIALIST` in `orchestrator/agent_loader.py`. The `detect_specialist` method counts extension occurrences across all file paths in the task output and returns the specialist with the highest count.

### Selection Priority

1. Check architect's explicit specialist recommendation (`architect_specialist` field from architect output).
2. Detect specialist from architect's declared file paths (`architect_file_paths`).
3. Detect specialist from regex-extracted file paths in agent_output.
4. Fall back to first specialist in the onboarding roster.
5. Fall back to language-detected specialist via `LANGUAGE_TO_SPECIALIST` mapping (also defined in `developer.py`).
6. Final fallback: `python-expert`.

Advisory specialists from the onboarding roster are dispatched in parallel before the implementation specialist runs.

---

## Onboarding and Roster Configuration

The onboarding node (`orchestrator/nodes/onboarding.py`) runs at the start of each pipeline execution. It detects the target project and builds two lists stored in state: `specialists` (implementation roster) and `advisory`.

### Language Detection and Specialist Mapping

The onboarding node inspects the target repo for language indicators:

| Indicator | Language Detected |
|-----------|------------------|
| `pyproject.toml`, `setup.py`, or `requirements.txt` | Python |
| `go.mod` | Go |
| `tsconfig.json` | TypeScript |
| `package.json` (no `tsconfig.json`) | JavaScript |

Language is then mapped to a specialist:

| Language | Default Specialist | Override Condition |
|----------|-------------------|--------------------|
| Python | python-expert | — |
| Go | go-expert | — |
| TypeScript | typescript-expert | react-expert if React detected in dependencies |
| JavaScript | typescript-expert | — |

React is detected by scanning `package.json` dependencies for names that match or are prefixed with `react`, `next`, `vue`, `angular`, `svelte`, `nuxt`, or `remix`.

### Advisory Specialist Triggers

| Trigger | Advisory Specialist Added |
|---------|--------------------------|
| Database dependency detected | postgres-expert |
| Security-related paths found | security-auditor |

**Database detection** checks the following sources for keywords (`psycopg`, `psycopg2`, `postgres`, `sqlalchemy`, `pgx`, `pq`, `pg`, `prisma`, `mysql`, `sqlite`):
- `pyproject.toml` or `requirements.txt`
- `go.mod`
- `package.json` dependencies
- Any `.sql` files present in the repo

**Security detection** scans all file and directory names in the repo for the keywords `auth`, `security`, `jwt`, or `oauth`.

### Roster Filtering

`AgentLoader.list_specialists()` returns only specialists that have an `agent.md` file in the agents directory. If a specialist is referenced in `config/agents.yaml` but has no `agent.md`, it is excluded from the roster and cannot be selected.

---

## Execution Models

### AdvisorAgent (API)

Defined in `orchestrator/nodes/base.py`.

- Supports single-call and multi-turn tool-use modes. In tool-use mode, iterates up to 25 turns with read-only codebase tools (`read_file`, `list_directory`, `grep`).
- Returns `AgentResult(text, token_in, token_out, cost_usd)`.
- Supports optional system prompt caching (`cache_control: ephemeral`) for repeated calls with the same system prompt.
- Used by: product_owner, architect, designer, consensus (workflow); postgres-expert, security-auditor (advisory specialists).

### DoerAgent (CLI + Ralph Loop)

Defined in `orchestrator/nodes/base.py`.

- Creates a git worktree for isolation (`git worktree add -b {branch}`). The worktree is placed at `{repo_parent}/.worktrees/{branch-slug}`.
- Runs the `claude` CLI iteratively (`ralph_loop`) up to `max_iterations` times (default: 10).
- Each iteration invokes: `claude --model {model} --output-format stream-json --max-budget-usd {n} -p {prompt}` with a configurable timeout (default 1800s for implementation specialists).
- On iteration 2+, the previous attempt's output is appended to the prompt with a retry instruction.
- Declares success when `completion_promise` appears in stdout.
- Returns `RalphResult(success, iterations, output)`.
- Cleans up the worktree on completion (in a `finally` block).
- Used by: python-expert, go-expert, react-expert, typescript-expert, documentation-writer (implementation specialists); reviewer, qa (workflow agents that run CLI).

The qa agent uses `completion_promise = "TESTS PASSING"` and `max_iterations = 8`, configured in `config/agents.yaml`. All other implementation specialists use `"TASK COMPLETE"` and `max_iterations = 10`.

---

## Customizing Agents

### Adding a New Specialist

1. Create the directory: `orchestrator/agents/specialists/{name}/`
2. Write `agent.md` — the system prompt for this specialist.
3. Optionally add `knowledge-base/` with domain reference files. Name files descriptively; the stem is used for keyword matching (e.g., `error-handling.md` matches tasks mentioning "error" or "handling").
4. Add an entry in `config/agents.yaml` under `specialists`. For a CLI specialist:

   ```yaml
   specialists:
     my-specialist:
       model: claude-sonnet-4-6
       execution: cli
       max_iterations: 10
       completion_promise: "TASK COMPLETE"
   ```

   For an advisory specialist:

   ```yaml
   specialists:
     my-advisor:
       model: claude-opus-4-6
       execution: api
   ```

5. If the specialist should be auto-detected from file extensions, add the mapping to `EXTENSION_TO_SPECIALIST` in `orchestrator/agent_loader.py`.
6. If the specialist should be included in the onboarding roster based on language, update `LANGUAGE_TO_SPECIALIST` in both `orchestrator/nodes/onboarding.py` and `orchestrator/nodes/developer.py`.
7. If it's an advisory specialist with a new trigger condition, add detection logic to `make_onboarding_node` in `orchestrator/nodes/onboarding.py`.

### Project-Specific Overrides

Target repos can customize agent behaviour without modifying the scaffold itself.

**Per-specialist override:** `.claude/agents/{specialist-name}.md` in the target repo.
Appended to that specialist's assembled prompt after the repo's `CLAUDE.md`. Use for project-specific coding standards, naming conventions, or constraints that apply only to one specialist.

**Project-wide context:** `CLAUDE.md` in the root of the target repo.
Read by all specialists during prompt assembly. Created (or updated) by `scaffold init`. Contains conventions, off-limits areas, architecture notes, and anything else that should inform all implementation work.

### Modifying Knowledge Bases

Knowledge-base files contain domain expertise: conventions, patterns, checklists.

- Location: `orchestrator/agents/{tier}/{name}/knowledge-base/`
- Format: Markdown
- Naming: descriptive, hyphenated (e.g., `error-handling.md`, `testing-patterns.md`)
- The filename stem is split on `-` and used as keywords for task-context matching

To add domain knowledge, create a new `.md` file in the appropriate `knowledge-base/` directory. No code changes are needed — the loader picks up all files at runtime.

For workflow agents, all KB files are always loaded. For specialists, files are keyword-matched; broader filenames (e.g., `patterns.md`) will match more tasks than narrow ones (e.g., `react-query-patterns.md`).

---

## Configuration Reference

Agent configuration lives in `config/agents.yaml`. Top-level keys:

| Key | Contents |
|-----|---------|
| `workflow` | One entry per workflow agent with `model` and `execution` |
| `specialists` | One entry per specialist with `model`, `execution`, and optionally `max_iterations`, `completion_promise` |
| `escalation` | Thresholds: `max_review_cycles`, `max_bug_cycles`, `stuck_loop_model` |

Each agent entry:

| Field | Values | Description |
|-------|--------|-------------|
| `model` | model ID string | Model used for this agent |
| `execution` | `api` or `cli` | Determines AdvisorAgent vs DoerAgent |
| `max_iterations` | integer | CLI agents only; max ralph_loop iterations |
| `completion_promise` | string | CLI agents only; substring that signals task completion |
| `timeout` | integer | CLI agents only; seconds before the subprocess is killed (default 600, specialists use 1800) |
| `max_budget_usd` | float | CLI agents only; per-iteration cost cap in USD passed to `--max-budget-usd` |
