from langgraph.types import interrupt

from orchestrator.event_bus import get_bus
from orchestrator.state import TaskState
from orchestrator.telegram import TelegramBot


def make_human_gate_node(bot: TelegramBot):
    def human_gate_node(state: TaskState) -> dict:
        bus = get_bus()
        reason = state.get("escalation_reason", "Unknown escalation")
        if bus:
            bus.node_enter("human_gate", state["task_id"])
            bus.escalation(reason, state["task_id"])
        options = ["Approve", "Revise", "Override", "Cancel"]

        bot.send_escalation(
            question=f"Task {state['task_id']}: {reason}",
            options=options,
            task_id=state["task_id"],
        )

        response = interrupt(
            {
                "question": reason,
                "options": options,
                "task_id": state["task_id"],
            }
        )

        choice = response.get("choice", "")
        if bus:
            bus.node_exit("human_gate", state["task_id"], f"decision={choice}")
        return {
            "verdict": choice,
            "escalation_reason": None,
            "agent_output": f"Human decided: {response}",
        }

    return human_gate_node
