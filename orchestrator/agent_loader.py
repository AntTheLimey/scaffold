from collections import Counter
from pathlib import Path

EXTENSION_TO_SPECIALIST = {
    ".py": "python-expert",
    ".go": "go-expert",
    ".tsx": "react-expert",
    ".jsx": "react-expert",
    ".ts": "typescript-expert",
    ".sql": "postgres-expert",
    ".md": "documentation-writer",
}

_SEP = "\n\n---\n\n"


class AgentLoader:
    def __init__(self, agents_dir: Path):
        self.agents_dir = agents_dir

    def load_workflow_agent(self, role: str) -> str:
        """Load workflow agent's full prompt (agent.md + ALL knowledge base files).
        Returns empty string if agent doesn't exist."""
        agent_dir = self.agents_dir / "workflow" / role
        agent_md = agent_dir / "agent.md"
        if not agent_md.exists():
            return ""

        sections = [agent_md.read_text()]
        kb_dir = agent_dir / "knowledge-base"
        if kb_dir.is_dir():
            for kb_file in sorted(kb_dir.iterdir()):
                if kb_file.is_file():
                    sections.append(kb_file.read_text())

        return _SEP.join(sections)

    def load_specialist(
        self,
        name: str,
        repo_path: Path,
        task_context: str,
        advisory_input: str = "",
    ) -> str:
        """Load specialist's prompt assembled with project context.
        Layers: agent.md + selected KBs + CLAUDE.md + overrides + advisory + task."""
        agent_dir = self.agents_dir / "specialists" / name
        agent_md = agent_dir / "agent.md"
        if not agent_md.exists():
            return ""

        sections = [agent_md.read_text()]

        kb_dir = agent_dir / "knowledge-base"
        if kb_dir.is_dir():
            selected = self._select_knowledge_bases(kb_dir, task_context)
            for kb_file in selected:
                sections.append(kb_file.read_text())

        claude_md = repo_path / "CLAUDE.md"
        if claude_md.exists():
            sections.append(claude_md.read_text())

        override = repo_path / ".claude" / "agents" / f"{name}.md"
        if override.exists():
            sections.append(override.read_text())

        if advisory_input:
            sections.append(advisory_input)

        if task_context:
            sections.append(task_context)

        return _SEP.join(sections)

    def list_specialists(self) -> list[str]:
        """Return sorted list of available specialist names (dirs with agent.md)."""
        specialists_dir = self.agents_dir / "specialists"
        if not specialists_dir.is_dir():
            return []
        names = [
            d.name for d in specialists_dir.iterdir() if d.is_dir() and (d / "agent.md").exists()
        ]
        return sorted(names)

    def detect_specialist(self, file_paths: list[str]) -> str:
        """Given file paths, return best-matching specialist name by extension count.
        Returns empty string if no match."""
        counts: Counter[str] = Counter()
        for fp in file_paths:
            ext = Path(fp).suffix
            specialist = EXTENSION_TO_SPECIALIST.get(ext)
            if specialist:
                counts[specialist] += 1
        if not counts:
            return ""
        return counts.most_common(1)[0][0]

    def _select_knowledge_bases(self, kb_dir: Path, task_context: str) -> list[Path]:
        """Select relevant KB files based on task context keywords.
        Falls back to all KBs if nothing matches or no context given."""
        all_kbs = sorted(f for f in kb_dir.iterdir() if f.is_file())
        if not task_context:
            return all_kbs

        context_words = set(task_context.lower().split())
        matched = [
            kb for kb in all_kbs if any(keyword in context_words for keyword in kb.stem.split("-"))
        ]
        return matched if matched else all_kbs
