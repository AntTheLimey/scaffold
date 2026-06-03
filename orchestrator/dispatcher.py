from __future__ import annotations

import json

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from orchestrator.artifacts import write_artifact
from orchestrator.budget import BudgetExceededError
from orchestrator.event_bus import get_bus
from orchestrator.state import TaskState, initial_state
from orchestrator.task_tree import TaskTree


def _topo_sort(children: list[dict]) -> list[dict]:
    """Sort children by depends_on. Tasks with no dependencies come first.
    Falls back to original order if depends_on is not used or on cycles."""
    if not any(c.get("depends_on") for c in children if isinstance(c, dict)):
        return children

    title_to_idx: dict[str, int] = {}
    for i, c in enumerate(children):
        if isinstance(c, dict):
            title_to_idx[c.get("title", "")] = i

    in_degree: dict[int, int] = {i: 0 for i in range(len(children))}
    graph: dict[int, list[int]] = {i: [] for i in range(len(children))}
    for i, c in enumerate(children):
        if not isinstance(c, dict):
            continue
        for dep_title in c.get("depends_on", []):
            dep_idx = title_to_idx.get(dep_title)
            if dep_idx is not None:
                graph[dep_idx].append(i)
                in_degree[i] += 1

    queue = [i for i in range(len(children)) if in_degree[i] == 0]
    sorted_indices: list[int] = []
    while queue:
        queue.sort()
        node = queue.pop(0)
        sorted_indices.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_indices) != len(children):
        return children

    return [children[i] for i in sorted_indices]


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
    max_budget_usd: float | None = None,
    repo_path: str = "",
) -> dict:
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    bus = get_bus()

    if bus:
        bus.emit(
            "task.start",
            task_id=state["task_id"],
            level=state["level"],
        )

    try:
        result = graph.invoke(state, config=config)
    except BudgetExceededError:
        tree.update_status(state["task_id"], "stuck")
        if bus:
            bus.emit("budget.exceeded", task_id=state["task_id"])
        return {"status": "stuck", "child_tasks": []}
    except Exception as exc:
        tree.update_status(state["task_id"], "stuck")
        if bus:
            bus.emit(
                "task.error",
                task_id=state["task_id"],
                error=str(exc),
            )
        return {"status": "stuck", "child_tasks": []}

    children = result.get("child_tasks", [])
    children = _topo_sort(children)
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
    budget_blown = False
    for child in children:
        if not isinstance(child, dict):
            child_statuses.append("stuck")
            if bus:
                bus.emit(
                    "task.error",
                    task_id=state["task_id"],
                    error=f"invalid child payload: {type(child).__name__}",
                )
            continue
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
        write_artifact(repo_path, child_id, "task_spec", child_spec)

        run_task(
            graph, tree, child_state, child_id, max_budget_usd=max_budget_usd, repo_path=repo_path
        )
        child_row = tree.get(child_id)
        child_statuses.append(child_row["status"] if child_row else "stuck")

        if max_budget_usd is not None and bus:
            try:
                bus.check_budget(max_budget_usd)
            except BudgetExceededError:
                bus.emit("budget.exceeded", task_id=state["task_id"])
                budget_blown = True
                break

    all_done = not budget_blown and all(s == "done" for s in child_statuses)
    final = "done" if all_done else "blocked"
    tree.update_status(state["task_id"], final)
    if bus:
        bus.emit(
            "task.done",
            task_id=state["task_id"],
            status=final,
            summary=f"{len(children)} children, status={final}",
        )
    return {**result, "status": final}
