# scaffold init Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `scaffold init` CLI command that detects a target repo, interviews the human, generates CLAUDE.md, and creates a project config file — plus multi-project support across the CLI.

**Architecture:** A new `orchestrator/init.py` module handles detection display, interview prompts, and file generation. Config loading gains a `project` parameter to resolve `config/projects/{name}.yaml`. All CLI commands gain `--project` support with backward compatibility for the root `project.yaml`.

**Tech Stack:** Python 3.12+, Click, PyYAML, pytest

**Spec:** `docs/superpowers/specs/2026-05-11-scaffold-init.md`

---

## File Structure

### Files Created

```
orchestrator/
  init.py                    # Init logic: display detection, interview, generate files
tests/
  test_init.py               # Tests for init module
```

### Files Modified

```
orchestrator/
  config.py                  # Add load_config project parameter, load_project function
  __main__.py                # Add init command, add --project to run/resume/decide
  preflight.py               # Verify project yaml exists when --project provided
  nodes/onboarding.py        # Extract detect_project to shared location (or import from init)
tests/
  conftest.py                # Update config_dir fixture for projects/ subdirectory
  test_config.py             # Tests for multi-project config loading
  test_cli.py                # Tests for init command and --project flag
  test_preflight.py          # Tests for project yaml check
```

---

### Task 1: Add multi-project config loading

**Files:**
- Modify: `orchestrator/config.py`
- Modify: `tests/test_config.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write tests for project-based config loading**

Add to `tests/test_config.py`:

```python
from pathlib import Path

from orchestrator.config import load_config


def test_load_config_with_project(tmp_path):
    governance = tmp_path / "governance.yaml"
    governance.write_text(
        "rapid:\n"
        "  product_scope:\n"
        "    recommend: product_owner\n"
        "raci:\n"
        "  write_code:\n"
        "    responsible: developer\n"
    )
    agents = tmp_path / "agents.yaml"
    agents.write_text(
        "workflow:\n"
        "  product_owner:\n"
        "    model: claude-opus-4-6\n"
        "    execution: api\n"
        "specialists:\n"
        "  python-expert:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 10\n"
        "    completion_promise: TASK COMPLETE\n"
        "escalation:\n"
        "  stuck_loop_model: claude-opus-4-6\n"
    )
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    project_file = projects_dir / "webapp.yaml"
    project_file.write_text(
        "repo_path: /tmp/webapp\n"
        "branch_prefix: scaffold\n"
        "max_concurrent_agents: 3\n"
        "db_path: scaffold_webapp.db\n"
    )
    cfg = load_config(str(tmp_path), project="webapp")
    assert cfg.project.repo_path == "/tmp/webapp"
    assert cfg.project.db_path == "scaffold_webapp.db"


def test_load_config_without_project_uses_root(config_dir):
    cfg = load_config(config_dir)
    assert cfg.project.repo_path == "/tmp/test-repo"


def test_load_config_project_not_found(tmp_path):
    governance = tmp_path / "governance.yaml"
    governance.write_text("rapid: {}\nraci: {}\n")
    agents = tmp_path / "agents.yaml"
    agents.write_text("workflow: {}\nspecialists: {}\nescalation: {}\n")
    import pytest

    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path), project="nonexistent")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test 2>&1 | grep -E "FAILED|PASSED|ERROR" | tail -5`
Expected: FAIL — `load_config()` does not accept `project` parameter

- [ ] **Step 3: Update config.py**

Replace `orchestrator/config.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class GovernanceConfig:
    rapid: dict[str, dict[str, str]]
    raci: dict[str, dict[str, str | list[str]]]


@dataclass
class AgentsConfig:
    workflow: dict[str, dict]
    specialists: dict[str, dict]
    escalation: dict


@dataclass
class ProjectConfig:
    repo_path: str
    branch_prefix: str = "scaffold"
    max_concurrent_agents: int = 3
    db_path: str = "scaffold.db"


@dataclass
class ScaffoldConfig:
    governance: GovernanceConfig
    agents: AgentsConfig
    project: ProjectConfig


