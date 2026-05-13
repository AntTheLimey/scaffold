from __future__ import annotations

import json

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from orchestrator.event_bus import get_bus
from orchestrator.state import TaskState, initial_state
from orchestrator.task_tree import TaskTree


def _normalize_acceptance(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except (json.JSONDecodeError, ValueError):
            pass
        return [raw]
    return []


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

    child_statuses: list[str] = []
    for child in children:
        child_level = child.get("level", "task")
        child_id = tree.create(
            title=child.get("title", "Untitled"),
            level=child_level,
            parent_id=state["task_id"],
            spec_ref=child.get("spec_ref"),
            acceptance=child.get("acceptance"),
        )

        child_state = initial_state(task_id=child_id, level=child_level)
        child_state["project_context"] = result.get("project_context", "")
        child_state["specialists"] = result.get("specialists", [])
        child_state["advisory"] = result.get("advisory", [])
        child_state["detected_languages"] = result.get("detected_languages", [])
        child_state["test_framework"] = result.get("test_framework", "")

        child_spec = f"# {child.get('title', 'Untitled')}\n\n"
        if child.get("spec_ref"):
            child_spec += f"Spec reference: {child['spec_ref']}\n\n"
        criteria = _normalize_acceptance(child.get("acceptance"))
        if criteria:
            child_spec += "Acceptance criteria:\n"
            child_spec += "\n".join(f"- {ac}" for ac in criteria)
        child_state["agent_output"] = child_spec

        child_result = run_task(graph, tree, child_state, child_id)
        child_statuses.append(child_result.get("status", "done"))

    final = "done" if all(s == "done" for s in child_statuses) else "blocked"
    tree.update_status(state["task_id"], final)
    if bus:
        bus.emit(
            "task.done",
            task_id=state["task_id"],
            status=final,
            summary=f"{len(children)} children, status={final}",
        )
    return result
