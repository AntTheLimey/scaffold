# Prioritization Frameworks

## MoSCoW Method

Classify every work item into one of four categories:

- **Must have**: Without this, the release has no value. The system does not
  function or is not legally compliant. Typically 60% or fewer of items.
- **Should have**: Important but not vital. The system works without it, but
  users will notice the gap. Typically 20% of items.
- **Could have**: Desirable. Improves experience but can be deferred without
  consequences. Typically 20% of items.
- **Won't have (this time)**: Explicitly out of scope. Documenting these prevents
  scope creep and sets expectations.

Decision rule: If removing the item means the release cannot ship, it is Must.
If it causes user complaints but the system works, it is Should. Everything else
is Could or Won't.

## RICE Scoring

Score each item on four dimensions:

- **Reach**: How many users/transactions does this affect per time period?
  Use concrete numbers, not "many" or "few."
- **Impact**: How much does this change behavior? Score: 3 (massive), 2 (high),
  1 (medium), 0.5 (low), 0.25 (minimal).
- **Confidence**: How sure are you of reach and impact estimates? Score: 100%
  (high — based on data), 80% (medium — based on analogies), 50% (low — gut
  feeling).
- **Effort**: Person-weeks of work. Include testing and review time.

Formula: RICE = (Reach x Impact x Confidence) / Effort

Compare items by RICE score. Items with Confidence below 50% should be
investigated further before committing.

## Impact/Effort Matrix

Plot items on a 2x2 grid:

| | Low Effort | High Effort |
|---|---|---|
| **High Impact** | Quick wins — do first | Major projects — plan carefully |
| **Low Impact** | Fill-ins — do when free | Avoid — deprioritize or cut |

Quick wins go into the current sprint. Major projects need decomposition before
commitment. Fill-ins are backlog items for slack time. Avoid items get moved to
Won't Have.

## Anti-Patterns

- **Priority inversion**: Working on low-impact items because they are easy
  while high-impact items rot in the backlog. Fix: time-box quick wins to 20%
  of capacity.
- **Everything is Must Have**: If more than 60% of items are Must, the
  classification is wrong. Re-evaluate with the question: "If we ship without
  this, does the product still work?"
- **HiPPO effect**: Highest Paid Person's Opinion overrides data. Fix: require
  RICE scores before priority discussions.
- **Sunk cost priority**: Continuing to prioritize items because effort was
  already spent. Fix: evaluate remaining value, not invested effort.
- **Recency bias**: The most recently reported issue gets highest priority. Fix:
  batch prioritization sessions at fixed intervals, not on every new request.
- **Urgency masquerading as importance**: A deadline does not make an item
  important. Separate urgency (time pressure) from importance (value delivered).
  An urgent but unimportant item should still rank below an important one.

## Applying Prioritization in Decomposition

When decomposing a spec into work items, assign priority at the feature level,
not the task level. Tasks inherit their parent feature's priority. This prevents
the common mistake of individual tasks being reprioritized away from their
feature's intent.

Order features within an epic so that the Must Have items form a walking skeleton:
a minimal end-to-end path through the system that works, even if it handles only
the simplest case.
