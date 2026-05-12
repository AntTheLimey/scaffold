import re
from pathlib import Path

import click
import yaml

from orchestrator.nodes.onboarding import detect_project

# Known names that require non-standard capitalisation.
_KNOWN_NAMES: dict[str, str] = {
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "fastapi": "FastAPI",
    "graphql": "GraphQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "nextjs": "Next.js",
    "nuxtjs": "Nuxt.js",
    "vuejs": "Vue.js",
    "reactjs": "React",
}


def _display_name(name: str) -> str:
    lower = name.lower()
    if lower in _KNOWN_NAMES:
        return _KNOWN_NAMES[lower]
    return name.capitalize()


def format_detection(detection: dict) -> str:
    languages = detection["detected_languages"]
    frameworks = detection["detected_frameworks"]
    test_fw = detection["test_framework"]
    has_db = detection["has_database"]
    has_make = detection["has_makefile"]
    claude_quality = detection["claude_md_quality"]

    lang_str = ", ".join(_display_name(lang) for lang in languages) if languages else "none"
    fw_str = ", ".join(_display_name(fw) for fw in frameworks) if frameworks else "none"
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
        parts = [_display_name(lang) for lang in languages]
        parts += [_display_name(fw) for fw in frameworks]
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


def derive_project_name(repo_path: str) -> str:
    name = Path(repo_path).resolve().name
    return name.lower().replace(" ", "-")


def generate_project_yaml(repo_path: str, project_name: str) -> str:
    data = {
        "repo_path": str(Path(repo_path)),
        "branch_prefix": "scaffold",
        "max_concurrent_agents": 3,
        "db_path": f"scaffold_{project_name}.db",
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def _write_project_yaml(projects_dir: Path, project_name: str, repo_path: str) -> None:
    content = generate_project_yaml(repo_path, project_name)
    (projects_dir / f"{project_name}.yaml").write_text(content)


def _write_project_overrides(repo: Path, interview: dict) -> str | None:
    conventions = interview.get("conventions", "")
    off_limits = interview.get("off_limits", "")
    if not conventions and not off_limits:
        return None
    agents_dir = repo / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if conventions:
        lines.append(f"## Conventions\n\n{conventions}")
    if off_limits:
        lines.append(f"## Off-Limits\n\n{off_limits}")
    content = "\n\n".join(lines) + "\n"
    path = agents_dir / "_project.md"
    path.write_text(content)
    return str(path)


def run_init(repo_path: str, config_dir: str, detection: dict | None = None) -> dict:
    repo = Path(repo_path).resolve()
    config = Path(config_dir)
    projects_dir = config / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    if detection is None:
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

    if claude_md_action in ("create", "overwrite"):
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
    claude_md_lines = len(claude_md_content.splitlines())

    _write_project_yaml(projects_dir, project_name, str(repo))

    overrides_path = _write_project_overrides(repo, interview)

    result = {
        "project_name": project_name,
        "claude_md_action": claude_md_action,
        "claude_md_path": str(claude_md_path),
        "claude_md_lines": claude_md_lines,
        "project_yaml_path": str(projects_dir / f"{project_name}.yaml"),
    }
    if overrides_path:
        result["overrides_path"] = overrides_path
    return result
