from orchestrator.agent_loader import AgentLoader
from orchestrator.json_utils import extract_json
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a technical architecture engine. You produce data models, API contracts, "
    "component boundaries, and file structure. You approve or reject technical approaches. "
    "You never write implementation code — that is the Developer's job.\n\n"
    "Output valid JSON with keys: technical_design (str), has_ui_component (bool), "
    "children (list of {title, level, spec_ref, acceptance})."
)


def make_architect_node(client, agent_loader: AgentLoader):
    agent = AdvisorAgent(
        role="architect",
        model="claude-opus-4-6",
        client=client,
    )

    def architect_node(state: TaskState) -> dict:
        system_prompt = agent_loader.load_workflow_agent("architect")
        if not system_prompt:
            system_prompt = SYSTEM_PROMPT
        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        user_message = (
            f"Design the technical approach for this feature.\n\n"
            f"Task: {state['task_id']}\n"
            f"Level: {state['level']}\n"
        )

        result = agent.call(
            system_prompt=system_prompt,
            user_message=user_message,
            cache_system=True,
        )

        parsed = extract_json(result.text)
        return {
            "has_ui_component": parsed.get("has_ui_component", False),
            "child_tasks": parsed.get("children", []),
            "status": "decomposing",
            "agent_output": result.text,
        }

    return architect_node