def load_config(config_dir: str | Path, project: str | None = None) -> ScaffoldConfig:
    config_dir = Path(config_dir)

    with open(config_dir / "governance.yaml") as f:
        gov_data = yaml.safe_load(f)
    governance = GovernanceConfig(
        rapid=gov_data.get("rapid", {}),
        raci=gov_data.get("raci", {}),
    )

    with open(config_dir / "agents.yaml") as f:
        agents_data = yaml.safe_load(f)
    agents = AgentsConfig(
        workflow=agents_data.get("workflow", {}),
        specialists=agents_data.get("specialists", {}),
        escalation=agents_data.get("escalation", {}),
    )

    if project:
        project_path = config_dir / "projects" / f"{project}.yaml"
        if not project_path.exists():
            raise FileNotFoundError(
                f"Project '{project}' not found at {project_path}. "
                f"Run 'scaffold init' first."
            )
        with open(project_path) as f:
            proj_data = yaml.safe_load(f)
    else:
        with open(config_dir / "project.yaml") as f:
            proj_data = yaml.safe_load(f)

    project_cfg = ProjectConfig(**proj_data)

    return ScaffoldConfig(governance=governance, agents=agents, project=project_cfg)
```

- [ ] **Step 4: Run tests**

Run: `make check`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/config.py tests/test_config.py
git commit -m "feat: support multi-project config loading via --project"
```

---

### Task 2: Create the init module with detection display

**Files:**
- Create: `orchestrator/init.py`
- Create: `tests/test_init.py`

- [ ] **Step 1: Write tests for detection display formatting**

Create `tests/test_init.py`:

```python
from orchestrator.init import format_detection


def test_format_detection_full():
    detection = {
        "detected_languages": ["python", "typescript"],
        "detected_frameworks": ["fastapi", "react"],
        "test_framework": "pytest",
        "has_database": True,
        "has_makefile": True,
        "claude_md_quality": "missing",
        "project_context": "",
    }
    output = format_detection(detection)
    assert "Python, TypeScript" in output
    assert "FastAPI, React" in output
    assert "pytest" in output
    assert "yes" in output.lower()
    assert "missing" in output.lower()


def test_format_detection_empty():
    detection = {
        "detected_languages": [],
        "detected_frameworks": [],
        "test_framework": "",
        "has_database": False,
        "has_makefile": False,
        "claude_md_quality": "missing",
        "project_context": "",
    }
    output = format_detection(detection)
    assert "none" in output.lower()


def test_format_detection_substantive_claude_md():
    detection = {
        "detected_languages": ["python"],
        "detected_frameworks": [],
        "test_framework": "pytest",
        "has_database": False,
        "has_makefile": True,
        "claude_md_quality": "substantive",
        "project_context": "x\n" * 60,
    }
    output = format_detection(detection)
    assert "substantive" in output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test 2>&1 | grep -E "FAILED|ERROR" | head -5`
Expected: FAIL — `orchestrator.init` does not exist

- [ ] **Step 3: Create init.py with format_detection**

Create `orchestrator/init.py`:

```python
from pathlib import Path


def format_detection(detection: dict) -> str:
    languages = detection["detected_languages"]
    frameworks = detection["detected_frameworks"]
    test_fw = detection["test_framework"]
    has_db = detection["has_database"]
    has_make = detection["has_makefile"]
    claude_quality = detection["claude_md_quality"]

    lang_str = ", ".join(lang.capitalize() for lang in languages) if languages else "none"
    fw_str = ", ".join(fw.capitalize() for fw in frameworks) if frameworks else "none"
    test_str = test_fw if test_fw else "none"
    db_str = "yes" if has_db else "no"
    make_str = "yes" if has_make else "no"

    lines = [
        "Detected:",
        f"  Languages ............. {lang_str}",
        f"  Frameworks ............ {fw_str}",
        f"  Test framework ........ {test_str}",
        f"  Database .............. {db_str}",
        f"  Makefile .............. {make_str}",
        f"  CLAUDE.md ............. {claude_quality}",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `make check`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/init.py tests/test_init.py
git commit -m "feat: add init module with detection display formatting"
```

---

### Task 3: Add interview and CLAUDE.md generation

**Files:**
- Modify: `orchestrator/init.py`
- Modify: `tests/test_init.py`

- [ ] **Step 1: Write tests for Makefile target extraction**

Add to `tests/test_init.py`:

