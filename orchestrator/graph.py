from pathlib import Path

from langgraph.graph import END, START, StateGraph

from orchestrator.agent_loader import AgentLoader
from orchestrator.config import AgentsConfig
from orchestrator.event_bus import get_bus
from orchestrator.nodes.architect import make_architect_node
from orchestrator.nodes.consensus import make_consensus_node
from orchestrator.nodes.designer import make_designer_node
from orchestrator.nodes.developer import make_developer_node
from orchestrator.nodes.human_gate import make_human_gate_node
from orchestrator.nodes.onboarding import make_onboarding_node
from orchestrator.nodes.product_owner import make_product_owner_node
from orchestrator.nodes.qa import make_qa_node
from orchestrator.nodes.reviewer import make_reviewer_node
from orchestrator.state import TaskState


def intake_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        dest = "human_gate"
    elif state["level"] == "epic":
        dest = "product_owner"
    elif state["level"] == "feature":
        dest = "architect"
    else:
        dest = "developer"
    bus = get_bus()
    if bus:
        bus.route("onboarding", dest, f"level={state['level']}", state["task_id"])
    return dest


def architect_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        dest = "human_gate"
    elif state.get("has_ui_component"):
        dest = "designer"
    else:
        dest = "developer"
    bus = get_bus()
    if bus:
        has_ui = state.get("has_ui_component", False)
        bus.route("architect", dest, f"has_ui={has_ui}", state["task_id"])
    return dest


def reviewer_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        dest = "human_gate"
    elif state["verdict"] == "approve":
        dest = "qa"
    elif state["review_cycles"] >= 3:
        dest = "human_gate"
    else:
        dest = "developer"
    bus = get_bus()
    if bus:
        reason = f"verdict={state['verdict']} cycles={state['review_cycles']}"
        bus.route("reviewer", dest, reason, state["task_id"])
    return dest


def qa_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        dest = "human_gate"
    elif state["verdict"] == "pass":
        dest = "__end__"
    elif state["bug_cycles"] >= 3:
        dest = "human_gate"
    else:
        dest = "developer"
    bus = get_bus()
    if bus:
        reason = f"verdict={state['verdict']} cycles={state['bug_cycles']}"
        bus.route("qa", dest, reason, state["task_id"])
    return dest


def human_gate_router(state: TaskState) -> str:
    verdict = state.get("verdict", "")
    dest = "developer" if verdict == "Revise" else "__end__"
    bus = get_bus()
    if bus:
        bus.route("human_gate", dest, f"verdict={verdict}", state["task_id"])
    return dest


def build_graph(
    client,
    bot,
    repo_path: str,
    branch_prefix: str,
    spec_path: str,
    agent_loader: AgentLoader,
    agents_config: AgentsConfig,
    checkpointer=None,
):
    graph = StateGraph(TaskState)

    def _model(role: str, default: str) -> str:
        return agents_config.workflow.get(role, {}).get("model", default)

    graph.add_node(
        "onboarding",
        make_onboarding_node(repo_path, Path(agent_loader.agents_dir)),
    )
    po_model = _model("product_owner", "claude-opus-4-6")
    graph.add_node(
        "product_owner",
        make_product_owner_node(client, spec_path, agent_loader, po_model),
    )
    graph.add_node(
        "architect",
        make_architect_node(client, agent_loader, _model("architect", "claude-opus-4-6")),
    )
    graph.add_node(
        "designer",
        make_designer_node(client, agent_loader, _model("designer", "claude-sonnet-4-6")),
    )
    graph.add_node(
        "developer",
        make_developer_node(repo_path, branch_prefix, agent_loader, agents_config, client),
    )
    reviewer_model = _model("reviewer", "claude-sonnet-4-6")
    graph.add_node(
        "reviewer",
        make_reviewer_node(repo_path, branch_prefix, reviewer_model, agent_loader),
    )
    qa_model = _model("qa", "claude-sonnet-4-6")
    graph.add_node(
        "qa",
        make_qa_node(repo_path, branch_prefix, qa_model, agent_loader),
    )
    consensus_model = _model("consensus", "claude-opus-4-6")
    graph.add_node(
        "consensus",
        make_consensus_node(client, agent_loader, consensus_model),
    )
    graph.add_node("human_gate", make_human_gate_node(bot))

    graph.add_edge(START, "onboarding")
    graph.add_conditional_edges(
        "onboarding",
        intake_router,
        {
            "product_owner": "product_owner",
            "architect": "architect",
            "developer": "developer",
            "human_gate": "human_gate",
        },
    )

    graph.add_edge("product_owner", "architect")

    graph.add_conditional_edges(
        "architect",
        architect_router,
        {
            "designer": "designer",
            "developer": "developer",
            "human_gate": "human_gate",
        },
    )

    graph.add_edge("designer", "developer")
    graph.add_edge("developer", "reviewer")

    graph.add_conditional_edges(
        "reviewer",
        reviewer_router,
        {
            "qa": "qa",
            "developer": "developer",
            "human_gate": "human_gate",
        },
    )

    graph.add_conditional_edges(
        "qa",
        qa_router,
        {
            "__end__": END,
            "developer": "developer",
            "human_gate": "human_gate",
        },
    )

    graph.add_edge("consensus", "human_gate")
    graph.add_conditional_edges(
        "human_gate",
        human_gate_router,
        {
            "developer": "developer",
            "__end__": END,
        },
    )

    return graph.compile(checkpointer=checkpointer)
