import json
from pathlib import Path

from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.state import TaskState

# Maps detected language to default specialist name
LANGUAGE_TO_SPECIALIST: dict[str, str] = {
    "python": "python-expert",
    "go": "go-expert",
    "typescript": "typescript-expert",
    "javascript": "typescript-expert",
}

# Keywords in file/directory paths that trigger security-auditor
_SECURITY_TRIGGERS = {"auth", "security", "jwt", "oauth"}

# Package-level deps in pyproject.toml that signal a database
_DB_PYPROJECT_KEYWORDS = {"psycopg", "psycopg2", "postgres", "sqlalchemy"}

# go.mod keywords that signal a database
_DB_GO_KEYWORDS = {"pgx", "postgres", "pq"}

# JS/TS frameworks detected from package.json dependencies
_JS_FRAMEWORKS = {"react", "next", "vue", "angular", "svelte", "nuxt", "remix"}

# Python frameworks detected from pyproject.toml dependencies
_PY_FRAMEWORKS = {"fastapi", "django", "flask", "sqlalchemy"}


# ---------------------------------------------------------------------------
# detect_project
# ---------------------------------------------------------------------------


def detect_project(repo_path: Path) -> dict:
    """Inspect repo_path and return a dict describing the project."""
    detected_languages: list[str] = []
    detected_frameworks: list[str] = []
    test_framework: str = ""
    has_makefile: bool = False
    has_database: bool = False
    claude_md_quality: str = "missing"
    project_context: str = ""

    # ---- Makefile ----
    if (repo_path / "Makefile").exists():
        has_makefile = True

    # ---- CLAUDE.md ----
    claude_md = repo_path / "CLAUDE.md"
    if claude_md.exists():
        text = claude_md.read_text()
        lines = text.splitlines()
        claude_md_quality = "substantive" if len(lines) >= 50 else "thin"
        project_context = text

    # ---- Python ----
    pyproject_text: str | None = None
    if (repo_path / "pyproject.toml").exists():
        detected_languages.append("python")
        pyproject_text = (repo_path / "pyproject.toml").read_text()
    elif (repo_path / "setup.py").exists() or (repo_path / "requirements.txt").exists():
        detected_languages.append("python")
        if (repo_path / "requirements.txt").exists():
            pyproject_text = None  # use requirements.txt path below

    # ---- Go ----
    go_mod_text: str | None = None
    if (repo_path / "go.mod").exists():
        detected_languages.append("go")
        go_mod_text = (repo_path / "go.mod").read_text()

    # ---- TypeScript ----
    if (repo_path / "tsconfig.json").exists():
        detected_languages.append("typescript")

    # ---- JavaScript (package.json without tsconfig) ----
    pkg_json_text: str | None = None
    if (repo_path / "package.json").exists():
        pkg_json_text = (repo_path / "package.json").read_text()
        if "typescript" not in detected_languages:
            detected_languages.append("javascript")

    # ---- Frameworks from package.json ----
    if pkg_json_text:
        try:
            pkg = json.loads(pkg_json_text)
        except json.JSONDecodeError:
            pkg = {}
        all_deps: set[str] = set()
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            all_deps.update(pkg.get(key, {}).keys())
        for dep in all_deps:
            dep_lower = dep.lower()
            for fw in _JS_FRAMEWORKS:
                exact = dep_lower == fw
                prefixed = dep_lower.startswith(f"{fw}-") or dep_lower.startswith(f"@{fw}/")
                if (exact or prefixed) and fw not in detected_frameworks:
                    detected_frameworks.append(fw)

    # ---- Frameworks from pyproject.toml ----
    if pyproject_text:
        text_lower = pyproject_text.lower()
        for fw in _PY_FRAMEWORKS:
            if fw in text_lower and fw not in detected_frameworks:
                detected_frameworks.append(fw)

    # ---- Test framework ----
    # pytest: [tool.pytest] section, conftest.py, or pytest.ini
    pytest_in_pyproject = pyproject_text is not None and "[tool.pytest" in pyproject_text
    pytest_via_files = (repo_path / "conftest.py").exists() or (repo_path / "pytest.ini").exists()
    if pytest_in_pyproject or pytest_via_files:
        test_framework = "pytest"

    if not test_framework and pkg_json_text:
        try:
            pkg = json.loads(pkg_json_text)
        except json.JSONDecodeError:
            pkg = {}
        dev_deps = set(pkg.get("devDependencies", {}).keys())
        if "vitest" in dev_deps:
            test_framework = "vitest"
        elif "jest" in dev_deps:
            test_framework = "jest"

    if not test_framework and "go" in detected_languages and list(repo_path.rglob("*_test.go")):
        test_framework = "go test"

    # ---- Database detection ----
    # pyproject.toml deps
    if pyproject_text:
        text_lower = pyproject_text.lower()
        if any(kw in text_lower for kw in _DB_PYPROJECT_KEYWORDS):
            has_database = True

    # requirements.txt
    if not has_database and (repo_path / "requirements.txt").exists():
        req_text = (repo_path / "requirements.txt").read_text().lower()
        if any(kw in req_text for kw in _DB_PYPROJECT_KEYWORDS):
            has_database = True

    # go.mod
    if not has_database and go_mod_text:
        text_lower = go_mod_text.lower()
        if any(kw in text_lower for kw in _DB_GO_KEYWORDS):
            has_database = True

    # package.json
    if not has_database and pkg_json_text:
        try:
            pkg = json.loads(pkg_json_text)
        except json.JSONDecodeError:
            pkg = {}
        all_deps_str = " ".join(
            list(pkg.get("dependencies", {}).keys()) + list(pkg.get("devDependencies", {}).keys())
        ).lower()
        if any(kw in all_deps_str for kw in {"pg", "postgres", "mysql", "sqlite", "prisma"}):
            has_database = True

    # .sql files anywhere in repo
    if not has_database and list(repo_path.rglob("*.sql")):
        has_database = True

    return {
        "repo_path": repo_path,
        "detected_languages": detected_languages,
        "detected_frameworks": detected_frameworks,
        "test_framework": test_framework,
        "has_makefile": has_makefile,
        "has_database": has_database,
        "claude_md_quality": claude_md_quality,
        "project_context": project_context,
    }


