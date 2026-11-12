import logging

from aifunnel.ai.base import AIProvider, ChatTurn
from aifunnel.config import Settings
from aifunnel.reliability import CircuitBreaker, with_retries

logger = logging.getLogger("aifunnel.ai")


class ResilientAIProvider(AIProvider):
    def __init__(
        self,
        inner: AIProvider,
        settings: Settings,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._inner = inner
        self._settings = settings
        self._breaker = breaker or CircuitBreaker(
            failure_threshold=settings.ai_circuit_failures,
            recovery_timeout=settings.ai_circuit_recovery_seconds,
        )

    @property
    def circuit_state(self) -> str:
        return self._breaker.state.value

    async def reply(self, history: list[ChatTurn], user_message: str) -> str:
        if not self._breaker.allow():
            logger.warning("ai circuit open — fallback reply")
            return self._settings.ai_fallback_reply

        async def _call() -> str:
            return await self._inner.reply(history, user_message)

        try:
            text = await with_retries(
                _call,
                attempts=self._settings.ai_max_retries,
                label="ai.reply",
            )
            self._breaker.success()
            return text
        except Exception as exc:
            self._breaker.failure()
            logger.exception("ai failed after retries: %s", exc)
            return self._settings.ai_fallback_reply
