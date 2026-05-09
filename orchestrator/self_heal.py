from orchestrator.telemetry import Telemetry


class SelfHealer:
    def __init__(
        self,
        telemetry: Telemetry,
        max_review_cycles: int = 3,
        max_bug_cycles: int = 3,
    ):
        self.telemetry = telemetry
        self.max_review_cycles = max_review_cycles
        self.max_bug_cycles = max_bug_cycles

    def check(self, task_id: str) -> dict | None:
        revise_count = self.telemetry.count_cycles(task_id, "revise")
        if revise_count >= self.max_review_cycles:
            return {
                "type": "escalate_model",
                "reason": f"Review cycle hit {revise_count} revisions",
                "task_id": task_id,
            }

        bug_count = self.telemetry.count_cycles(task_id, "bug")
        if bug_count >= self.max_bug_cycles:
            return {
                "type": "escalate_model",
                "reason": f"Bug cycle hit {bug_count} iterations",
                "task_id": task_id,
            }

        return None

    def check_epic(self, epic_id: str) -> dict | None:
        conn = self.telemetry.conn
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE parent_id = ? AND status = 'stuck'",
            (epic_id,),
        ).fetchone()
        if row["cnt"] >= 3:
            return {
                "type": "pause_epic",
                "reason": f"{row['cnt']} tasks stuck in epic {epic_id}",
                "epic_id": epic_id,
            }
        return None
