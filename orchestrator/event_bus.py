from __future__ import annotations

import sqlite3
from datetime import datetime

import click

from orchestrator.telemetry import Telemetry

_bus: EventBus | None = None


class EventBus:
    def __init__(self, conn: sqlite3.Connection):
        self.telemetry = Telemetry(conn)

    def emit(
        self,
        event_type: str,
        agent_role: str = "",
        task_id: str = "",
        run_id: str | None = None,
        **data: object,
    ) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        role = agent_role.ljust(14) if agent_role else " " * 14
        etype = event_type.ljust(14)
        detail = "  ".join(f"{k}={v}" for k, v in data.items()) if data else ""
        click.echo(f"[{ts}] {role} | {etype} | {task_id[:11]:<11} | {detail}")
        self.telemetry.log(
            event_type=event_type,
            event_data=dict(data),
            task_id=task_id or None,
            agent_role=agent_role or None,
            run_id=run_id,
        )

    def node_enter(self, node: str, task_id: str, level: str = "") -> None:
        self.emit("node.enter", agent_role=node, task_id=task_id, level=level)

    def node_exit(self, node: str, task_id: str, summary: str = "") -> None:
        self.emit("node.exit", agent_role=node, task_id=task_id, summary=summary)

    def api_call_start(self, agent_role: str, model: str, prompt_chars: int, task_id: str) -> None:
        self.emit(
            "api.call",
            agent_role=agent_role,
            task_id=task_id,
            model=model,
            prompt_chars=prompt_chars,
        )

    def api_call_done(
        self,
        agent_role: str,
        model: str,
        token_in: int,
        token_out: int,
        task_id: str,
    ) -> None:
        self.emit(
            "api.response",
            agent_role=agent_role,
            task_id=task_id,
            model=model,
            token_in=token_in,
            token_out=token_out,
        )

    def cli_start(self, agent_role: str, model: str, iteration: int, task_id: str) -> None:
        self.emit(
            "cli.start",
            agent_role=agent_role,
            task_id=task_id,
            model=model,
            iteration=iteration,
        )

    def cli_done(self, agent_role: str, iteration: int, success: bool, task_id: str) -> None:
        self.emit(
            "cli.done",
            agent_role=agent_role,
            task_id=task_id,
            iteration=iteration,
            success=success,
        )

    def route(self, from_node: str, to_node: str, reason: str, task_id: str) -> None:
        self.emit(
            "graph.route",
            agent_role=from_node,
            task_id=task_id,
            to=to_node,
            reason=reason,
        )

    def error(self, agent_role: str, error_msg: str, task_id: str) -> None:
        self.emit("agent.error", agent_role=agent_role, task_id=task_id, error=error_msg)

    def escalation(self, reason: str, task_id: str) -> None:
        self.emit("agent.escalate", task_id=task_id, reason=reason)


def init_event_bus(conn: sqlite3.Connection) -> EventBus:
    global _bus
    _bus = EventBus(conn)
    return _bus


def get_bus() -> EventBus | None:
    return _bus
