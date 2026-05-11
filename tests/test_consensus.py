import json
from unittest.mock import MagicMock

import pytest

from orchestrator.nodes.consensus import make_consensus_node
from orchestrator.state import initial_state


def make_mock_client(responses: list[str]):
    client = MagicMock()
    side_effects = []
    for text in responses:
        resp = MagicMock()
        resp.content = [MagicMock(text=text)]
        resp.usage.input_tokens = 300
        resp.usage.output_tokens = 200
        side_effects.append(resp)
    client.messages.create.side_effect = side_effects
    return client


@pytest.fixture
def mock_agent_loader():
    loader = MagicMock()
    loader.load_workflow_agent.return_value = ""
    return loader


def test_consensus_resolves_on_concession(mock_agent_loader):
    client = make_mock_client(
        [
            json.dumps({"position": "Use REST", "concedes": False}),
            json.dumps({"position": "Use GraphQL", "concedes": False}),
            json.dumps({"position": "REST is fine", "concedes": True}),
        ]
    )
    node_fn = make_consensus_node(client, mock_agent_loader)
    state = initial_state(task_id="task-001", level="task")
    result = node_fn(state)
    assert result["escalation_reason"] is None
    assert "resolved" in result["agent_output"].lower() or result["verdict"] != ""


def test_consensus_escalates_on_deadlock(mock_agent_loader):
    client = make_mock_client(
        [
            json.dumps({"position": "Use REST", "concedes": False}),
            json.dumps({"position": "Use GraphQL", "concedes": False}),
            json.dumps({"position": "Still REST", "concedes": False}),
            json.dumps({"position": "Still GraphQL", "concedes": False}),
        ]
    )
    node_fn = make_consensus_node(client, mock_agent_loader)
    state = initial_state(task_id="task-001", level="task")
    result = node_fn(state)
    assert result["escalation_reason"] is not None
    assert "deadlock" in result["escalation_reason"].lower()


def test_consensus_uses_agent_loader_prompt(mock_agent_loader):
    mock_agent_loader.load_workflow_agent.return_value = "Custom consensus prompt."
    client = make_mock_client(
        [
            json.dumps({"position": "Use REST", "concedes": False}),
            json.dumps({"position": "Use GraphQL", "concedes": True}),
        ]
    )
    node_fn = make_consensus_node(client, mock_agent_loader)
    state = initial_state(task_id="task-001", level="task")
    node_fn(state)
    mock_agent_loader.load_workflow_agent.assert_called_once_with("consensus")
    call_args = client.messages.create.call_args_list[0]
    system_arg = call_args.kwargs["system"]
    system_text = system_arg[0]["text"] if isinstance(system_arg, list) else system_arg
    assert "Custom consensus prompt." in system_text
