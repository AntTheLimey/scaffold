import json
from unittest.mock import MagicMock

import pytest

from orchestrator.nodes.product_owner import make_product_owner_node
from orchestrator.state import initial_state


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "children": [
                        {
                            "title": "Auth System",
                            "level": "feature",
                            "spec_ref": "Section 2",
                            "acceptance": ["JWT works"],
                        },
                        {
                            "title": "WebSocket Server",
                            "level": "feature",
                            "spec_ref": "Section 10",
                            "acceptance": ["Clients connect"],
                        },
                    ]
                }
            )
        )
    ]
    response.usage.input_tokens = 800
    response.usage.output_tokens = 300
    client.messages.create.return_value = response
    return client


@pytest.fixture
def mock_agent_loader():
    loader = MagicMock()
    loader.load_workflow_agent.return_value = ""
    return loader


def make_node(mock_client, mock_agent_loader, spec_path="/tmp/spec.md"):
    return make_product_owner_node(mock_client, spec_path=spec_path, agent_loader=mock_agent_loader)


def test_product_owner_decomposes_epic(mock_client, mock_agent_loader):
    node_fn = make_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="epic-001", level="epic")
    result = node_fn(state)
    assert len(result["child_tasks"]) == 2
    assert result["child_tasks"][0]["title"] == "Auth System"
    assert result["status"] == "decomposing"


def test_product_owner_calls_opus(mock_client, mock_agent_loader):
    node_fn = make_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "opus" in call_args.kwargs["model"]


def test_product_owner_includes_spec_in_prompt(mock_client, mock_agent_loader, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Section 12.1\nBuild core platform.")
    node_fn = make_node(mock_client, mock_agent_loader, spec_path=str(spec))
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    user_msg = call_args.kwargs["messages"][0]["content"]
    assert "Build core platform" in user_msg


def test_product_owner_uses_agent_loader_prompt(mock_client, mock_agent_loader):
    mock_agent_loader.load_workflow_agent.return_value = "Custom product owner prompt."
    node_fn = make_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    mock_agent_loader.load_workflow_agent.assert_called_once_with("product_owner")
    call_args = mock_client.messages.create.call_args
    system_arg = call_args.kwargs["system"]
    system_text = system_arg[0]["text"] if isinstance(system_arg, list) else system_arg
    assert "Custom product owner prompt." in system_text


def test_product_owner_appends_project_context(mock_client, mock_agent_loader):
    node_fn = make_node(mock_client, mock_agent_loader)
    state = initial_state(task_id="epic-001", level="epic")
    state["project_context"] = "This project builds a VTT platform."
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    system_arg = call_args.kwargs["system"]
    system_text = system_arg[0]["text"] if isinstance(system_arg, list) else system_arg
    assert "This project builds a VTT platform." in system_text
