from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class GovernanceConfig:
    rapid: dict[str, dict[str, str]]
    raci: dict[str, dict[str, str | list[str]]]


@dataclass
class AgentsConfig:
    roles: dict[str, dict]


@dataclass
class ProjectConfig:
    repo_path: str
    branch_prefix: str = "scaffold"
    max_concurrent_agents: int = 3
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    db_path: str = "scaffold.db"
    spec_path: str = ""


@dataclass
class ScaffoldConfig:
    governance: GovernanceConfig
    agents: AgentsConfig
    project: ProjectConfig


def load_config(config_dir: str | Path) -> ScaffoldConfig:
    config_dir = Path(config_dir)

    with open(config_dir / "governance.yaml") as f:
        gov_data = yaml.safe_load(f)
    governance = GovernanceConfig(
        rapid=gov_data.get("rapid", {}),
        raci=gov_data.get("raci", {}),
    )

    with open(config_dir / "agents.yaml") as f:
        agents_data = yaml.safe_load(f)
    agents = AgentsConfig(roles=agents_data.get("roles", {}))

    with open(config_dir / "project.yaml") as f:
        proj_data = yaml.safe_load(f)
    project = ProjectConfig(**proj_data)

    return ScaffoldConfig(governance=governance, agents=agents, project=project)
