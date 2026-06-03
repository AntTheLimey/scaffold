import functools

from orchestrator.agent_loader import AgentLoader
from orchestrator.artifacts import read_artifact, write_artifact
from orchestrator.event_bus import get_bus
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState
from orchestrator.tools import CODEBASE_TOOLS, execute_tool

SYSTEM_PROMPT = (
    "You are a UI/UX specification engine. You produce layouts, interaction patterns, "
    "responsive behavior descriptions, and component specifications. "
    "You never write code — that is the Developer's job."
)


def make_designer_node(
    client,
    agent_loader: AgentLoader,
    model: str = "claude-sonnet-4-6",
    scaffold_budget_usd: float | None = None,
    repo_path: str = "",
):
    agent = AdvisorAgent(
        role="designer",
        model=model,
        client=client,
    )
    tool_executor = functools.partial(execute_tool, repo_path=repo_path) if repo_path else None
    tools = CODEBASE_TOOLS if repo_path else None

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

        task_spec = read_artifact(repo_path, state["task_id"], "task_spec")
        user_message = f"Create a UI/UX specification for this task.\n\nTask: {state['task_id']}\n"
        if task_spec:
            user_message += f"\n{task_spec}\n"
        if bus:
            bus.api_call_start(
                "designer", model, len(system_prompt) + len(user_message), state["task_id"]
            )
        result = agent.call(
            system_prompt=system_prompt,
            user_message=user_message,
            tools=tools,
            tool_executor=tool_executor,
            task_id=state["task_id"],
        )
        if bus:
            bus.api_call_done(
                "designer", model, result.token_in, result.token_out, state["task_id"]
            )
            if scaffold_budget_usd is not None:
                bus.check_budget(scaffold_budget_usd)
            bus.node_exit("designer", state["task_id"])
        write_artifact(repo_path, state["task_id"], "designer", result.text)
        return {"agent_output": result.text}

    return designer_node
