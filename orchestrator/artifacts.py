from pathlib import Path

ARTIFACTS_DIR = ".scaffold/artifacts"


def artifact_dir(repo_path: str, task_id: str) -> Path:
    return Path(repo_path) / ARTIFACTS_DIR / task_id


def write_artifact(repo_path: str, task_id: str, role: str, content: str) -> Path | None:
    if not repo_path:
        return None
    try:
        directory = artifact_dir(repo_path, task_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{role}.md"
        path.write_text(content, encoding="utf-8")
        return path
    except OSError:
        return None


def read_artifact(repo_path: str, task_id: str, role: str) -> str:
    if not repo_path:
        return ""
    try:
        path = artifact_dir(repo_path, task_id) / f"{role}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return ""