# ---------------------------------------------------------------------------
# make_onboarding_node
# ---------------------------------------------------------------------------


def _has_security_paths(repo_path: Path) -> bool:
    """Return True if any file or directory name under repo_path contains a security keyword."""
    for item in repo_path.rglob("*"):
        name_lower = item.name.lower()
        # strip extension for file names
        stem_lower = item.stem.lower()
        if any(kw in name_lower or kw in stem_lower for kw in _SECURITY_TRIGGERS):
            return True
    return False


def make_onboarding_node(repo_path: str, agents_dir: Path):
    """Return a LangGraph-compatible node function for project onboarding."""
    _repo_path = Path(repo_path)
    loader = AgentLoader(agents_dir)

    def onboarding_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("onboarding", state["task_id"], state["level"])

        if state.get("specialists"):
            if bus:
                bus.node_exit(
                    "onboarding",
                    state["task_id"],
                    "passthrough (context inherited)",
                )
            return {}

        detection = detect_project(_repo_path)
        available = loader.list_specialists()

        languages = detection["detected_languages"]
        frameworks = detection["detected_frameworks"]

        # Build primary specialists list
        specialists: list[str] = []
        seen: set[str] = set()
        for lang in languages:
            candidate = LANGUAGE_TO_SPECIALIST.get(lang)
            if candidate is None:
                continue
            # typescript + react → use react-expert instead
            if lang == "typescript" and "react" in frameworks:
                candidate = "react-expert"
            if candidate in available and candidate not in seen:
                specialists.append(candidate)
                seen.add(candidate)

        # Build advisory specialists list
        advisory: list[str] = []

        if detection["has_database"] and "postgres-expert" in available:
            advisory.append("postgres-expert")

        has_security = _has_security_paths(_repo_path)
        auditor_available = "security-auditor" in available and "security-auditor" not in advisory
        if has_security and auditor_available:
            advisory.append("security-auditor")

        result = {
            "specialists": specialists,
            "advisory": advisory,
            "project_context": detection["project_context"],
            "detected_languages": languages,
            "test_framework": detection["test_framework"],
        }
        if bus:
            bus.node_exit(
                "onboarding",
                state["task_id"],
                f"langs={languages} specialists={specialists} advisory={advisory}",
            )
        return result

    return onboarding_node
