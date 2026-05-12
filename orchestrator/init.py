from pathlib import Path  # noqa: F401

# Known names that require non-standard capitalisation.
_KNOWN_NAMES: dict[str, str] = {
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "fastapi": "FastAPI",
    "graphql": "GraphQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "nextjs": "Next.js",
    "nuxtjs": "Nuxt.js",
    "vuejs": "Vue.js",
    "reactjs": "React",
}


def _display_name(name: str) -> str:
    lower = name.lower()
    if lower in _KNOWN_NAMES:
        return _KNOWN_NAMES[lower]
    return name.capitalize()


def format_detection(detection: dict) -> str:
    languages = detection["detected_languages"]
    frameworks = detection["detected_frameworks"]
    test_fw = detection["test_framework"]
    has_db = detection["has_database"]
    has_make = detection["has_makefile"]
    claude_quality = detection["claude_md_quality"]

    lang_str = ", ".join(_display_name(lang) for lang in languages) if languages else "none"
    fw_str = ", ".join(_display_name(fw) for fw in frameworks) if frameworks else "none"
    test_str = test_fw if test_fw else "none"
    db_str = "yes" if has_db else "no"
    make_str = "yes" if has_make else "no"

    lines = [
        "Detected:",
        f"  Languages ............. {lang_str}",
        f"  Frameworks ............ {fw_str}",
        f"  Test framework ........ {test_str}",
        f"  Database .............. {db_str}",
        f"  Makefile .............. {make_str}",
        f"  CLAUDE.md ............. {claude_quality}",
    ]
    return "\n".join(lines)
