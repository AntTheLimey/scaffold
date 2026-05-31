# API Cost Tracking for Workflow & Advisory Agents

## Problem

The scaffold's budget system only tracks costs from CLI-based specialists (DoerAgent). Workflow agents (product_owner, architect, consensus) and advisory specialists (postgres-expert, security-auditor) use the Anthropic API directly via AdvisorAgent — the SDK returns token counts but not dollar amounts. These Opus calls are invisible to the budget system.

In the Inkwell test run, ~$1 of Opus API spend was untracked.

## Requirements

1. **Model pricing table** — A lookup of input/output token prices per model. Must be easy to update when Anthropic changes pricing. Store as a Python dict, not YAML/JSON (it's code-level config that changes rarely).

2. **Token-to-dollar conversion** — After each `api_call_done` event, calculate `cost_usd` from the token counts and model name using the pricing table. Include `cost_usd` in the event data, same pattern as `cli.done` events.

3. **Budget check after API calls** — AdvisorAgent calls should count toward the scaffold-level budget. After each API call in workflow nodes and the developer node's advisory dispatch, check cumulative cost against the budget limit.

4. **cumulative_cost() includes API spend** — The `Telemetry.cumulative_cost()` query must sum costs from both `cli.done` and `api.response` events.

5. **Report includes API costs** — `scaffold report --costs` should show total spend including API calls.

## Architecture

- New module: `orchestrator/pricing.py` — contains the pricing table and a `estimate_cost(model: str, token_in: int, token_out: int) -> float` function.
- Modify: `orchestrator/event_bus.py` — `api_call_done()` accepts or computes `cost_usd`, includes it in event data.
- Modify: `orchestrator/telemetry.py` — `cumulative_cost()` query sums from both event types.
- Modify: `orchestrator/nodes/base.py` — `AdvisorAgent.call()` returns cost_usd in AgentResult.
- Modify: workflow nodes that call AdvisorAgent — emit cost and check budget.
- Modify: `orchestrator/nodes/developer.py` — advisory dispatch checks budget.

## Pricing (as of May 2026)

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------:|----------------------:|
| claude-opus-4-6 | $15.00 | $75.00 |
| claude-sonnet-4-6 | $3.00 | $15.00 |
| claude-haiku-4-5 | $0.80 | $4.00 |

## Constraints

- Must not break existing CLI cost tracking
- Must not require API key or network call to get pricing (hardcoded table)
- Budget checks should use the same `bus.check_budget()` path as DoerAgent
- Tests must not make real API calls
