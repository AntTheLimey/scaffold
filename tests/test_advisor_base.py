from unittest.mock import MagicMock

import pytest

from orchestrator.nodes.base import AdvisorAgent


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text="Here is my analysis.")]
    response.usage.input_tokens = 500
    response.usage.output_tokens = 200
    client.messages.create.return_value = response
    return client


def test_advisor_call(mock_client):
    agent = AdvisorAgent(
        role="product_owner",
        model="claude-opus-4-20250514",
        client=mock_client,
    )
    result = agent.call(
        system_prompt="You are a product decomposition engine.",
        user_message="Decompose this spec into epics.",
    )
    assert result.text == "Here is my analysis."
    assert result.token_in == 500
    assert result.token_out == 200


def test_advisor_uses_correct_model(mock_client):
    agent = AdvisorAgent(
        role="architect",
        model="claude-opus-4-20250514",
        client=mock_client,
    )
    agent.call(system_prompt="Design.", user_message="Design the schema.")
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == "claude-opus-4-20250514"


def test_advisor_passes_system_prompt(mock_client):
    agent = AdvisorAgent(
        role="architect",
        model="claude-opus-4-20250514",
        client=mock_client,
    )
    agent.call(system_prompt="You are an architect.", user_message="Design.")
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["system"] == "You are an architect."


def test_advisor_with_cache_control(mock_client):
    agent = AdvisorAgent(
        role="product_owner",
        model="claude-opus-4-20250514",
        client=mock_client,
    )
    agent.call(
        system_prompt="You are a PO.",
        user_message="Decompose.",
        cache_system=True,
    )
    call_args = mock_client.messages.create.call_args
    system_arg = call_args.kwargs["system"]
    assert isinstance(system_arg, list)
    assert system_arg[0]["cache_control"] == {"type": "ephemeral"}
