# Structured Debate Reference

## Debate Format

The consensus node facilitates a maximum of 2 rounds of structured debate
between two parties. Each round has two exchanges (one per party), for a
maximum of 4 total exchanges.

### Round Structure

```
Round 1:
  Party A (recommend role): States initial position with evidence
  Party B (agree role): Responds with counterargument or concession

Round 2 (if needed):
  Party A: Rebuts Party B's counterargument with new evidence
  Party B: Responds with final counterargument or concession

If no concession after Round 2: Escalate to human_gate
```

### Position Requirements

Each position statement must include:
- **Claim**: What the party believes should happen.
- **Evidence**: Why this approach is better. Cite specific technical facts,
  existing code patterns, acceptance criteria, or risk assessments.
- **Tradeoff acknowledgment**: What the downsides of this position are.
  Positions that ignore tradeoffs are weaker.

### What Constitutes a Concession

A party concedes when they explicitly state that the other position is
preferable. Concession must include a reason — "I concede" without explanation
is not valid.

Valid concession: "The separate repository approach is better because the
migration risk outweighs the short-term complexity cost."

Invalid concession: "Fine, do it your way." (No reasoning.)

## Argument Evaluation

### Strong Arguments

- **Evidence-based**: References specific code, data, acceptance criteria,
  or documented requirements.
- **Risk-quantified**: States what could go wrong and how likely it is,
  not just "this is risky."
- **Tradeoff-aware**: Acknowledges the cost of the proposed approach.
- **Precedent-aware**: References how similar decisions were made elsewhere
  in the codebase or in the project's conventions.
- **Acceptance-aligned**: Ties back to what the task is trying to achieve.

### Weak Arguments

- **Appeal to authority**: "This is best practice" without explanation of why.
- **Appeal to novelty**: "This is the modern way" without evidence it is better
  for this context.
- **Appeal to tradition**: "We have always done it this way" without evidence
  the old way is still appropriate.
- **Unfalsifiable claims**: "This might cause problems someday" without
  specifying what problems or when.
- **Ad hominem**: Attacking the other agent's role or capability instead of
  the argument.
- **False dichotomy**: Presenting only two options when others exist.

### Evaluation Criteria (in order of weight)

1. **Correctness**: Does the approach produce correct results?
2. **Security**: Does the approach introduce vulnerabilities?
3. **Acceptance criteria alignment**: Which approach better satisfies the
   task's requirements?
4. **Simplicity**: Which approach has fewer moving parts?
5. **Consistency**: Which approach aligns with existing codebase patterns?
6. **Future flexibility**: Which approach is easier to change later?
   (Lowest weight — do not over-index on speculation.)

## Resolution Patterns

### Direct Resolution
One party concedes because the other's argument is clearly stronger. This is
the ideal outcome.

### Synthesis Resolution
Both positions have merit. The resolution combines elements of both. Example:
"Use the simpler approach now, but add the interface that allows migration
to the more sophisticated approach later."

### Scope Resolution
The disagreement is actually about different scopes. Party A is optimizing for
this task; Party B is optimizing for the project long-term. Resolution: follow
Party A for this task, create a follow-up task for Party B's concern.

### Constraint Resolution
New information eliminates one option. Example: a dependency constraint makes
one approach infeasible, resolving the debate by elimination.

## Escalation Criteria

Escalate to human_gate when:

- **Deadlock after 2 rounds**: Neither party concedes. The arguments are
  roughly equal in strength, or the parties are arguing past each other.
  Present both positions and the key point of disagreement.

- **Scope disagreement**: The debate is about what to build, not how to build
  it. Technical agents should not make product scope decisions.

- **Risk disagreement**: The parties disagree about whether a risk is
  acceptable. Risk tolerance is a human judgment call.

- **Value judgment**: The debate requires choosing between competing user
  needs or business priorities.

- **Precedent conflict**: Both parties cite valid but contradictory patterns
  from the existing codebase. The codebase is inconsistent, and only a human
  can set the direction.

### Escalation Format

```
Consensus deadlock after {N} rounds. Escalating to human_gate.

Position A ({role}): {one-paragraph summary of their strongest argument}
Position B ({role}): {one-paragraph summary of their strongest argument}

Key disagreement: {one sentence identifying the core point of contention}
Recommendation: {which position the adjudicator leans toward and why, or
"no recommendation" if arguments are truly equal}
```

## Debate Anti-Patterns

- **Infinite refinement**: Each round makes smaller and smaller distinctions.
  If the difference between positions is trivial, pick either one and move on.
- **Goal-post moving**: A party changes their position each round instead of
  responding to the counterargument. Pin each party to their initial claim.
- **Scope creep**: The debate expands to cover issues beyond the original
  disagreement. Keep the debate focused on the specific decision point.
- **Consensus theater**: Both parties agree quickly without substantive
  exchange. This suggests the debate was unnecessary or the parties are
  not engaging seriously. Flag if the first exchange results in concession
  without any counterargument being made.
