import httpx

from aifunnel.ai.base import AIProvider, ChatTurn
from aifunnel.config import Settings


class OpenAICompatProvider(AIProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def reply(self, history: list[ChatTurn], user_message: str) -> str:
        messages = [{"role": "system", "content": self._settings.ai_system_prompt}]
        for turn in history[-12:]:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": user_message})

        headers = {
            "Authorization": f"Bearer {self._settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.ai_model,
            "messages": messages,
            "temperature": 0.4,
        }
        url = self._settings.ai_base_url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()
