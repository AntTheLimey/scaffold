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
| AdvisorAgent tool use | 5 | 5 | L (3) | 5.0 | Done | Multi-turn tool loop in AdvisorAgent.call() with three read-only codebase tools (read_file, list_directory, grep). PO, architect, and designer nodes wired with repo-scoped tools. |
| Cost estimation (pre-run) | 2 | 2 | M (2) | 3.0 | Idea | Estimate cost before running (model prices x estimated tokens). Budget controls are done; this adds pre-run estimation only. |
| Structured output for AdvisorAgents | 4 | 3 | M (2) | 5.5 | Idea | Replace JSON-in-text extraction (regex on response.content[0].text) with Anthropic's structured output or tool_use for schema-enforced responses. Eliminates parse failures and retries. |
| Agent memory / cross-run context | 4 | 2 | L (3) | 3.3 | Idea | Persist lessons learned across runs — what patterns worked, what the codebase looks like, what failed last time. Currently every run starts cold. |
| Parallel specialist dispatch | 3 | 2 | L (3) | 2.7 | Idea | Developer node dispatches one specialist at a time. When a task touches multiple domains (Go + React), run specialists in parallel worktrees. |
| Streaming console output | 2 | 1 | M (2) | 2.5 | Idea | DoerAgent subprocess runs are silent for up to 10 minutes. Stream claude CLI output to console in real time for operator visibility. |
| Checkpoint resume UX | 3 | 2 | M (2) | 4.0 | Idea | Current resume requires knowing the thread ID and re-running with the right flags. Add `scaffold resume` that lists interrupted runs and lets you pick one. |
| Human gate improvements | 3 | 2 | M (2) | 4.0 | Idea | Human gate currently escalates via Telegram. Add interactive terminal mode, approval timeouts, and context summaries so the operator can make informed decisions. |
| Web dashboard + control plane | 5 | 4 | XL (4) | 3.5 | Idea | Web-based UI (lightweight Python web server) to monitor runs in real time, view agent events/tool calls/costs, inspect task trees, manage human gate approvals, and trigger/resume runs. Replaces CLI as the primary operator interface. |
| Run isolation + stale cleanup | 3 | 3 | M (2) | 4.5 | Partial | `scaffold clean` command added for worktree/branch/DB cleanup. Still needed: `run_id` concept to tag tasks/events per run and scope budget checks to the active run. |
| API cost tracking (Opus/advisor) | 4 | 4 | M (2) | 6.0 | Done | Model pricing table + token-to-dollar conversion in api_call_done events. |
| Timeout cost recovery | 4 | 5 | M (2) | 6.5 | Idea | When DoerAgent subprocess times out, the process is killed before emitting the final `result` JSON with `total_cost_usd`. The work was billed but the scaffold records $0. Parse incremental costs from streamed assistant events during the run, not just the final summary. Trial run 2 had 8 iterations at $0.00 that were actually billed. |
| Per-iteration budget cap for CLI specialists | 4 | 4 | S (1) | 12.0 | Idea | Pass `--max-budget-usd` to each `claude -p` invocation to cap individual iterations. Trial run 2 saw single Sonnet iterations costing $4 on greenfield bootstrap. A $2/iteration cap would force the specialist to commit incremental progress rather than trying to build everything in one shot. |
| Specialist selection by task domain | 5 | 4 | M (2) | 7.0 | Idea | Developer node picks specialist by file-extension matching, which fails on greenfield repos (no files yet) and domain-mismatch tasks (SQL schema routed to react-expert). The architect should declare which specialist to use in its output, or the specialist should be inferred from the task's domain keywords (schema/migration → go-expert or postgres-expert, not react-expert). Trial run 2: FitD schema task dispatched to react-expert, which built a Python scaffold copy instead of SQL. |
| End-to-end integration test | 4 | 3 | L (3) | 3.7 | Idea | Run the full pipeline against a trivial test repo with mocked API/CLI responses. Current tests are unit-level only — no test covers the full graph traversal. |

## Completed

| Item | PR | Notes |
|------|----|-------|
| Observability: tool call logging + wallclock time | #3 | DoerAgent stream-json parsing, tool.call events, wallclock in report, tool_usage view |
| Budget controls | #4 | Per-specialist --max-budget-usd, scaffold-level cumulative cost check, BudgetExceededError abort |
| API cost tracking (Opus/advisor) | #5 | Model pricing table, token-to-dollar conversion in api_call_done events |
| AdvisorAgent tool use | #5 | Multi-turn tool loop with read_file, list_directory, grep. PO/architect/designer read the codebase before deciding. |
| Trial run 1 fixes | main | Reviewer worktree, developer git commit, language-aware specialist fallback, depends_on ordering, scaffold clean command |

## Notes

- **Trial run 2 results (2026-05-31):** PO decomposed into 6 features.
  Feature 1 (DB schema) produced 2,052 lines of real SQL — the first
  successful code output. Feature 2 (FitD reconciliation) built the wrong
  thing (Python scaffold copy instead of SQL) due to specialist mismatch.
  Features 3-6 hit API rate limit. Total tracked spend: $15.28, actual
  likely $20-25. Fixes that worked: reviewer worktree, developer commit,
  language detection. Next priorities: specialist selection by task domain,
  per-iteration budget cap, timeout cost recovery.
