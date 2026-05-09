import json
import sqlite3
import uuid
from datetime import datetime, timezone


class Telemetry:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def log(
        self,
        event_type: str,
        event_data: dict,
        task_id: str | None = None,
        agent_role: str | None = None,
        run_id: str | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())[:12]
        self.conn.execute(
            "INSERT INTO events (id, task_id, agent_role, run_id, event_type, event_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, task_id, agent_role, run_id, event_type, json.dumps(event_data)),
        )
        self.conn.commit()
        return event_id

    def get_events(self, task_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events WHERE task_id = ? ORDER BY timestamp",
            (task_id,),
        ).fetchall()

    def get_events_by_type(self, event_type: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp",
            (event_type,),
        ).fetchall()

    def count_cycles(self, task_id: str, cycle_type: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM events "
            "WHERE task_id = ? AND event_type = 'task.cycle' "
            "AND json_extract(event_data, '$.cycle_type') = ?",
            (task_id, cycle_type),
        ).fetchone()
        return row["cnt"]

    def start_run(self, task_id: str, agent_role: str, model: str) -> str:
        run_id = str(uuid.uuid4())[:12]
        self.conn.execute(
            "INSERT INTO agent_runs (id, task_id, agent_role, model) VALUES (?, ?, ?, ?)",
            (run_id, task_id, agent_role, model),
        )
        self.conn.commit()
        self.log(
            task_id=task_id,
            agent_role=agent_role,
            run_id=run_id,
            event_type="agent.start",
            event_data={"model": model},
        )
        return run_id

    def finish_run(
        self,
        run_id: str,
        outcome: str,
        iterations: int | None = None,
        token_in: int | None = None,
        token_out: int | None = None,
        output: dict | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE agent_runs SET finished_at = ?, outcome = ?, iterations = ?, "
            "token_in = ?, token_out = ?, output = ? WHERE id = ?",
            (now, outcome, iterations, token_in, token_out,
             json.dumps(output) if output else None, run_id),
        )
        self.conn.commit()

    def get_failure_brief(self, task_id: str) -> str:
        events = self.conn.execute(
            "SELECT event_type, event_data FROM events "
            "WHERE task_id = ? AND event_type IN "
            "('agent.error', 'task.cycle', 'agent.output') "
            "ORDER BY timestamp",
            (task_id,),
        ).fetchall()
        if not events:
            return ""
        lines = []
        for e in events:
            data = json.loads(e["event_data"])
            lines.append(f"[{e['event_type']}] {json.dumps(data)}")
        return "\n".join(lines)
