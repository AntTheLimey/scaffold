import subprocess

from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.json_utils import extract_json
from orchestrator.state import TaskState

REVIEW_PROMPT = (
    "You are a code review engine. Review the git diff for correctness, style, "
    "security, and adherence to the acceptance criteria. Output valid JSON with "
    "keys: verdict ('approve' or 'revise'), feedback (str — empty if approved, "
    "specific revision instructions if revise)."
)


def make_reviewer_node(repo_path: str, branch_prefix: str, model: str, agent_loader: AgentLoader):
    def reviewer_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("reviewer", state["task_id"])
        branch = f"{branch_prefix}/{state['task_id']}"

        base_prompt = agent_loader.load_workflow_agent("reviewer") or REVIEW_PROMPT

        project_context = state.get("project_context", "")
        if project_context:
            base_prompt = f"{base_prompt}\n\n{project_context}"

        prompt = (
            f"{base_prompt}\n\n"
            f"Task: {state['task_id']}\n"
            f"Review the current changes on branch '{branch}'."
        )

        if bus:
            bus.cli_start("reviewer", model, 1, state["task_id"])
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=300,
        )

        parsed = extract_json(result.stdout)
        verdict = parsed.get("verdict", "revise")
        feedback = parsed.get("feedback", "")
        if bus:
            bus.cli_done("reviewer", 1, verdict == "approve", state["task_id"])

        if verdict == "approve":
            if bus:
                bus.node_exit("reviewer", state["task_id"], "approved")
            return {
                "verdict": "approve",
                "feedback": "",
                "status": "testing",
                "agent_output": result.stdout,
            }
        if bus:
            bus.node_exit(
                "reviewer",
                state["task_id"],
                f"revise cycle={state['review_cycles'] + 1}",
            )
        return {
            "verdict": "revise",
            "feedback": feedback,
            "review_cycles": state["review_cycles"] + 1,
            "agent_output": result.stdout,
        }

    return reviewer_node
