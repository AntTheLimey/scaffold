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


def test_agents_config_has_workflow_and_specialists(config_dir):
    cfg = load_config(config_dir)
    assert "product_owner" in cfg.agents.workflow
    assert "architect" in cfg.agents.workflow
    assert "python-expert" in cfg.agents.specialists
    assert "go-expert" in cfg.agents.specialists


def test_agents_config_has_escalation(config_dir):
    cfg = load_config(config_dir)
    escalation = cfg.agents.escalation
    assert escalation["stuck_loop_model"] == "claude-opus-4-6"
    assert escalation["max_review_cycles"] == 3
    assert escalation["max_bug_cycles"] == 3
    assert escalation["cost_threshold_per_run"] == 5.00


def test_workflow_agent_model_assignment(config_dir):
    cfg = load_config(config_dir)
    po = cfg.agents.workflow["product_owner"]
    assert po["model"] == "claude-opus-4-6"
    assert po["execution"] == "api"


def test_specialist_ralph_config(config_dir):
    cfg = load_config(config_dir)
    expert = cfg.agents.specialists["python-expert"]
    assert expert["max_iterations"] == 10
    assert expert["completion_promise"] == "TASK COMPLETE"


def test_project_config(config_dir):
    cfg = load_config(config_dir)
    assert cfg.project.max_concurrent_agents == 3
    assert cfg.project.branch_prefix == "scaffold"


def test_project_config_no_telegram_fields(config_dir):
    cfg = load_config(config_dir)
    assert not hasattr(cfg.project, "telegram_bot_token")
    assert not hasattr(cfg.project, "telegram_chat_id")
    assert not hasattr(cfg.project, "spec_path")
