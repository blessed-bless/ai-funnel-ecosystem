import pytest

from aifunnel.ai.base import AIProvider, ChatTurn
from aifunnel.ai.resilient import ResilientAIProvider
from aifunnel.config import Settings
from aifunnel.reliability import CircuitBreaker, with_retries


@pytest.mark.asyncio
async def test_with_retries_succeeds_second_try():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    assert await with_retries(flaky, attempts=3, base_delay=0.01, label="t") == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_resilient_ai_fallback():
    class BoomAI(AIProvider):
        async def reply(self, history: list[ChatTurn], user_message: str) -> str:
            raise RuntimeError("down")

    settings = Settings(
        ai_max_retries=2,
        ai_circuit_failures=2,
        ai_circuit_recovery_seconds=60,
        ai_fallback_reply="fallback-text",
        crm_api_token="test-token-strong",
    )
    provider = ResilientAIProvider(BoomAI(), settings, CircuitBreaker(2, 60))
    text = await provider.reply([], "привет")
    assert text == "fallback-text"
