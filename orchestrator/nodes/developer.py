from orchestrator.nodes.base import DoerAgent
from orchestrator.state import TaskState


def make_developer_node(repo_path: str, branch_prefix: str, model: str):
    def developer_node(state: TaskState) -> dict:
        doer = DoerAgent(
            role="developer",
            model=model,
            max_iterations=10,
            completion_promise="TASK COMPLETE",
        )

        branch = f"{branch_prefix}/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)

        prompt = (
            f"Implement the following task. When complete, output 'TASK COMPLETE'.\n\n"
            f"Task: {state['task_id']}\n"
        )

        failure_context = ""
        if state.get("feedback"):
            failure_context = (
                f"Previous review feedback:\n{state['feedback']}\n"
                "Address this feedback in your implementation."
            )
            prompt += f"\n\nReview feedback to address:\n{state['feedback']}"

        result = doer.ralph_loop(
            worktree_path=worktree_path,
            prompt=prompt,
            failure_context=failure_context,
        )

        if result.success:
            return {
                "status": "in_review",
                "verdict": "",
                "feedback": "",
                "agent_output": result.output,
            }
        return {
            "status": "stuck",
            "agent_output": result.output,
        }

    return developer_node
