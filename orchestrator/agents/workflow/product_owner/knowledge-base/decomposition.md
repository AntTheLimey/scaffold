# Decomposition Reference

## Epic / Feature / Task Hierarchy

### Epic
A large body of work that delivers a user-facing capability area. Epics are
too large to implement directly — they exist to organize related features.

Characteristics:
- Spans multiple development sessions (weeks to months).
- Has a theme: "User Authentication," "Search," "Reporting."
- Acceptance criteria describe the capability at a high level.
- Contains 3-8 features. Fewer suggests it is really a feature; more suggests
  it needs sub-epics.

### Feature
A single, demonstrable outcome within an epic. Features are the primary unit
of product planning and delivery.

Characteristics:
- Delivers one observable change to the user experience or system behavior.
- Completable in 1-5 development sessions.
- Has specific, testable acceptance criteria.
- Contains 2-6 tasks. One task suggests it is actually a task, not a feature.
  More than 6 suggests the feature needs splitting.

### Task
An atomic unit of work. Tasks are what developers actually implement.

Characteristics:
- Modifies 1-3 files.
- Completable in a single focused session (2-4 hours).
- Has narrow, precise acceptance criteria (1-3 items).
- The developer does not need to make design decisions — those are in the
  feature spec and architecture design.

## Vertical Slicing

Every slice must cut through all layers of the system needed to deliver
observable value. A vertical slice for a "save user profile" feature touches:

1. UI: the form and submit button
2. API: the endpoint that receives the data
3. Business logic: validation rules
4. Persistence: storing the data

Anti-pattern: Horizontal slicing splits by layer ("build the database schema"
then "build the API" then "build the UI"). This delays value delivery because
no single slice produces working functionality.

Test for vertical slicing: "Can I demo this to a user?" If yes, it is vertical.
If the answer is "they'd need to also have slice X," the slicing is wrong.

## Walking Skeleton

The first set of features in an epic should form a walking skeleton: the
thinnest possible end-to-end implementation that exercises the architecture.

Properties of a walking skeleton:
- It handles only the simplest case (one input type, happy path only).
- It touches every layer and integration point.
- It can be deployed and demonstrated.
- It proves the architecture works before investing in edge cases.

Example: For an "E-commerce Checkout" epic, the walking skeleton is:
"User adds one item to cart and completes purchase with a test payment method."
Not: "Build the payment gateway integration."

## Size Heuristics

### Too Large (needs splitting)
- Acceptance criteria exceed 6 items.
- Description uses "and" to connect unrelated behaviors.
- Estimate exceeds 3 days of development.
- Requires changes to more than 5 files.
- Multiple user roles are involved in the same work item.

### Too Small (consider merging)
- Takes less than 30 minutes to implement.
- Single-line configuration change with no behavioral impact.
- Cannot be meaningfully tested in isolation.
- Would produce a commit message that is longer than the code change.

### Right-Sized
- 1-3 files changed.
- 2-4 acceptance criteria.
- One user role or system actor.
- Can be described in one sentence without "and."
- A developer can hold the entire scope in working memory.

## Dependency Management

When decomposing, identify dependencies between work items:

- **Hard dependency**: Task B literally cannot start until Task A is complete
  (e.g., the database table must exist before the API can query it).
- **Soft dependency**: Task B would benefit from Task A being done first, but
  can proceed with mocks or stubs.

Minimize hard dependencies by designing interfaces first. If Task B depends on
Task A's database schema, the schema definition can be extracted as a separate
Task C that both depend on.

Order work items so that the critical path (longest chain of hard dependencies)
is as short as possible.

## Common Decomposition Mistakes

- **Big bang decomposition**: Trying to identify every task upfront. Instead,
  decompose one level at a time — epics into features now, features into tasks
  when the feature is next in line for development.
- **Implementation-driven decomposition**: Splitting by code changes rather than
  by user value. "Add database column" is not a work item — it is part of
  "Support user bio field."
- **Orphaned tasks**: Tasks that do not trace to any acceptance criterion. If
  no criterion needs it, the task is either unnecessary or the criteria are
  incomplete.
- **Missing integration tasks**: Each feature should include a task that verifies
  the feature works end-to-end, not just that individual components work.
