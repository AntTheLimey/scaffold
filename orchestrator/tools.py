from __future__ import annotations

import subprocess
from pathlib import Path


def _resolve_safe(repo_path: str, relative: str) -> Path | str:
    root = Path(repo_path).resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        return f"error: path '{relative}' is outside the repository root"
    return resolved


def read_file(repo_path: str, file_path: str, offset: int = 0, limit: int = 500) -> str:
    result = _resolve_safe(repo_path, file_path)
    if isinstance(result, str):
        return result
    resolved = result
    if not resolved.exists():
        return f"error: file not found: {file_path}"
    lines = resolved.read_text(errors="replace").splitlines()
    selected = lines[offset : offset + limit]
    return "\n".join(f"{offset + i + 1}\t{line}" for i, line in enumerate(selected))


def list_directory(repo_path: str, path: str = ".") -> str:
    result = _resolve_safe(repo_path, path)
    if isinstance(result, str):
        return result
    resolved = result
    if not resolved.exists():
        return f"error: directory not found: {path}"
    entries = sorted(resolved.iterdir(), key=lambda p: p.name)
    lines = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        lines.append(entry.name + "/" if entry.is_dir() else entry.name)
    return "\n".join(lines)


def grep(repo_path: str, pattern: str, path: str = ".", max_results: int = 50) -> str:
    result = _resolve_safe(repo_path, path)
    if isinstance(result, str):
        return result
    resolved = result
    proc = subprocess.Popen(
        ["grep", "-rn", "--include=*", pattern, str(resolved)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    root = Path(repo_path).resolve()
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        try:
            file_part, rest = line.split(":", 1)
            rel = Path(file_part).resolve().relative_to(root)
            lines.append(f"{rel}:{rest}")
        except (ValueError, TypeError):
            lines.append(line)
        if len(lines) >= max_results:
            proc.terminate()
            break
    proc.wait()
    return "\n".join(lines)


CODEBASE_TOOLS: list[dict] = [
    {
        "name": "read_file",
        "description": (
            "Read lines from a file in the repository. Returns numbered lines in '1\\tline' format."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file within the repository.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Zero-based line offset to start reading from.",
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to return.",
                    "default": 500,
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "list_directory",
        "description": (
            "List entries in a directory within the repository. "
            "Directories are shown with a trailing '/'. Dotfiles are skipped."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the directory within the repository.",
                    "default": ".",
                },
            },
            "required": [],
        },
    },
    {
        "name": "grep",
        "description": (
            "Search for a pattern recursively within the repository. "
            "Returns matching lines with file paths relative to the repository root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The grep pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "Relative path to restrict the search to.",
                    "default": ".",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matching lines to return.",
                    "default": 50,
                },
            },
            "required": ["pattern"],
        },
    },
]

_TOOL_DISPATCH: dict[str, object] = {
    "read_file": lambda inputs, repo_path: read_file(
        repo_path,
        inputs["file_path"],
        inputs.get("offset", 0),
        inputs.get("limit", 500),
    ),
    "list_directory": lambda inputs, repo_path: list_directory(
        repo_path,
        inputs.get("path", "."),
    ),
    "grep": lambda inputs, repo_path: grep(
        repo_path,
        inputs["pattern"],
        inputs.get("path", "."),
        inputs.get("max_results", 50),
    ),
}


def execute_tool(name: str, inputs: dict, repo_path: str) -> str:
    handler = _TOOL_DISPATCH.get(name)
    if handler is None:
        return f"error: unknown tool '{name}'"
    try:
        return handler(inputs, repo_path)  # type: ignore[operator]
    except Exception as exc:
        return f"error: {exc}"
