import json
from pathlib import Path

from orchestrator.nodes.onboarding import (
    detect_project,
    make_onboarding_node,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_specialist(agents_dir: Path, name: str) -> None:
    agent_dir = agents_dir / "specialists" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.md").write_text(f"# {name} specialist")


# ---------------------------------------------------------------------------
# detect_project — language detection
# ---------------------------------------------------------------------------


def test_detect_project_finds_python_via_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'")
    result = detect_project(tmp_path)
    assert "python" in result["detected_languages"]


def test_detect_project_finds_python_via_setup_py(tmp_path):
    (tmp_path / "setup.py").write_text("from setuptools import setup")
    result = detect_project(tmp_path)
    assert "python" in result["detected_languages"]


def test_detect_project_finds_python_via_requirements_txt(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask\nrequests")
    result = detect_project(tmp_path)
    assert "python" in result["detected_languages"]


def test_detect_project_finds_go(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/myapp\ngo 1.21")
    result = detect_project(tmp_path)
    assert "go" in result["detected_languages"]


def test_detect_project_finds_typescript(tmp_path):
    (tmp_path / "tsconfig.json").write_text("{}")
    result = detect_project(tmp_path)
    assert "typescript" in result["detected_languages"]


def test_detect_project_finds_javascript(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "myapp"}))
    result = detect_project(tmp_path)
    assert "javascript" in result["detected_languages"]


def test_detect_project_no_languages_when_empty_dir(tmp_path):
    result = detect_project(tmp_path)
    assert result["detected_languages"] == []


# ---------------------------------------------------------------------------
# detect_project — framework detection
# ---------------------------------------------------------------------------


def test_detect_project_finds_react_from_package_json_deps(tmp_path):
    pkg = {"dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    result = detect_project(tmp_path)
    assert "react" in result["detected_frameworks"]


def test_detect_project_finds_next_from_package_json_deps(tmp_path):
    pkg = {"dependencies": {"next": "^14.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    result = detect_project(tmp_path)
    assert "next" in result["detected_frameworks"]


def test_detect_project_finds_fastapi_from_pyproject(tmp_path):
    content = "[project]\ndependencies = ['fastapi>=0.100']"
    (tmp_path / "pyproject.toml").write_text(content)
    result = detect_project(tmp_path)
    assert "fastapi" in result["detected_frameworks"]


def test_detect_project_finds_django_from_pyproject(tmp_path):
    content = "[project]\ndependencies = ['django>=4.0']"
    (tmp_path / "pyproject.toml").write_text(content)
    result = detect_project(tmp_path)
    assert "django" in result["detected_frameworks"]


def test_detect_project_finds_flask_from_pyproject(tmp_path):
    content = "[project]\ndependencies = ['flask>=2.0']"
    (tmp_path / "pyproject.toml").write_text(content)
    result = detect_project(tmp_path)
    assert "flask" in result["detected_frameworks"]


def test_detect_project_finds_sqlalchemy_from_pyproject(tmp_path):
    content = "[project]\ndependencies = ['sqlalchemy>=2.0']"
    (tmp_path / "pyproject.toml").write_text(content)
    result = detect_project(tmp_path)
    assert "sqlalchemy" in result["detected_frameworks"]


def test_detect_project_no_frameworks_when_empty_dir(tmp_path):
    result = detect_project(tmp_path)
    assert result["detected_frameworks"] == []


# ---------------------------------------------------------------------------
# detect_project — typescript + react combo
# ---------------------------------------------------------------------------


def test_detect_project_typescript_and_react(tmp_path):
    (tmp_path / "tsconfig.json").write_text("{}")
    pkg = {"dependencies": {"react": "^18.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    result = detect_project(tmp_path)
    assert "typescript" in result["detected_languages"]
    assert "react" in result["detected_frameworks"]


# ---------------------------------------------------------------------------
# detect_project — test framework detection
# ---------------------------------------------------------------------------


def test_detect_project_finds_pytest_via_pyproject_tool_section(tmp_path):
    content = "[project]\nname = 'foo'\n\n[tool.pytest.ini_options]\ntestpaths = ['tests']"
    (tmp_path / "pyproject.toml").write_text(content)
    result = detect_project(tmp_path)
    assert result["test_framework"] == "pytest"


def test_detect_project_finds_pytest_via_conftest(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'")
    (tmp_path / "conftest.py").write_text("import pytest")
    result = detect_project(tmp_path)
    assert result["test_framework"] == "pytest"


def test_detect_project_finds_pytest_via_pytest_ini(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = tests")
    result = detect_project(tmp_path)
    assert result["test_framework"] == "pytest"


def test_detect_project_finds_vitest_from_package_json(tmp_path):
    pkg = {"devDependencies": {"vitest": "^1.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    result = detect_project(tmp_path)
    assert result["test_framework"] == "vitest"


def test_detect_project_finds_jest_from_package_json(tmp_path):
    pkg = {"devDependencies": {"jest": "^29.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    result = detect_project(tmp_path)
    assert result["test_framework"] == "jest"


def test_detect_project_finds_go_test_via_test_files(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/myapp\ngo 1.21")
    (tmp_path / "main_test.go").write_text("package main")
    result = detect_project(tmp_path)
    assert result["test_framework"] == "go test"


def test_detect_project_no_test_framework_when_empty_dir(tmp_path):
    result = detect_project(tmp_path)
    assert result["test_framework"] == ""


# ---------------------------------------------------------------------------
# detect_project — Makefile
# ---------------------------------------------------------------------------


def test_detect_project_finds_makefile(tmp_path):
    (tmp_path / "Makefile").write_text("build:\n\tgo build")
    result = detect_project(tmp_path)
    assert result["has_makefile"] is True


def test_detect_project_no_makefile(tmp_path):
    result = detect_project(tmp_path)
    assert result["has_makefile"] is False


# ---------------------------------------------------------------------------
# detect_project — database detection
# ---------------------------------------------------------------------------


def test_detect_project_finds_postgres_via_psycopg_in_pyproject(tmp_path):
    content = "[project]\ndependencies = ['psycopg2-binary>=2.9']"
    (tmp_path / "pyproject.toml").write_text(content)
    result = detect_project(tmp_path)
    assert result["has_database"] is True


def test_detect_project_finds_postgres_via_pgx_in_go_mod(tmp_path):
    content = "module example.com/app\ngo 1.21\n\nrequire github.com/jackc/pgx/v5 v5.5.0"
    (tmp_path / "go.mod").write_text(content)
    result = detect_project(tmp_path)
    assert result["has_database"] is True


def test_detect_project_finds_postgres_via_sql_file(tmp_path):
    (tmp_path / "schema.sql").write_text("CREATE TABLE users (id SERIAL PRIMARY KEY);")
    result = detect_project(tmp_path)
    assert result["has_database"] is True


def test_detect_project_finds_postgres_via_sqlalchemy_in_pyproject(tmp_path):
    content = "[project]\ndependencies = ['sqlalchemy>=2.0']"
    (tmp_path / "pyproject.toml").write_text(content)
    result = detect_project(tmp_path)
    assert result["has_database"] is True


def test_detect_project_no_database_when_clean_repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'hello'\ndependencies = []")
    result = detect_project(tmp_path)
    assert result["has_database"] is False


# ---------------------------------------------------------------------------
# detect_project — CLAUDE.md quality scoring
# ---------------------------------------------------------------------------


def test_detect_project_claude_md_missing(tmp_path):
    result = detect_project(tmp_path)
    assert result["claude_md_quality"] == "missing"


def test_detect_project_claude_md_thin(tmp_path):
    thin_content = "\n".join(["# Project"] + [f"line {i}" for i in range(10)])
    (tmp_path / "CLAUDE.md").write_text(thin_content)
    result = detect_project(tmp_path)
    assert result["claude_md_quality"] == "thin"


def test_detect_project_claude_md_substantive(tmp_path):
    substantive_content = "\n".join([f"line {i}" for i in range(60)])
    (tmp_path / "CLAUDE.md").write_text(substantive_content)
    result = detect_project(tmp_path)
    assert result["claude_md_quality"] == "substantive"


# ---------------------------------------------------------------------------
# detect_project — result structure
# ---------------------------------------------------------------------------


def test_detect_project_returns_repo_path(tmp_path):
    result = detect_project(tmp_path)
    assert result["repo_path"] == tmp_path


def test_detect_project_returns_project_context_from_claude_md(tmp_path):
    content = "\n".join([f"line {i}" for i in range(60)])
    (tmp_path / "CLAUDE.md").write_text(content)
    result = detect_project(tmp_path)
    assert "line 0" in result["project_context"]


def test_detect_project_project_context_empty_when_no_claude_md(tmp_path):
    result = detect_project(tmp_path)
    assert result["project_context"] == ""


# ---------------------------------------------------------------------------
# make_onboarding_node — specialist routing
# ---------------------------------------------------------------------------


def test_onboarding_node_maps_python_to_python_expert(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "python-expert" in result["specialists"]


def test_onboarding_node_maps_go_to_go_expert(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "go-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "go.mod").write_text("module example.com/app\ngo 1.21")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "go-expert" in result["specialists"]


def test_onboarding_node_maps_typescript_to_typescript_expert(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "typescript-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tsconfig.json").write_text("{}")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "typescript-expert" in result["specialists"]


def test_onboarding_node_maps_typescript_with_react_to_react_expert(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "react-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tsconfig.json").write_text("{}")
    pkg = {"dependencies": {"react": "^18.0.0"}}
    (repo / "package.json").write_text(json.dumps(pkg))

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "react-expert" in result["specialists"]
    assert "typescript-expert" not in result["specialists"]


def test_onboarding_node_maps_javascript_to_typescript_expert(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "typescript-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    pkg = {"name": "myapp"}
    (repo / "package.json").write_text(json.dumps(pkg))

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "typescript-expert" in result["specialists"]


def test_onboarding_node_only_includes_existing_specialists(tmp_path):
    agents_dir = tmp_path / "agents"
    # Only create python-expert, NOT go-expert
    make_specialist(agents_dir, "python-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'")
    (repo / "go.mod").write_text("module example.com/app\ngo 1.21")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "python-expert" in result["specialists"]
    assert "go-expert" not in result["specialists"]


# ---------------------------------------------------------------------------
# make_onboarding_node — advisory specialists
# ---------------------------------------------------------------------------


def test_onboarding_node_adds_postgres_expert_when_database_detected(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    make_specialist(agents_dir, "postgres-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\ndependencies = ['psycopg2-binary']")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "postgres-expert" in result["advisory"]


def test_onboarding_node_no_postgres_expert_when_no_database(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    make_specialist(agents_dir, "postgres-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'\ndependencies = []")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "postgres-expert" not in result["advisory"]


def test_onboarding_node_adds_security_auditor_when_auth_path_present(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    make_specialist(agents_dir, "security-auditor")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'")
    auth_dir = repo / "auth"
    auth_dir.mkdir()
    (auth_dir / "login.py").write_text("# auth logic")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "security-auditor" in result["advisory"]


def test_onboarding_node_adds_security_auditor_when_jwt_in_path(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    make_specialist(agents_dir, "security-auditor")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'")
    (repo / "jwt_handler.py").write_text("# jwt logic")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "security-auditor" in result["advisory"]


def test_onboarding_node_no_security_auditor_when_not_available(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    # security-auditor NOT created
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'")
    auth_dir = repo / "auth"
    auth_dir.mkdir()

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "security-auditor" not in result["advisory"]


# ---------------------------------------------------------------------------
# make_onboarding_node — return shape
# ---------------------------------------------------------------------------


def test_onboarding_node_returns_required_keys(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    expected_keys = (
        "specialists",
        "advisory",
        "project_context",
        "detected_languages",
        "test_framework",
    )
    for key in expected_keys:
        assert key in result, f"missing key: {key}"


def test_onboarding_node_loads_project_context_from_claude_md(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'")
    content = "\n".join([f"instruction line {i}" for i in range(60)])
    (repo / "CLAUDE.md").write_text(content)

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "instruction line 0" in result["project_context"]


def test_onboarding_node_includes_detected_languages_in_result(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'foo'")

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert "python" in result["detected_languages"]


def test_onboarding_node_includes_test_framework_in_result(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    repo = tmp_path / "repo"
    repo.mkdir()
    content = "[project]\nname = 'foo'\n\n[tool.pytest.ini_options]\ntestpaths = ['tests']"
    (repo / "pyproject.toml").write_text(content)

    node = make_onboarding_node(str(repo), agents_dir)
    result = node({})

    assert result["test_framework"] == "pytest"
