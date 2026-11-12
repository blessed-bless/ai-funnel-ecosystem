import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("CRM_API_TOKEN", "test-token-strong")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-strong-32bytes!!")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin-test-pass")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("CHAT_RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("CRM_PROTECT_HTML", "false")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("WEBHOOK_URL", "")


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
    from aifunnel import db as dbmod
    from aifunnel.ai.factory import reset_ai_singleton
    from aifunnel.api.deps import reset_limiters
    from aifunnel.config import get_settings
    from aifunnel.services import admins as admin_service
    from aifunnel.services import funnels as funnel_service

    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    get_settings.cache_clear()
    reset_ai_singleton()
    reset_limiters()
    dbmod.rebind_engine(os.environ["DATABASE_URL"])
    await dbmod.init_db()
    settings = get_settings()
    async with dbmod.SessionLocal() as session:
        await funnel_service.ensure_default_funnel(session)
        await admin_service.ensure_bootstrap_admin(session, settings)

    from aifunnel.api.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await dbmod.dispose_engine()
