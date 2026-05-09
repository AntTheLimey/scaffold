import pytest
from orchestrator.config import load_config
from orchestrator.router import Router


@pytest.fixture
def router(config_dir):
    cfg = load_config(config_dir)
    return Router(cfg.governance)


def test_route_epic_to_product_owner(router):
    role = router.route_task(level="epic", status="pending")
    assert role == "product_owner"


def test_route_feature_to_architect(router):
    role = router.route_task(level="feature", status="pending")
    assert role == "architect"


def test_route_task_to_developer(router):
    role = router.route_task(level="task", status="ready")
    assert role == "developer"


def test_route_in_review_to_reviewer(router):
    role = router.route_task(level="task", status="in_review")
    assert role == "reviewer"


def test_route_testing_to_qa(router):
    role = router.route_task(level="task", status="testing")
    assert role == "qa"


def test_get_rapid_roles(router):
    roles = router.get_rapid_roles("product_scope")
    assert roles["recommend"] == "product_owner"
    assert roles["agree"] == "architect"
    assert roles["decide"] == "human"


def test_get_accountable_for_activity(router):
    accountable = router.get_accountable("write_code")
    assert accountable == "reviewer"


def test_needs_consensus_when_agree_vetoes(router):
    assert router.needs_consensus("product_scope", vetoed=True) is True


def test_no_consensus_when_agreed(router):
    assert router.needs_consensus("product_scope", vetoed=False) is False
