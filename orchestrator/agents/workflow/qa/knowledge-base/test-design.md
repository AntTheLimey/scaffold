# Test Design Reference

## Test Pyramid

Distribute tests according to the pyramid: many unit tests at the base, fewer
integration tests in the middle, fewest end-to-end tests at the top.

### Unit Tests (Base — 70% of tests)
- Test one function or method in isolation.
- No external dependencies: no database, no network, no file system.
- Replace dependencies with mocks, stubs, or fakes.
- Execute in milliseconds.
- One logical assertion per test (one reason to fail).

### Integration Tests (Middle — 20% of tests)
- Test the interaction between two or more components.
- May use a real database (in-memory or test instance) but no external services.
- Verify that components work together: data flows correctly through the stack.
- Execute in seconds, not minutes.

### End-to-End Tests (Top — 10% of tests)
- Test a complete user workflow through the full system.
- Exercise the actual deployment configuration.
- Slow and brittle — use sparingly for critical paths only.
- Verify: "Can a user accomplish their goal?"

Inverting the pyramid (many E2E, few unit tests) leads to slow test suites,
flaky CI pipelines, and difficulty pinpointing failures.

## TDD Cycle

Red-Green-Refactor:

1. **Red**: Write a test that fails. The test defines the expected behavior.
   Run the test to confirm it fails (not due to syntax error, but because the
   behavior does not exist yet).

2. **Green**: Write the minimum code to make the test pass. Do not optimize.
   Do not handle edge cases. Just make the test green.

3. **Refactor**: Clean up the code without changing behavior. Tests must stay
   green throughout refactoring.

In the QA pipeline, TDD applies when writing tests before the implementation
is complete (stub-first approach) or when the implementation has bugs that
need test-driven fixes.

## Test Isolation

Each test must be independent of every other test.

Rules:
- No shared mutable state between tests. Each test creates its own fixtures.
- Tests run in any order and produce the same result.
- Tests can run in parallel without interference.
- Database tests use transactions that roll back after each test, or use
  fresh in-memory databases.
- File system tests use temporary directories cleaned up in teardown.
- Time-dependent tests use frozen time (mock the clock, do not use sleep).

Detecting isolation violations:
- A test passes alone but fails in the full suite (or vice versa).
- Test results change when run order changes.
- Tests fail intermittently without code changes.

## Fixtures and Setup

- Fixtures provide the test's preconditions (database state, mock objects,
  configuration).
- Prefer explicit setup in each test over shared setup methods. Readability
  is more important than DRY in tests.
- Use factory functions to create test data: `make_user(name="test")` is
  clearer than an opaque fixture.
- Tear down everything you set up. Use try/finally or framework-provided
  cleanup hooks.

## Mocking Strategy

Use mocks for external boundaries only:
- Network calls (HTTP, gRPC, WebSocket).
- Database queries (in unit tests; use real DB in integration tests).
- File system operations.
- Clock/time.
- Random number generation.

Do NOT mock:
- Internal classes or functions under your control. If you need to mock an
  internal dependency, the design may need a boundary (interface/protocol).
- The code under test itself.
- Data structures or value objects.

Mock fidelity: Mocks should behave like the real thing for the test scenario.
A mock that always returns success does not test error handling.

## Parameterized Tests

When testing the same behavior with different inputs, use parameterized tests
instead of copy-pasting test functions.

Use parameterized tests for:
- Boundary values (0, 1, max, max+1).
- Equivalence classes (valid email formats, invalid email formats).
- Multiple input types that should produce the same behavior.

Do NOT parameterize when:
- The assertions differ per input (that is multiple tests, not one).
- The setup differs significantly per case.
- Parameterization makes the test harder to understand than separate functions.

## Test Anti-Patterns

- **Testing implementation, not behavior**: Asserting that a specific method
  was called instead of asserting the observable outcome. Refactoring the
  implementation breaks the test even though behavior is unchanged.
- **Flaky tests**: Tests that sometimes pass and sometimes fail. Common causes:
  timing dependencies, shared state, network calls, unordered collections.
- **Test that tests nothing**: A test with no assertions, or assertions that
  are always true.
- **Overly broad assertions**: `assert result is not None` when you should
  check the actual content.
- **Test setup longer than test**: If setup is 40 lines and the test is 2,
  the test scope is too wide or the setup should be a factory function.
- **Commented-out tests**: Deleted behavior that is no longer tested.
  Remove or fix them.
