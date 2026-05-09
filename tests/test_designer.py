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


def test_designer_produces_ui_spec(mock_client):
    node_fn = make_designer_node(mock_client)
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    result = node_fn(state)
    assert "Clock component" in result["agent_output"]


def test_designer_uses_sonnet(mock_client):
    node_fn = make_designer_node(mock_client)
    state = initial_state(task_id="task-ui-001", level="task")
    state["has_ui_component"] = True
    node_fn(state)
    call_args = mock_client.messages.create.call_args
    assert "sonnet" in call_args.kwargs["model"]