```python
from orchestrator.init import extract_makefile_targets


def test_extract_makefile_targets(tmp_path):
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        ".PHONY: install test lint\n"
        "\n"
        "install:\n"
        "\tpip install -e .\n"
        "\n"
        "test:\n"
        "\tpytest\n"
        "\n"
        "lint:\n"
        "\truff check .\n"
    )
    targets = extract_makefile_targets(tmp_path)
    assert "install" in targets
    assert "test" in targets
    assert "lint" in targets
    assert ".PHONY" not in targets


def test_extract_makefile_targets_no_makefile(tmp_path):
    targets = extract_makefile_targets(tmp_path)
    assert targets == []
```

- [ ] **Step 2: Write tests for code style detection**

Add to `tests/test_init.py`:

```python
from orchestrator.init import detect_code_style


def test_detect_code_style_ruff(tmp_path):
    ruff_toml = tmp_path / "ruff.toml"
    ruff_toml.write_text('line-length = 100\ntarget-version = "py312"\n')
    style = detect_code_style(tmp_path)
    assert "ruff" in style.lower()
    assert "100" in style


def test_detect_code_style_pyproject_ruff(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.ruff]\nline-length = 88\n')
    style = detect_code_style(tmp_path)
    assert "ruff" in style.lower()


def test_detect_code_style_eslint(tmp_path):
    eslint = tmp_path / ".eslintrc.json"
    eslint.write_text('{"rules": {}}')
    style = detect_code_style(tmp_path)
    assert "eslint" in style.lower()


def test_detect_code_style_prettier(tmp_path):
    prettier = tmp_path / ".prettierrc"
    prettier.write_text('{"tabWidth": 2}')
    style = detect_code_style(tmp_path)
    assert "prettier" in style.lower()


def test_detect_code_style_none(tmp_path):
    style = detect_code_style(tmp_path)
    assert style == ""
```

- [ ] **Step 3: Write tests for CLAUDE.md generation**

Add to `tests/test_init.py`:

```python
from orchestrator.init import generate_claude_md


def test_generate_claude_md_full():
    detection = {
        "detected_languages": ["python"],
        "detected_frameworks": ["fastapi"],
        "test_framework": "pytest",
        "has_database": True,
        "has_makefile": True,
        "claude_md_quality": "missing",
        "project_context": "",
    }
    interview = {
        "description": "A REST API for managing widgets",
        "conventions": "Use pydantic v2 model_validate",
        "off_limits": "Do not modify alembic migrations directly",
    }
    makefile_targets = ["install", "test", "lint", "format"]
    code_style = "ruff (line-length: 100)"

    content = generate_claude_md(detection, interview, makefile_targets, code_style)
    assert "# A REST API for managing widgets" in content
    assert "Python" in content
    assert "Fastapi" in content or "FastAPI" in content
    assert "pytest" in content
    assert "make install" in content or "install" in content
    assert "pydantic v2" in content
    assert "alembic" in content


def test_generate_claude_md_minimal():
    detection = {
        "detected_languages": ["go"],
        "detected_frameworks": [],
        "test_framework": "go test",
        "has_database": False,
        "has_makefile": False,
        "claude_md_quality": "missing",
        "project_context": "",
    }
    interview = {
        "description": "CLI tool for batch processing",
        "conventions": "",
        "off_limits": "",
    }
    content = generate_claude_md(detection, interview, [], "")
    assert "# CLI tool for batch processing" in content
    assert "Go" in content
    assert "## Conventions" not in content
    assert "## Off-Limits" not in content


def test_generate_claude_md_no_empty_sections():
    detection = {
        "detected_languages": [],
        "detected_frameworks": [],
        "test_framework": "",
        "has_database": False,
        "has_makefile": False,
        "claude_md_quality": "missing",
        "project_context": "",
    }
    interview = {
        "description": "A project",
        "conventions": "",
        "off_limits": "",
    }
    content = generate_claude_md(detection, interview, [], "")
    assert "## Key Commands" not in content
    assert "## Code Style" not in content
    assert "## Conventions" not in content
    assert "## Off-Limits" not in content
```

- [ ] **Step 4: Implement helpers and generate_claude_md**

Add to `orchestrator/init.py`:

