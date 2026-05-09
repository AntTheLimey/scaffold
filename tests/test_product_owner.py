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


def test_product_owner_decomposes_epic(mock_client):
    node_fn = make_product_owner_node(mock_client, spec_path="/tmp/spec.md")
    state = initial_state(task_id="epic-001", level="epic")
    result = node_fn(state)
    assert len(result["child_tasks"]) == 2
    assert result["child_tasks"][0]["title"] == "Auth System"
    assert result["status"] == "decomposing"


def test_product_owner_calls_opus(mock_client):
    node_fn = make_product_owner_node(mock_client, spec_path="/tmp/spec.md")
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "opus" in call_args.kwargs["model"]


def test_product_owner_includes_spec_in_prompt(mock_client, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Section 12.1\nBuild core platform.")
    node_fn = make_product_owner_node(mock_client, spec_path=str(spec))
    state = initial_state(task_id="epic-001", level="epic")
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    user_msg = call_args.kwargs["messages"][0]["content"]
    assert "Build core platform" in user_msg
