import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_jwt_and_me(client: AsyncClient):
    bad = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401

    login = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-test-pass"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["actor"] == "admin"
    assert me.json()["method"] == "jwt"

    leads = await client.get("/api/leads", headers={"Authorization": f"Bearer {token}"})
    assert leads.status_code == 200


@pytest.mark.asyncio
async def test_metrics_and_messages(client: AsyncClient):
    chat = await client.post(
        "/api/chat",
        json={"source": "t", "message": "Нужна CRM автоматизация заявок, +79005554433"},
    )
    assert chat.status_code == 200
    lead_id = chat.json()["lead_id"]

    msgs = await client.get(
        f"/api/leads/{lead_id}/messages",
        headers={"X-CRM-Token": "test-token-strong"},
    )
    assert msgs.status_code == 200
    assert len(msgs.json()) >= 2

    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    assert "aifunnel_http_requests_total" in metrics.text
