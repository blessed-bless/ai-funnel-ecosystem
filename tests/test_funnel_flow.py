import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_ready(client: AsyncClient):
    health = await client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert "version" in body

    ready = await client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["database"] == "ok"


@pytest.mark.asyncio
async def test_security_headers(client: AsyncClient):
    r = await client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-request-id")


@pytest.mark.asyncio
async def test_funnel_to_ready_lead(client: AsyncClient):
    hit = await client.post(
        "/api/funnel/hit",
        json={"source": "landing", "utm_campaign": "gh", "funnel_slug": "default"},
    )
    assert hit.status_code == 200
    assert hit.json()["source"] == "landing:gh"
    assert hit.json()["stage_slug"] == "awareness"

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
        json={"lead_id": lead_id, "message": "Контакт: +7 900 111-22-33"},
    )
    assert chat2.status_code == 200
    body2 = chat2.json()
    assert body2["ready_for_handoff"] is True
    assert body2["status"] == "ready"
    assert body2["score"] >= 70

    leads = await client.get("/api/leads", headers={"X-CRM-Token": "test-token-strong"})
    assert leads.status_code == 200
    items = leads.json()
    assert any(item["id"] == lead_id and item["phone"] for item in items)

    stats = await client.get("/api/stats", headers={"X-CRM-Token": "test-token-strong"})
    assert stats.status_code == 200
    assert stats.json()["leads_ready"] >= 1


@pytest.mark.asyncio
async def test_crm_requires_token(client: AsyncClient):
    r = await client.get("/api/leads")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_funnels_list(client: AsyncClient):
    r = await client.get("/api/funnels", headers={"X-CRM-Token": "test-token-strong"})
    assert r.status_code == 200
    data = r.json()
    assert any(item["slug"] == "default" for item in data)
    assert data[0]["stages"]
