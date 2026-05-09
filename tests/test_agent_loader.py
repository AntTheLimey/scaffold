from pathlib import Path

from orchestrator.agent_loader import EXTENSION_TO_SPECIALIST, AgentLoader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_workflow_agent(
    agents_dir: Path, role: str, kb_files: dict[str, str] | None = None
) -> None:
    """Create a minimal workflow agent directory under agents_dir/workflow/<role>/."""
    agent_dir = agents_dir / "workflow" / role
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.md").write_text(f"# {role} agent")
    if kb_files:
        kb_dir = agent_dir / "kb"
        kb_dir.mkdir(exist_ok=True)
        for name, content in kb_files.items():
            (kb_dir / name).write_text(content)


def make_specialist(agents_dir: Path, name: str, kb_files: dict[str, str] | None = None) -> None:
    """Create a minimal specialist directory under agents_dir/specialists/<name>/."""
    agent_dir = agents_dir / "specialists" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.md").write_text(f"# {name} specialist")
    if kb_files:
        kb_dir = agent_dir / "kb"
        kb_dir.mkdir(exist_ok=True)
        for name_f, content in kb_files.items():
            (kb_dir / name_f).write_text(content)


# ---------------------------------------------------------------------------
# load_workflow_agent
# ---------------------------------------------------------------------------


def test_load_workflow_agent_returns_agent_md_and_all_kb(tmp_path):
    agents_dir = tmp_path / "agents"
    make_workflow_agent(
        agents_dir,
        "architect",
        kb_files={
            "design-patterns.md": "Design patterns KB",
            "testing-patterns.md": "Testing KB",
        },
    )
    loader = AgentLoader(agents_dir)
    result = loader.load_workflow_agent("architect")

    assert "# architect agent" in result
    assert "Design patterns KB" in result
    assert "Testing KB" in result
    # sections joined with separator
    assert "---" in result


def test_load_workflow_agent_no_kb(tmp_path):
    agents_dir = tmp_path / "agents"
    make_workflow_agent(agents_dir, "reviewer")
    loader = AgentLoader(agents_dir)
    result = loader.load_workflow_agent("reviewer")

    assert "# reviewer agent" in result


def test_load_workflow_agent_missing_returns_empty_string(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    loader = AgentLoader(agents_dir)
    result = loader.load_workflow_agent("nonexistent")

    assert result == ""


def test_load_workflow_agent_missing_agents_dir_returns_empty_string(tmp_path):
    loader = AgentLoader(tmp_path / "no-such-dir")
    assert loader.load_workflow_agent("anything") == ""


# ---------------------------------------------------------------------------
# load_specialist
# ---------------------------------------------------------------------------


def test_load_specialist_includes_project_claude_md(tmp_path):
    agents_dir = tmp_path / "agents"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "CLAUDE.md").write_text("# Project CLAUDE.md content")

    make_specialist(agents_dir, "python-expert")
    loader = AgentLoader(agents_dir)
    result = loader.load_specialist("python-expert", repo_path, "write some tests")

    assert "# Project CLAUDE.md content" in result


def test_load_specialist_includes_advisory_input(tmp_path):
    agents_dir = tmp_path / "agents"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    make_specialist(agents_dir, "python-expert")
    loader = AgentLoader(agents_dir)
    result = loader.load_specialist(
        "python-expert", repo_path, "implement feature", advisory_input="Use async patterns"
    )

    assert "Use async patterns" in result


def test_load_specialist_includes_task_context(tmp_path):
    agents_dir = tmp_path / "agents"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    make_specialist(agents_dir, "python-expert")
    loader = AgentLoader(agents_dir)
    result = loader.load_specialist("python-expert", repo_path, "refactor the database layer")

    assert "refactor the database layer" in result


def test_load_specialist_includes_project_override(tmp_path):
    agents_dir = tmp_path / "agents"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    override_dir = repo_path / ".claude" / "agents"
    override_dir.mkdir(parents=True)
    (override_dir / "python-expert.md").write_text("Override instructions for python-expert")

    make_specialist(agents_dir, "python-expert")
    loader = AgentLoader(agents_dir)
    result = loader.load_specialist("python-expert", repo_path, "do something")

    assert "Override instructions for python-expert" in result


def test_load_specialist_no_override_still_works(tmp_path):
    agents_dir = tmp_path / "agents"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    make_specialist(agents_dir, "python-expert")
    loader = AgentLoader(agents_dir)
    result = loader.load_specialist("python-expert", repo_path, "do something")

    assert "# python-expert specialist" in result


