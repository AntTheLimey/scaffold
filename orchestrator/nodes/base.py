import json as _json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import click

from orchestrator.event_bus import get_bus


@dataclass
class CliOutput:
    result_text: str
    tool_names: list[str]
    cost_usd: float | None


def parse_cli_output(stdout: str) -> CliOutput:
    tool_names: list[str] = []
    result_text: str | None = None
    cost_usd: float | None = None
    found_jsonl = False
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = _json.loads(line)
        except (ValueError, TypeError):
            continue
        found_jsonl = True
        obj_type = obj.get("type")
        if obj_type == "assistant":
            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = block.get("name")
                    if isinstance(name, str):
                        tool_names.append(name)
        elif obj_type == "result":
            result_text = obj.get("result", "")
            cost_usd = obj.get("total_cost_usd")
    if not found_jsonl or result_text is None:
        return CliOutput(result_text=stdout, tool_names=[], cost_usd=None)
    return CliOutput(result_text=result_text, tool_names=tool_names, cost_usd=cost_usd)


@dataclass
class AgentResult:
    text: str
    token_in: int
    token_out: int


class AdvisorAgent:
    def __init__(self, role: str, model: str, client):
        self.role = role
        self.model = model
        self.client = client

    def call(
        self,
        system_prompt: str,
        user_message: str,
        cache_system: bool = False,
    ) -> AgentResult:
        if cache_system:
            system = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_prompt

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return AgentResult(
            text=response.content[0].text,
            token_in=response.usage.input_tokens,
            token_out=response.usage.output_tokens,
        )


@dataclass
class RalphResult:
    success: bool
    iterations: int
    output: str


class DoerAgent:
    def __init__(
        self,
        role: str,
        model: str,
        max_iterations: int = 10,
        completion_promise: str = "TASK COMPLETE",
        max_budget_usd: float | None = None,
    ):
        self.role = role
        self.model = model
        self.max_iterations = max_iterations
        self.completion_promise = completion_promise
        self.max_budget_usd = max_budget_usd

    def create_worktree(self, repo_path: Path | str, branch: str) -> Path:
        repo_path = Path(repo_path)
        worktree_dir = repo_path.parent / f".worktrees/{branch.replace('/', '-')}"

        if worktree_dir.exists():
            return worktree_dir

        branch_exists = (
            subprocess.run(
                ["git", "rev-parse", "--verify", branch],
                cwd=repo_path,
                capture_output=True,
            ).returncode
            == 0
        )

        if branch_exists:
            subprocess.run(
                ["git", "worktree", "add", str(worktree_dir), branch],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
        else:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(worktree_dir)],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
        return worktree_dir

    def cleanup_worktree(self, repo_path: Path | str, worktree_path: Path | str) -> None:
        repo_path = Path(repo_path)
        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path)],
            cwd=repo_path,
            capture_output=True,
        )

    def ralph_loop(
        self,
        worktree_path: str | Path,
        prompt: str,
        failure_context: str = "",
        task_id: str = "",
        scaffold_budget_usd: float | None = None,
    ) -> RalphResult:
        bus = get_bus()
        last_output = ""
        for i in range(1, self.max_iterations + 1):
            if bus:
                bus.cli_start(self.role, self.model, i, task_id)
            if i > 1 and last_output:
                current_prompt = (
                    f"{prompt}\n\n--- PREVIOUS ATTEMPT (iteration {i - 1}) ---\n"
                    f"{last_output}\n--- END PREVIOUS ATTEMPT ---\n\n"
                    "The previous attempt did not complete the task. "
                    "Fix the issues and try again."
                )
            elif failure_context:
                current_prompt = f"{prompt}\n\n--- FAILURE CONTEXT ---\n{failure_context}\n---"
            else:
                current_prompt = prompt

            success = False
            iteration_cost: float | None = None
            try:
                cmd = ["claude", "--model", self.model]
                if self.max_budget_usd is not None:
                    cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])
                cmd.extend(
                    [
                        "--output-format",
                        "stream-json",
                        "--verbose",
                        "-p",
                        current_prompt,
                    ]
                )
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(worktree_path),
                    timeout=600,
                )
                parsed = parse_cli_output(result.stdout)
                if result.stdout and not parsed.tool_names and parsed.cost_usd is None:
                    click.echo(
                        f"[{self.role}] JSONL parse fallback — tool calls not logged",
                        err=True,
                    )
                last_output = parsed.result_text
                iteration_cost = parsed.cost_usd
                success = self.completion_promise in parsed.result_text
                if bus:
                    for tool_name in parsed.tool_names:
                        bus.tool_call(self.role, tool_name, task_id)
            finally:
                if bus:
                    bus.cli_done(
                        self.role,
                        i,
                        success,
                        task_id,
                        cost_usd=iteration_cost,
                    )
            if bus and scaffold_budget_usd is not None:
                bus.check_budget(scaffold_budget_usd)
            if success:
                return RalphResult(success=True, iterations=i, output=parsed.result_text)

        return RalphResult(success=False, iterations=self.max_iterations, output=last_output)
