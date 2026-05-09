import subprocess

import pytest

from orchestrator.nodes.base import DoerAgent


@pytest.fixture
def doer():
    return DoerAgent(
        role="developer",
        model="claude-sonnet-4-20250514",
        max_iterations=3,
        completion_promise="TASK COMPLETE",
    )


def test_create_worktree_reuses_existing_branch(doer, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo_path,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": str(tmp_path),
        },
    )
    worktree_path = doer.create_worktree(repo_path, "scaffold/task-001")
    assert worktree_path.exists()

    doer.cleanup_worktree(repo_path, worktree_path)
    assert not worktree_path.exists()

    worktree_path2 = doer.create_worktree(repo_path, "scaffold/task-001")
    assert worktree_path2.exists()

    doer.cleanup_worktree(repo_path, worktree_path2)


def test_create_worktree_reuses_existing_worktree(doer, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo_path,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": str(tmp_path),
        },
    )
    worktree_path = doer.create_worktree(repo_path, "scaffold/task-002")
    assert worktree_path.exists()

    worktree_path2 = doer.create_worktree(repo_path, "scaffold/task-002")
    assert worktree_path2 == worktree_path
    assert worktree_path2.exists()

    doer.cleanup_worktree(repo_path, worktree_path)
