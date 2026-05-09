from unittest.mock import MagicMock

import pytest

from orchestrator.nodes.human_gate import make_human_gate_node
from orchestrator.state import initial_state


def test_human_gate_sends_escalation_before_interrupt():
    bot = MagicMock()
    bot.send_escalation.return_value = 42
    node_fn = make_human_gate_node(bot)
    state = initial_state(task_id="task-001", level="task")
    state["escalation_reason"] = "Review cycle hit 3 revisions"

    with pytest.raises(RuntimeError):
        node_fn(state)
    bot.send_escalation.assert_called_once()
    call_args = bot.send_escalation.call_args
    question = call_args.kwargs.get("question", call_args.args[0] if call_args.args else "")
    assert "3 revisions" in question
