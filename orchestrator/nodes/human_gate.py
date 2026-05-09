from langgraph.types import interrupt

from orchestrator.state import TaskState
from orchestrator.telegram import TelegramBot


def make_human_gate_node(bot: TelegramBot):
    def human_gate_node(state: TaskState) -> dict:
        reason = state.get("escalation_reason", "Unknown escalation")
        options = ["Approve", "Revise", "Override", "Cancel"]

        bot.send_escalation(
            question=f"Task {state['task_id']}: {reason}",
            options=options,
            task_id=state["task_id"],
        )

        response = interrupt({
            "question": reason,
            "options": options,
            "task_id": state["task_id"],
        })

        return {
            "verdict": response.get("choice", ""),
            "escalation_reason": None,
            "agent_output": f"Human decided: {response}",
        }

    return human_gate_node
