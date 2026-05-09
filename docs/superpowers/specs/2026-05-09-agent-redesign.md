# Agent Prompt & Tooling Redesign

## Goal

Replace the scaffold's bare-bones agent prompts with a two-tier agent architecture — workflow agents and domain specialists — each with thorough priming, knowledge bases, and runtime context assembly. Add an onboarding phase that prepares target repos for agent consumption. Convert the developer node from a generalist into a specialist dispatcher.

## Context

The scaffold is a project-agnostic LangGraph orchestrator. Its agents currently operate on 20-line generic prompts with no examples, no failure recovery, no knowledge bases, and hardcoded Inkwell-specific content. Reference projects (gm-apprentice, ai-dba-workbench, pgedge-postgres-mcp, pgedge-skills) demonstrate that effective agents need: rich role definitions, domain knowledge bases, project context from the target repo, and layered prompt assembly at runtime.

## Architecture

### Agent Taxonomy

All agents share the same structure: an `agent.md` prompt file plus a `knowledge-base/` directory. They are divided into two categories by role, not by structure.

**Workflow agents** own phases of the orchestration pipeline. They use the Anthropic API (AdvisorAgent). They carry methodology knowledge bases — frameworks and techniques for their discipline. They do not write code.

**Specialist agents** own implementation domains. They are spawned via `claude` CLI in git worktrees (DoerAgent). They carry technical knowledge bases — language patterns, tooling, and conventions. Some specialists are advisory-only (they research and recommend but do not write code directly).

### Context Ownership

The scaffold owns all agents and their expertise. This is a reusable workforce — adding a specialist to the scaffold makes it available for every project.

The target repo owns its own context: CLAUDE.md (architecture, commands, conventions), and optionally `.claude/agents/<name>.md` files with project-specific overrides for individual specialists.

At runtime, agents are primed by combining scaffold expertise with target repo context.

## Directory Structure

```
orchestrator/
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
        agent.md                    # Advisory role
        knowledge-base/
          schema-conventions.md
          query-patterns.md
          connection-pooling.md
      documentation-writer/
        agent.md
        knowledge-base/
          style-guide.md
      security-auditor/
        agent.md                    # Advisory role
        knowledge-base/
          owasp-checklist.md
          auth-patterns.md
  agent_loader.py                   # Reads agent.md + knowledge bases, assembles prompts
  nodes/
    onboarding.py                   # New node: detect, assess, interview, generate, configure
    developer.py                    # Modified: specialist dispatcher
    base.py                        # Modified: prompt assembly methods
    ...
```

The old `prompts/` directory is removed.

## Agent Prompt Format

Every agent.md file — workflow and specialist alike — uses this section structure:

```markdown
# {Agent Name}

## Responsibilities
What this agent does. Specific deliverables and scope boundaries.

## Constraints
What this agent must NOT do. Role boundaries and forbidden actions.

## Shared References
Where this agent finds context at runtime. Project-agnostic pointers:
the task spec, the target repo's CLAUDE.md, upstream agent output.

## Standards
Quality bars this agent enforces. Measurable criteria, not aspirations.

## Environment Detection
(Where applicable — agents that interact with the filesystem)
What to check before acting. Read CLAUDE.md, detect test framework,
check for Makefile, read existing code patterns.

## Escalation Triggers
Specific conditions that cause this agent to route to human_gate
rather than proceeding. Named conditions, not vague "when in doubt."

## Output Format
The exact JSON schema or output structure downstream nodes expect.

## Examples
Few-shot examples of good output AND bad output, with explanations
of why the bad output fails. Minimum two examples per agent.

## Failure Recovery
What to do when inputs are missing, garbled, or ambiguous. Specific
actions, not "handle gracefully."
```

### Prompt Depth

Each agent.md should be 80-150 lines. The Examples and Failure Recovery sections are where most agents fall short — these sections must contain concrete, specific content, not generic instructions.

### Knowledge Base Files

Each knowledge base file covers one domain topic in depth: frameworks, patterns, checklists, anti-patterns, decision trees. These are reference material the agent consults, not instructions the agent follows mechanically.

Knowledge base files should be 50-200 lines each. They are loaded selectively at runtime — the agent loader picks relevant files based on the task, not all files every time.

## Onboarding Node

A new node added to the LangGraph graph as the first step in every scaffold run.

### Position in Graph

```
START → onboarding → intake_router → product_owner → architect → ...
```

Runs once per scaffold run. Its output flows through the graph state and is available to every downstream node.

### Behavior

**Step 1 — Detect.** Read the target repo for existing context:
- CLAUDE.md presence and depth
- `.claude/agents/` with project-specific overrides
- Languages and frameworks (pyproject.toml, go.mod, tsconfig.json, package.json)
- Dev tooling (Makefile, CI config, pre-commit)
- Database usage (pgx/psycopg in deps, .sql files, docker-compose with Postgres)
- Test suite presence and framework

**Step 2 — Assess.** Score what was found:
- CLAUDE.md present and substantive (>50 lines with architecture + commands + conventions) → use as-is
- CLAUDE.md present but thin (<50 lines or missing key sections) → augment
- CLAUDE.md missing → generate

