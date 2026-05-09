from typing import TypedDict


class TaskState(TypedDict):
    task_id: str
    level: str
    status: str
    has_ui_component: bool
    verdict: str
    feedback: str
    review_cycles: int
    bug_cycles: int
    model_override: str | None
    escalation_reason: str | None
    agent_output: str
    child_tasks: list[dict]
    specialists: list[str]
    advisory: list[str]
    project_context: str
    detected_languages: list[str]
    test_framework: str


def initial_state(task_id: str, level: str) -> TaskState:
    return TaskState(
        task_id=task_id,
        level=level,
        status="pending",
        has_ui_component=False,
        verdict="",
        feedback="",
        review_cycles=0,
        bug_cycles=0,
        model_override=None,
        escalation_reason=None,
        agent_output="",
        child_tasks=[],
        specialists=[],
        advisory=[],
        project_context="",
        detected_languages=[],
        test_framework="",
    )
