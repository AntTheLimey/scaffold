# Python Testing Patterns

## pytest Conventions

### Test file structure

```python
"""Tests for module_name."""
import pytest
from project.module_name import function_under_test


class TestFunctionUnderTest:
    """Group tests for a single function or class."""

    def test_valid_input_returns_expected(self):
        result = function_under_test("valid")
        assert result == expected_value

    def test_invalid_input_raises_value_error(self):
        with pytest.raises(ValueError, match="specific message"):
            function_under_test("invalid")
```

### Naming convention

- Files: `test_{module_name}.py` matching the source file name.
- Classes: `TestClassName` grouping related tests.
- Functions: `test_{what}_{when}_{expected}` describing the scenario.

## Fixtures

### Scope levels

```python
@pytest.fixture  # function scope (default) — created per test
@pytest.fixture(scope="class")  # shared within a test class
@pytest.fixture(scope="module")  # shared within a test file
@pytest.fixture(scope="session")  # shared across all tests
```

Use function scope by default. Wider scopes only for expensive resources
(database connections, compiled schemas).

### Factory fixtures

Prefer factories over static fixtures for test data:

```python
@pytest.fixture
def make_user():
    def _make_user(name="test", email="test@example.com", **overrides):
        defaults = {"name": name, "email": email, "active": True}
        defaults.update(overrides)
        return User(**defaults)
    return _make_user

def test_inactive_user_cannot_login(make_user):
    user = make_user(active=False)
    assert not user.can_login()
```

### tmp_path fixture

Use `tmp_path` (pathlib.Path) for file system tests:

```python
def test_writes_output_file(tmp_path):
    output = tmp_path / "result.txt"
    write_result(output, "data")
    assert output.read_text() == "data"
```

Never use hardcoded paths or `/tmp` directly.

## Mocking

### unittest.mock patterns

```python
from unittest.mock import Mock, patch, MagicMock

# Patch at the import location, not the definition location
@patch("project.service.external_client")
def test_service_calls_client(mock_client):
    mock_client.fetch.return_value = {"key": "value"}
    result = service.process()
    mock_client.fetch.assert_called_once_with(expected_args)

# Context manager for fine-grained control
def test_with_context_manager():
    with patch("project.module.dependency") as mock_dep:
        mock_dep.return_value = "mocked"
        assert module.function() == "processed: mocked"
```

### Mock anti-patterns

- Do not mock the function you are testing.
- Do not mock data classes or value objects.
- Do not use `MagicMock` when `Mock(spec=RealClass)` provides type safety.
- Do not mock more than 2 dependencies in a single test — the function
  may need refactoring.

## Parameterize

```python
@pytest.mark.parametrize("input_val, expected", [
    ("valid@email.com", True),
    ("no-at-sign.com", False),
    ("", False),
    ("@no-local.com", False),
    ("user@.no-domain", False),
])
def test_validate_email(input_val, expected):
    assert validate_email(input_val) == expected
```

Use IDs for clarity in test output:

```python
@pytest.mark.parametrize("input_val, expected", [
    pytest.param("valid@email.com", True, id="valid-email"),
    pytest.param("", False, id="empty-string"),
])
```

## Async Testing

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected

# Async fixtures
@pytest.fixture
async def async_client():
    async with AsyncClient() as client:
        yield client
```

Requires `pytest-asyncio` in dependencies.

## Anti-Patterns to Avoid

- **Sleep in tests**: Use `unittest.mock.patch` to mock time or use
  `freezegun` for time-dependent logic. Never `time.sleep()`.
- **Assert True/False without context**: `assert result` gives no useful
  failure message. Use `assert result == expected_value`.
- **Testing private methods**: Test through the public API. If you cannot,
  the design needs refactoring.
- **Shared mutable state**: Each test creates its own data. No module-level
  variables that tests modify.
- **Catching exceptions to assert**: Use `pytest.raises`, not try/except
  with `assert False`.