```python
import re


def extract_makefile_targets(repo_path: Path) -> list[str]:
    makefile = repo_path / "Makefile"
    if not makefile.exists():
        return []
    targets: list[str] = []
    for line in makefile.read_text().splitlines():
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):", line)
        if match:
            targets.append(match.group(1))
    return targets


def detect_code_style(repo_path: Path) -> str:
    tools: list[str] = []

    ruff_toml = repo_path / "ruff.toml"
    if ruff_toml.exists():
        text = ruff_toml.read_text()
        match = re.search(r"line-length\s*=\s*(\d+)", text)
        length = f", line-length: {match.group(1)}" if match else ""
        tools.append(f"ruff{length}")
    elif (repo_path / "pyproject.toml").exists():
        text = (repo_path / "pyproject.toml").read_text()
        if "[tool.ruff]" in text:
            match = re.search(r"line-length\s*=\s*(\d+)", text)
            length = f", line-length: {match.group(1)}" if match else ""
            tools.append(f"ruff{length}")

    for name in (".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.yml"):
        if (repo_path / name).exists():
            tools.append("eslint")
            break

    if (repo_path / "biome.json").exists():
        tools.append("biome")

    if (repo_path / ".prettierrc").exists():
        tools.append("prettier")

    if (repo_path / ".golangci.yml").exists() or (repo_path / ".golangci.yaml").exists():
        tools.append("golangci-lint")

    return ", ".join(tools)


def generate_claude_md(
    detection: dict,
    interview: dict,
    makefile_targets: list[str],
    code_style: str,
) -> str:
    sections: list[str] = []

    sections.append(f"# {interview['description']}")

    languages = detection["detected_languages"]
    frameworks = detection["detected_frameworks"]
    if languages or frameworks:
        parts = [lang.capitalize() for lang in languages]
        parts += [fw.capitalize() for fw in frameworks]
        sections.append(f"\n## Architecture\n\n{', '.join(parts)}")

    has_commands = bool(makefile_targets)
    has_test = bool(detection["test_framework"])
    if has_commands or has_test:
        dev_lines = ["\n## Development"]
        if has_commands:
            dev_lines.append("\n### Key Commands\n")
            dev_lines.append("```")
            for target in makefile_targets:
                dev_lines.append(f"make {target}")
            dev_lines.append("```")
        if has_test:
            dev_lines.append(f"\n### Testing\n\nFramework: {detection['test_framework']}")
        sections.append("\n".join(dev_lines))

    if code_style:
        sections.append(f"\n## Code Style\n\n{code_style}")

    if interview.get("conventions"):
        sections.append(f"\n## Conventions\n\n{interview['conventions']}")

    if interview.get("off_limits"):
        sections.append(f"\n## Off-Limits\n\n{interview['off_limits']}")

    return "\n".join(sections) + "\n"
```

- [ ] **Step 5: Run tests**

Run: `make check`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add orchestrator/init.py tests/test_init.py
git commit -m "feat: add Makefile parsing, code style detection, CLAUDE.md generation"
```

---

### Task 4: Add project YAML generation

**Files:**
- Modify: `orchestrator/init.py`
- Modify: `tests/test_init.py`

- [ ] **Step 1: Write tests for project name derivation and YAML generation**

Add to `tests/test_init.py`:

```python
import yaml

from orchestrator.init import derive_project_name, generate_project_yaml


def test_derive_project_name_simple():
    assert derive_project_name("/home/user/my-webapp") == "my-webapp"


def test_derive_project_name_spaces():
    assert derive_project_name("/home/user/My Project") == "my-project"


def test_derive_project_name_uppercase():
    assert derive_project_name("/home/user/MyApp") == "myapp"


def test_derive_project_name_trailing_slash():
    assert derive_project_name("/home/user/repo/") == "repo"


def test_generate_project_yaml():
    content = generate_project_yaml("/home/user/webapp", "webapp")
    data = yaml.safe_load(content)
    assert data["repo_path"] == "/home/user/webapp"
    assert data["branch_prefix"] == "scaffold"
    assert data["max_concurrent_agents"] == 3
    assert data["db_path"] == "scaffold_webapp.db"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test 2>&1 | grep -E "FAILED|ERROR" | head -5`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement project YAML generation**

Add to `orchestrator/init.py`:

