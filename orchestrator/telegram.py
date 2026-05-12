import json

import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = TELEGRAM_API.format(token=token)
        self.client = httpx.Client(timeout=30)
        self._offset = 0

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def ping(self) -> bool:
        if not self.token:
            return False
        try:
            resp = self.client.get(f"{self.base_url}/getMe")
            resp.raise_for_status()
            bot_name = resp.json().get("result", {}).get("username", "unknown")
            msg_resp = self.client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": f"Scaffold connected. Bot @{bot_name} ready.",
                },
            )
            msg_resp.raise_for_status()
            return True
        except (httpx.HTTPError, KeyError):
            return False

    def send_escalation(self, question: str, options: list[str], task_id: str) -> int:
        if not self.token:
            return 0
        keyboard = {
            "inline_keyboard": [
                [{"text": opt, "callback_data": json.dumps({"task": task_id, "choice": opt})}]
                for opt in options
            ]
        }
        resp = self.client.post(
            f"{self.base_url}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": f"Escalation\n\n{question}",
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            },
        )
        resp.raise_for_status()
        return resp.json()["result"]["message_id"]

    def send_digest(self, done: int, in_progress: int, blocked: int, cost_today: float) -> None:
        if not self.token:
            return
        text = (
            f"Status Digest\n\n"
            f"Done: {done}\n"
            f"In Progress: {in_progress}\n"
            f"Blocked: {blocked}\n"
            f"Cost today: ${cost_today:.2f}"
        )
        resp = self.client.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
        )
        resp.raise_for_status()

    def poll_for_callback(self, timeout: int = 300) -> dict | None:
        if not self.token:
            return None
        resp = self.client.post(
            f"{self.base_url}/getUpdates",
            json={
                "timeout": timeout,
                "offset": self._offset,
                "allowed_updates": ["callback_query"],
            },
        )
        resp.raise_for_status()
        updates = resp.json().get("result", [])
        for update in updates:
            self._offset = update["update_id"] + 1
            if "callback_query" in update:
                data = json.loads(update["callback_query"]["data"])
                self.client.post(
                    f"{self.base_url}/answerCallbackQuery",
                    json={"callback_query_id": update["callback_query"]["id"]},
                )
                return data
        return None
