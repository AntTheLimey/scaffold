from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a UI/UX specification engine. You produce layouts, interaction patterns, "
    "responsive behavior descriptions, and component specifications. "
    "You never write code — that is the Developer's job."
)


def make_designer_node(client):
    agent = AdvisorAgent(
        role="designer",
        model="claude-sonnet-4-20250514",
        client=client,
    )

    def designer_node(state: TaskState) -> dict:
        user_message = f"Create a UI/UX specification for this task.\n\nTask: {state['task_id']}\n"
        result = agent.call(system_prompt=SYSTEM_PROMPT, user_message=user_message)
        return {"agent_output": result.text}

    return designer_node
