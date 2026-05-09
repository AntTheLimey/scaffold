from pathlib import Path

from orchestrator.json_utils import extract_json

from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a product decomposition engine. You break master specifications "
    "into discrete, implementable work items. You define acceptance criteria "
    "for each item. You never prescribe implementation details — that is the "
    "Architect's job. You never write code.\n\n"
    "Output valid JSON with a single key 'children', containing a list of objects. "
    "Each object has: title (str), level ('feature' or 'task'), spec_ref (str), "
    "acceptance (list[str])."
)


def make_product_owner_node(client, spec_path: str):
    agent = AdvisorAgent(
        role="product_owner",
        model="claude-opus-4-20250514",
        client=client,
    )

    def product_owner_node(state: TaskState) -> dict:
        spec_content = ""
        spec_file = Path(spec_path)
        if spec_file.exists():
            spec_content = spec_file.read_text()

        user_message = (
            f"Decompose this into child work items.\n\n"
            f"Task: {state['task_id']}\n"
            f"Level: {state['level']}\n\n"
            f"Master Spec:\n{spec_content}"
        )

        result = agent.call(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            cache_system=True,
        )

        parsed = extract_json(result.text)
        return {
            "child_tasks": parsed.get("children", []),
            "status": "decomposing",
            "agent_output": result.text,
        }

    return product_owner_node
