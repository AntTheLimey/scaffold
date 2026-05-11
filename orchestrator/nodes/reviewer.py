import subprocess

from orchestrator.agent_loader import AgentLoader
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

        if verdict == "approve":
            return {
                "verdict": "approve",
                "feedback": "",
                "status": "testing",
                "agent_output": result.stdout,
            }
        return {
            "verdict": "revise",
            "feedback": feedback,
            "review_cycles": state["review_cycles"] + 1,
            "agent_output": result.stdout,
        }

    return reviewer_node