```python
import yaml


def derive_project_name(repo_path: str) -> str:
    name = Path(repo_path).resolve().name
    return name.lower().replace(" ", "-")


def generate_project_yaml(repo_path: str, project_name: str) -> str:
    data = {
        "repo_path": str(Path(repo_path).resolve()),
        "branch_prefix": "scaffold",
        "max_concurrent_agents": 3,
        "db_path": f"scaffold_{project_name}.db",
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False)
```

- [ ] **Step 4: Run tests**

Run: `make check`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/init.py tests/test_init.py
git commit -m "feat: add project name derivation and YAML generation"
```

---

### Task 5: Add the run_init orchestrator function

**Files:**
- Modify: `orchestrator/init.py`
- Modify: `tests/test_init.py`

- [ ] **Step 1: Write tests for run_init**

Add to `tests/test_init.py`:

```python
from unittest.mock import patch, call

from orchestrator.init import run_init


def test_run_init_creates_claude_md(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (repo / "ruff.toml").write_text("line-length = 100\n")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects").mkdir()

    with patch("click.prompt", side_effect=["A widget API", "", ""]):
        run_init(str(repo), str(config_dir))

    claude_md = repo / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text()
    assert "# A widget API" in content


def test_run_init_creates_project_yaml(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects").mkdir()

    with patch("click.prompt", side_effect=["A project", "", ""]):
        run_init(str(repo), str(config_dir))

    project_yaml = config_dir / "projects" / "myrepo.yaml"
    assert project_yaml.exists()
    data = yaml.safe_load(project_yaml.read_text())
    assert data["repo_path"] == str(repo.resolve())


def test_run_init_creates_projects_dir_if_missing(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    with patch("click.prompt", side_effect=["A project", "", ""]):
        run_init(str(repo), str(config_dir))

    assert (config_dir / "projects").is_dir()


def test_run_init_skips_when_substantive_claude_md(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    claude_md = repo / "CLAUDE.md"
    claude_md.write_text("# Existing\n" + "line\n" * 60)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects").mkdir()

    with patch("click.prompt") as mock_prompt:
        mock_prompt.return_value = "skip"
        result = run_init(str(repo), str(config_dir))

    assert result["claude_md_action"] == "skip"
    content = claude_md.read_text()
    assert "# Existing" in content


def test_run_init_overwrites_when_requested(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    claude_md = repo / "CLAUDE.md"
    claude_md.write_text("# Old\n" + "line\n" * 60)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects").mkdir()

    with patch("click.prompt", side_effect=["overwrite", "New description", "", ""]):
        run_init(str(repo), str(config_dir))

    content = claude_md.read_text()
    assert "# New description" in content
    assert "# Old" not in content


def test_run_init_returns_summary(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects").mkdir()

    with patch("click.prompt", side_effect=["A project", "", ""]):
        result = run_init(str(repo), str(config_dir))

    assert "project_name" in result
    assert "claude_md_path" in result
    assert "project_yaml_path" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test 2>&1 | grep -E "FAILED|ERROR" | head -5`
Expected: FAIL — `run_init` not defined

- [ ] **Step 3: Implement run_init**

Add to `orchestrator/init.py` (add the import at the top of the file):

```python
import click

from orchestrator.nodes.onboarding import detect_project
```

Then add the function:

```python
def run_init(repo_path: str, config_dir: str) -> dict:
    repo = Path(repo_path).resolve()
    config = Path(config_dir)
    projects_dir = config / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    detection = detect_project(repo)
    project_name = derive_project_name(str(repo))

    claude_md_action = "create"
    if detection["claude_md_quality"] == "substantive":
        choice = click.prompt(
            f"CLAUDE.md already exists ({len(detection['project_context'].splitlines())} lines). "
            "Overwrite, augment, or skip?",
            type=click.Choice(["overwrite", "augment", "skip"], case_sensitive=False),
            default="skip",
        )
        claude_md_action = choice
        if choice == "skip":
            _write_project_yaml(projects_dir, project_name, str(repo))
            return {
                "project_name": project_name,
                "claude_md_action": "skip",
                "claude_md_path": str(repo / "CLAUDE.md"),
                "project_yaml_path": str(projects_dir / f"{project_name}.yaml"),
            }

    if claude_md_action in ("create", "overwrite") or detection["claude_md_quality"] != "substantive":
        description = click.prompt("What does this project do?")
        conventions = click.prompt(
            "Any conventions not captured in existing docs? (press Enter to skip)",
            default="",
        )
        off_limits = click.prompt(
            "Anything agents should avoid touching? (press Enter to skip)",
            default="",
        )
    else:
        description = click.prompt("Project description (for header)", default="")
        conventions = ""
        off_limits = ""

    interview = {
        "description": description,
        "conventions": conventions,
        "off_limits": off_limits,
    }

    makefile_targets = extract_makefile_targets(repo)
    code_style = detect_code_style(repo)

    claude_md_content = generate_claude_md(detection, interview, makefile_targets, code_style)

    claude_md_path = repo / "CLAUDE.md"
    if claude_md_action == "augment" and claude_md_path.exists():
        existing = claude_md_path.read_text()
        claude_md_content = existing.rstrip() + "\n\n" + claude_md_content
    claude_md_path.write_text(claude_md_content)

    _write_project_yaml(projects_dir, project_name, str(repo))

    return {
        "project_name": project_name,
        "claude_md_action": claude_md_action,
        "claude_md_path": str(claude_md_path),
        "project_yaml_path": str(projects_dir / f"{project_name}.yaml"),
    }


def _write_project_yaml(projects_dir: Path, project_name: str, repo_path: str) -> None:
    content = generate_project_yaml(repo_path, project_name)
    (projects_dir / f"{project_name}.yaml").write_text(content)
```

- [ ] **Step 4: Run tests**

Run: `make check`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/init.py tests/test_init.py
git commit -m "feat: add run_init orchestrator function"
```

---

### Task 6: Add the init CLI command

**Files:**
- Modify: `orchestrator/__main__.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write CLI tests for init command**

Add to `tests/test_cli.py`:

```python
from unittest.mock import MagicMock, patch

from orchestrator.__main__ import cli


def test_cli_init_command(runner, tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects").mkdir()

    with patch("orchestrator.__main__.run_init") as mock_init:
        mock_init.return_value = {
            "project_name": "myrepo",
            "claude_md_action": "create",
            "claude_md_path": str(repo / "CLAUDE.md"),
            "project_yaml_path": str(config_dir / "projects" / "myrepo.yaml"),
        }
        result = runner.invoke(
            cli,
            ["init", str(repo), "--config", str(config_dir)],
        )
        assert result.exit_code == 0
        mock_init.assert_called_once_with(str(repo), str(config_dir))
        assert "myrepo" in result.output


def test_cli_init_shows_detection(runner, tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    with (
        patch("orchestrator.__main__.detect_project") as mock_detect,
        patch("orchestrator.__main__.format_detection") as mock_format,
        patch("orchestrator.__main__.run_init") as mock_init,
    ):
        mock_detect.return_value = {
            "detected_languages": ["python"],
            "detected_frameworks": [],
            "test_framework": "pytest",
            "has_database": False,
            "has_makefile": True,
            "claude_md_quality": "missing",
            "project_context": "",
        }
        mock_format.return_value = "Detected:\n  Languages ... Python"
        mock_init.return_value = {
            "project_name": "myrepo",
            "claude_md_action": "create",
            "claude_md_path": str(repo / "CLAUDE.md"),
            "project_yaml_path": str(config_dir / "projects" / "myrepo.yaml"),
        }
        result = runner.invoke(
            cli,
            ["init", str(repo), "--config", str(config_dir)],
        )
        assert result.exit_code == 0
        assert "Detected" in result.output


def test_cli_help_shows_init(runner):
    result = runner.invoke(cli, ["--help"])
    assert "init" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test 2>&1 | grep -E "FAILED|ERROR" | head -5`
Expected: FAIL — init command does not exist

- [ ] **Step 3: Add init command to __main__.py**

Add these imports at the top of `orchestrator/__main__.py`:

```python
from orchestrator.init import format_detection, run_init
from orchestrator.nodes.onboarding import detect_project
```

Add this command after the `preflight` command:

```python
@cli.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.option(
    "--config", default="config/", type=click.Path(), help="Scaffold config directory"
)
def init(repo_path, config):
    """Initialize a target repo for scaffold."""
    repo = Path(repo_path).resolve()
    detection = detect_project(repo)
    click.echo(f"\n{format_detection(detection)}\n")
    result = run_init(str(repo), config)
    click.echo(f"\nCreated:")
    click.echo(f"  {result['claude_md_path']}")
    click.echo(f"  {result['project_yaml_path']}")
    project = result["project_name"]
    click.echo(
        f"\nRun 'scaffold run --spec <spec> --config {config} "
        f"--project {project}' to start."
    )
```

- [ ] **Step 4: Run tests**

Run: `make check`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/__main__.py tests/test_cli.py
git commit -m "feat: add scaffold init CLI command"
```

---

### Task 7: Add --project flag to run, resume, decide

**Files:**
- Modify: `orchestrator/__main__.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write tests for --project flag**

Add to `tests/test_cli.py`:

```python
def test_cli_run_with_project(runner, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Test Spec")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    governance = config_dir / "governance.yaml"
    governance.write_text("rapid: {}\nraci: {}\n")
    agents = config_dir / "agents.yaml"
    agents.write_text(
        "workflow:\n"
        "  product_owner:\n"
        "    model: claude-opus-4-6\n"
        "    execution: api\n"
        "specialists:\n"
        "  python-expert:\n"
        "    model: claude-sonnet-4-6\n"
        "    execution: cli\n"
        "    max_iterations: 10\n"
        "    completion_promise: TASK COMPLETE\n"
        "escalation:\n"
        "  stuck_loop_model: claude-opus-4-6\n"
    )
    projects_dir = config_dir / "projects"
    projects_dir.mkdir()
    project_file = projects_dir / "webapp.yaml"
    project_file.write_text(
        f"repo_path: /tmp/repo\n"
        f"branch_prefix: scaffold\n"
        f"max_concurrent_agents: 3\n"
        f"db_path: ':memory:'\n"
    )

    with (
        patch("orchestrator.__main__.build_graph") as mock_build,
        patch("orchestrator.__main__.TelegramBot"),
        patch("orchestrator.__main__.SqliteSaver"),
        patch("orchestrator.__main__.AgentLoader"),
        patch("orchestrator.__main__.run_preflight") as mock_preflight,
    ):
        mock_preflight.return_value.ok = True
        mock_graph = MagicMock()
        mock_build.return_value = mock_graph

        result = runner.invoke(
            cli,
            [
                "run",
                "--spec", str(spec),
                "--config", str(config_dir),
                "--project", "webapp",
            ],
        )
        assert result.exit_code == 0


def test_cli_run_project_not_found(runner, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Test Spec")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    governance = config_dir / "governance.yaml"
    governance.write_text("rapid: {}\nraci: {}\n")
    agents = config_dir / "agents.yaml"
    agents.write_text("workflow: {}\nspecialists: {}\nescalation: {}\n")

    result = runner.invoke(
        cli,
        [
            "run",
            "--spec", str(spec),
            "--config", str(config_dir),
            "--project", "nonexistent",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test 2>&1 | grep -E "FAILED|ERROR" | head -5`
Expected: FAIL — `run` command does not accept `--project`

- [ ] **Step 3: Update CLI commands with --project**

In `orchestrator/__main__.py`, update the `run` command:

```python
@cli.command()
@click.option("--spec", required=True, type=click.Path(exists=True), help="Path to master spec")
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
@click.option("--project", default=None, help="Project name (from config/projects/)")
def run(spec, config, project):
    """Start a new scaffold run from a master spec."""
    try:
        cfg = load_config(config, project=project)
    except FileNotFoundError as e:
        click.echo(str(e))
        raise SystemExit(1)
    preflight_result = run_preflight(cfg)
    if not preflight_result.ok:
        for check in preflight_result.checks:
            click.echo(f"  {check.name} {'.' * (30 - len(check.name))} {check.status}")
        click.echo("\nPreflight failed. Fix the issues above and try again.")
        raise SystemExit(1)
    conn = init_db(cfg.project.db_path)

    with SqliteSaver.from_conn_string(_checkpoint_path(cfg.project.db_path)) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            tree = TaskTree(conn)
            task_id = tree.create(title="Root", level="epic", spec_ref=spec)
            state = initial_state(task_id=task_id, level="epic")
            thread_config: RunnableConfig = {"configurable": {"thread_id": task_id}}

            click.echo(f"Scaffold started. Task: {task_id}, DB: {cfg.project.db_path}")

            result = graph.invoke(state, config=thread_config)
            click.echo(f"Run complete. Status: {result.get('status', 'unknown')}")
        finally:
            bot.close()
    conn.close()
```

Update `resume`:

```python
@cli.command()
@click.option("--task", required=True, help="Task ID to resume")
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
@click.option("--spec", default="", help="Path to master spec (needed if re-entering planning)")
@click.option("--project", default=None, help="Project name (from config/projects/)")
def resume(task, db, config, spec, project):
    """Resume an interrupted scaffold run."""
    if not Path(db).exists():
        click.echo("No database found. Run 'scaffold run' first.")
        raise SystemExit(1)

    try:
        cfg = load_config(config, project=project)
    except FileNotFoundError as e:
        click.echo(str(e))
        raise SystemExit(1)

    with SqliteSaver.from_conn_string(_checkpoint_path(db)) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            thread_config: RunnableConfig = {"configurable": {"thread_id": task}}
            click.echo(f"Resuming task {task} from {db}")
            result = graph.invoke(None, config=thread_config)
            click.echo(f"Resume complete. Status: {result.get('status', 'unknown')}")
        finally:
            bot.close()
```

Update `decide`:

```python
@cli.command()
@click.option("--task", required=True, help="Task ID to respond to")
@click.option(
    "--choice", required=True, type=click.Choice(["Approve", "Revise", "Override", "Cancel"])
)
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
@click.option("--spec", default="", help="Path to master spec (needed if re-entering planning)")
@click.option("--project", default=None, help="Project name (from config/projects/)")
def decide(task, choice, db, config, spec, project):
    """Provide a human decision for a paused task."""
    if not Path(db).exists():
        click.echo("No database found.")
        raise SystemExit(1)

    try:
        cfg = load_config(config, project=project)
    except FileNotFoundError as e:
        click.echo(str(e))
        raise SystemExit(1)

    with SqliteSaver.from_conn_string(_checkpoint_path(db)) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            thread_config: RunnableConfig = {"configurable": {"thread_id": task}}
            result = graph.invoke(
                Command(resume={"choice": choice}),
                config=thread_config,
            )
            click.echo(f"Decision applied: {choice} for task {task}")
            click.echo(f"Status: {result.get('status', 'unknown')}")
        finally:
            bot.close()
```

- [ ] **Step 4: Run tests**

Run: `make check`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/__main__.py tests/test_cli.py
git commit -m "feat: add --project flag to run, resume, decide commands"
```

---

### Task 8: Update conftest and existing tests

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Verify all existing tests still pass**

Run: `make check`

The existing `config_dir` fixture writes `project.yaml` at the root, which is the backward-compatible path. All existing tests should still pass because `load_config` without `project=` falls back to root `project.yaml`.

If any tests fail, update them to match the new `load_config` signature.

- [ ] **Step 2: Run full test suite**

Run: `make check`
Expected: All PASS

- [ ] **Step 3: Commit (only if changes were needed)**

```bash
git add tests/conftest.py tests/test_cli.py
git commit -m "fix: update test fixtures for multi-project config"
```

---

### Task 9: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md to document init command**

Add the `scaffold init` command to the Key Commands section and document the multi-project config structure. In the Architecture section, add `init.py` to the module list.

In the Architecture list, after the `preflight.py` line, add:

```
  - **init.py** — project initialization: detection display, interview, CLAUDE.md generation
```

In the Key Commands code block, after the `scaffold preflight` line, add:

```
scaffold init /path/to/repo --config config/   # Initialize a target repo
```

In the Configuration section, update the `project.yaml` subsection:

```markdown
### project.yaml

Per-project config in `config/projects/{name}.yaml`. Keys: `repo_path`, `branch_prefix`, `max_concurrent_agents`, `db_path`.

Legacy: a single `config/project.yaml` is supported for backward compatibility when `--project` is not provided.

Credentials are NOT stored in config files — use environment variables.
```

- [ ] **Step 2: Run make check**

Run: `make check`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document scaffold init and multi-project config"
```