**Step 3 — Interview** (if CLAUDE.md needs generating or augmenting). Ask the human via human_gate/Telegram escalation:
- What does this project do? (one sentence)
- Any conventions not captured in existing docs?
- Anything agents should avoid touching?

**Step 4 — Generate.** Write or augment CLAUDE.md with: architecture summary, dev commands (detected from Makefile), testing setup (detected framework and patterns), code style (detected from linter configs). Write project-specific agent overrides to `.claude/agents/` only if the project has unusual conventions.

**Step 5 — Configure.** Based on detected languages and frameworks, set the specialist roster in the graph state. Example output:

```python
{
    "specialists": ["python-expert", "postgres-expert"],
    "advisory": ["security-auditor"],
    "project_context": "contents of CLAUDE.md",
    "detected_languages": ["python"],
    "detected_frameworks": ["fastapi", "sqlalchemy"],
    "has_makefile": True,
    "test_framework": "pytest",
}
```

### What the Onboarding Node Does NOT Do

- Modify the scaffold's own agents or knowledge bases
- Install tools or change the target repo's dependencies
- Make architectural decisions (that's the architect's job)
- Run on resume — only on fresh scaffold runs

## Developer Node as Dispatcher

The developer node transforms from a generalist DoerAgent into a specialist dispatcher.

### Dispatch Flow

**1. Read task context.** Extract the file list from the architect's technical design. Read the specialist roster from the onboarding node's state output.

**2. Match specialists.** Map files to specialists by extension and path:
- `.py` → python-expert
- `.go` → go-expert
- `.tsx`, `.jsx` → react-expert
- `.ts` (non-React) → typescript-expert
- `.sql`, migration paths → attach postgres-expert as advisory
- Documentation files → documentation-writer
- Auth/security paths → attach security-auditor as advisory

If a task spans multiple languages, select the primary specialist (most files) and attach others as advisory.

**3. Dispatch advisory specialists first.** If the task has advisory specialists attached (postgres-expert, security-auditor), dispatch them via the Anthropic API with the task spec and relevant knowledge base files. Collect their recommendations.

**4. Assemble the implementation prompt.** Combine layers in this order:
1. Specialist's `agent.md` (from scaffold)
2. Relevant knowledge base files from the specialist's `knowledge-base/` (selected based on task content, not all files)
3. Target repo's CLAUDE.md (project context)
4. Target repo's `.claude/agents/<specialist>.md` (project-specific overrides, if present)
5. Advisory specialist recommendations (if any)
6. The architect's technical design
7. The task spec with acceptance criteria
8. Review feedback from previous revise cycles (if any)

**5. Spawn the specialist** via `claude` CLI in the worktree with the assembled prompt. The Ralph loop runs as before: check for completion promise, retry with failure context, cap at max iterations.

### What Does NOT Change

- The Ralph loop mechanism
- Worktree management (create, reuse, cleanup)
- Graph edges (developer → reviewer → developer on revise, reviewer → qa on approve)
- The reviewer and QA nodes (they still run via CLI, but now get their own thorough prompts loaded via the agent loader)

## Agent Loader

New module: `orchestrator/agent_loader.py`

Responsibilities:
- Read an agent's `agent.md` from disk and parse it
- Read knowledge base files from the agent's `knowledge-base/` directory
- Select relevant knowledge base files based on task content (keyword matching or explicit file list from the task spec)
- Read project-specific overrides from the target repo's `.claude/agents/` if present
- Assemble a composite prompt string from all layers

Interface:

```python
class AgentLoader:
    def __init__(self, agents_dir: Path):
        """agents_dir is orchestrator/agents/"""

    def load_workflow_agent(self, role: str) -> str:
        """Load a workflow agent's full prompt (agent.md + all knowledge base files).
        Used by AdvisorAgent nodes."""

    def load_specialist(
        self,
        name: str,
        repo_path: Path,
        task_context: str,
        advisory_input: str = "",
    ) -> str:
        """Load a specialist's prompt assembled with project context.
        Used by the developer node dispatcher."""

    def list_specialists(self) -> list[str]:
        """Return available specialist names."""

    def detect_specialist(self, file_paths: list[str]) -> str:
        """Given a list of file paths, return the best-matching specialist name."""
```

The `AdvisorAgent.load_prompt()` method (currently in base.py but unused) is replaced by `AgentLoader.load_workflow_agent()`. The old method is removed.

## Reviewer and QA Nodes

The reviewer and QA nodes also benefit from this redesign. They currently run `claude -p` with inline prompt strings. In the new design:

- The reviewer node uses `AgentLoader.load_workflow_agent("reviewer")` to get the full reviewer prompt (agent.md + security-checklist.md + review-methodology.md)
- The QA node uses `AgentLoader.load_workflow_agent("qa")` to get the full QA prompt (agent.md + test-design.md + acceptance-mapping.md)
- Both get the target repo's CLAUDE.md appended for project context

The graph wiring does not change.

## State Changes

The `TaskState` TypedDict gains fields from the onboarding node:

