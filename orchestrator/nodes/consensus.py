from orchestrator.agent_loader import AgentLoader
from orchestrator.event_bus import get_bus
from orchestrator.json_utils import extract_json
from orchestrator.nodes.base import AdvisorAgent
from orchestrator.state import TaskState

SYSTEM_PROMPT = (
    "You are a structured debate adjudicator. Two agents disagree. "
    "Write your position or rebuttal. Output JSON with keys: "
    "position (str), concedes (bool)."
)

MAX_ROUNDS = 2


def make_consensus_node(client, agent_loader: AgentLoader, model: str = "claude-opus-4-6"):
    agent = AdvisorAgent(
        role="consensus",
        model=model,
        client=client,
    )

    def consensus_node(state: TaskState) -> dict:
        bus = get_bus()
        if bus:
            bus.node_enter("consensus", state["task_id"])
        system_prompt = agent_loader.load_workflow_agent("consensus")
        if not system_prompt:
            system_prompt = SYSTEM_PROMPT
        project_context = state.get("project_context", "")
        if project_context:
            system_prompt += f"\n\n--- Project Context ---\n{project_context}\n---"

        positions = []
        for round_num in range(MAX_ROUNDS):
            for party in ["recommend", "agree"]:
                prompt = f"Round {round_num + 1}, party: {party}."
                if positions:
                    prompt += "\nPrevious positions:\n" + "\n".join(f"- {p}" for p in positions)
                tid = state["task_id"]
                if bus:
                    chars = len(system_prompt) + len(prompt)
                    bus.api_call_start("consensus", model, chars, tid)
                result = agent.call(system_prompt=system_prompt, user_message=prompt)
                if bus:
                    bus.api_call_done("consensus", model, result.token_in, result.token_out, tid)
                parsed = extract_json(result.text)
                if not parsed:
                    continue
                positions.append(f"{party}: {parsed.get('position', '')}")
                if parsed.get("concedes", False):
                    position = parsed.get("position", "")
                    msg = f"Resolved in round {round_num + 1}: {party} concedes. {position}"
                    if bus:
                        summary = f"resolved round={round_num + 1}"
                        bus.node_exit("consensus", state["task_id"], summary)
                    return {
                        "verdict": "resolved",
                        "escalation_reason": None,
                        "agent_output": msg,
                    }

        if bus:
            bus.node_exit("consensus", state["task_id"], f"deadlock after {MAX_ROUNDS} rounds")
        return {
            "escalation_reason": f"Consensus deadlock after {MAX_ROUNDS} rounds",
            "agent_output": "\n".join(positions),
        }

    return consensus_node