def test_load_specialist_selects_relevant_kbs(tmp_path):
    agents_dir = tmp_path / "agents"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    make_specialist(
        agents_dir,
        "python-expert",
        kb_files={
            "testing-patterns.md": "Testing KB content",
            "async-patterns.md": "Async KB content",
        },
    )
    loader = AgentLoader(agents_dir)
    # task context mentions "testing" — should match testing-patterns.md
    result = loader.load_specialist("python-expert", repo_path, "write testing utilities")

    assert "Testing KB content" in result
    # async-patterns.md should NOT be included since "async" and "patterns" are not in context
    assert "Async KB content" not in result


def test_load_specialist_falls_back_to_all_kbs_when_no_match(tmp_path):
    agents_dir = tmp_path / "agents"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    make_specialist(
        agents_dir,
        "python-expert",
        kb_files={
            "testing-patterns.md": "Testing KB content",
            "async-patterns.md": "Async KB content",
        },
    )
    loader = AgentLoader(agents_dir)
    # context has no keywords matching either KB stem
    result = loader.load_specialist("python-expert", repo_path, "do something completely unrelated")

    assert "Testing KB content" in result
    assert "Async KB content" in result


def test_load_specialist_falls_back_to_all_kbs_when_no_context(tmp_path):
    agents_dir = tmp_path / "agents"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    make_specialist(
        agents_dir,
        "python-expert",
        kb_files={
            "testing-patterns.md": "Testing KB",
            "async-patterns.md": "Async KB",
        },
    )
    loader = AgentLoader(agents_dir)
    result = loader.load_specialist("python-expert", repo_path, "")

    assert "Testing KB" in result
    assert "Async KB" in result


# ---------------------------------------------------------------------------
# list_specialists
# ---------------------------------------------------------------------------


def test_list_specialists_returns_sorted_names(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    make_specialist(agents_dir, "go-expert")
    make_specialist(agents_dir, "react-expert")

    loader = AgentLoader(agents_dir)
    result = loader.list_specialists()

    assert result == sorted(result)
    assert "python-expert" in result
    assert "go-expert" in result
    assert "react-expert" in result


def test_list_specialists_excludes_dirs_without_agent_md(tmp_path):
    agents_dir = tmp_path / "agents"
    make_specialist(agents_dir, "python-expert")
    # directory without agent.md
    (agents_dir / "specialists" / "orphan").mkdir(parents=True)

    loader = AgentLoader(agents_dir)
    result = loader.list_specialists()

    assert "python-expert" in result
    assert "orphan" not in result


def test_list_specialists_empty_when_no_specialists_dir(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    loader = AgentLoader(agents_dir)
    assert loader.list_specialists() == []


# ---------------------------------------------------------------------------
# detect_specialist
# ---------------------------------------------------------------------------


def test_detect_specialist_py_maps_to_python_expert(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist(["main.py", "utils.py"]) == "python-expert"


def test_detect_specialist_go_maps_to_go_expert(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist(["server.go", "handler.go"]) == "go-expert"


def test_detect_specialist_majority_wins_for_mixed_files(tmp_path):
    loader = AgentLoader(tmp_path)
    files = ["a.py", "b.py", "c.py", "d.go"]
    assert loader.detect_specialist(files) == "python-expert"


def test_detect_specialist_returns_empty_string_for_unknown_extensions(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist(["image.png", "data.csv", "archive.zip"]) == ""


def test_detect_specialist_returns_empty_string_for_empty_list(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist([]) == ""


def test_detect_specialist_tsx_maps_to_react_expert(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist(["App.tsx", "Button.tsx"]) == "react-expert"


def test_detect_specialist_jsx_maps_to_react_expert(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist(["App.jsx"]) == "react-expert"


def test_detect_specialist_ts_maps_to_typescript_expert(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist(["types.ts", "api.ts"]) == "typescript-expert"


def test_detect_specialist_sql_maps_to_postgres_expert(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist(["migration.sql"]) == "postgres-expert"


def test_detect_specialist_md_maps_to_documentation_writer(tmp_path):
    loader = AgentLoader(tmp_path)
    assert loader.detect_specialist(["README.md", "CHANGELOG.md"]) == "documentation-writer"


# ---------------------------------------------------------------------------
# EXTENSION_TO_SPECIALIST constant
# ---------------------------------------------------------------------------


def test_extension_to_specialist_covers_expected_types():
    assert EXTENSION_TO_SPECIALIST[".py"] == "python-expert"
    assert EXTENSION_TO_SPECIALIST[".go"] == "go-expert"
    assert EXTENSION_TO_SPECIALIST[".tsx"] == "react-expert"
    assert EXTENSION_TO_SPECIALIST[".jsx"] == "react-expert"
    assert EXTENSION_TO_SPECIALIST[".ts"] == "typescript-expert"
    assert EXTENSION_TO_SPECIALIST[".sql"] == "postgres-expert"
    assert EXTENSION_TO_SPECIALIST[".md"] == "documentation-writer"
