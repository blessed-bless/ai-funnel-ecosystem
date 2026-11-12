import re

from aifunnel.ai.base import AIProvider, ChatTurn


class MockAIProvider(AIProvider):
    """Детерминированный консультант без внешних API — для локальной разработки и CI."""

    async def reply(self, history: list[ChatTurn], user_message: str) -> str:
        text = user_message.strip()
        lower = text.lower()
        phone = _extract_phone(text)
        asked_phone = any("телефон" in (t.content or "").lower() for t in history if t.role == "assistant")
        asked_need = any(
            "задач" in (t.content or "").lower() or "что нужно" in (t.content or "").lower()
            for t in history
            if t.role == "assistant"
        )

        if phone:
            return (
                f"Принял контакт {phone}. Зафиксирую заявку для менеджера. "
                "Если нужно что-то уточнить — напиши одним сообщением."
            )

        if any(w in lower for w in ("бот", "telegram", "воронк", "crm", "автоматиз", "интеграц")):
            return (
                "Похоже на автоматизацию продаж или поддержки. "
                "Опиши задачу в 1–2 предложениях и оставь телефон — передам менеджеру."
            )

        if not asked_need and len(history) < 2:
            return (
                "Привет. Я помогу собрать заявку: что нужно автоматизировать "
                "и как с тобой связаться. Расскажи задачу своими словами."
            )

        if not asked_phone:
            return (
                "Записал. Оставь номер телефона в формате +7… — "
                "менеджер свяжется и уточнит детали."
            )

        return "Ок. Напиши телефон или коротко уточни задачу — оформлю заявку."


def _extract_phone(text: str) -> str | None:
    match = re.search(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", text)
    return match.group(0) if match else None
