from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a UI/UX specification engine. You produce layouts, interaction patterns, "
    "responsive behavior descriptions, and component specifications. "
    "You never write code — that is the Developer's job."
)


def make_designer_node(client, agent_loader: AgentLoader, model: str = "claude-sonnet-4-6"):
    agent = AdvisorAgent(
        role="designer",
        model=model,
        client=client,
    )

    def designer_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("designer", state["task_id"])
        system_prompt = agent_loader.load_workflow_agent("designer")
        if not system_prompt:
            system_prompt = SYSTEM_PROMPT
        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        user_message = f"Create a UI/UX specification for this task.\n\nTask: {state['task_id']}\n"
        if bus:
            bus.api_call_start(
                "designer", model, len(system_prompt) + len(user_message), state["task_id"]
            )
        result = agent.call(system_prompt=system_prompt, user_message=user_message)
        if bus:
            bus.api_call_done(
                "designer", model, result.token_in, result.token_out, state["task_id"]
            )
            bus.node_exit("designer", state["task_id"])
        return {"agent_output": result.text}

    return designer_node
