import pytest
from httpx import AsyncClient


HEADERS = {"X-CRM-Token": "test-token-strong"}


@pytest.mark.asyncio
async def test_phone_dedupe_merges(client: AsyncClient):
    first = await client.post(
        "/api/leads",
        headers=HEADERS,
        json={"source": "landing", "phone": "+7 (900) 111-22-33", "name": "Аня"},
    )
    assert first.status_code == 200
    lead_id = first.json()["id"]
    assert first.json()["phone_normalized"] == "79001112233"

    second = await client.post(
        "/api/leads",
        headers=HEADERS,
        json={
            "source": "telegram",
            "phone": "8 900 111 22 33",
            "need": "Нужен бот под заявки из рекламы",
        },
    )
    assert second.status_code == 200
    assert second.json()["id"] == lead_id
    assert second.json()["need"]
    assert second.json()["name"] == "Аня"


@pytest.mark.asyncio
async def test_stage_transition_rules(client: AsyncClient):
    created = await client.post(
        "/api/leads",
        headers=HEADERS,
        json={"source": "manual", "status": "new", "phone": "+79002223344"},
    )
    lead_id = created.json()["id"]

    bad = await client.patch(
        f"/api/leads/{lead_id}",
        headers=HEADERS,
        json={"status": "ready"},
    )
    assert bad.status_code == 400

    ok = await client.patch(
        f"/api/leads/{lead_id}",
        headers=HEADERS,
        json={"status": "qualifying"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "qualifying"

    ready = await client.patch(
        f"/api/leads/{lead_id}",
        headers=HEADERS,
        json={"status": "ready"},
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_soft_delete_and_restore(client: AsyncClient):
    created = await client.post(
        "/api/leads",
        headers=HEADERS,
        json={"source": "manual", "phone": "+79003334455", "name": "DeleteMe"},
    )
    lead_id = created.json()["id"]

    deleted = await client.delete(f"/api/leads/{lead_id}", headers=HEADERS)
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None

    listed = await client.get("/api/leads", headers=HEADERS)
    assert all(item["id"] != lead_id for item in listed.json())

    with_deleted = await client.get(
        "/api/leads", headers=HEADERS, params={"include_deleted": "true"}
    )
    assert any(item["id"] == lead_id for item in with_deleted.json())

    restored = await client.post(f"/api/leads/{lead_id}/restore", headers=HEADERS)
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None


@pytest.mark.asyncio
async def test_bulk_status_and_import_csv(client: AsyncClient):
    a = await client.post(
        "/api/leads",
        headers=HEADERS,
        json={"source": "bulk", "status": "new", "phone": "+79004445566"},
    )
    b = await client.post(
        "/api/leads",
        headers=HEADERS,
        json={"source": "bulk", "status": "new", "phone": "+79005556677"},
    )
    ids = [a.json()["id"], b.json()["id"]]

    bulk = await client.post(
        "/api/leads/bulk/status",
        headers=HEADERS,
        json={"lead_ids": ids, "status": "qualifying"},
    )
    assert bulk.status_code == 200
    body = bulk.json()
    assert body["updated"] == 2
    assert body["failed"] == []

    csv_body = (
        "source,name,phone,need,status,tags\n"
        "import,Импорт Один,+79006667788,Нужен парсер,new,csv\n"
        "import,Импорт Два,+79007778899,Нужен CRM,new,csv\n"
    )
    imported = await client.post(
        "/api/leads/import.csv",
        headers=HEADERS,
        files={"file": ("leads.csv", csv_body.encode("utf-8"), "text/csv")},
    )
    assert imported.status_code == 200
    result = imported.json()
    assert result["created"] >= 2
    assert result["errors"] == []

    found = await client.get("/api/leads", headers=HEADERS, params={"q": "79006667788"})
    assert found.status_code == 200
    assert len(found.json()) >= 1


@pytest.mark.asyncio
async def test_managers_and_timeline(client: AsyncClient):
    managers = await client.get("/api/managers", headers=HEADERS)
    assert managers.status_code == 200
    assert isinstance(managers.json(), list)
    assert len(managers.json()) >= 1

    upsert = await client.post(
        "/api/managers",
        headers=HEADERS,
        json={"name": "Ops", "telegram_chat_id": "123456"},
    )
    assert upsert.status_code == 200
    assert upsert.json()["name"] == "Ops"

    created = await client.post(
        "/api/leads",
        headers=HEADERS,
        json={"source": "timeline", "phone": "+79008889900", "need": "Проверка timeline"},
    )
    lead_id = created.json()["id"]

    await client.patch(
        f"/api/leads/{lead_id}",
        headers=HEADERS,
        json={"status": "qualifying", "assigned_manager_id": upsert.json()["id"]},
    )

    acts = await client.get(f"/api/leads/{lead_id}/activities", headers=HEADERS)
    assert acts.status_code == 200
    kinds = {item["kind"] for item in acts.json()}
    assert "created" in kinds
    assert "status_change" in kinds
