import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CRM_API_TOKEN", "test-token")
os.environ.setdefault("AI_PROVIDER", "mock")

from aifunnel.api.app import app  # noqa: E402
from aifunnel.config import get_settings  # noqa: E402
from aifunnel.db import init_db  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client(tmp_path: Path):
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    get_settings.cache_clear()
    # Rebind engine for this test DB
    from aifunnel import db as dbmod

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    dbmod.engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    dbmod.SessionLocal = async_sessionmaker(dbmod.engine, expire_on_commit=False)
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_funnel_to_ready_lead(client: AsyncClient):
    hit = await client.post("/api/funnel/hit", json={"source": "landing", "utm_campaign": "gh"})
    assert hit.status_code == 200
    assert hit.json()["source"] == "landing:gh"

    chat1 = await client.post(
        "/api/chat",
        json={
            "source": "landing:gh",
            "telegram_id": "1001",
            "telegram_username": "tester",
            "message": "Нужен Telegram-бот и воронка под заявки",
        },
    )
    assert chat1.status_code == 200
    body1 = chat1.json()
    lead_id = body1["lead_id"]
    assert body1["reply"]

    chat2 = await client.post(
        "/api/chat",
        json={
            "lead_id": lead_id,
            "message": "Контакт: +7 900 111-22-33",
        },
    )
    assert chat2.status_code == 200
    body2 = chat2.json()
    assert body2["ready_for_handoff"] is True
    assert body2["status"] == "ready"

    leads = await client.get("/api/leads", headers={"X-CRM-Token": "test-token"})
    assert leads.status_code == 200
    items = leads.json()
    assert any(item["id"] == lead_id and item["phone"] for item in items)


@pytest.mark.asyncio
async def test_crm_requires_token(client: AsyncClient):
    r = await client.get("/api/leads")
    assert r.status_code == 401
