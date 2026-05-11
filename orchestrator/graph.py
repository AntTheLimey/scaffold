from pathlib import Path

from langgraph.graph import END, START, StateGraph

from orchestrator.agent_loader import AgentLoader
from orchestrator.config import AgentsConfig
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
        return "human_gate"
    level = state["level"]
    if level == "epic":
        return "product_owner"
    if level == "feature":
        return "architect"
    return "developer"


def architect_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        return "human_gate"
    if state.get("has_ui_component"):
        return "designer"
    return "developer"


def reviewer_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        return "human_gate"
    if state["verdict"] == "approve":
        return "qa"
    if state["review_cycles"] >= 3:
        return "human_gate"
    return "developer"


def qa_router(state: TaskState) -> str:
    if state.get("escalation_reason"):
        return "human_gate"
    if state["verdict"] == "pass":
        return "__end__"
    if state["bug_cycles"] >= 3:
        return "human_gate"
    return "developer"


def human_gate_router(state: TaskState) -> str:
    verdict = state.get("verdict", "")
    if verdict == "Revise":
        return "developer"
    return "__end__"


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

    reviewer_model = agents_config.workflow.get("reviewer", {}).get("model", "claude-sonnet-4-6")
    qa_model = agents_config.workflow.get("qa", {}).get("model", "claude-sonnet-4-6")

    graph.add_node(
        "onboarding",
        make_onboarding_node(repo_path, Path(agent_loader.agents_dir)),
    )
    graph.add_node("product_owner", make_product_owner_node(client, spec_path, agent_loader))
    graph.add_node("architect", make_architect_node(client, agent_loader))
    graph.add_node("designer", make_designer_node(client, agent_loader))
    graph.add_node(
        "developer",
        make_developer_node(repo_path, branch_prefix, agent_loader, agents_config, client),
    )
    graph.add_node(
        "reviewer", make_reviewer_node(repo_path, branch_prefix, reviewer_model, agent_loader)
    )
    graph.add_node("qa", make_qa_node(repo_path, branch_prefix, qa_model, agent_loader))
    graph.add_node("consensus", make_consensus_node(client, agent_loader))
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
