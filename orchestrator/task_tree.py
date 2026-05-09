import json
import sqlite3
import uuid
from datetime import UTC, datetime

VALID_STATUSES = {
    "pending",
    "decomposing",
    "ready",
    "in_progress",
    "in_review",
    "testing",
    "done",
    "blocked",
    "stuck",
}


class TaskTree:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        title: str,
        level: str,
        parent_id: str | None = None,
        spec_ref: str | None = None,
        acceptance: list[str] | None = None,
    ) -> str:
        task_id = str(uuid.uuid4())[:12]
        self.conn.execute(
            "INSERT INTO tasks (id, parent_id, level, status, title, spec_ref, acceptance) "
            "VALUES (?, ?, ?, 'pending', ?, ?, ?)",
            (
                task_id,
                parent_id,
                level,
                title,
                spec_ref,
                json.dumps(acceptance) if acceptance else None,
            ),
        )
        self.conn.commit()
        return task_id

    def get(self, task_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    def update_status(self, task_id: str, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, task_id),
        )
        self.conn.commit()

    def update_assignment(self, task_id: str, agent_role: str, model: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            "UPDATE tasks SET assigned_to = ?, model = ?, updated_at = ? WHERE id = ?",
            (agent_role, model, now, task_id),
        )
        self.conn.commit()

    def update_branch(self, task_id: str, branch: str) -> None:
        self.conn.execute("UPDATE tasks SET branch = ? WHERE id = ?", (branch, task_id))
        self.conn.commit()

    def list_children(self, parent_id: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM tasks WHERE parent_id = ?", (parent_id,)).fetchall()

    def list_by_status(self, status: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM tasks WHERE status = ?", (status,)).fetchall()

    def add_dependency(self, blocker_id: str, blocked_id: str) -> None:
        self.conn.execute(
            "INSERT INTO task_edges (blocker_id, blocked_id) VALUES (?, ?)",
            (blocker_id, blocked_id),
        )
        self.conn.commit()

    def get_blockers(self, task_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT t.* FROM tasks t "
            "JOIN task_edges e ON t.id = e.blocker_id "
            "WHERE e.blocked_id = ?",
            (task_id,),
        ).fetchall()

    def get_ready_tasks(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT t.* FROM tasks t "
            "WHERE t.status = 'ready' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM task_edges e "
            "  JOIN tasks b ON e.blocker_id = b.id "
            "  WHERE e.blocked_id = t.id AND b.status != 'done'"
            ")"
        ).fetchall()
