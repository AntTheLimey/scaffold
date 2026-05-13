from __future__ import annotations

import json

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from orchestrator.event_bus import get_bus
from orchestrator.state import TaskState, initial_state
from orchestrator.task_tree import TaskTree


def run_task(
    graph: CompiledStateGraph,
    tree: TaskTree,
    state: TaskState,
    thread_id: str,
) -> dict:
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    bus = get_bus()

    if bus:
        bus.emit(
            "task.start",
            task_id=state["task_id"],
            level=state["level"],
        )

    result = graph.invoke(state, config=config)

    children = result.get("child_tasks", [])
    if not children:
        tree.update_status(state["task_id"], result.get("status", "done"))
        if bus:
            bus.emit(
                "task.done",
                task_id=state["task_id"],
                status=result.get("status", "done"),
            )
        return result

    tree.update_status(state["task_id"], "decomposing")
    if bus:
        bus.emit(
            "task.decomposed",
            task_id=state["task_id"],
            children=len(children),
        )

    for child in children:
        child_id = tree.create(
            title=child.get("title", "Untitled"),
            level=child.get("level", "task"),
            parent_id=state["task_id"],
            spec_ref=child.get("spec_ref"),
            acceptance=child.get("acceptance"),
        )

        child_state = initial_state(task_id=child_id, level=child["level"])
        child_state["project_context"] = result.get("project_context", "")
        child_state["specialists"] = result.get("specialists", [])
        child_state["advisory"] = result.get("advisory", [])
        child_state["detected_languages"] = result.get("detected_languages", [])
        child_state["test_framework"] = result.get("test_framework", "")

        child_spec = f"# {child.get('title', 'Untitled')}\n\n"
        if child.get("spec_ref"):
            child_spec += f"Spec reference: {child['spec_ref']}\n\n"
        if child.get("acceptance"):
            criteria = child["acceptance"]
            if isinstance(criteria, str):
                criteria = json.loads(criteria)
            child_spec += "Acceptance criteria:\n"
            child_spec += "\n".join(f"- {ac}" for ac in criteria)
        child_state["agent_output"] = child_spec

        run_task(graph, tree, child_state, child_id)

    tree.update_status(state["task_id"], "done")
    if bus:
        bus.emit(
            "task.done",
            task_id=state["task_id"],
            status="done",
            summary=f"all {len(children)} children complete",
        )
    return result
