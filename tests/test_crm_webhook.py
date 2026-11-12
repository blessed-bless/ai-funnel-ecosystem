import json

import pytest
from httpx import ASGITransport, AsyncClient

from aifunnel.config import Settings
from aifunnel.services.webhooks import sign_payload


def test_webhook_signature_stable():
    body = b'{"event":"lead.ready","data":{"lead_id":1}}'
    sig = sign_payload("secret", body)
    assert sig == sign_payload("secret", body)
    assert sig != sign_payload("other", body)


@pytest.mark.asyncio
async def test_crm_html_requires_login(tmp_path, monkeypatch):
    import os

    from aifunnel import db as dbmod
    from aifunnel.ai.factory import reset_ai_singleton
    from aifunnel.api.deps import reset_limiters
    from aifunnel.config import get_settings
    from aifunnel.services import admins as admin_service
    from aifunnel.services import funnels as funnel_service

    monkeypatch.setenv("CRM_PROTECT_HTML", "true")
    monkeypatch.setenv("CRM_API_TOKEN", "test-token-strong")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-strong-32bytes!!")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-test-pass")
    db_path = tmp_path / "crm.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    get_settings.cache_clear()
    reset_ai_singleton()
    reset_limiters()
    dbmod.rebind_engine(os.environ["DATABASE_URL"])
    await dbmod.init_db()
    async with dbmod.SessionLocal() as session:
        await funnel_service.ensure_default_funnel(session)
        await admin_service.ensure_bootstrap_admin(session, get_settings())

    from aifunnel.api.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        denied = await client.get("/crm")
        assert denied.status_code in {303, 307}
        assert "/crm/login" in denied.headers.get("location", "")

        login_page = await client.get("/crm/login")
        assert login_page.status_code == 200

        logged = await client.post(
            "/crm/login",
            data={"username": "admin", "password": "admin-test-pass"},
            follow_redirects=False,
        )
        assert logged.status_code in {303, 307}
        assert client.cookies.get("aifunnel_session")

        ok = await client.get("/crm")
        assert ok.status_code == 200
        assert "Заявки" in ok.text


@pytest.mark.asyncio
async def test_outbox_webhook_called(monkeypatch):
    from aifunnel import db as dbmod
    from aifunnel.config import get_settings
    from aifunnel.services import outbox

    calls: list[tuple[str, dict]] = []

    async def fake_post(settings: Settings, event: str, payload: dict) -> None:
        calls.append((event, payload))

    monkeypatch.setattr("aifunnel.services.webhooks.post_webhook", fake_post)
    monkeypatch.setattr(outbox, "webhooks", type("W", (), {"post_webhook": staticmethod(fake_post)}))

    async with dbmod.SessionLocal() as session:
        job = await outbox.enqueue(session, kind="notify_ready_lead", payload={"lead_id": 7, "phone": "+7900"})
        await outbox.process_job(session, job)
        await session.refresh(job)
        assert job.status == "done"
    assert calls and calls[0][0] == "lead.ready"
    assert calls[0][1]["lead_id"] == 7
