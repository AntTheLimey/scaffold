from orchestrator.artifacts import artifact_dir, read_artifact, write_artifact


def test_write_artifact_creates_file(tmp_path):
    path = write_artifact(str(tmp_path), "task-001", "architect", "design content")
    assert path.exists()
    assert path.read_text() == "design content"
    assert path == tmp_path / ".scaffold" / "artifacts" / "task-001" / "architect.md"


def test_write_artifact_creates_directories(tmp_path):
    write_artifact(str(tmp_path), "task-001", "architect", "content")
    assert (tmp_path / ".scaffold" / "artifacts" / "task-001").is_dir()


def test_write_artifact_overwrites_existing(tmp_path):
    write_artifact(str(tmp_path), "task-001", "architect", "v1")
    write_artifact(str(tmp_path), "task-001", "architect", "v2")
    path = tmp_path / ".scaffold" / "artifacts" / "task-001" / "architect.md"
    assert path.read_text() == "v2"


def test_read_artifact_returns_content(tmp_path):
    write_artifact(str(tmp_path), "task-001", "architect", "design content")
    content = read_artifact(str(tmp_path), "task-001", "architect")
    assert content == "design content"


def test_read_artifact_returns_empty_when_missing(tmp_path):
    content = read_artifact(str(tmp_path), "task-001", "architect")
    assert content == ""


def test_artifact_dir_returns_path(tmp_path):
    result = artifact_dir(str(tmp_path), "task-001")
    assert result == tmp_path / ".scaffold" / "artifacts" / "task-001"


def test_write_artifact_no_op_when_no_repo_path():
    result = write_artifact("", "task-001", "architect", "content")
    assert result is None


def test_read_artifact_returns_empty_when_no_repo_path():
    content = read_artifact("", "task-001", "architect")
    assert content == ""


def test_write_artifact_returns_none_on_os_error(tmp_path):
    bad_path = str(tmp_path / "nonexistent" / "deep" / "path")
    # Create a file where a directory is expected to block mkdir
    blocker = tmp_path / "nonexistent"
    blocker.write_text("file, not dir")
    result = write_artifact(bad_path, "task-001", "architect", "content")
    assert result is None


def test_read_artifact_returns_empty_on_os_error(tmp_path):
    # Create a directory where the .md file would be, causing read_text to fail
    artifact_file = tmp_path / ".scaffold" / "artifacts" / "task-001" / "architect.md"
    artifact_file.mkdir(parents=True)
    content = read_artifact(str(tmp_path), "task-001", "architect")
    assert content == ""
