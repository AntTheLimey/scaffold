# Review Methodology Reference

## Review Order

Process the diff in a consistent order to avoid missing issues:

1. **Security scan**: Check for OWASP Top 10 vulnerabilities first. Security
   issues are always the highest priority and can make all other feedback moot.

2. **Acceptance criteria check**: For each acceptance criterion in the task,
   verify the diff contains code that satisfies it. Mark each criterion as
   met, unmet, or partially met.

3. **Correctness review**: Read the logic. Check for:
   - Off-by-one errors in loops and ranges.
   - Null/None handling — is every nullable value checked before use?
   - Error handling — are errors caught, logged, and handled appropriately?
   - Edge cases — empty inputs, maximum values, concurrent access.
   - Resource management — are files, connections, and handles closed?

4. **Performance review**: Look for:
   - N+1 queries (loop that makes a database call per iteration).
   - Unbounded collections (loading all records without pagination).
   - Missing indexes on queried fields.
   - Unnecessary computation in hot paths.

5. **Style and convention review**: Only flag deviations that the project's
   linter does not catch. If the linter allows it, so should the reviewer.
   Do not enforce personal preferences.

## Severity Levels

### CRITICAL
Immediate security risk or data loss potential. Examples: SQL injection,
authentication bypass, unencrypted PII storage, data deletion without
confirmation. Always triggers "revise" verdict.

### HIGH
Correctness bug that will cause failures in production. Examples: null pointer
on a common code path, wrong return type, missing error handling for expected
error conditions. Always triggers "revise" verdict.

### MEDIUM
Performance issue or maintainability concern that will cause problems over time.
Examples: N+1 query, overly complex function, missing logging for error paths.
Triggers "revise" only if the performance impact is measurable or the
maintainability issue is in a frequently modified area.

### LOW
Style or convention issue not caught by the linter. Examples: inconsistent
naming in new code, missing documentation for a public API, unnecessary
intermediate variable. Does NOT trigger "revise" on its own. Mention as
informational feedback in an otherwise approved review.

## Writing Actionable Feedback

### Good Feedback Pattern

```
[SEVERITY] file/path.ext:LINE — What is wrong.
Fix: Specific instruction.
```

Example:
```
[HIGH] src/services/payment.py:67 — Amount is calculated as a floating-point
number. Currency arithmetic with floats causes rounding errors.
Fix: Use decimal.Decimal for all monetary calculations, or represent amounts
as integer cents.
```

### Bad Feedback Patterns

- "This could be improved." (How? What is wrong?)
- "Consider using a different approach." (Which approach? Why?)
- "Needs refactoring." (What specifically? The developer cannot act on this.)
- "Not sure about this." (Either identify the issue or do not mention it.)

Every piece of feedback must answer: What is the problem? Where is it?
What should the developer do instead?

## When to Approve Despite Imperfections

Approve when:
- All acceptance criteria are met.
- No CRITICAL or HIGH severity issues exist.
- MEDIUM issues are documented as follow-up tasks, not blockers.
- The code follows existing project patterns, even if those patterns are not
  ideal.
- The code is correct and secure, even if you would structure it differently.

Do NOT approve when:
- Any acceptance criterion is unmet.
- Any security vulnerability exists.
- Any correctness bug exists on a code path that will execute in production.
- The code introduces a pattern that conflicts with established project
  conventions without explicit architectural approval.

## Review Anti-Patterns

- **Nitpick-driven review**: Spending most feedback on style while missing
  correctness issues. Run through the severity hierarchy top-down.
- **Approval fatigue**: Approving to unblock the pipeline after too many
  review cycles. If the code is not ready, it is not ready. Escalate instead.
- **Scope expansion**: Requesting changes to code outside the task's diff.
  Those are separate tasks, not review feedback.
- **Architecture in review**: Requesting fundamental design changes during
  code review. Architecture decisions happen before development, not during
  review. If the architecture is wrong, escalate to the Architect.
- **Reviewer as gatekeeper**: Using review power to enforce personal
  preferences. The reviewer checks against objective criteria (security,
  correctness, acceptance criteria), not subjective taste.

## Handling Repeated Revisions

After 2 revision cycles on the same issue:
1. Re-read the original feedback. Was it specific enough?
2. If the developer is misunderstanding the feedback, rephrase with a concrete
   example of the expected change.
3. If the developer disagrees with the feedback, this is a technical dispute.
   Escalate to the consensus node rather than continuing the cycle.
4. After 3 cycles, set escalation_reason to "review_cycle_exceeded." The
   developer and reviewer may have incompatible assumptions that need
   human resolution.
