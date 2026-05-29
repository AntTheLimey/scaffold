import pytest

from orchestrator.tools import CODEBASE_TOOLS, execute_tool, grep, list_directory, read_file


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "hello.py").write_text("line1\nline2\nline3\nline4\nline5\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.txt").write_text("nested content\n")
    return tmp_path


# --- read_file ---


def test_read_file_returns_numbered_lines(repo):
    result = read_file(str(repo), "hello.py")
    assert "1\tline1" in result
    assert "2\tline2" in result
    assert "5\tline5" in result


def test_read_file_offset_and_limit(repo):
    result = read_file(str(repo), "hello.py", offset=2, limit=2)
    lines = result.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("3\t")
    assert lines[1].startswith("4\t")


def test_read_file_nested(repo):
    result = read_file(str(repo), "sub/nested.txt")
    assert "nested content" in result


def test_read_file_not_found(repo):
    result = read_file(str(repo), "missing.py")
    assert "error" in result.lower()


def test_read_file_path_traversal_blocked(repo):
    result = read_file(str(repo), "../../etc/passwd")
    assert "outside" in result


# --- list_directory ---


def test_list_directory_root(repo):
    result = list_directory(str(repo))
    assert "hello.py" in result
    assert "sub/" in result


def test_list_directory_subdir(repo):
    result = list_directory(str(repo), "sub")
    assert "nested.txt" in result


def test_list_directory_not_found(repo):
    result = list_directory(str(repo), "nonexistent")
    assert "error" in result.lower()


def test_list_directory_path_traversal_blocked(repo):
    result = list_directory(str(repo), "../../")
    assert "outside" in result


# --- grep ---


def test_grep_finds_pattern(repo):
    result = grep(str(repo), "line3")
    assert "line3" in result


def test_grep_respects_path(repo):
    result = grep(str(repo), "content", path="sub")
    assert "content" in result
    assert "hello.py" not in result


def test_grep_max_results(repo, tmp_path):
    big = tmp_path / "big.txt"
    big.write_text("\n".join(["match"] * 100))
    result = grep(str(tmp_path), "match", max_results=5)
    assert len(result.splitlines()) <= 5


def test_grep_no_matches(repo):
    result = grep(str(repo), "zzznomatch999")
    assert result == ""


def test_grep_path_traversal_blocked(repo):
    result = grep(str(repo), "anything", path="../../etc")
    assert "outside" in result


# --- execute_tool + CODEBASE_TOOLS ---


def test_execute_tool_dispatches_read_file(repo):
    result = execute_tool("read_file", {"file_path": "hello.py"}, str(repo))
    assert "1\tline1" in result


def test_execute_tool_dispatches_list_directory(repo):
    result = execute_tool("list_directory", {}, str(repo))
    assert "hello.py" in result


def test_execute_tool_dispatches_grep(repo):
    result = execute_tool("grep", {"pattern": "line2"}, str(repo))
    assert "line2" in result


def test_execute_tool_unknown_tool(repo):
    result = execute_tool("fly_to_moon", {}, str(repo))
    assert "unknown" in result.lower()


def test_codebase_tools_has_three_definitions():
    assert len(CODEBASE_TOOLS) == 3
    names = {t["name"] for t in CODEBASE_TOOLS}
    assert names == {"read_file", "list_directory", "grep"}


def test_codebase_tools_have_input_schema():
    for tool in CODEBASE_TOOLS:
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
