import re
from pathlib import Path

from orchestrator.agent_loader import AgentLoader
from orchestrator.config import AgentsConfig
from orchestrator.nodes.base import AdvisorAgent, DoerAgent
from orchestrator.state import TaskState


def _extract_file_paths(text: str) -> list[str]:
    """Extract file paths from text using regex."""
    pattern = r"[\w./\-]+\.(?:py|go|tsx|jsx|ts|js|sql|md|yaml|yml|json|toml)"
    return list(set(re.findall(pattern, text)))


def make_developer_node(
    repo_path: str,
    branch_prefix: str,
    agent_loader: AgentLoader,
    agents_config: AgentsConfig,
    client=None,
):
    def developer_node(state: TaskState) -> dict:
        # 1. Read task context
        agent_output = state.get("agent_output", "")
        specialist_names = state.get("specialists", [])
        advisory_names = state.get("advisory", [])

        # 2. Extract file paths from agent_output
        file_paths = _extract_file_paths(agent_output)

        # 3. Select specialist — match file types against roster
        specialist_name = ""
        detected = agent_loader.detect_specialist(file_paths) if file_paths else ""
        if detected and (not specialist_names or detected in specialist_names):
            specialist_name = detected
        if not specialist_name and specialist_names:
            specialist_name = specialist_names[0]
        if not specialist_name:
            specialist_name = "python-expert"

        # 4. Get specialist config
        spec_config = agents_config.specialists[specialist_name]

        # 5. Dispatch advisory specialists
        advisory_input = ""
        if client and advisory_names:
            recommendations: list[str] = []
            for adv_name in advisory_names:
                adv_config = agents_config.specialists.get(adv_name, {})
                if adv_config.get("execution") == "api":
                    advisor = AdvisorAgent(
                        role=adv_name,
                        model=adv_config["model"],
                        client=client,
                    )
                    result = advisor.call(
                        system_prompt=f"You are a {adv_name} advisor.",
                        user_message=f"Review and advise on this task:\n\n{agent_output}",
                    )
                    recommendations.append(result.text)
            if recommendations:
                advisory_input = "\n\n".join(recommendations)

        # 6. Assemble implementation prompt
        task_context = f"Task: {state['task_id']}\n\nTechnical design:\n{agent_output}\n"
        prompt = agent_loader.load_specialist(
            specialist_name, Path(repo_path), task_context, advisory_input
        )

        # 7. Append review feedback
        failure_context = ""
        if state.get("feedback"):
            failure_context = (
                f"Previous review feedback:\n{state['feedback']}\n"
                "Address this feedback in your implementation."
            )
            prompt += f"\n\nReview feedback to address:\n{state['feedback']}"

        # 8. Create DoerAgent with specialist config
        doer = DoerAgent(
            role=specialist_name,
            model=spec_config["model"],
            max_iterations=spec_config.get("max_iterations", 10),
            completion_promise=spec_config.get("completion_promise", "TASK COMPLETE"),
        )

        # 9. Create worktree, run ralph_loop, cleanup in finally block
        branch = f"{branch_prefix}/{state['task_id']}"
        worktree_path = doer.create_worktree(repo_path, branch)
        try:
            result = doer.ralph_loop(
                worktree_path=worktree_path,
                prompt=prompt,
                failure_context=failure_context,
            )
        finally:
            doer.cleanup_worktree(repo_path, worktree_path)

        # 10. Return result
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
