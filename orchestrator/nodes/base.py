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
