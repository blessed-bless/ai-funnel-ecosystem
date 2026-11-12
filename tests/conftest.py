import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("CRM_API_TOKEN", "test-token-strong")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("CHAT_RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")


@pytest.fixture(autouse=True)
def _clear_caches():
    from aifunnel.ai.factory import reset_ai_singleton
    from aifunnel.config import get_settings

    get_settings.cache_clear()
    reset_ai_singleton()
    yield
    get_settings.cache_clear()
    reset_ai_singleton()


@pytest.fixture
async def client(tmp_path: Path):
    from aifunnel.config import get_settings
    from aifunnel.db import init_db, rebind_engine
    from aifunnel.ai.factory import reset_ai_singleton

    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    get_settings.cache_clear()
    reset_ai_singleton()
    rebind_engine(os.environ["DATABASE_URL"])
    await init_db()

    from aifunnel.api.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
