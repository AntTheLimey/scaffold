# Agentic Scaffold — Architecture

## Overview

The orchestrator is a LangGraph `StateGraph` with 9 nodes and 5 conditional routers.
Execution is resumable at any node boundary via SQLite checkpointing.

---

## Pipeline Flow

```
START → onboarding → intake_router
                         ├── epic    → product_owner → architect
                         ├── feature → architect
                         └── task    → developer

architect → architect_router
              ├── has_ui → designer → developer
              └── no_ui  → developer

developer → reviewer → reviewer_router
                          ├── approve        → qa
                          ├── revise (< 3)   → developer  (loop)
                          └── revise (>= 3)  → human_gate

qa → qa_router
       ├── pass          → END
       ├── fail (< 3)    → developer  (loop)
       └── fail (>= 3)   → human_gate

human_gate → human_gate_router
               ├── Revise → developer
               └── other  → END

consensus → human_gate  (always)
```

---

## Node Descriptions

### onboarding

First node in every run. Scans the target repo to detect project context:

- **Languages** — Python, Go, TypeScript, JavaScript
- **Frameworks** — FastAPI, Django, Flask, React, Vue, Angular, and others
- **Test framework** — pytest, vitest, jest, go test
- **Database presence** — deps in `pyproject.toml`, `go.mod`, `package.json`, `.sql` files
- **CLAUDE.md quality** — missing / thin (<50 lines) / substantive (≥50 lines)

From this it builds the specialist roster: language-matched implementation specialists, plus advisory specialists (`postgres-expert` if a database is detected, `security-auditor` if auth or security paths are found).

### product_owner

Decomposes epic-level specs into features and tasks. Reads the master spec file and produces a JSON array of child tasks, each with a title, level, spec reference, and acceptance criteria.

### architect

Designs the technical approach for a feature. Produces a technical design document, detects whether any UI components are involved, and decomposes the feature into implementation tasks. Routes to `designer` when a UI component is detected.

### designer

Produces UI/UX specifications for features that have a UI component. Does not write code — outputs layout specs, interaction patterns, responsive behaviour, and component specifications.

### developer

The specialist dispatcher and the most complex node:

1. Extracts file paths from the technical design.
2. Detects which implementation specialist matches those file types (e.g. `.py` → `python-expert`, `.tsx` → `react-expert`).
3. Dispatches advisory specialists (`postgres-expert`, `security-auditor`) for recommendations.
4. Assembles the specialist prompt via `AgentLoader`.
5. Creates a git worktree for isolated work.
6. Runs the `ralph_loop` (iterative implementation with completion detection).
7. Cleans up the worktree.
8. Returns `in_review` on success or `stuck` on failure.

### reviewer

Reviews the implementation on the worktree branch. Extracts a verdict (`approve` or `revise`) and any feedback. Routes back to `developer` on revise; escalates to `human_gate` after 3 cycles.

### qa

Runs and validates tests on the implementation branch using the `ralph_loop` with a completion-promise search. Routes back to `developer` on failure; escalates to `human_gate` after 3 cycles.

### consensus

Two-round structured debate for deadlocked decisions. Both parties state positions, then respond to each other. If either concedes the issue resolves; if both refuse after two rounds the node escalates to `human_gate`.

### human_gate

Escalation handler. Sends a Telegram notification (if configured), then calls LangGraph `interrupt()` to pause execution. Resumes when a human provides a decision via `scaffold decide` or a Telegram callback.

---

## Agent Architecture

### Two Tiers

**Workflow agents** own pipeline phases. They use the API directly (`AdvisorAgent` class), never write code, and carry methodology knowledge bases.

**Specialist agents** own implementation domains. Two subtypes:

- **Implementation specialists** — spawned via the `claude` CLI inside git worktrees (`DoerAgent` class).
- **Advisory specialists** — provide recommendations via API without writing code (`AdvisorAgent` class).

### Agent Prompt Assembly (AgentLoader)

Agents are primed at runtime by layering context in order:

| Layer | Source |
|-------|--------|
| 1. Base prompt | `agents/{workflow\|specialists}/{name}/agent.md` |
| 2. Knowledge bases | `agents/{...}/{name}/knowledge-base/*.md` (keyword-matched for specialists) |
| 3. Project context | Target repo's `CLAUDE.md` |
| 4. Overrides | Target repo's `.claude/agents/{name}.md` |
| 5. Advisory input | Recommendations from advisory specialists (developer node only) |
| 6. Task context | Technical design, task description |

### DoerAgent and the Ralph Loop

The `ralph_loop` is the iterative execution model for CLI-based agents:

1. Invoke the `claude` CLI with the assembled prompt in the worktree directory.
2. Check output for a `completion_promise` string (e.g. `TASK COMPLETE`).
3. If found → success.
4. If not found and iterations remain → append previous output with a retry instruction and loop.
5. If `max_iterations` exceeded → return failure (`stuck`).

Each iteration has a 600-second timeout.

### Git Worktree Isolation

The `developer` node creates a git worktree for each task:

- **Branch** — `{branch_prefix}/{task_id}`
- **Location** — `.worktrees/{branch_prefix}-{task_id}`
- Reuses an existing worktree/branch if one is present.
- Cleaned up after `ralph_loop` completes, whether success or failure.

---

## State Management

### TaskState (LangGraph TypedDict)

Shared state passed across all nodes. Key fields:

| Field | Purpose |
|-------|---------|
| `task_id`, `level`, `status` | Task identity and lifecycle |
| `verdict`, `feedback` | Reviewer / QA output |
| `agent_output` | Technical design or implementation output |
| `specialists`, `advisory` | Agent rosters built by onboarding |
| `project_context`, `detected_languages`, `test_framework` | Repo context |
| `review_cycles`, `bug_cycles` | Loop counters |
| `escalation_reason`, `has_ui_component` | Routing flags |
| `child_tasks` | Subtasks produced by product_owner or architect |

### Checkpointing

Uses LangGraph's `SqliteSaver`. Checkpoints are stored in `{db_stem}_checkpoints.db`. This enables `scaffold resume` to recover from any interruption at node granularity.

---

## Database

SQLite with WAL mode and foreign keys enforced. Four tables plus one event log:

| Table | Purpose |
|-------|---------|
| `tasks` | Hierarchical task tree (epic → feature → task → subtask) |
| `task_edges` | Dependency graph (blocking relationships) |
| `decisions` | RAPID governance records |
| `agent_runs` | Per-agent execution records (tokens, iterations, outcome) |
| `events` | Detailed event log for debugging |

Three materialized views: `epic_costs`, `cycle_hotspots`, `agent_efficiency`.

---

## Self-Healing

The `SelfHealer` monitors for two conditions:

- **Stuck loops** — tasks exceeding `max_review_cycles` or `max_bug_cycles` are escalated to `human_gate`.
- **Cascading failures** — three or more stuck tasks within an epic causes the epic to be paused.

---

## Governance

Governance rules are defined in `governance.yaml` using RAPID and RACI frameworks:

- **RAPID** — decision routing: who recommends, agrees, and decides.
- **RACI** — activity responsibility: responsible, accountable, consulted, informed.
- **Consensus** — deadlock resolution via the structured two-round debate node.
- **Human gate** — final escalation for issues unresolved by consensus.
