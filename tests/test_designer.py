from unittest.mock import MagicMock

import pytest

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
