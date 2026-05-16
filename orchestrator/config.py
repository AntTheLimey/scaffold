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
    max_budget_usd: float | None = None


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
                f"Project '{project}' not found at {project_path}. Run 'scaffold init' first."
            )
        with open(project_path) as f:
            proj_data = yaml.safe_load(f)
    else:
        with open(config_dir / "project.yaml") as f:
            proj_data = yaml.safe_load(f)
    project_cfg = ProjectConfig(**proj_data)

    return ScaffoldConfig(governance=governance, agents=agents, project=project_cfg)
