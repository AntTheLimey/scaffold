# Story Writing Reference

## User Story Format

The standard format:

```
As a [type of user],
I want [action or capability],
so that [benefit or outcome].
```

The "so that" clause is not optional. It forces clarity about why the feature
exists. If you cannot articulate the benefit, the story may not be worth building.

Variations for non-user-facing work:

```
As the [system/service],
when [trigger condition],
then [expected behavior],
so that [operational benefit].
```

## Acceptance Criteria Patterns

### Given/When/Then (Gherkin-style)

```
Given [precondition or initial state],
When [action is taken],
Then [expected outcome].
```

Rules for good acceptance criteria:
- Each criterion tests exactly one behavior.
- The "Then" clause is verifiable by a machine (assert-able).
- No implementation language: "returns an error" not "throws a 422."
- Include the negative case: what should NOT happen.

### Checklist Style

For simpler stories, a checklist works:

```
- [ ] New users can register with email and password
- [ ] Duplicate emails are rejected with a clear message
- [ ] Passwords must be at least 8 characters
```

Each checkbox item must still be independently testable.

## INVEST Criteria

Every story should be:

- **Independent**: Can be built and delivered without waiting for other stories.
  If two stories must be done in sequence, they may be one story.
- **Negotiable**: Details can be discussed. The story is a conversation starter,
  not a contract. The "how" is flexible; the "what" and "why" are fixed.
- **Valuable**: Delivers value to a user or the business. Infrastructure tasks
  are wrapped in the value they enable.
- **Estimable**: The team can estimate effort. If they cannot, the story needs
  splitting or more research (spike).
- **Small**: Completable in a single development session (1-3 files changed,
  1-2 days maximum). If it requires more, split it.
- **Testable**: Acceptance criteria exist and can be automated. If you cannot
  write a test for it, it is not a story — it is a wish.

## Splitting Strategies

When a story is too large (fails the Small criterion), apply these patterns:

### By Workflow Step
Split a multi-step process into one story per step:
- "User enters registration form" (form rendering)
- "User submits registration" (validation and persistence)
- "User receives confirmation email" (async notification)

### By Data Variation
Split by the types of input handled:
- "Process credit card payment"
- "Process bank transfer payment"
- "Process stored credit payment"

### By Business Rule
Split by the rules applied:
- "Calculate shipping for domestic orders"
- "Calculate shipping for international orders"
- "Apply free shipping for orders over threshold"

### By Interface
Split by where the feature appears:
- "Admin views user list in dashboard"
- "API returns user list for integrations"

### By Happy Path vs Edge Case
Build the happy path first:
- "User logs in with correct credentials" (first)
- "User sees error for wrong password" (second)
- "User is locked out after 5 failed attempts" (third)

### Anti-Patterns in Splitting

- **Technical layer splitting**: "Build the API" then "Build the UI" breaks
  vertical slicing. Each story should deliver a thin vertical slice.
- **Arbitrary size splitting**: "Do the first half of the form" is not a
  meaningful split. Split by behavior, not by percentage.
- **Spike as a story**: Research spikes produce knowledge, not shippable
  increments. Track them separately.