```python
class TaskState(TypedDict):
    # ... existing fields ...
    specialists: list[str]          # Specialist roster for this project
    advisory: list[str]             # Advisory specialists for this project
    project_context: str            # Target repo CLAUDE.md content
    detected_languages: list[str]   # Languages found in target repo
    test_framework: str             # Detected test framework
```

## Migration

- Delete `prompts/` directory (6 files)
- Create `orchestrator/agents/workflow/` (6 agents, ~18 knowledge base files)
- Create `orchestrator/agents/specialists/` (7 specialists, ~18 knowledge base files)
- Create `orchestrator/agent_loader.py`
- Create `orchestrator/nodes/onboarding.py`
- Modify `orchestrator/nodes/developer.py` (specialist dispatch)
- Modify `orchestrator/nodes/reviewer.py` (load full prompt via AgentLoader)
- Modify `orchestrator/nodes/qa.py` (load full prompt via AgentLoader)
- Modify `orchestrator/nodes/base.py` (remove old `load_prompt`, add prompt assembly support)
- Modify `orchestrator/graph.py` (add onboarding node, update edges)
- Modify `orchestrator/state.py` (add new state fields)
- Update tests for all modified modules
- Update CLAUDE.md to document the new agent architecture

## Setup & Configuration

### Credential Management

The scaffold requires three categories of credentials at runtime:

**Environment variables** (not stored in config files):
- `ANTHROPIC_API_KEY` — used by AdvisorAgent for all API calls
- `TELEGRAM_BOT_TOKEN` — used by TelegramBot for human_gate escalations (optional — if not set, human_gate uses CLI-only interrupt)
- `TELEGRAM_CHAT_ID` — the chat to send escalations to (optional, paired with token)

The `telegram_bot_token` and `telegram_chat_id` fields are removed from `project.yaml`. Credentials never live in config files that could be committed. The `TelegramBot` initialization reads from environment, with the scaffold gracefully degrading to CLI-only interrupt if Telegram is not configured.

**Claude CLI authentication** (managed by the user outside the scaffold):
- The `claude` CLI must be installed and authenticated before running the scaffold
- The preflight check validates this

**Git identity** (managed by the user's global git config):
- The scaffold does not set git user.name/user.email — it uses whatever is configured globally or in the target repo
- The preflight check validates that git identity is configured

### Updated agents.yaml

The current agents.yaml maps 6 workflow roles to models. The new structure adds a `specialists` section:

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
    execution: api              # Advisory — does not write code
  documentation-writer:
    model: claude-sonnet-4-6
    execution: cli
    max_iterations: 5
    completion_promise: "TASK COMPLETE"
  security-auditor:
    model: claude-opus-4-6
    execution: api              # Advisory — does not write code

escalation:
  stuck_loop_model: claude-opus-4-6
  max_review_cycles: 3
  max_bug_cycles: 3
  cost_threshold_per_run: 5.00
```

Key changes:
- Top-level `roles` key split into `workflow` and `specialists`
- Advisory specialists use `execution: api` — they're called via the Anthropic SDK, not the CLI
- Implementation specialists use `execution: cli` with `max_iterations` and `completion_promise`
- The developer node reads specialist config to determine execution mode and parameters

The `AgentsConfig` dataclass and `load_config` function are updated to parse the new structure.

### Updated project.yaml

```yaml
repo_path: /path/to/target/repo
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold.db
```

Changes:
- `telegram_bot_token` and `telegram_chat_id` removed (moved to env vars)
- `spec_path` removed (passed via `--spec` CLI flag, not baked into config)

### Preflight Check

A new CLI command `scaffold preflight` and a function called automatically at the start of `scaffold run`. Validates everything the scaffold needs before starting work:

```
$ scaffold preflight --config config/

Preflight Check
  ANTHROPIC_API_KEY .............. OK
  Claude CLI installed ........... OK
  Claude CLI authenticated ....... OK
  Git identity configured ........ OK
  Target repo exists ............. OK (/path/to/repo)
  Target repo is git repo ........ OK
  Config files valid ............. OK
  Telegram (optional) ............ SKIP (not configured)

Ready to run.
```

Checks:
1. `ANTHROPIC_API_KEY` is set and non-empty
2. `claude` CLI is on PATH (`which claude`)
3. `claude` CLI is authenticated (`claude --version` or similar non-destructive command)
4. `git config user.name` and `git config user.email` return values
5. `repo_path` from project.yaml exists and is a git repository
6. All three config files (governance.yaml, agents.yaml, project.yaml) parse without error
7. Telegram env vars present (optional — reports SKIP if not configured)

If any required check fails, the preflight reports the failure and exits with a non-zero code. `scaffold run` calls preflight automatically and aborts if it fails.

## Out of Scope

- MCP server integration (the scaffold does not configure MCP servers for sub-agents in this iteration)
- `.claude/settings.json` or hooks management in the target repo
- Skills installation in the target repo
- Knowledge base evolution (agents don't update their own knowledge bases — that's a future feature)
- Agent benchmarking (no A/B testing of prompt effectiveness in this iteration)
