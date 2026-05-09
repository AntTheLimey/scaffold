# Acceptance Criteria to Test Mapping

## Criteria-to-Test Process

For each acceptance criterion in the task:

1. **Parse the criterion**: Identify the precondition (Given), action (When),
   and expected outcome (Then). If the criterion is not in Given/When/Then
   format, convert it mentally.

2. **Write the happy path test**: Test the criterion as stated. This is the
   minimum required test.

3. **Derive edge cases**: For each element of the criterion, identify boundary
   values and exceptional conditions.

4. **Write negative tests**: Test what should NOT happen. If the criterion says
   "valid users can access," also test "invalid users cannot access."

5. **Map to test functions**: Name each test to identify which criterion it
   validates: `test_{criterion_keyword}_{scenario}`.

## Edge Case Derivation

For each type of input, apply these edge case patterns:

### Strings
- Empty string
- Single character
- Maximum length (if specified)
- Maximum length + 1
- Unicode characters (emoji, CJK, RTL text)
- Strings with only whitespace
- Strings with special characters (quotes, backslashes, null bytes)
- Strings with HTML/script tags (XSS vectors)

### Numbers
- Zero
- Negative (if the domain should be positive)
- Maximum value for the type
- Minimum value for the type
- Decimal values when integers are expected
- NaN and Infinity (in languages that have them)

### Collections
- Empty collection
- Single element
- Many elements (performance boundary)
- Duplicate elements
- Null/None elements within the collection

### Dates and Times
- Now
- Far future (year 9999)
- Far past (year 0001)
- Leap year dates (Feb 29)
- Timezone boundaries (UTC, UTC+14, UTC-12)
- DST transitions

### Authentication/Authorization
- No credentials provided
- Expired credentials
- Valid credentials, wrong permissions
- Valid credentials, correct permissions
- Credentials for a deleted/disabled account

## Given/When/Then Format

### Given (Precondition)
Describes the state of the system before the action. Each Given clause maps to
test setup code.

```
Given a registered user with email "test@example.com"
  → Create a user record in the test database

Given an empty product catalog
  → Ensure the products table/collection is empty

Given a user who has exceeded their rate limit
  → Insert rate limit records that exceed the threshold
```

### When (Action)
Describes the action being tested. Each When clause maps to the function call
or HTTP request under test.

```
When the user submits login with correct credentials
  → Call login_service.authenticate(email, password)

When a GET request is made to /api/products
  → Send HTTP GET to the test server's /api/products endpoint
```

### Then (Expected Outcome)
Describes the observable result. Each Then clause maps to one assertion.

```
Then a session token is returned
  → assert result.token is not None
  → assert len(result.token) == 64

Then the response contains an empty list
  → assert response.status_code == 200
  → assert response.json()["data"] == []
```

## Priority Order for Test Writing

When time or iteration budget is limited, write tests in this order:

1. **Security-critical paths**: Authentication, authorization, data validation.
   These have the highest cost of failure.

2. **Happy path for each criterion**: The basic positive case. This proves the
   feature works as specified.

3. **Error handling paths**: What happens when things go wrong? Missing input,
   invalid data, unavailable dependencies.

4. **Boundary conditions**: Edge cases at the limits of valid input.

5. **Performance-sensitive paths**: Tests that verify response times or
   resource usage for critical operations.

6. **Regression tests**: If a bug was found during development, write a test
   that would have caught it.

## Test Naming Convention

Test function names should read as a specification:

```
test_{what}_{when}_{expected}
```

Examples:
```
test_login_with_valid_credentials_returns_token
test_login_with_wrong_password_returns_401
test_login_after_5_failed_attempts_locks_account
test_profile_with_long_bio_truncates_at_500_chars
test_search_with_empty_query_returns_all_results
```

Avoid:
```
test_login           # too vague
test_login_1         # meaningless suffix
test_it_works        # untestable name
test_feature_123     # ticket number is not a description
```

## Unmappable Criteria

Some acceptance criteria resist testing:

- "The UI feels responsive" — Convert to measurable: "Page loads in under 2
  seconds" or "Interactions respond within 200ms."
- "The code is maintainable" — Not a test criterion. This is a review concern.
- "Users find it intuitive" — Convert to: "A new user can complete the primary
  task without documentation." Then test the steps.

If a criterion truly cannot be mapped to a test, report it as an
"untestable_criterion" escalation so the Product Owner can rewrite it.
