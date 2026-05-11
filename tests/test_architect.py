import json
from unittest.mock import MagicMock

import pytest

from orchestrator.nodes.architect import make_architect_node
from orchestrator.state import initial_state


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "technical_design": "Use JWT with httpOnly cookies. chi middleware.",
                    "has_ui_component": False,
                    "children": [
                        {
                            "title": "Auth middleware",
                            "level": "task",
                            "spec_ref": "Section 2.1",
                            "acceptance": ["JWT validates", "Expired tokens rejected"],
                        },
                    ],
                }
            )
        )
    ]
    response.usage.input_tokens = 600
    response.usage.output_tokens = 400
    client.messages.create.return_value = response
    return client


@pytest.fixture
def mock_agent_loader():
    loader = MagicMock()
    loader.load_workflow_agent.return_value = ""
    return loader


def test_architect_produces_design(mock_client, mock_agent_loader):
    node_fn = make_architect_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="feat-001", level="feature")
    result = node_fn(state)
    assert "technical_design" in result["agent_output"]
    assert result["status"] == "decomposing"


def test_architect_detects_ui_component(mock_client, mock_agent_loader):
    response = MagicMock()
    response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "technical_design": "React component with clock SVG",
                    "has_ui_component": True,
                    "children": [],
                }
            )
        )
    ]
    response.usage.input_tokens = 500
    response.usage.output_tokens = 300
    mock_client.messages.create.return_value = response
    node_fn = make_architect_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="feat-002", level="feature")
    result = node_fn(state)
    assert result["has_ui_component"] is True


def test_architect_creates_implementation_tasks(mock_client, mock_agent_loader):
    node_fn = make_architect_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="feat-001", level="feature")
    result = node_fn(state)
    assert len(result["child_tasks"]) == 1
    assert result["child_tasks"][0]["title"] == "Auth middleware"


def test_architect_uses_agent_loader_prompt(mock_client, mock_agent_loader):
    mock_agent_loader.load_workflow_agent.return_value = "Custom architect prompt."
    node_fn = make_architect_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="feat-001", level="feature")
    node_fn(state)
    mock_agent_loader.load_workflow_agent.assert_called_once_with("architect")
    call_args = mock_client.messages.create.call_args
    system_arg = call_args.kwargs["system"]
    system_text = system_arg[0]["text"] if isinstance(system_arg, list) else system_arg
    assert "Custom architect prompt." in system_text


def test_architect_appends_project_context(mock_client, mock_agent_loader):
    node_fn = make_architect_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="feat-001", level="feature")
    state["project_context"] = "This project builds a VTT platform."
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    system_arg = call_args.kwargs["system"]
    system_text = system_arg[0]["text"] if isinstance(system_arg, list) else system_arg
    assert "This project builds a VTT platform." in system_text
