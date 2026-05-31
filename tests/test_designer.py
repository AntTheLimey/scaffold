from unittest.mock import MagicMock, patch

import pytest

from orchestrator.budget import BudgetExceededError
from orchestrator.nodes.designer import make_designer_node
from orchestrator.state import initial_state


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text="Clock component: SVG circle, 4/6/8/12 segments. "
            "Click to fill/unfill. Animate on tick."
        )
    ]
    response.usage.input_tokens = 400
    response.usage.output_tokens = 200
    client.messages.create.return_value = response
    return client


@pytest.fixture
def mock_agent_loader():
    loader = MagicMock()
    loader.load_workflow_agent.return_value = ""
    return loader


def test_designer_produces_ui_spec(mock_client, mock_agent_loader):
    node_fn = make_designer_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    result = node_fn(state)
    assert "Clock component" in result["agent_output"]


def test_designer_uses_sonnet(mock_client, mock_agent_loader):
    node_fn = make_designer_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "sonnet" in call_args.kwargs["model"]


def test_designer_uses_agent_loader_prompt(mock_client, mock_agent_loader):
    mock_agent_loader.load_workflow_agent.return_value = "Custom designer prompt."
    node_fn = make_designer_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    node_fn(state)
    mock_agent_loader.load_workflow_agent.assert_called_once_with("designer")
    call_args = mock_client.messages.create.call_args
    system_arg = call_args.kwargs["system"]
    system_text = system_arg[0]["text"] if isinstance(system_arg, list) else system_arg
    assert "Custom designer prompt." in system_text


def test_designer_appends_project_context(mock_client, mock_agent_loader):
    node_fn = make_designer_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    state["project_context"] = "A VTT platform for tabletop games."
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    system_arg = call_args.kwargs["system"]
    system_text = system_arg[0]["text"] if isinstance(system_arg, list) else system_arg
    assert "A VTT platform for tabletop games." in system_text


def test_designer_checks_budget_after_api_call(mock_client, mock_agent_loader):
    mock_bus = MagicMock()
    mock_bus.check_budget.side_effect = BudgetExceededError(spent=6.0, limit=5.0)
    with patch("orchestrator.nodes.designer.get_bus", return_value=mock_bus):
        node_fn = make_designer_node(mock_client, mock_agent_loader, scaffold_budget_usd=5.0)
        state = initial_state(task_id="task-ui-001", level="task")
        with pytest.raises(BudgetExceededError):
            node_fn(state)
    mock_bus.check_budget.assert_called_once_with(5.0)


def test_designer_no_budget_check_when_none(mock_client, mock_agent_loader):
    mock_bus = MagicMock()
    with patch("orchestrator.nodes.designer.get_bus", return_value=mock_bus):
        node_fn = make_designer_node(mock_client, mock_agent_loader)
        state = initial_state(task_id="task-ui-001", level="task")
        node_fn(state)
    mock_bus.check_budget.assert_not_called()


def test_designer_passes_tools_to_advisor(mock_client, mock_agent_loader):
    node_fn = make_designer_node(mock_client, mock_agent_loader, repo_path="/tmp/repo")
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "tools" in call_args.kwargs
    tool_names = {t["name"] for t in call_args.kwargs["tools"]}
    assert tool_names == {"read_file", "list_directory", "grep"}
