import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from orchestrator.config import ScaffoldConfig
from orchestrator.telegram import TelegramBot


@dataclass
class Check:
    name: str
    passed: bool
    status: str


@dataclass
class PreflightResult:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.passed or c.status == "SKIP" for c in self.checks)


def run_preflight(cfg: ScaffoldConfig) -> PreflightResult:
    result = PreflightResult()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    result.checks.append(
        Check(
            name="ANTHROPIC_API_KEY",
            passed=bool(api_key),
            status="OK" if api_key else "FAIL",
        )
    )

    claude_path = shutil.which("claude")
    result.checks.append(
        Check(
            name="Claude CLI installed",
            passed=claude_path is not None,
            status="OK" if claude_path else "FAIL",
        )
    )

    git_name = subprocess.run(
        ["git", "config", "user.name"],
        capture_output=True,
        text=True,
    )
    git_email = subprocess.run(
        ["git", "config", "user.email"],
        capture_output=True,
        text=True,
    )
    git_ok = git_name.returncode == 0 and git_email.returncode == 0
    result.checks.append(
        Check(
            name="Git identity configured",
            passed=git_ok,
            status="OK" if git_ok else "FAIL",
        )
    )

    repo_path = Path(cfg.project.repo_path)
    repo_exists = repo_path.exists() and (repo_path / ".git").exists()
    result.checks.append(
        Check(
            name="Target repo exists",
            passed=repo_exists,
            status=f"OK ({repo_path})" if repo_exists else "FAIL",
        )
    )

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    has_telegram = bool(telegram_token and telegram_chat)
    if has_telegram:
        bot = TelegramBot(token=telegram_token, chat_id=telegram_chat)
        try:
            telegram_ok = bot.ping()
        finally:
            bot.close()
        result.checks.append(
            Check(
                name="Telegram",
                passed=telegram_ok,
                status="OK (test message sent)" if telegram_ok else "FAIL (check token/chat_id)",
            )
        )
    else:
        result.checks.append(
            Check(
                name="Telegram (optional)",
                passed=True,
                status="SKIP (not configured)",
            )
        )

    return result
