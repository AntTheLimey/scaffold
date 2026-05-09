# Python Packaging

## pyproject.toml Structure

### Minimal project configuration

```toml
[project]
name = "project-name"
version = "0.1.0"
description = "One-line description"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
    "pyright>=1.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Version pinning strategy

- **Direct dependencies**: Use `>=` minimum with no upper bound.
  `httpx>=0.27` not `httpx>=0.27,<0.28`.
- **Dev dependencies**: Use `>=` minimum. Pin exact versions only in
  lock files.
- **Never use `==`** in pyproject.toml for library packages. It prevents
  users from resolving compatible versions.
- **Applications** may pin more tightly using a lock file (uv.lock,
  pip-compile output).

## Entry Points

### Console scripts

```toml
[project.scripts]
mycommand = "project.cli:main"
```

The function `main()` in `project/cli.py` becomes the `mycommand` CLI.

### Plugin entry points

```toml
[project.entry-points."myapp.plugins"]
myplugin = "project.plugins.myplugin:Plugin"
```

## Package Discovery

### src layout (recommended)

```
project-root/
  src/
    project_name/
      __init__.py
      module.py
  tests/
    test_module.py
  pyproject.toml
```

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/project_name"]
```

### flat layout

```
project-root/
  project_name/
    __init__.py
    module.py
  tests/
    test_module.py
  pyproject.toml
```

Most build backends auto-discover packages in flat layout.

## Tool Configuration in pyproject.toml

### ruff

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.ruff.lint.isort]
known-first-party = ["project_name"]
```

### pyright

```toml
[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
reportMissingTypeStubs = false
```

### pytest

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
asyncio_mode = "auto"
```

## Dependency Groups (PEP 735)

For Python 3.12+ projects using modern tooling:

```toml
[dependency-groups]
test = ["pytest>=8.0", "pytest-asyncio>=0.23"]
lint = ["ruff>=0.4"]
type = ["pyright>=1.1"]
dev = [{include-group = "test"}, {include-group = "lint"}, {include-group = "type"}]
```

## Common Patterns

- **Single source of truth for version**: Use `version` in pyproject.toml.
  If dynamic, use `[tool.hatch.version]` or `[tool.setuptools.dynamic]`.
- **README as long description**: `readme = "README.md"` in `[project]`.
- **License**: `license = {text = "MIT"}` or `license-files = ["LICENSE"]`.
- **Python version**: Set `requires-python` to the minimum supported version.
  Test against this version in CI.
