import subprocess
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


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

    def load_prompt(self) -> str:
        prompt_file = PROMPTS_DIR / f"{self.role}.md"
        if prompt_file.exists():
            return prompt_file.read_text()
        return ""

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
    ):
        self.role = role
        self.model = model
        self.max_iterations = max_iterations
        self.completion_promise = completion_promise

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
    ) -> RalphResult:
        last_output = ""
        for i in range(1, self.max_iterations + 1):
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

            result = subprocess.run(
                ["claude", "--model", self.model, "-p", current_prompt],
                capture_output=True,
                text=True,
                cwd=str(worktree_path),
                timeout=600,
            )
            last_output = result.stdout
            if self.completion_promise in result.stdout:
                return RalphResult(success=True, iterations=i, output=result.stdout)

        return RalphResult(success=False, iterations=self.max_iterations, output=last_output)
