from orchestrator.config import ScaffoldConfig, load_config


def test_load_config(config_dir):
    cfg = load_config(config_dir)
    assert isinstance(cfg, ScaffoldConfig)


def test_governance_rapid(config_dir):
    cfg = load_config(config_dir)
    scope = cfg.governance.rapid["product_scope"]
    assert scope["recommend"] == "product_owner"
    assert scope["agree"] == "architect"
    assert scope["decide"] == "human"


def test_governance_raci(config_dir):
    cfg = load_config(config_dir)
    write_code = cfg.governance.raci["write_code"]
    assert write_code["responsible"] == "developer"
    assert write_code["accountable"] == "reviewer"


def test_agent_model_assignment(config_dir):
    cfg = load_config(config_dir)
    po = cfg.agents.roles["product_owner"]
    assert po["model"] == "claude-opus-4-20250514"
    assert po["execution"] == "api"


def test_agent_ralph_config(config_dir):
    cfg = load_config(config_dir)
    dev = cfg.agents.roles["developer"]
    assert dev["max_iterations"] == 10
    assert dev["completion_promise"] == "TASK COMPLETE"


def test_project_config(config_dir):
    cfg = load_config(config_dir)
    assert cfg.project.max_concurrent_agents == 3
    assert cfg.project.branch_prefix == "scaffold"
