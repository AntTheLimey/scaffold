from orchestrator.nodes.base import DoerAgent
from orchestrator.state import TaskState


def make_qa_node(repo_path: str, model: str):
    def qa_node(state: TaskState) -> dict:
        doer = DoerAgent(
            role="qa",
            model=model,
            max_iterations=8,
            completion_promise="TESTS PASSING",
        )

        branch = f"scaffold/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)

        prompt = (
            f"Write and run tests for this task. Validate the acceptance criteria. "
            f"When all tests pass, output 'TESTS PASSING'.\n\n"
            f"Task: {state['task_id']}\n"
        )

        result = doer.ralph_loop(worktree_path=worktree_path, prompt=prompt)

        if result.success:
            return {
                "verdict": "pass",
                "status": "done",
                "feedback": "",
                "agent_output": result.output,
            }
        return {
            "verdict": "fail",
            "feedback": result.output,
            "bug_cycles": state["bug_cycles"] + 1,
            "agent_output": result.output,
        }

    return qa_node
