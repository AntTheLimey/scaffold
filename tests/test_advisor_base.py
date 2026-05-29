from unittest.mock import MagicMock, patch

import pytest

from orchestrator.nodes.base import AdvisorAgent, AgentResult


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


def test_advisor_result_has_cost_usd_field():
    result = AgentResult(text="ok", token_in=100, token_out=50)
    assert hasattr(result, "cost_usd")
    assert isinstance(result.cost_usd, float)


def test_advisor_cost_computed_for_known_model(mock_client):
    # mock returns 500 input + 200 output tokens; claude-opus-4-6 = $15/$75 per MTok
    expected = (500 * 15.0 + 200 * 75.0) / 1_000_000
    agent = AdvisorAgent(role="architect", model="claude-opus-4-6", client=mock_client)
    result = agent.call(system_prompt="Design.", user_message="Design the schema.")
    assert result.cost_usd == pytest.approx(expected)


def test_advisor_unknown_model_cost_is_zero(mock_client):
    agent = AdvisorAgent(role="product_owner", model="claude-unknown-future-9", client=mock_client)
    result = agent.call(system_prompt="You are a PO.", user_message="Decompose.")
    assert result.cost_usd == 0.0


# ---------------------------------------------------------------------------
# Multi-turn tool loop helpers
# ---------------------------------------------------------------------------


def _make_tool_use_response(tool_name, tool_id, tool_input, token_in=300, token_out=100):
    response = MagicMock()
    response.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.id = tool_id
    tool_block.input = tool_input
    response.content = [tool_block]
    response.usage.input_tokens = token_in
    response.usage.output_tokens = token_out
    return response


def _make_text_response(text, token_in=200, token_out=150):
    response = MagicMock()
    response.stop_reason = "end_of_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    response.content = [text_block]
    response.usage.input_tokens = token_in
    response.usage.output_tokens = token_out
    return response


# ---------------------------------------------------------------------------
# Multi-turn tool loop tests
# ---------------------------------------------------------------------------


def test_advisor_call_without_tools_unchanged(mock_client):
    """No-tools path: single API call and 'tools' kwarg must not be passed."""
    agent = AdvisorAgent(role="architect", model="claude-opus-4-20250514", client=mock_client)
    result = agent.call(system_prompt="Design.", user_message="Design the schema.")
    assert mock_client.messages.create.call_count == 1
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "tools" not in call_kwargs
    assert result.text == "Here is my analysis."


def test_advisor_single_turn_tool_use():
    """One tool call followed by a text response."""
    client = MagicMock()
    tool_resp = _make_tool_use_response(
        "read_file", "tid1", {"path": "main.py"}, token_in=300, token_out=100
    )
    text_resp = _make_text_response("Done reading.", token_in=200, token_out=150)
    client.messages.create.side_effect = [tool_resp, text_resp]

    executor = MagicMock(return_value="# file contents")
    agent = AdvisorAgent(role="coder", model="claude-opus-4-20250514", client=client)
    tools = [{"name": "read_file", "description": "Read a file"}]
    result = agent.call(
        system_prompt="You are a coder.",
        user_message="Read main.py",
        tools=tools,
        tool_executor=executor,
    )

    assert result.text == "Done reading."
    assert client.messages.create.call_count == 2
    executor.assert_called_once_with("read_file", {"path": "main.py"})
    assert result.token_in == 500  # 300 + 200
    assert result.token_out == 250  # 100 + 150


def test_advisor_multi_turn_tool_use():
    """Three API calls: list_directory, read_file, then final text."""
    client = MagicMock()
    resp1 = _make_tool_use_response(
        "list_directory", "t1", {"path": "."}, token_in=400, token_out=120
    )
    resp2 = _make_tool_use_response(
        "read_file", "t2", {"path": "app.py"}, token_in=500, token_out=200
    )
    resp3 = _make_text_response("Analysis complete.", token_in=300, token_out=200)
    client.messages.create.side_effect = [resp1, resp2, resp3]

    executor = MagicMock(side_effect=["[app.py]", "# app source"])
    agent = AdvisorAgent(role="reviewer", model="claude-opus-4-20250514", client=client)
    tools = [
        {"name": "list_directory", "description": "List directory"},
        {"name": "read_file", "description": "Read a file"},
    ]
    result = agent.call(
        system_prompt="Review the code.",
        user_message="Analyse the repo.",
        tools=tools,
        tool_executor=executor,
    )

    assert result.text == "Analysis complete."
    assert client.messages.create.call_count == 3
    assert executor.call_count == 2
    assert result.token_in == 1200  # 400 + 500 + 300
    assert result.token_out == 520  # 120 + 200 + 200


def test_advisor_max_turns_cap():
    """When max_turns is exhausted the method returns without infinite loop."""
    client = MagicMock()
    client.messages.create.return_value = _make_tool_use_response(
        "read_file", "t1", {"path": "x.py"}
    )
    executor = MagicMock(return_value="content")
    agent = AdvisorAgent(role="coder", model="claude-opus-4-20250514", client=client)
    tools = [{"name": "read_file", "description": "Read a file"}]
    result = agent.call(
        system_prompt="Code.",
        user_message="Go.",
        tools=tools,
        tool_executor=executor,
        max_turns=2,
    )
    assert client.messages.create.call_count == 2
    assert isinstance(result.text, str)


def test_advisor_tool_loop_emits_tool_call_events():
    """tool.call events are emitted via the event bus for each tool invocation."""
    client = MagicMock()
    resp1 = _make_tool_use_response("search_code", "t1", {"query": "def main"})
    resp2 = _make_tool_use_response("read_file", "t2", {"path": "main.py"})
    resp3 = _make_text_response("Found it.")
    client.messages.create.side_effect = [resp1, resp2, resp3]

    executor = MagicMock(return_value="result")
    mock_bus = MagicMock()

    with patch("orchestrator.nodes.base.get_bus", return_value=mock_bus):
        agent = AdvisorAgent(role="analyst", model="claude-opus-4-20250514", client=client)
        tools = [{"name": "search_code"}, {"name": "read_file"}]
        agent.call(
            system_prompt="Analyse.",
            user_message="Find main.",
            tools=tools,
            tool_executor=executor,
            task_id="task-42",
        )

    assert mock_bus.tool_call.call_count == 2
    mock_bus.tool_call.assert_any_call("analyst", "search_code", "task-42")
    mock_bus.tool_call.assert_any_call("analyst", "read_file", "task-42")


def test_advisor_tool_loop_cost_aggregation():
    """Tokens and cost are accumulated correctly across turns for claude-opus-4-6."""
    client = MagicMock()
    resp1 = _make_tool_use_response(
        "read_file", "t1", {"path": "f.py"}, token_in=1000, token_out=500
    )
    resp2 = _make_text_response("Done.", token_in=2000, token_out=800)
    client.messages.create.side_effect = [resp1, resp2]

    executor = MagicMock(return_value="content")
    agent = AdvisorAgent(role="coder", model="claude-opus-4-6", client=client)
    tools = [{"name": "read_file", "description": "Read a file"}]
    result = agent.call(
        system_prompt="Code.",
        user_message="Read f.py",
        tools=tools,
        tool_executor=executor,
    )

    assert result.token_in == 3000  # 1000 + 2000
    assert result.token_out == 1300  # 500 + 800
    # claude-opus-4-6: $15/$75 per MTok
    expected_cost = (3000 * 15.0 + 1300 * 75.0) / 1_000_000
    assert result.cost_usd == pytest.approx(expected_cost)
