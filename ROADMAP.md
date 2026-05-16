# Agentic Scaffold — Roadmap

Items are force-ranked by score. Higher score = do first.

**Formula:** Score = (Impact x 2 + Urgency) / Effort

| Impact | Meaning |
|:------:|---------|
| 5 | Directly improves agent output quality |
| 4 | Improves orchestration reliability |
| 3 | Improves developer/operator experience |
| 2 | Adds new capability |
| 1 | Nice to have |

| Urgency | Meaning |
|:-------:|---------|
| 5 | Blocks other work |
| 4 | Active need (current development) |
| 3 | Next logical step |
| 2 | Eventually |
| 1 | Whenever |

| Effort | Meaning |
|:------:|---------|
| S (1) | < 1 hour |
| M (2) | 1-4 hours |
| L (3) | 4-12 hours |
| XL (4) | 12+ hours |

---

## The List

| Item | Impact | Urgency | Effort | Score | Status | Notes |
|------|:------:|:-------:|:------:|:-----:|--------|-------|
| AdvisorAgent tool use | 5 | 5 | L (3) | 5.0 | Planned | Workflow agents (architect, reviewer, qa) are blind — they can't read the codebase, query MCP servers, or use any tools. Add a tool execution loop to AdvisorAgent.call() with per-agent tool rosters. Single highest-impact improvement to scaffold output quality. |
| Cost estimation (pre-run) | 2 | 2 | M (2) | 3.0 | Idea | Estimate cost before running (model prices x estimated tokens). Budget controls are done; this adds pre-run estimation only. |
| Structured output for AdvisorAgents | 4 | 3 | M (2) | 5.5 | Idea | Replace JSON-in-text extraction (regex on response.content[0].text) with Anthropic's structured output or tool_use for schema-enforced responses. Eliminates parse failures and retries. |
| Agent memory / cross-run context | 4 | 2 | L (3) | 3.3 | Idea | Persist lessons learned across runs — what patterns worked, what the codebase looks like, what failed last time. Currently every run starts cold. |
| Parallel specialist dispatch | 3 | 2 | L (3) | 2.7 | Idea | Developer node dispatches one specialist at a time. When a task touches multiple domains (Go + React), run specialists in parallel worktrees. |
| Streaming console output | 2 | 1 | M (2) | 2.5 | Idea | DoerAgent subprocess runs are silent for up to 10 minutes. Stream claude CLI output to console in real time for operator visibility. |
| Checkpoint resume UX | 3 | 2 | M (2) | 4.0 | Idea | Current resume requires knowing the thread ID and re-running with the right flags. Add `scaffold resume` that lists interrupted runs and lets you pick one. |
| Human gate improvements | 3 | 2 | M (2) | 4.0 | Idea | Human gate currently escalates via Telegram. Add interactive terminal mode, approval timeouts, and context summaries so the operator can make informed decisions. |
| Web dashboard + control plane | 5 | 4 | XL (4) | 3.5 | Idea | Web-based UI (lightweight Python web server) to monitor runs in real time, view agent events/tool calls/costs, inspect task trees, manage human gate approvals, and trigger/resume runs. Replaces CLI as the primary operator interface. |
| End-to-end integration test | 4 | 3 | L (3) | 3.7 | Idea | Run the full pipeline against a trivial test repo with mocked API/CLI responses. Current tests are unit-level only — no test covers the full graph traversal. |

## Completed

| Item | PR | Notes |
|------|----|-------|
| Observability: tool call logging + wallclock time | #3 | DoerAgent stream-json parsing, tool.call events, wallclock in report, tool_usage view |
| Budget controls | #4 | Per-specialist --max-budget-usd, scaffold-level cumulative cost check, BudgetExceededError abort |

## Notes

- **AdvisorAgent tool use** is the most impactful single change. Workflow
  agents currently make decisions about a codebase they can't see. The
  architect designs without reading the code structure, the reviewer
  evaluates without checking what was written. Do this immediately after
  the observability PR lands.

- **Observability and budget controls are done.** We can now see what
  agents do (tool calls, wallclock time) and cap how much they spend
  (per-specialist and scaffold-wide). Ready for a real test run.
