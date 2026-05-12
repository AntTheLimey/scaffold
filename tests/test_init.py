from orchestrator.init import format_detection


def test_format_detection_full():
    detection = {
        "detected_languages": ["python", "typescript"],
        "detected_frameworks": ["fastapi", "react"],
        "test_framework": "pytest",
        "has_database": True,
        "has_makefile": True,
        "claude_md_quality": "missing",
        "project_context": "",
    }
    output = format_detection(detection)
    assert "Python, TypeScript" in output
    assert "FastAPI, React" in output
    assert "pytest" in output
    assert "yes" in output.lower()
    assert "missing" in output.lower()


def test_format_detection_empty():
    detection = {
        "detected_languages": [],
        "detected_frameworks": [],
        "test_framework": "",
        "has_database": False,
        "has_makefile": False,
        "claude_md_quality": "missing",
        "project_context": "",
    }
    output = format_detection(detection)
    assert "none" in output.lower()


def test_format_detection_substantive_claude_md():
    detection = {
        "detected_languages": ["python"],
        "detected_frameworks": [],
        "test_framework": "pytest",
        "has_database": False,
        "has_makefile": True,
        "claude_md_quality": "substantive",
        "project_context": "x\n" * 60,
    }
    output = format_detection(detection)
    assert "substantive" in output.lower()
