from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.nodes.base import DoerAgent
from orchestrator.state import TaskState

QA_PROMPT = (
    "Write and run tests for this task. Validate the acceptance criteria. "
    "When all tests pass, output 'TESTS PASSING'."
)


def make_qa_node(repo_path: str, branch_prefix: str, model: str, agent_loader: AgentLoader):
    def qa_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("qa", state["task_id"])
        doer = DoerAgent(
            role="qa",
            model=model,
            max_iterations=8,
            completion_promise="TESTS PASSING",
        )

        branch = f"{branch_prefix}/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)

        base_prompt = agent_loader.load_workflow_agent("qa") or QA_PROMPT

        project_context = state.get("project_context", "")
        if project_context:
            base_prompt = f"{base_prompt}\n\n{project_context}"

        prompt = f"{base_prompt}\n\nTask: {state['task_id']}\n"

        try:
            result = doer.ralph_loop(
                worktree_path=worktree_path, prompt=prompt, task_id=state["task_id"]
            )
        finally:
            doer.cleanup_worktree(repo_path, worktree_path)

        if result.success:
            if bus:
                bus.node_exit("qa", state["task_id"], "pass")
            return {
                "verdict": "pass",
                "status": "done",
                "feedback": "",
                "agent_output": result.output,
            }
        if bus:
            bus.node_exit("qa", state["task_id"], f"fail cycle={state['bug_cycles'] + 1}")
        return {
            "verdict": "fail",
            "feedback": result.output,
            "bug_cycles": state["bug_cycles"] + 1,
            "agent_output": result.output,
        }

    return qa_node
