import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_export_and_notes(client: AsyncClient):
    headers = {"X-CRM-Token": "test-token-strong"}
    created = await client.post(
        "/api/leads",
        headers=headers,
        json={
            "source": "manual",
            "name": "Иван Тест",
            "phone": "+79001234567",
            "need": "Нужен бот под заявки",
            "tags": "vip,bots",
            "status": "ready",
        },
    )
    assert created.status_code == 200
    lead_id = created.json()["id"]

    found = await client.get("/api/leads", headers=headers, params={"q": "7900123"})
    assert found.status_code == 200
    assert any(item["id"] == lead_id for item in found.json())

    tagged = await client.get("/api/leads", headers=headers, params={"tag": "vip"})
    assert tagged.status_code == 200
    assert any(item["id"] == lead_id for item in tagged.json())

    note = await client.post(
        f"/api/leads/{lead_id}/notes",
        headers=headers,
        json={"body": "Перезвонить после обеда", "author": "mgr"},
    )
    assert note.status_code == 200
    assert "Перезвонить" in note.json()["body"]

    notes = await client.get(f"/api/leads/{lead_id}/notes", headers=headers)
    assert notes.status_code == 200
    assert len(notes.json()) >= 1

    export = await client.get("/api/leads/export.csv", headers=headers)
    assert export.status_code == 200
    assert "text/csv" in export.headers.get("content-type", "")
    assert "79001234567" in export.text
