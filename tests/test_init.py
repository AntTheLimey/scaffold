import yaml

from orchestrator.init import (
    derive_project_name,
    detect_code_style,
    extract_makefile_targets,
    format_detection,
    generate_claude_md,
    generate_project_yaml,
)


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


def test_detect_code_style_ruff(tmp_path):
    ruff_toml = tmp_path / "ruff.toml"
    ruff_toml.write_text('line-length = 100\ntarget-version = "py312"\n')
    style = detect_code_style(tmp_path)
    assert "ruff" in style.lower()
    assert "100" in style


def test_detect_code_style_pyproject_ruff(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.ruff]\nline-length = 88\n")
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
    assert "pytest" in content
    assert "install" in content
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
